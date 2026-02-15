"""Slack avatar tools - retrieve user's profile avatar."""

import httpx
from arcade_mcp_server import Context, tool
from arcade_mcp_server.auth import Slack

SLACK_API_BASE = "https://slack.com/api"


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


async def _get_user_info(token: str, user_id: str) -> dict:
    """Get a user's profile via users.info."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{SLACK_API_BASE}/users.info",
            headers={"Authorization": f"Bearer {token}"},
            params={"user": user_id},
        )
        response.raise_for_status()
        data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Slack users.info failed: {data.get('error', 'unknown')}")
    return data["user"]


def _extract_avatar_url(user_info: dict) -> str:
    """Extract the best available avatar URL from a user profile."""
    profile = user_info.get("profile", {})
    # Prefer image_512, fall back to smaller sizes
    for key in ("image_512", "image_192", "image_72", "image_48", "image_24"):
        url = profile.get(key)
        if url:
            return url
    raise RuntimeError("No avatar URL found in user profile")


def _extract_display_name(user_info: dict) -> str:
    """Extract the best available display name from a user profile."""
    profile = user_info.get("profile", {})
    return (
        profile.get("display_name")
        or profile.get("real_name")
        or user_info.get("real_name")
        or user_info.get("name")
        or "Unknown"
    )


@tool(requires_auth=Slack(scopes=["users:read"]))
async def get_user_avatar(
    context: Context,
) -> dict:
    """Get the authenticated user's Slack avatar URL and display name.

    Automatically identifies you from the Slack auth token, retrieves your
    profile, and returns your avatar image URL.
    """
    token = context.get_auth_token_or_empty()

    user_id = await _get_own_user_id(token)
    user_info = await _get_user_info(token, user_id)
    avatar_url = _extract_avatar_url(user_info)
    display_name = _extract_display_name(user_info)

    return {
        "user_id": user_id,
        "display_name": display_name,
        "avatar_url": avatar_url,
    }
