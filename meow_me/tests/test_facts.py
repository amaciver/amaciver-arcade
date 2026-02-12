"""Tests for the cat facts tool (facts.py)."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from meow_me.tools.facts import _parse_facts_response, get_cat_fact

SAMPLE_SINGLE_FACT_RESPONSE = {"data": ["Cats sleep 70% of their lives."]}
SAMPLE_MULTI_FACT_RESPONSE = {
    "data": [
        "Cats sleep 70% of their lives.",
        "A group of cats is called a clowder.",
        "Cats have over 20 vocalizations, including the purr.",
    ]
}
SAMPLE_EMPTY_FACT_RESPONSE = {"data": []}


# --- Unit tests for _parse_facts_response ---

class TestParseFactsResponse:
    def test_parse_single_fact(self):
        result = _parse_facts_response(SAMPLE_SINGLE_FACT_RESPONSE)
        assert result == ["Cats sleep 70% of their lives."]

    def test_parse_multiple_facts(self):
        result = _parse_facts_response(SAMPLE_MULTI_FACT_RESPONSE)
        assert len(result) == 3
        assert "A group of cats is called a clowder." in result

    def test_parse_empty_response(self):
        result = _parse_facts_response(SAMPLE_EMPTY_FACT_RESPONSE)
        assert result == []

    def test_parse_missing_data_key(self):
        result = _parse_facts_response({})
        assert result == []

    def test_parse_preserves_order(self):
        result = _parse_facts_response(SAMPLE_MULTI_FACT_RESPONSE)
        assert result[0] == "Cats sleep 70% of their lives."
        assert result[2] == "Cats have over 20 vocalizations, including the purr."


# --- Tests for get_cat_fact tool ---

class TestGetCatFact:
    @pytest.mark.asyncio
    async def test_fetch_single_fact(self):
        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_SINGLE_FACT_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.facts.httpx.AsyncClient", return_value=mock_client):
            result = await get_cat_fact(count=1)

        assert result["count"] == 1
        assert len(result["facts"]) == 1
        assert result["facts"][0] == "Cats sleep 70% of their lives."

    @pytest.mark.asyncio
    async def test_fetch_multiple_facts(self):
        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_MULTI_FACT_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.facts.httpx.AsyncClient", return_value=mock_client):
            result = await get_cat_fact(count=3)

        assert result["count"] == 3
        assert len(result["facts"]) == 3

    @pytest.mark.asyncio
    async def test_count_clamped_to_minimum(self):
        """Count below 1 should be clamped to 1."""
        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_SINGLE_FACT_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.facts.httpx.AsyncClient", return_value=mock_client):
            result = await get_cat_fact(count=0)

        # Should have requested count=1 (clamped)
        mock_client.get.assert_called_once()
        call_kwargs = mock_client.get.call_args
        assert call_kwargs[1]["params"]["count"] == 1

    @pytest.mark.asyncio
    async def test_count_clamped_to_maximum(self):
        """Count above 5 should be clamped to 5."""
        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_MULTI_FACT_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.facts.httpx.AsyncClient", return_value=mock_client):
            result = await get_cat_fact(count=10)

        call_kwargs = mock_client.get.call_args
        assert call_kwargs[1]["params"]["count"] == 5

    @pytest.mark.asyncio
    async def test_empty_api_response(self):
        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_EMPTY_FACT_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.facts.httpx.AsyncClient", return_value=mock_client):
            result = await get_cat_fact(count=1)

        assert result["count"] == 0
        assert result["facts"] == []

    @pytest.mark.asyncio
    async def test_api_url_correct(self):
        """Verify we hit the correct MeowFacts URL."""
        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_SINGLE_FACT_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.facts.httpx.AsyncClient", return_value=mock_client):
            await get_cat_fact(count=1)

        call_args = mock_client.get.call_args
        assert "meowfacts.herokuapp.com" in call_args[0][0]
