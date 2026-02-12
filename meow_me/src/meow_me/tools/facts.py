"""MeowFacts API tools - fetch random cat facts."""

from typing import Annotated

import httpx
from arcade_mcp_server import tool

MEOWFACTS_URL = "https://meowfacts.herokuapp.com/"


def _parse_facts_response(data: dict) -> list[str]:
    """Extract facts list from MeowFacts API response."""
    return data.get("data", [])


@tool
async def get_cat_fact(
    count: Annotated[int, "Number of cat facts to fetch (1-5)"] = 1,
) -> dict:
    """Fetch random cat facts from the MeowFacts API.

    Returns one or more random cat facts. No authentication required.
    """
    count = max(1, min(count, 5))

    async with httpx.AsyncClient() as client:
        response = await client.get(MEOWFACTS_URL, params={"count": count})
        response.raise_for_status()
        data = response.json()

    facts = _parse_facts_response(data)
    return {
        "facts": facts,
        "count": len(facts),
    }
