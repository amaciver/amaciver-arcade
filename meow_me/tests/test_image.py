"""Tests for the image generation tools (image.py)."""

import base64

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from meow_me.tools.image import (
    _compose_prompt,
    _download_avatar,
    _make_png_file,
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
    @pytest.mark.asyncio
    async def test_fallback_when_no_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            result = await generate_cat_image(
                cat_fact="Cats are great",
                avatar_url="https://example.com/avatar.png",
            )
        assert result["fallback"] is True
        assert result["image_base64"] == _PLACEHOLDER_PNG_B64
        assert result["cat_fact"] == "Cats are great"
        assert result["style"] == "cartoon"

    @pytest.mark.asyncio
    async def test_fallback_image_is_valid_base64(self):
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

        assert result["fallback"] is False
        assert result["image_base64"] == fake_b64
        assert result["cat_fact"] == "Cats purr at 25 Hz"
        assert result["style"] == "watercolor"
        assert "watercolor" in result["prompt_used"].lower()

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
        assert "Cats have 230 bones" in result["prompt_used"]
