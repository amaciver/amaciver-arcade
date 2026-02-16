"""Image generation tools - create cat-themed art from avatars using OpenAI."""

import asyncio
import base64
import io
import logging
import os
from typing import Annotated

import httpx
from arcade_mcp_server import tool
from openai import OpenAI

logger = logging.getLogger(__name__)

STYLE_PROMPTS = {
    "cartoon": (
        "Transform this photo into a whimsical cartoon illustration. "
        "Add playful cats and cat-themed elements throughout the scene. "
        "The person should be reimagined as a fun cartoon character. "
        "Vibrant colors, bold outlines, and a playful atmosphere."
    ),
    "watercolor": (
        "Transform this photo into a beautiful watercolor painting with cats. "
        "Add elegant cats woven into the composition in a soft watercolor style. "
        "Gentle color washes, flowing brushstrokes, and dreamy atmosphere."
    ),
    "anime": (
        "Transform this photo into an anime-style illustration with cats. "
        "Add cute anime-style cats as companions. "
        "Big expressive eyes, colorful hair, vibrant anime art style."
    ),
    "photorealistic": (
        "Transform this photo into a photorealistic scene featuring cats. "
        "Add realistic cats interacting naturally with the person. "
        "High detail, natural lighting, cinematic composition."
    ),
}

DEFAULT_STYLE = "cartoon"


def _compose_prompt(cat_fact: str, style: str) -> str:
    """Build the image generation prompt from a cat fact and style."""
    style_base = STYLE_PROMPTS.get(style, STYLE_PROMPTS[DEFAULT_STYLE])
    return (
        f"{style_base} "
        f"Incorporate this cat fact into the scene visually: '{cat_fact}'. "
        f"Include the fact as stylized text at the bottom of the image."
    )


async def _download_avatar(avatar_url: str) -> bytes:
    """Download avatar image bytes from a URL."""
    async with httpx.AsyncClient() as client:
        response = await client.get(avatar_url, follow_redirects=True)
        response.raise_for_status()
        return response.content


def _make_png_file(data: bytes) -> io.BytesIO:
    """Wrap raw image bytes into a file-like object with a .png name."""
    buf = io.BytesIO(data)
    buf.name = "avatar.png"
    return buf


def _generate_image_openai(avatar_bytes: bytes, prompt: str) -> str:
    """Call OpenAI images.edit and return base64-encoded PNG."""
    client = OpenAI()
    response = client.images.edit(
        model="gpt-image-1",
        image=_make_png_file(avatar_bytes),
        prompt=prompt,
        size="1024x1024",
    )
    b64 = response.data[0].b64_json
    if not b64:
        raise RuntimeError("OpenAI returned no image data")
    return b64


def _make_preview_thumbnail(png_b64: str, size: int = 512, quality: int = 80) -> str:
    """Compress a full-res PNG (base64) into a small JPEG thumbnail (base64).

    Used for MCP ImageContent so Claude Desktop can display a preview
    without the full ~2MB PNG going through the transport.
    """
    from PIL import Image

    png_bytes = base64.b64decode(png_b64)
    img = Image.open(io.BytesIO(png_bytes))
    img = img.resize((size, size), Image.LANCZOS)
    img = img.convert("RGB")  # JPEG doesn't support alpha

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode()


# Tiny 1x1 transparent PNG as fallback placeholder
_PLACEHOLDER_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4"
    "2mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

# Server-side stash for the most recently generated image.
# This avoids sending ~1.5MB base64 through the LLM context.
# Tools like send_cat_image can reference it via "__last__".
_last_generated_image: dict = {}


def get_last_generated_image() -> dict:
    """Get the last generated image stash (used by send_cat_image)."""
    return _last_generated_image


