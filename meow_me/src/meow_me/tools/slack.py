"""Slack integration tools - send cat facts and images via Slack."""

import base64
import os
from typing import Annotated

import httpx
from arcade_mcp_server import Context, tool
from arcade_mcp_server.auth import Slack

from meow_me.tools.avatar import _get_user_info, _extract_avatar_url
from meow_me.tools.image import _download_avatar, _generate_image_openai, _compose_prompt

SLACK_API_BASE = "https://slack.com/api"
MEOWFACTS_URL = "https://meowfacts.herokuapp.com/"


async def _get_own_user_id(token: str) -> str:
    """Get the authenticated user's Slack ID via auth.test."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SLACK_API_BASE}/auth.test",
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Slack auth.test failed: {data.get('error', 'unknown')}")
    return data["user_id"]


def _format_cat_fact_message(fact: str) -> str:
    """Format a cat fact for Slack with emoji."""
    return f":cat: *Meow Fact:*\n{fact}"


async def _fetch_one_fact() -> str:
    """Fetch a single cat fact from MeowFacts API."""
    async with httpx.AsyncClient() as client:
        response = await client.get(MEOWFACTS_URL)
        response.raise_for_status()
        data = response.json()
    facts = data.get("data", [])
    return facts[0] if facts else "Cats are amazing!"


async def _open_dm_channel(token: str, user_id: str) -> str:
    """Open a DM channel with a user via conversations.open."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SLACK_API_BASE}/conversations.open",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"users": user_id},
        )
        response.raise_for_status()
        data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Slack conversations.open failed: {data.get('error', 'unknown')}")
    return data["channel"]["id"]


async def _send_slack_message(token: str, channel: str, text: str) -> dict:
    """Send a message via Slack chat.postMessage."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SLACK_API_BASE}/chat.postMessage",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"channel": channel, "text": text},
        )
        response.raise_for_status()
        data = response.json()

    if not data.get("ok"):
        return {
            "success": False,
            "error": data.get("error", "unknown"),
        }
    return {
        "success": True,
        "channel": data.get("channel"),
        "timestamp": data.get("ts"),
    }


@tool(requires_auth=Slack(scopes=["chat:write", "im:write", "users:read"]))
async def meow_me(
    context: Context,
) -> dict:
    """Send a random cat fact with cat-themed art as a Slack DM to yourself.

    One-shot pipeline: fetches a cat fact, retrieves your avatar, generates
    a stylized cat-themed image from your avatar, and DMs the result to you.
    Falls back to text-only if image generation is unavailable.

    Note: Image upload requires a Slack token with files:write scope.
    Arcade's built-in Slack OAuth does not support files:write, so image
    uploads only work with a direct SLACK_BOT_TOKEN. When files:write is
    unavailable, this tool sends a text-only cat fact to your DMs.
    """
    token = context.get_auth_token_or_empty()

    # 1. Get the authenticated user's ID
    user_id = await _get_own_user_id(token)

    # 2. Open a DM channel
    dm_channel = await _open_dm_channel(token, user_id)

    # 3. Fetch a random cat fact
    fact = await _fetch_one_fact()

    # 4. Try the full image pipeline (avatar + image gen + upload)
    image_generated = False
    image_sent = False

    if os.getenv("OPENAI_API_KEY"):
        try:
            # Get avatar URL
            user_info = await _get_user_info(token, user_id)
            avatar_url = _extract_avatar_url(user_info)

            # Download avatar and generate image
            avatar_bytes = await _download_avatar(avatar_url)
            prompt = _compose_prompt(fact, "cartoon")
            image_b64 = _generate_image_openai(avatar_bytes, prompt)
            image_generated = True

            # Upload image to DM
            image_bytes = base64.b64decode(image_b64)
            upload_info = await _get_upload_url(token, "meow_art.png", len(image_bytes))
            await _upload_file_bytes(upload_info["upload_url"], image_bytes)
            caption = _format_cat_fact_message(fact)
            await _complete_upload(token, upload_info["file_id"], dm_channel, caption)
            image_sent = True
        except Exception:
            # Fallback: send text-only if any step fails
            pass

    # 5. If image wasn't sent, send text-only fact
    if not image_sent:
        message = _format_cat_fact_message(fact)
        await _send_slack_message(token, dm_channel, message)

    return {
        "success": True,
        "fact": fact,
        "image_generated": image_generated,
        "image_sent": image_sent,
        "recipient": user_id,
        "channel": dm_channel,
    }


@tool(requires_auth=Slack(scopes=["chat:write"]))
async def send_cat_fact(
    context: Context,
    channel: Annotated[str, "Slack channel ID or name (e.g. #general or C1234567890)"],
    count: Annotated[int, "Number of cat facts to send (1-3)"] = 1,
) -> dict:
    """Send random cat fact(s) to a specific Slack channel.

    Fetches cat facts from MeowFacts API and posts them to the given channel.
    """
    token = context.get_auth_token_or_empty()
    count = max(1, min(count, 3))

    # Fetch facts
    async with httpx.AsyncClient() as client:
        response = await client.get(MEOWFACTS_URL, params={"count": count})
        response.raise_for_status()
        data = response.json()
    facts = data.get("data", [])

    # Send each fact
    results = []
    for fact in facts:
        message = _format_cat_fact_message(fact)
        result = await _send_slack_message(token, channel, message)
        result["fact"] = fact
        results.append(result)

    return {
        "facts_sent": len(results),
        "channel": channel,
        "results": results,
    }


async def _resolve_channel_id(token: str, channel: str) -> str:
    """Resolve a channel name (e.g. '#general' or 'general') to a channel ID.

    If the input already looks like a Slack channel ID (starts with C/G/D),
    returns it unchanged. Requires the ``channels:read`` bot scope to look up
    channel names; falls back to passing the raw value through if the scope is
    missing (so channel IDs still work without the extra scope).
    """
    # Already a channel ID
    if channel and channel[0] in ("C", "G", "D") and channel[1:].isalnum():
        return channel

    # Strip leading '#'
    name = channel.lstrip("#")

    try:
        async with httpx.AsyncClient() as client:
            cursor = ""
            while True:
                params: dict = {"limit": "200", "types": "public_channel,private_channel"}
                if cursor:
                    params["cursor"] = cursor
                response = await client.get(
                    f"{SLACK_API_BASE}/conversations.list",
                    headers={"Authorization": f"Bearer {token}"},
                    params=params,
                )
                response.raise_for_status()
                data = response.json()
                if not data.get("ok"):
                    error = data.get("error", "unknown")
                    if error == "missing_scope":
                        # channels:read scope not available — fall back to raw value
                        return channel
                    raise RuntimeError(
                        f"Slack conversations.list failed: {error}"
                    )
                for ch in data.get("channels", []):
                    if ch.get("name") == name:
                        return ch["id"]
                cursor = data.get("response_metadata", {}).get("next_cursor", "")
                if not cursor:
                    break
    except RuntimeError:
        raise
    except Exception:
        # Network or other error — fall back to raw value
        return channel

    raise RuntimeError(f"Channel '{channel}' not found in workspace")


async def _get_upload_url(token: str, filename: str, length: int) -> dict:
    """Get an external upload URL via files.getUploadURLExternal."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SLACK_API_BASE}/files.getUploadURLExternal",
            headers={"Authorization": f"Bearer {token}"},
            data={"filename": filename, "length": length},
        )
        response.raise_for_status()
        data = response.json()
    if not data.get("ok"):
        raise RuntimeError(
            f"Slack files.getUploadURLExternal failed: {data.get('error', 'unknown')}"
        )
    return {"upload_url": data["upload_url"], "file_id": data["file_id"]}


