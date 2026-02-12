"""Tests for the Slack integration tools (slack.py)."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from meow_me.tools.slack import (
    _format_cat_fact_message,
    _fetch_one_fact,
    _get_own_user_id,
    _open_dm_channel,
    _send_slack_message,
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
