"""Tests for the image generation tools (image.py)."""

import base64

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from meow_me.tools.image import (
    _compose_prompt,
    _download_avatar,
    _make_png_file,
    _last_generated_image,
    _PLACEHOLDER_PNG_B64,
    STYLE_PROMPTS,
    DEFAULT_STYLE,
    generate_cat_image,
)


# --- Tests for _compose_prompt ---

class TestComposePrompt:
    def test_includes_cat_fact(self):
        prompt = _compose_prompt("Cats sleep 16 hours.", "cartoon")
        assert "Cats sleep 16 hours." in prompt

    def test_includes_style_base(self):
        prompt = _compose_prompt("Test fact", "watercolor")
        assert "watercolor" in prompt.lower()

    def test_falls_back_to_default_for_unknown_style(self):
        prompt = _compose_prompt("Test fact", "nonexistent_style")
        default_prompt = _compose_prompt("Test fact", DEFAULT_STYLE)
        assert prompt == default_prompt

    def test_all_styles_produce_different_prompts(self):
        prompts = {
            style: _compose_prompt("Same fact", style) for style in STYLE_PROMPTS
        }
        # All prompts should be unique
        assert len(set(prompts.values())) == len(STYLE_PROMPTS)

    def test_includes_text_instruction(self):
        prompt = _compose_prompt("Test fact", "cartoon")
        assert "text" in prompt.lower()


# --- Tests for _download_avatar ---

class TestDownloadAvatar:
    @pytest.mark.asyncio
    async def test_returns_image_bytes(self):
        fake_image = b"\x89PNG\r\n\x1a\nfake_image_data"
        mock_response = MagicMock()
        mock_response.content = fake_image
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.image.httpx.AsyncClient", return_value=mock_client):
            result = await _download_avatar("https://example.com/avatar.png")

        assert result == fake_image

    @pytest.mark.asyncio
    async def test_follows_redirects(self):
        mock_response = MagicMock()
        mock_response.content = b"image_data"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.image.httpx.AsyncClient", return_value=mock_client):
            await _download_avatar("https://example.com/avatar.png")

        call_kwargs = mock_client.get.call_args
        assert call_kwargs[1].get("follow_redirects") is True


# --- Tests for _make_png_file ---

class TestMakePngFile:
    def test_returns_bytesio_with_name(self):
        data = b"test_data"
        result = _make_png_file(data)
        assert result.name == "avatar.png"
        assert result.read() == data

    def test_position_at_start(self):
        data = b"test_data"
        result = _make_png_file(data)
        assert result.tell() == 0


# --- Tests for generate_cat_image tool ---

class TestGenerateCatImage:
    def setup_method(self):
        _last_generated_image.clear()

    @pytest.mark.asyncio
    async def test_error_when_no_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            result = await generate_cat_image(
                cat_fact="Cats are great",
                avatar_url="https://example.com/avatar.png",
            )
        assert "error" in result
        assert "OPENAI_API_KEY" in result["error"]
        assert result["cat_fact"] == "Cats are great"
        assert result["style"] == "cartoon"

    @pytest.mark.asyncio
    async def test_placeholder_is_valid_base64(self):
        decoded = base64.b64decode(_PLACEHOLDER_PNG_B64)
        # Should start with PNG magic bytes
        assert decoded[:4] == b"\x89PNG"

    @pytest.mark.asyncio
    async def test_successful_generation(self):
        fake_b64 = base64.b64encode(b"fake_image").decode()
        fake_avatar = b"\x89PNGfake"

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}):
            with patch(
                "meow_me.tools.image._download_avatar",
                new_callable=AsyncMock,
                return_value=fake_avatar,
            ):
                with patch(
                    "meow_me.tools.image._generate_image_openai",
                    return_value=fake_b64,
                ):
                    result = await generate_cat_image(
                        cat_fact="Cats purr at 25 Hz",
                        avatar_url="https://example.com/avatar.png",
                        style="watercolor",
                    )

        assert result["success"] is True
        assert "image_base64" not in result  # base64 is stashed, not returned
        assert result["cat_fact"] == "Cats purr at 25 Hz"
        assert result["style"] == "watercolor"
        assert "watercolor" in result["prompt_used"].lower()
        # Verify server-side stash
        assert _last_generated_image["base64"] == fake_b64
        assert _last_generated_image["cat_fact"] == "Cats purr at 25 Hz"

    @pytest.mark.asyncio
    async def test_invalid_style_defaults_to_cartoon(self):
        with patch.dict("os.environ", {}, clear=True):
            result = await generate_cat_image(
                cat_fact="Test",
                avatar_url="https://example.com/avatar.png",
                style="nonexistent",
            )
        assert result["style"] == "cartoon"

    @pytest.mark.asyncio
    async def test_prompt_includes_fact(self):
        with patch.dict("os.environ", {}, clear=True):
            result = await generate_cat_image(
                cat_fact="Cats have 230 bones",
                avatar_url="https://example.com/avatar.png",
            )
        # No prompt_used when error (no API key), but the fact is in the result
        assert result["cat_fact"] == "Cats have 230 bones"

    @pytest.mark.asyncio
    async def test_avatar_download_failure(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}):
            with patch(
                "meow_me.tools.image._download_avatar",
                new_callable=AsyncMock,
                side_effect=Exception("Connection refused"),
            ):
                result = await generate_cat_image(
                    cat_fact="Test",
                    avatar_url="https://bad-url.com/avatar.png",
                )
        assert "error" in result
        assert "download avatar" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_openai_generation_failure(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}):
            with patch(
                "meow_me.tools.image._download_avatar",
                new_callable=AsyncMock,
                return_value=b"fake_avatar",
            ):
                with patch(
                    "meow_me.tools.image._generate_image_openai",
                    side_effect=Exception("API rate limit"),
                ):
                    result = await generate_cat_image(
                        cat_fact="Test",
                        avatar_url="https://example.com/avatar.png",
                    )
        assert "error" in result
        assert "generation failed" in result["error"].lower()

    def teardown_method(self):
        _last_generated_image.clear()
