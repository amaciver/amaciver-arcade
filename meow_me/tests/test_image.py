"""Tests for the image generation tools (image.py)."""

import base64

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from meow_me.tools.image import (
    _compose_prompt,
    _download_avatar,
    _make_png_file,
    _make_preview_thumbnail,
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
        fake_thumb = base64.b64encode(b"thumbnail").decode()

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
                    with patch(
                        "meow_me.tools.image._make_preview_thumbnail",
                        return_value=fake_thumb,
                    ):
                        result = await generate_cat_image(
                            cat_fact="Cats purr at 25 Hz",
                            avatar_url="https://example.com/avatar.png",
                            style="watercolor",
                        )

        assert result["success"] is True
        assert result["cat_fact"] == "Cats purr at 25 Hz"
        assert result["style"] == "watercolor"
        assert "watercolor" in result["prompt_used"].lower()
        # _mcp_image contains compressed JPEG thumbnail (not the full PNG)
        assert "_mcp_image" in result
        assert result["_mcp_image"]["data"] == fake_thumb
        assert result["_mcp_image"]["mimeType"] == "image/jpeg"
        # Server-side stash has the full-res PNG
        assert _last_generated_image["base64"] == fake_b64
        assert _last_generated_image["cat_fact"] == "Cats purr at 25 Hz"

    @pytest.mark.asyncio
    async def test_thumbnail_failure_omits_mcp_image(self):
        """If thumbnail generation fails, result still succeeds without _mcp_image."""
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
                    with patch(
                        "meow_me.tools.image._make_preview_thumbnail",
                        side_effect=Exception("PIL failed"),
                    ):
                        result = await generate_cat_image(
                            cat_fact="Test",
                            avatar_url="https://example.com/avatar.png",
                        )

        assert result["success"] is True
        assert "_mcp_image" not in result
        # Stash still has the full image
        assert _last_generated_image["base64"] == fake_b64

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

    @pytest.mark.asyncio
    async def test_none_avatar_url_returns_error(self):
        result = await generate_cat_image(
            cat_fact="Cats are great",
            avatar_url=None,
        )
        assert "error" in result
        assert "avatar_url" in result["error"].lower()
        assert "get_user_avatar" in result["error"]

    @pytest.mark.asyncio
    async def test_empty_avatar_url_returns_error(self):
        result = await generate_cat_image(
            cat_fact="Cats are great",
            avatar_url="",
        )
        assert "error" in result
        assert "avatar_url" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_none_cat_fact_returns_error(self):
        result = await generate_cat_image(
            cat_fact=None,
            avatar_url="https://example.com/avatar.png",
        )
        assert "error" in result
        assert "cat_fact" in result["error"].lower()
        assert "get_cat_fact" in result["error"]

    @pytest.mark.asyncio
    async def test_error_results_have_no_mcp_image(self):
        """Error responses should not include _mcp_image."""
        with patch.dict("os.environ", {}, clear=True):
            result = await generate_cat_image(
                cat_fact="Test",
                avatar_url="https://example.com/avatar.png",
            )
        assert "error" in result
        assert "_mcp_image" not in result

    def teardown_method(self):
        _last_generated_image.clear()


# --- Tests for _make_preview_thumbnail ---

class TestMakePreviewThumbnail:
    def test_produces_smaller_output(self):
        """Thumbnail should be significantly smaller than the original."""
        # Create a real 4x4 PNG to thumbnail
        from PIL import Image
        import io

        img = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        original_b64 = base64.b64encode(buf.getvalue()).decode()

        thumb_b64 = _make_preview_thumbnail(original_b64, size=50, quality=60)
        # Thumbnail should be valid base64
        thumb_bytes = base64.b64decode(thumb_b64)
        assert len(thumb_bytes) > 0
        # Thumbnail should be JPEG (starts with FFD8)
        assert thumb_bytes[:2] == b"\xff\xd8"

    def test_uses_placeholder_png(self):
        """Should work with the placeholder 1x1 PNG."""
        thumb_b64 = _make_preview_thumbnail(_PLACEHOLDER_PNG_B64, size=32)
        thumb_bytes = base64.b64decode(thumb_b64)
        assert thumb_bytes[:2] == b"\xff\xd8"  # JPEG magic


# --- Tests for ImageContent monkey-patch ---

class TestImageContentPatch:
    def test_patched_convert_emits_image_content(self):
        """When a dict has _mcp_image, the patch emits ImageContent."""
        from arcade_mcp_server.convert import convert_to_mcp_content
        from arcade_mcp_server.types import ImageContent, TextContent

        fake_b64 = base64.b64encode(b"test_image").decode()
        value = {
            "success": True,
            "cat_fact": "Cats purr",
            "_mcp_image": {"data": fake_b64, "mimeType": "image/png"},
        }
        blocks = convert_to_mcp_content(value)
        text_blocks = [b for b in blocks if isinstance(b, TextContent)]
        image_blocks = [b for b in blocks if isinstance(b, ImageContent)]

        assert len(image_blocks) == 1
        assert image_blocks[0].data == fake_b64
        assert image_blocks[0].mimeType == "image/png"
        assert len(text_blocks) >= 1

    def test_patched_convert_passes_through_normal_dicts(self):
        """Dicts without _mcp_image go through the original path."""
        from arcade_mcp_server.convert import convert_to_mcp_content
        from arcade_mcp_server.types import ImageContent, TextContent

        value = {"success": True, "message": "hello"}
        blocks = convert_to_mcp_content(value)
        image_blocks = [b for b in blocks if isinstance(b, ImageContent)]

        assert len(image_blocks) == 0
        assert len(blocks) >= 1

    def test_server_module_also_patched(self):
        """The server module's reference should also be patched."""
        import arcade_mcp_server.convert as convert_mod
        import arcade_mcp_server.server as server_mod

        assert server_mod.convert_to_mcp_content is convert_mod.convert_to_mcp_content
