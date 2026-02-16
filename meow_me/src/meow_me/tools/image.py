"""Image generation tools - create cat-themed art from avatars using OpenAI."""

import asyncio
import base64
import io
import os
from typing import Annotated

import httpx
from arcade_mcp_server import tool
from openai import OpenAI

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
    cat_fact: Annotated[str, "The cat fact to incorporate into the image"],
    avatar_url: Annotated[str, "URL of the user's avatar image"],
    style: Annotated[str, "Art style: cartoon, watercolor, anime, or photorealistic"] = "cartoon",
) -> dict:
    """Generate a cat-themed image by transforming a user's avatar.

    Downloads the avatar, composes a prompt from the cat fact and style,
    and uses OpenAI's gpt-image-1 to create stylized cat art.

    The generated image is stored server-side. To send it to Slack, call
    send_cat_image with image_base64 set to '__last__'.

    Falls back with an error message if OPENAI_API_KEY is not set.
    """
    style = style if style in STYLE_PROMPTS else DEFAULT_STYLE
    prompt = _compose_prompt(cat_fact, style)

    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        return {
            "error": "OPENAI_API_KEY not set. Image generation requires an OpenAI API key.",
            "prompt_used": prompt,
            "style": style,
            "cat_fact": cat_fact,
        }

    try:
        # Download avatar
        avatar_bytes = await _download_avatar(avatar_url)
    except Exception as e:
        return {
            "error": f"Failed to download avatar from {avatar_url}: {e}",
            "style": style,
            "cat_fact": cat_fact,
        }

    try:
        # Generate image (sync call, run in thread to avoid blocking event loop)
        image_b64 = await asyncio.to_thread(_generate_image_openai, avatar_bytes, prompt)
    except Exception as e:
        return {
            "error": f"Image generation failed: {e}",
            "prompt_used": prompt,
            "style": style,
            "cat_fact": cat_fact,
        }

    # Stash the image server-side (avoids sending ~1.5MB through LLM context)
    _last_generated_image.clear()
    _last_generated_image["base64"] = image_b64
    _last_generated_image["cat_fact"] = cat_fact
    _last_generated_image["style"] = style

    return {
        "success": True,
        "prompt_used": prompt,
        "style": style,
        "cat_fact": cat_fact,
        "image_size_bytes": len(image_b64),
        "hint": "Image stored server-side. Call send_cat_image with image_base64='__last__' to send it to Slack, or call meow_me for the full pipeline.",
    }
