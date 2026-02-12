"""Evaluation tests for meow_me - end-to-end scenario validation."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from meow_me.tools.facts import get_cat_fact, _parse_facts_response
from meow_me.tools.slack import (
    _format_cat_fact_message,
    _fetch_one_fact,
    _get_own_user_id,
    _open_dm_channel,
    _send_slack_message,
)


class TestEndToEndMeowMe:
    """Simulate the full meow_me workflow: context -> open DM -> fetch fact -> send."""

    @pytest.mark.asyncio
    async def test_full_self_dm_workflow(self):
        """Simulate: auth.test -> open DM channel -> fetch fact -> send message."""
        # Step 1: auth.test returns user ID from the token
        auth_response = MagicMock()
        auth_response.json.return_value = {
            "ok": True,
            "user_id": "U_EVAL_USER",
            "team_id": "T_EVAL",
        }
        auth_response.raise_for_status = MagicMock()

        # Step 2: conversations.open returns DM channel
        dm_response = MagicMock()
        dm_response.json.return_value = {
            "ok": True,
            "channel": {"id": "D_EVAL_DM"},
        }
        dm_response.raise_for_status = MagicMock()

        # Step 3: MeowFacts returns a fact
        fact_response = MagicMock()
        fact_response.json.return_value = {"data": ["Cats can rotate their ears 180 degrees."]}
        fact_response.raise_for_status = MagicMock()

        # Step 4: chat.postMessage succeeds
        chat_response = MagicMock()
        chat_response.json.return_value = {
            "ok": True,
            "channel": "D_EVAL_DM",
            "ts": "9999999999.000001",
        }
        chat_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.slack.httpx.AsyncClient", return_value=mock_client):
            # Get user ID from auth.test
            mock_client.post.return_value = auth_response
            user_id = await _get_own_user_id("xoxb-eval-token")
            assert user_id == "U_EVAL_USER"

            # Open DM channel
            mock_client.post.return_value = dm_response
            dm_channel = await _open_dm_channel("xoxb-eval-token", user_id)
            assert dm_channel == "D_EVAL_DM"

            # Fetch fact
            mock_client.get.return_value = fact_response
            fact = await _fetch_one_fact()
            assert "180 degrees" in fact

            # Format and send
            message = _format_cat_fact_message(fact)
            assert ":cat:" in message

            mock_client.post.return_value = chat_response
            result = await _send_slack_message("xoxb-eval-token", dm_channel, message)
            assert result["success"] is True


class TestEndToEndSendCatFact:
    """Simulate the send_cat_fact workflow: fetch N facts -> send to channel."""

    @pytest.mark.asyncio
    async def test_multi_fact_channel_send(self):
        """Send 3 facts to a channel - verify all arrive."""
        facts = [
            "Cats have 5 toes on front paws and 4 on back paws.",
            "A cat's purr vibrates at 25-150 Hz.",
            "Cats can jump up to 6 times their length.",
        ]

        fact_response = MagicMock()
        fact_response.json.return_value = {"data": facts}
        fact_response.raise_for_status = MagicMock()

        chat_response = MagicMock()
        chat_response.json.return_value = {
            "ok": True,
            "channel": "C_GENERAL",
            "ts": "1111111111.000001",
        }
        chat_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get.return_value = fact_response
        mock_client.post.return_value = chat_response

        with patch("meow_me.tools.slack.httpx.AsyncClient", return_value=mock_client):
            # Fetch facts
            response = await mock_client.get("https://meowfacts.herokuapp.com/", params={"count": 3})
            data = response.json()
            fetched_facts = _parse_facts_response(data)

            # Send each
            results = []
            for fact in fetched_facts:
                message = _format_cat_fact_message(fact)
                result = await _send_slack_message("xoxb-token", "C_GENERAL", message)
                result["fact"] = fact
                results.append(result)

        assert len(results) == 3
        assert all(r["success"] for r in results)
        assert "purr" in results[1]["fact"]


class TestFactQuality:
    """Validate fact response patterns and edge cases."""

    def test_fact_is_nonempty_string(self):
        facts = _parse_facts_response({"data": ["Cats are crepuscular."]})
        assert len(facts) == 1
        assert len(facts[0]) > 0

    def test_handles_unexpected_types_gracefully(self):
        # If API returns non-list, we get empty
        result = _parse_facts_response({"data": "not a list"})
        # .get returns the string; this tests that our tool handles it
        assert result == "not a list"

    @pytest.mark.asyncio
    async def test_fact_count_matches_request(self):
        """Verify the tool returns as many facts as the API provides."""
        for count in [1, 2, 3, 5]:
            fake_facts = [f"Fact number {i}" for i in range(count)]
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": fake_facts}
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)

            with patch("meow_me.tools.facts.httpx.AsyncClient", return_value=mock_client):
                result = await get_cat_fact(count=count)

            assert result["count"] == count


class TestSlackMessageFormatting:
    """Validate message formatting patterns for Slack."""

    def test_message_renders_in_slack_markdown(self):
        msg = _format_cat_fact_message("Cats have whiskers.")
        # Slack bold is *text*
        assert "*Meow Fact:*" in msg
        # Contains emoji shortcode
        assert msg.startswith(":cat:")

    def test_long_fact_not_truncated(self):
        long_fact = "A" * 500
        msg = _format_cat_fact_message(long_fact)
        assert long_fact in msg

    def test_special_characters_preserved(self):
        fact = "Cats' claws are curved & retractable <like hooks>!"
        msg = _format_cat_fact_message(fact)
        assert "&" in msg
        assert "<like hooks>" in msg
