"""Tests for the Slack integration tools (slack.py)."""

import base64

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from meow_me.tools.slack import (
    _format_cat_fact_message,
    _fetch_one_fact,
    _get_own_user_id,
    _open_dm_channel,
    _send_slack_message,
    _resolve_channel_id,
    _get_upload_url,
    _upload_file_bytes,
    _complete_upload,
)

SAMPLE_SINGLE_FACT_RESPONSE = {"data": ["Cats sleep 70% of their lives."]}
SAMPLE_CHAT_POST_SUCCESS = {
    "ok": True,
    "channel": "D12345678",
    "ts": "1234567890.123456",
}
SAMPLE_CHAT_POST_FAILURE = {"ok": False, "error": "channel_not_found"}


# --- Unit tests for _format_cat_fact_message ---

class TestFormatCatFactMessage:
    def test_format_includes_emoji(self):
        result = _format_cat_fact_message("Cats are great.")
        assert ":cat:" in result

    def test_format_includes_fact(self):
        fact = "Cats sleep 70% of their lives."
        result = _format_cat_fact_message(fact)
        assert fact in result

    def test_format_includes_bold_header(self):
        result = _format_cat_fact_message("Test fact")
        assert "*Meow Fact:*" in result

    def test_format_has_newline_before_fact(self):
        result = _format_cat_fact_message("Test fact")
        assert "\nTest fact" in result


# --- Tests for _fetch_one_fact ---