@tool
async def generate_cat_image(
    cat_fact: Annotated[str, "The cat fact to incorporate into the image. Call get_cat_fact first to get one."],
    avatar_url: Annotated[str, "Full HTTPS URL of the user's avatar image. Call get_user_avatar first to get this URL."],
    style: Annotated[str, "Art style: cartoon, watercolor, anime, or photorealistic"] = "cartoon",
) -> dict:
    """Generate a cat-themed image by transforming a user's avatar.

    IMPORTANT: Before calling this tool, you must first call:
    1. get_user_avatar - to get the avatar_url
    2. get_cat_fact - to get a cat_fact

    Then pass the avatar_url string and cat_fact string to this tool.

    The generated image is stored server-side. To send it to Slack, call
    send_cat_image with image_base64 set to '__last__'.
    """
    logger.debug(
        "generate_cat_image called: cat_fact=%r, avatar_url=%r, style=%r",
        cat_fact, avatar_url, style,
    )

    # Validate inputs
    if not avatar_url or avatar_url == "None":
        return {
            "error": (
                "avatar_url is missing. Call get_user_avatar first, then pass "
                "the 'avatar_url' value from its response to this tool."
            ),
            "cat_fact": cat_fact or "",
            "style": style if style in STYLE_PROMPTS else DEFAULT_STYLE,
        }

    if not cat_fact or cat_fact == "None":
        return {
            "error": (
                "cat_fact is missing. Call get_cat_fact first, then pass "
                "one of the facts to this tool."
            ),
            "avatar_url": avatar_url,
            "style": style if style in STYLE_PROMPTS else DEFAULT_STYLE,
        }

    style = style if style in STYLE_PROMPTS else DEFAULT_STYLE
    prompt = _compose_prompt(cat_fact, style)

    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY not set")
        return {
            "error": "OPENAI_API_KEY not set. Image generation requires an OpenAI API key.",
            "prompt_used": prompt,
            "style": style,
            "cat_fact": cat_fact,
        }

    try:
        # Download avatar
        logger.debug("Downloading avatar from %s", avatar_url)
        avatar_bytes = await _download_avatar(avatar_url)
        logger.debug("Avatar downloaded: %d bytes", len(avatar_bytes))
    except Exception as e:
        logger.error("Avatar download failed: %s", e)
        return {
            "error": f"Failed to download avatar from {avatar_url}: {e}",
            "style": style,
            "cat_fact": cat_fact,
        }

    try:
        # Generate image (sync call, run in thread to avoid blocking event loop)
        logger.debug("Calling OpenAI image generation...")
        image_b64 = await asyncio.to_thread(_generate_image_openai, avatar_bytes, prompt)
        logger.debug("Image generated: %d bytes base64", len(image_b64))
    except Exception as e:
        logger.error("Image generation failed: %s", e)
        return {
            "error": f"Image generation failed: {e}",
            "prompt_used": prompt,
            "style": style,
            "cat_fact": cat_fact,
        }

    # Stash the full-res image server-side (for send_cat_image and CLI agent)
    _last_generated_image.clear()
    _last_generated_image["base64"] = image_b64
    _last_generated_image["cat_fact"] = cat_fact
    _last_generated_image["style"] = style

    # Build a compressed JPEG thumbnail for inline display in Claude Desktop.
    # Full-res PNG is ~2MB; thumbnail is ~50-100KB.
    try:
        preview_b64 = _make_preview_thumbnail(image_b64)
        logger.debug("Preview thumbnail: %d bytes base64", len(preview_b64))
    except Exception as e:
        logger.warning("Thumbnail generation failed, skipping preview: %s", e)
        preview_b64 = None

    result = {
        "success": True,
        "prompt_used": prompt,
        "style": style,
        "cat_fact": cat_fact,
        "image_size_bytes": len(image_b64),
        "hint": "Image stored server-side. Call send_cat_image with image_base64='__last__' to send it to Slack.",
    }

    # _mcp_image is intercepted by our patched convert_to_mcp_content
    # and emitted as a real MCP ImageContent block, so Claude Desktop
    # renders it inline instead of dumping base64 text.
    if preview_b64:
        result["_mcp_image"] = {"data": preview_b64, "mimeType": "image/jpeg"}

    return result
