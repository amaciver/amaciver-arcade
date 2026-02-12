"""Slack integration tools - send cat facts via Slack DM."""

from typing import Annotated

import httpx
from arcade_mcp_server import Context, tool
from arcade_mcp_server.auth import Slack

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


@tool(requires_auth=Slack(scopes=["chat:write", "im:write"]))
async def meow_me(
    context: Context,
) -> dict:
    """Send a random cat fact as a Slack DM to yourself.

    Automatically identifies you from the Slack auth token, opens a DM
    conversation, and sends you a random cat fact.
    """
    token = context.get_auth_token_or_empty()

    # Get the authenticated user's ID from the token
    user_id = await _get_own_user_id(token)

    # Open a DM channel with the user
    dm_channel = await _open_dm_channel(token, user_id)

    # Fetch a random cat fact
    fact = await _fetch_one_fact()

    # Send the fact as a DM
    message = _format_cat_fact_message(fact)
    result = await _send_slack_message(token, dm_channel, message)
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