class TestFetchOneFact:
    @pytest.mark.asyncio
    async def test_returns_first_fact(self):
        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_SINGLE_FACT_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.slack.httpx.AsyncClient", return_value=mock_client):
            fact = await _fetch_one_fact()

        assert fact == "Cats sleep 70% of their lives."

    @pytest.mark.asyncio
    async def test_fallback_on_empty_response(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.slack.httpx.AsyncClient", return_value=mock_client):
            fact = await _fetch_one_fact()

        assert fact == "Cats are amazing!"


# --- Tests for _get_own_user_id ---

class TestGetOwnUserId:
    @pytest.mark.asyncio
    async def test_returns_user_id_from_auth_test(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "user_id": "U_AUTH_USER",
            "team_id": "T12345",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.slack.httpx.AsyncClient", return_value=mock_client):
            user_id = await _get_own_user_id("xoxb-token")

        assert user_id == "U_AUTH_USER"

    @pytest.mark.asyncio
    async def test_raises_on_auth_test_failure(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": False, "error": "invalid_auth"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.slack.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RuntimeError, match="invalid_auth"):
                await _get_own_user_id("bad-token")

    @pytest.mark.asyncio
    async def test_calls_auth_test_endpoint(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "user_id": "U123"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.slack.httpx.AsyncClient", return_value=mock_client):
            await _get_own_user_id("xoxb-token")

        call_args = mock_client.post.call_args
        assert "auth.test" in call_args[0][0]


# --- Tests for _open_dm_channel ---

class TestOpenDmChannel:
    @pytest.mark.asyncio
    async def test_returns_dm_channel_id(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "channel": {"id": "D_DM_CHANNEL"},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.slack.httpx.AsyncClient", return_value=mock_client):
            channel_id = await _open_dm_channel("xoxb-token", "U12345678")

        assert channel_id == "D_DM_CHANNEL"

    @pytest.mark.asyncio
    async def test_raises_on_failure(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": False, "error": "user_not_found"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.slack.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RuntimeError, match="user_not_found"):
                await _open_dm_channel("xoxb-token", "U_BAD")

    @pytest.mark.asyncio
    async def test_calls_conversations_open(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "channel": {"id": "D_DM"},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.slack.httpx.AsyncClient", return_value=mock_client):
            await _open_dm_channel("xoxb-token", "U12345678")

        call_args = mock_client.post.call_args
        assert "conversations.open" in call_args[0][0]
        assert call_args[1]["json"]["users"] == "U12345678"


# --- Tests for _send_slack_message ---

class TestSendSlackMessage:
    @pytest.mark.asyncio
    async def test_successful_send(self):
        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_CHAT_POST_SUCCESS
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.slack.httpx.AsyncClient", return_value=mock_client):
            result = await _send_slack_message("token", "C123", "Hello")

        assert result["success"] is True
        assert result["channel"] == "D12345678"
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_failed_send(self):
        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_CHAT_POST_FAILURE
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.slack.httpx.AsyncClient", return_value=mock_client):
            result = await _send_slack_message("token", "C999", "Hello")

        assert result["success"] is False
        assert result["error"] == "channel_not_found"

    @pytest.mark.asyncio
    async def test_sends_correct_payload(self):
        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_CHAT_POST_SUCCESS
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.slack.httpx.AsyncClient", return_value=mock_client):
            await _send_slack_message("xoxb-token", "C123", "Test message")

        call_kwargs = mock_client.post.call_args
        assert call_kwargs[1]["json"]["channel"] == "C123"
        assert call_kwargs[1]["json"]["text"] == "Test message"
        assert "chat.postMessage" in call_kwargs[0][0]


# --- Tests for _get_upload_url ---

class TestGetUploadUrl:
    @pytest.mark.asyncio
    async def test_returns_upload_url_and_file_id(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "upload_url": "https://files.slack.com/upload/v1/abc123",
            "file_id": "F0123456789",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.slack.httpx.AsyncClient", return_value=mock_client):
            result = await _get_upload_url("xoxb-token", "meow_art.png", 1024)

        assert result["upload_url"] == "https://files.slack.com/upload/v1/abc123"
        assert result["file_id"] == "F0123456789"

    @pytest.mark.asyncio
    async def test_raises_on_failure(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": False, "error": "not_authed"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.slack.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RuntimeError, match="not_authed"):
                await _get_upload_url("bad-token", "file.png", 100)

    @pytest.mark.asyncio
    async def test_calls_correct_endpoint(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "upload_url": "https://files.slack.com/upload",
            "file_id": "F123",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.slack.httpx.AsyncClient", return_value=mock_client):
            await _get_upload_url("xoxb-token", "meow_art.png", 1024)

        call_args = mock_client.post.call_args
        assert "files.getUploadURLExternal" in call_args[0][0]


# --- Tests for _upload_file_bytes ---

class TestUploadFileBytes:
    @pytest.mark.asyncio
    async def test_posts_bytes_to_url(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        file_bytes = b"fake_image_data"
        with patch("meow_me.tools.slack.httpx.AsyncClient", return_value=mock_client):
            await _upload_file_bytes("https://upload.example.com/abc", file_bytes)

        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://upload.example.com/abc"
        assert call_args[1]["content"] == file_bytes


# --- Tests for _complete_upload ---

class TestCompleteUpload:
    @pytest.mark.asyncio
    async def test_completes_successfully(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "files": [{"id": "F123"}]}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.slack.httpx.AsyncClient", return_value=mock_client):
            result = await _complete_upload("xoxb-token", "F123", "C456", "caption")

        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_raises_on_failure(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": False, "error": "invalid_file_id"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.slack.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RuntimeError, match="invalid_file_id"):
                await _complete_upload("xoxb-token", "F_BAD", "C456", "caption")

    @pytest.mark.asyncio
    async def test_sends_correct_payload(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.slack.httpx.AsyncClient", return_value=mock_client):
            await _complete_upload("xoxb-token", "F123", "C456", "A cat fact!")

        call_args = mock_client.post.call_args
        assert "files.completeUploadExternal" in call_args[0][0]
        payload = call_args[1]["json"]
        assert payload["files"] == [{"id": "F123", "title": "Meow Art"}]
        assert payload["channel_id"] == "C456"
        assert payload["initial_comment"] == "A cat fact!"


# --- Tests for _resolve_channel_id ---

class TestResolveChannelId:
    @pytest.mark.asyncio
    async def test_passthrough_channel_id(self):
        """Channel IDs starting with C/G/D are returned unchanged."""
        result = await _resolve_channel_id("xoxb-token", "C01234567")
        assert result == "C01234567"

    @pytest.mark.asyncio
    async def test_passthrough_group_id(self):
        result = await _resolve_channel_id("xoxb-token", "G01234567")
        assert result == "G01234567"

    @pytest.mark.asyncio
    async def test_passthrough_dm_id(self):
        result = await _resolve_channel_id("xoxb-token", "D01234567")
        assert result == "D01234567"

    @pytest.mark.asyncio
    async def test_resolves_channel_name(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "channels": [
                {"id": "C111", "name": "random"},
                {"id": "C222", "name": "general"},
            ],
            "response_metadata": {"next_cursor": ""},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.slack.httpx.AsyncClient", return_value=mock_client):
            result = await _resolve_channel_id("xoxb-token", "general")

        assert result == "C222"

    @pytest.mark.asyncio
    async def test_resolves_hash_prefixed_name(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "channels": [{"id": "C333", "name": "general"}],
            "response_metadata": {"next_cursor": ""},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.slack.httpx.AsyncClient", return_value=mock_client):
            result = await _resolve_channel_id("xoxb-token", "#general")

        assert result == "C333"

    @pytest.mark.asyncio
    async def test_raises_when_not_found(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "channels": [{"id": "C111", "name": "random"}],
            "response_metadata": {"next_cursor": ""},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.slack.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RuntimeError, match="not found"):
                await _resolve_channel_id("xoxb-token", "#nonexistent")

    @pytest.mark.asyncio
    async def test_missing_scope_falls_back_to_raw_value(self):
        """When channels:read scope is missing, returns the channel value as-is."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": False,
            "error": "missing_scope",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.slack.httpx.AsyncClient", return_value=mock_client):
            result = await _resolve_channel_id("xoxb-token", "#general")

        assert result == "#general"
