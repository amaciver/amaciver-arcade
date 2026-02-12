"""Slack integration tools - send cat facts via Slack DM."""

from typing import Annotated

import httpx
from arcade_mcp_server import Context, tool
from arcade_mcp_server.auth import Slack

SLACK_API_BASE = "https://slack.com/api"
MEOWFACTS_URL = "https://meowfacts.herokuapp.com/"


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


async def _get_own_user_id(token: str) -> str:
    """Get the authenticated user's Slack user ID via auth.test."""
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


@tool(requires_auth=Slack(scopes=["chat:write", "users:read"]))
async def meow_me(
    context: Context,
) -> dict:
    """Fetch a random cat fact and DM it to yourself on Slack.

    Uses Arcade's Slack OAuth to authenticate, then sends a cat fact
    as a direct message to the authenticated user.
    """
    token = context.get_auth_token_or_empty()

    # Get the user's own Slack ID
    user_id = await _get_own_user_id(token)

    # Fetch a random cat fact
    fact = await _fetch_one_fact()

    # DM it to yourself (posting to a user ID opens a DM)
    message = _format_cat_fact_message(fact)
    result = await _send_slack_message(token, user_id, message)
    result["fact"] = fact
    result["recipient"] = user_id
    return result


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
