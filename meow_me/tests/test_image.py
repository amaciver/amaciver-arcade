"""Tests for the image generation tools (image.py).

Tests the async start/poll pattern for image generation:
- start_cat_image_generation: validates inputs, starts background thread
- check_image_status: polls for completion, stashes results
"""

import base64
import threading

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from meow_me.tools.image import (
    _compose_prompt,
    _download_avatar,
    _make_png_file,
    _make_preview_thumbnail,
    _last_generated_image,
    _pending_jobs,
    _PLACEHOLDER_PNG_B64,
    _try_get_secret,
    STYLE_PROMPTS,
    DEFAULT_STYLE,
    start_cat_image_generation,
    check_image_status,
)


def _mock_context(secrets=None):
    """Create a mock Context that returns secrets from a dict."""
    _secrets = secrets or {}

    def _get_secret(key):
        if key in _secrets:
            return _secrets[key]
        raise ValueError(f"Secret {key} not found")

    ctx = MagicMock()
    ctx.get_secret = MagicMock(side_effect=_get_secret)
    return ctx


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


# --- Tests for _try_get_secret ---

class TestTryGetSecret:
    def test_returns_secret_from_context(self):
        ctx = _mock_context({"OPENAI_API_KEY": "sk-test"})
        assert _try_get_secret(ctx, "OPENAI_API_KEY") == "sk-test"

    def test_falls_back_to_env_var(self):
        ctx = _mock_context()  # No secrets
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-from-env"}, clear=True):
            assert _try_get_secret(ctx, "OPENAI_API_KEY") == "sk-from-env"

    def test_returns_empty_when_not_available(self):
        ctx = _mock_context()  # No secrets
        with patch.dict("os.environ", {}, clear=True):
            assert _try_get_secret(ctx, "OPENAI_API_KEY") == ""


# --- Tests for start_cat_image_generation ---

