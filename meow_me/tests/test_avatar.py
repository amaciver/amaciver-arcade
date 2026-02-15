"""Tests for the Slack avatar tools (avatar.py)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from meow_me.tools.avatar import (
    _get_own_user_id,
    _get_user_info,
    _extract_avatar_url,
    _extract_display_name,
)

SAMPLE_USER_INFO = {
    "id": "U012ABC",
    "name": "alexcat",
    "real_name": "Alex Cat",
    "profile": {
        "display_name": "Alex",
        "real_name": "Alex Cat",
        "image_24": "https://avatars.slack-edge.com/alex_24.png",
        "image_48": "https://avatars.slack-edge.com/alex_48.png",
        "image_72": "https://avatars.slack-edge.com/alex_72.png",
        "image_192": "https://avatars.slack-edge.com/alex_192.png",
        "image_512": "https://avatars.slack-edge.com/alex_512.png",
    },
}


def _make_mock_client(response_data: dict, method: str = "post"):
    """Create a mock httpx.AsyncClient with a preset response."""
    mock_response = MagicMock()
    mock_response.json.return_value = response_data
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    getattr(mock_client, method).return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


# --- Tests for _get_own_user_id ---

class TestGetOwnUserId:
    @pytest.mark.asyncio
    async def test_returns_user_id(self):
        mock_client = _make_mock_client({"ok": True, "user_id": "U012ABC"})
        with patch("meow_me.tools.avatar.httpx.AsyncClient", return_value=mock_client):
            result = await _get_own_user_id("xoxb-token")
        assert result == "U012ABC"

    @pytest.mark.asyncio
    async def test_raises_on_failure(self):
        mock_client = _make_mock_client({"ok": False, "error": "invalid_auth"})
        with patch("meow_me.tools.avatar.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RuntimeError, match="invalid_auth"):
                await _get_own_user_id("bad-token")


# --- Tests for _get_user_info ---

class TestGetUserInfo:
    @pytest.mark.asyncio
    async def test_returns_user_object(self):
        mock_client = _make_mock_client(
            {"ok": True, "user": SAMPLE_USER_INFO}, method="get"
        )
        with patch("meow_me.tools.avatar.httpx.AsyncClient", return_value=mock_client):
            result = await _get_user_info("xoxb-token", "U012ABC")
        assert result["id"] == "U012ABC"
        assert result["profile"]["image_512"] == "https://avatars.slack-edge.com/alex_512.png"

    @pytest.mark.asyncio
    async def test_raises_on_failure(self):
        mock_client = _make_mock_client(
            {"ok": False, "error": "user_not_found"}, method="get"
        )
        with patch("meow_me.tools.avatar.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RuntimeError, match="user_not_found"):
                await _get_user_info("xoxb-token", "U_BAD")

    @pytest.mark.asyncio
    async def test_calls_users_info_endpoint(self):
        mock_client = _make_mock_client(
            {"ok": True, "user": SAMPLE_USER_INFO}, method="get"
        )
        with patch("meow_me.tools.avatar.httpx.AsyncClient", return_value=mock_client):
            await _get_user_info("xoxb-token", "U012ABC")
        call_args = mock_client.get.call_args
        assert "users.info" in call_args[0][0]
        assert call_args[1]["params"]["user"] == "U012ABC"


# --- Tests for _extract_avatar_url ---

class TestExtractAvatarUrl:
    def test_prefers_image_512(self):
        result = _extract_avatar_url(SAMPLE_USER_INFO)
        assert result == "https://avatars.slack-edge.com/alex_512.png"

    def test_falls_back_to_smaller_image(self):
        user_info = {
            "profile": {
                "image_72": "https://avatars.slack-edge.com/alex_72.png",
            }
        }
        result = _extract_avatar_url(user_info)
        assert result == "https://avatars.slack-edge.com/alex_72.png"

    def test_raises_when_no_avatar(self):
        user_info = {"profile": {}}
        with pytest.raises(RuntimeError, match="No avatar URL"):
            _extract_avatar_url(user_info)

    def test_raises_when_no_profile(self):
        user_info = {}
        with pytest.raises(RuntimeError, match="No avatar URL"):
            _extract_avatar_url(user_info)


# --- Tests for _extract_display_name ---

class TestExtractDisplayName:
    def test_prefers_display_name(self):
        result = _extract_display_name(SAMPLE_USER_INFO)
        assert result == "Alex"

    def test_falls_back_to_real_name(self):
        user_info = {"profile": {"real_name": "Alex Cat"}}
        result = _extract_display_name(user_info)
        assert result == "Alex Cat"

    def test_falls_back_to_top_level_name(self):
        user_info = {"name": "alexcat", "profile": {}}
        result = _extract_display_name(user_info)
        assert result == "alexcat"

    def test_returns_unknown_when_empty(self):
        user_info = {"profile": {}}
        result = _extract_display_name(user_info)
        assert result == "Unknown"