async def _upload_file_bytes(upload_url: str, file_bytes: bytes) -> None:
    """Upload file bytes to the Slack-provided upload URL."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            upload_url,
            content=file_bytes,
            headers={"Content-Type": "application/octet-stream"},
        )
        response.raise_for_status()


async def _complete_upload(
    token: str, file_id: str, channel: str, initial_comment: str
) -> dict:
    """Complete the file upload via files.completeUploadExternal.

    Resolves channel names (e.g. '#general') to channel IDs automatically,
    since this API endpoint requires a channel ID.
    """
    channel_id = await _resolve_channel_id(token, channel)
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SLACK_API_BASE}/files.completeUploadExternal",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "files": [{"id": file_id, "title": "Meow Art"}],
                "channel_id": channel_id,
                "initial_comment": initial_comment,
            },
        )
        response.raise_for_status()
        data = response.json()
    if not data.get("ok"):
        raise RuntimeError(
            f"Slack files.completeUploadExternal failed: {data.get('error', 'unknown')}"
        )
    return data


@tool(requires_auth=Slack(scopes=["chat:write"]))
async def send_cat_image(
    context: Context,
    cat_fact: Annotated[str, "The cat fact to include as a caption"],
    channel: Annotated[str, "Slack channel ID or name (e.g. #general or C1234567890)"],
    image_base64: Annotated[str, "Base64-encoded PNG data, or '__last__' to use the most recently generated image"] = "__last__",
) -> dict:
    """Upload a cat-themed image with a fact caption to a Slack channel.

    Takes a base64-encoded image (from generate_cat_image) and uploads it
    to the specified Slack channel using the file upload API.

    Use image_base64='__last__' (default) to automatically use the image
    from the most recent generate_cat_image call.

    Note: Requires a Slack token with files:write scope for file uploads.
    Arcade's built-in Slack OAuth does not support files:write, so this tool
    falls back to sending the cat fact as text if file upload fails.
    """
    token = context.get_auth_token_or_empty()

    # Resolve __last__ reference from server-side stash
    if image_base64 == "__last__":
        from meow_me.tools.image import get_last_generated_image
        stash = get_last_generated_image()
        if stash.get("base64"):
            image_base64 = stash["base64"]
            cat_fact = cat_fact or stash.get("cat_fact", "")
        else:
            return {
                "error": "No image available. Call generate_cat_image first, then call send_cat_image.",
            }

    # Decode image
    image_bytes = base64.b64decode(image_base64)

    # Try file upload (requires files:write scope on the token)
    try:
        upload_info = await _get_upload_url(token, "meow_art.png", len(image_bytes))
        await _upload_file_bytes(upload_info["upload_url"], image_bytes)
        caption = _format_cat_fact_message(cat_fact)
        await _complete_upload(token, upload_info["file_id"], channel, caption)
        return {
            "success": True,
            "channel": channel,
            "file_id": upload_info["file_id"],
            "cat_fact": cat_fact,
        }
    except Exception as e:
        # Fallback: send text-only if file upload fails (e.g. missing files:write scope)
        message = _format_cat_fact_message(cat_fact)
        await _send_slack_message(token, channel, message)
        return {
            "success": True,
            "channel": channel,
            "cat_fact": cat_fact,
            "image_uploaded": False,
            "fallback_reason": f"File upload failed ({e}), sent text-only fact instead.",
        }