class TestStartCatImageGeneration:
    def setup_method(self):
        _last_generated_image.clear()
        _pending_jobs.clear()

    def teardown_method(self):
        _last_generated_image.clear()
        _pending_jobs.clear()

    @pytest.mark.asyncio
    async def test_error_when_no_api_key(self):
        ctx = _mock_context()  # No secrets
        with patch.dict("os.environ", {}, clear=True):
            result = await start_cat_image_generation(
                context=ctx,
                cat_fact="Cats are great",
                avatar_url="https://example.com/avatar.png",
            )
        assert "error" in result
        assert "OPENAI_API_KEY" in result["error"]

    @pytest.mark.asyncio
    async def test_returns_job_id(self):
        ctx = _mock_context({"OPENAI_API_KEY": "sk-test"})
        fake_avatar = b"\x89PNGfake"

        with patch(
            "meow_me.tools.image._download_avatar",
            new_callable=AsyncMock,
            return_value=fake_avatar,
        ):
            with patch(
                "meow_me.tools.image._generate_image_openai",
                return_value=base64.b64encode(b"fake_image").decode(),
            ):
                result = await start_cat_image_generation(
                    context=ctx,
                    cat_fact="Cats purr at 25 Hz",
                    avatar_url="https://example.com/avatar.png",
                )

        assert "job_id" in result
        assert result["status"] == "generating"
        assert "estimated_seconds" in result
        # Job should be in pending jobs
        assert result["job_id"] in _pending_jobs

    @pytest.mark.asyncio
    async def test_none_avatar_url_returns_error(self):
        ctx = _mock_context()
        result = await start_cat_image_generation(
            context=ctx,
            cat_fact="Cats are great",
            avatar_url=None,
        )
        assert "error" in result
        assert "avatar_url" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_empty_avatar_url_returns_error(self):
        ctx = _mock_context()
        result = await start_cat_image_generation(
            context=ctx,
            cat_fact="Cats are great",
            avatar_url="",
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_none_cat_fact_returns_error(self):
        ctx = _mock_context()
        result = await start_cat_image_generation(
            context=ctx,
            cat_fact=None,
            avatar_url="https://example.com/avatar.png",
        )
        assert "error" in result
        assert "cat_fact" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_style_defaults_to_cartoon(self):
        ctx = _mock_context()  # No secrets → error path, but style gets normalized
        result = await start_cat_image_generation(
            context=ctx,
            cat_fact="Test",
            avatar_url="https://example.com/avatar.png",
            style="nonexistent",
        )
        assert result["style"] == "cartoon"

    @pytest.mark.asyncio
    async def test_avatar_download_failure(self):
        ctx = _mock_context({"OPENAI_API_KEY": "sk-test"})
        with patch(
            "meow_me.tools.image._download_avatar",
            new_callable=AsyncMock,
            side_effect=Exception("Connection refused"),
        ):
            result = await start_cat_image_generation(
                context=ctx,
                cat_fact="Test",
                avatar_url="https://bad-url.com/avatar.png",
            )
        assert "error" in result
        assert "download avatar" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_placeholder_is_valid_base64(self):
        decoded = base64.b64decode(_PLACEHOLDER_PNG_B64)
        assert decoded[:4] == b"\x89PNG"


# --- Tests for check_image_status ---

class TestCheckImageStatus:
    def setup_method(self):
        _last_generated_image.clear()
        _pending_jobs.clear()

    def teardown_method(self):
        _last_generated_image.clear()
        _pending_jobs.clear()

    @pytest.mark.asyncio
    async def test_unknown_job_id(self):
        result = await check_image_status(job_id="nonexistent")
        assert "error" in result
        assert "Unknown job_id" in result["error"]

    @pytest.mark.asyncio
    async def test_in_progress_job(self):
        # Create a mock thread that's "alive"
        mock_thread = MagicMock(spec=threading.Thread)
        mock_thread.is_alive.return_value = True
        _pending_jobs["test123"] = {
            "thread": mock_thread,
            "cat_fact": "Test",
            "style": "cartoon",
        }

        result = await check_image_status(job_id="test123")
        assert result["status"] == "generating"
        assert result["job_id"] == "test123"

    @pytest.mark.asyncio
    async def test_completed_job(self):
        fake_b64 = base64.b64encode(b"fake_image").decode()
        mock_thread = MagicMock(spec=threading.Thread)
        mock_thread.is_alive.return_value = False
        _pending_jobs["done123"] = {
            "thread": mock_thread,
            "cat_fact": "Cats purr",
            "style": "watercolor",
            "result": fake_b64,
        }

        with patch("meow_me.tools.image._make_preview_thumbnail", return_value="thumb_b64"):
            result = await check_image_status(job_id="done123")

        assert result["status"] == "complete"
        assert result["cat_fact"] == "Cats purr"
        assert result["style"] == "watercolor"
        assert result["image_size_bytes"] == len(fake_b64)
        # Should stash in _last_generated_image
        assert _last_generated_image["base64"] == fake_b64
        assert _last_generated_image["cat_fact"] == "Cats purr"

    @pytest.mark.asyncio
    async def test_completed_job_with_preview(self):
        fake_b64 = base64.b64encode(b"fake_image").decode()
        fake_thumb = "thumb_data"
        mock_thread = MagicMock(spec=threading.Thread)
        mock_thread.is_alive.return_value = False
        _pending_jobs["preview123"] = {
            "thread": mock_thread,
            "cat_fact": "Test",
            "style": "cartoon",
            "result": fake_b64,
        }

        with patch("meow_me.tools.image._make_preview_thumbnail", return_value=fake_thumb):
            result = await check_image_status(job_id="preview123")

        assert "_mcp_image" in result
        assert result["_mcp_image"]["data"] == fake_thumb
        assert result["_mcp_image"]["mimeType"] == "image/jpeg"

    @pytest.mark.asyncio
    async def test_completed_job_thumbnail_failure(self):
        """If thumbnail fails, result still succeeds without _mcp_image."""
        fake_b64 = base64.b64encode(b"fake_image").decode()
        mock_thread = MagicMock(spec=threading.Thread)
        mock_thread.is_alive.return_value = False
        _pending_jobs["nothumb"] = {
            "thread": mock_thread,
            "cat_fact": "Test",
            "style": "cartoon",
            "result": fake_b64,
        }

        with patch("meow_me.tools.image._make_preview_thumbnail", side_effect=Exception("PIL failed")):
            result = await check_image_status(job_id="nothumb")

        assert result["status"] == "complete"
        assert "_mcp_image" not in result

    @pytest.mark.asyncio
    async def test_failed_job(self):
        mock_thread = MagicMock(spec=threading.Thread)
        mock_thread.is_alive.return_value = False
        _pending_jobs["fail123"] = {
            "thread": mock_thread,
            "cat_fact": "Test",
            "style": "cartoon",
            "error": "API rate limit exceeded",
        }

        result = await check_image_status(job_id="fail123")
        assert result["status"] == "failed"
        assert "rate limit" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_no_result_job(self):
        """Thread finished but no result and no error."""
        mock_thread = MagicMock(spec=threading.Thread)
        mock_thread.is_alive.return_value = False
        _pending_jobs["empty123"] = {
            "thread": mock_thread,
            "cat_fact": "Test",
            "style": "cartoon",
        }

        result = await check_image_status(job_id="empty123")
        assert result["status"] == "failed"
        assert "no image data" in result["error"].lower()


# --- Tests for _make_preview_thumbnail ---

class TestMakePreviewThumbnail:
    def test_produces_smaller_output(self):
        """Thumbnail should be significantly smaller than the original."""
        from PIL import Image
        import io

        img = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        original_b64 = base64.b64encode(buf.getvalue()).decode()

        thumb_b64 = _make_preview_thumbnail(original_b64, size=50, quality=60)
        thumb_bytes = base64.b64decode(thumb_b64)
        assert len(thumb_bytes) > 0
        assert thumb_bytes[:2] == b"\xff\xd8"  # JPEG magic

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
