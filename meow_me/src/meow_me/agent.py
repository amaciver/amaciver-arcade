#!/usr/bin/env python3
"""Meow Art agent - LLM-powered CLI that creates cat-fact-inspired art.

This agent connects to Arcade-deployed MCP tools remotely via the Arcade SDK.
The LLM (gpt-4o-mini) decides which tools to call based on user input —
there is no hardcoded orchestration logic in the agent itself.

Usage:
    uv run python -m meow_me              # Interactive agent (requires OPENAI_API_KEY + ARCADE_API_KEY)
    uv run python -m meow_me --slack      # Pass SLACK_BOT_TOKEN to tools (all features)
    uv run python -m meow_me --demo       # Scripted demo (no API keys needed)

For MCP server mode (used by Claude Desktop, Cursor, etc.):
    uv run arcade mcp -p meow_me stdio    # STDIO transport
    uv run arcade mcp -p meow_me http     # HTTP transport
"""

import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# System prompt (drives LLM tool selection and conversation flow)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are Meow Art, a fun and friendly agent that creates cat-fact-inspired art \
and sends it via Slack.

TOOLS AVAILABLE (provided by Arcade-deployed MCP server):
- MeowMe_GetCatFact(count)                          — Fetch 1-5 random cat facts (always works)
- MeowMe_GetUserAvatar()                            — Get your Slack avatar URL (needs Slack auth)
- MeowMe_GenerateCatImage(cat_fact, avatar_url, style) — Create stylized art from avatar + fact (needs OPENAI_API_KEY)
- MeowMe_SendCatFact(channel, count)                — Send text fact(s) to a Slack channel (needs Slack auth)
- MeowMe_SendCatImage(cat_fact, channel, image_base64) — Upload image + caption to Slack (needs Slack auth)
- MeowMe_SaveImageLocally(image_base64, cat_fact)   — Save generated image to local file (no auth needed)
- MeowMe_MeowMe()                                   — One-shot: fact + avatar + image + DM self (needs Slack auth + OPENAI_API_KEY)

ROUTING RULES:

1. "Meow me" (standalone, no modifiers) → call MeowMe_MeowMe() immediately.
   No questions asked. It handles everything internally and DMs the user.
   - "Meow me" ✓  "Meow me!" ✓  "Hit me with a meow" ✓
   - IMPORTANT: If the user adds ANY modifier (a channel, a style, a count,
     a specific fact), it is NOT a MeowMe_MeowMe call. Treat it as interactive.
   - "Meow me to #random" → INTERACTIVE (channel specified)
   - "Meow me in watercolor" → INTERACTIVE (style specified)
   - "Meow me 3 facts" → INTERACTIVE (count specified)

2. Everything else → follow this two-phase flow:
   a. FACT PHASE: Call MeowMe_GetCatFact. Present the fact(s). Let the user rotate
      (call MeowMe_GetCatFact again) until they're happy.
   b. DELIVERY PHASE: Ask "with image or just text?"
      - Text only → ask where to send → MeowMe_SendCatFact(channel)
      - With image → MeowMe_GetUserAvatar → MeowMe_GenerateCatImage → ask where → MeowMe_SendCatImage(channel)
      - Display only (no send) → just show the fact/image in chat

3. If the user says "another" / "new one" / "different fact" → call MeowMe_GetCatFact again.

4. If the user specifies a channel upfront, remember it but still ask about image vs text.

5. If the user just says "tell me a fact" with no send intent, display the fact
   and offer: another fact, an image, or send it somewhere.

6. When Slack is NOT available:
   - "Meow me" → MeowMe_GetCatFact → MeowMe_GenerateCatImage → MeowMe_SaveImageLocally (display path)
   - Skip MeowMe_SendCatFact, MeowMe_SendCatImage, MeowMe_MeowMe, MeowMe_GetUserAvatar entirely.
   - For MeowMe_GenerateCatImage without an avatar, use a placeholder URL like
     "https://placecats.com/512/512" as the avatar_url.

7. After MeowMe_GenerateCatImage, always call MeowMe_SaveImageLocally() to save the image
   to a local file so the user can view it. It automatically uses the last generated image.

Be concise, fun, and cat-themed in your responses. Use cat emoji sparingly.
If a tool fails because of missing auth, explain what's needed and suggest alternatives.
"""


# ---------------------------------------------------------------------------
# --slack mode: user resolution (bot tokens need manual user identification)
# ---------------------------------------------------------------------------

_slack_config: dict = {"use_direct_token": False}


async def _fetch_slack_users(token: str) -> list[dict]:
    """Fetch all non-bot, non-deleted workspace members via users.list (paginated)."""
    import httpx

    users: list[dict] = []
    cursor = ""
    async with httpx.AsyncClient() as client:
        while True:
            params: dict = {"limit": "200"}
            if cursor:
                params["cursor"] = cursor
            resp = await client.get(
                "https://slack.com/api/users.list",
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                raise RuntimeError(f"Slack users.list failed: {data.get('error', 'unknown')}")
            for member in data.get("members", []):
                if member.get("is_bot") or member.get("deleted") or member.get("id") == "USLACKBOT":
                    continue
                users.append(member)
            cursor = data.get("response_metadata", {}).get("next_cursor", "")
            if not cursor:
                break
    return users


def _match_users(users: list[dict], query: str) -> list[dict]:
    """Find workspace members matching a query (case-insensitive).

    Matches against name (handle), display_name, and real_name.
    """
    q = query.lower().lstrip("@")
    matches = []
    for user in users:
        name = (user.get("name") or "").lower()
        profile = user.get("profile", {})
        display = (profile.get("display_name") or "").lower()
        real = (profile.get("real_name") or "").lower()
        if q in (name, display, real) or q in name or q in display or q in real:
            matches.append(user)
    return matches


async def _resolve_human_user(token: str) -> dict:
    """Prompt for Slack username, look up via users.list, cache the result.

    Returns {"user_id": ..., "display_name": ...} and stores in _slack_config.
    """
    print("  Resolving your Slack identity...", flush=True)
    users = await _fetch_slack_users(token)

    for attempt in range(3):
        query = input("  Enter your Slack username or display name: ").strip()
        if not query:
            print("  Please enter a name.", flush=True)
            continue

        matches = _match_users(users, query)

        if len(matches) == 1:
            user = matches[0]
            profile = user.get("profile", {})
            display = profile.get("display_name") or profile.get("real_name") or user.get("name", "")
            _slack_config["target_user_id"] = user["id"]
            _slack_config["target_display_name"] = display
            return {"user_id": user["id"], "display_name": display}

        if len(matches) > 1:
            print(f"  Found {len(matches)} matches:", flush=True)
            for i, user in enumerate(matches[:10], 1):
                profile = user.get("profile", {})
                display = profile.get("display_name") or profile.get("real_name") or ""
                handle = user.get("name", "")
                print(f"    {i}. @{handle} ({display}) [{user['id']}]", flush=True)
            try:
                choice = int(input("  Enter number: ").strip()) - 1
                if 0 <= choice < len(matches[:10]):
                    user = matches[choice]
                    profile = user.get("profile", {})
                    display = profile.get("display_name") or profile.get("real_name") or user.get("name", "")
                    _slack_config["target_user_id"] = user["id"]
                    _slack_config["target_display_name"] = display
                    return {"user_id": user["id"], "display_name": display}
            except (ValueError, EOFError):
                pass
            print("  Invalid selection, try again.", flush=True)
            continue

        print(f"  No users found matching '{query}'. Try again.", flush=True)

    print("  Could not resolve Slack user after 3 attempts.", flush=True)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Capability detection (drives system prompt adaptation)
# ---------------------------------------------------------------------------


def _detect_capabilities() -> dict:
    """Detect which API capabilities are available based on env vars and CLI flags."""
    has_slack_token = _slack_config["use_direct_token"] and bool(os.getenv("SLACK_BOT_TOKEN"))
    has_arcade_key = bool(os.getenv("ARCADE_API_KEY"))
    return {
        "openai": bool(os.getenv("OPENAI_API_KEY")),
        "slack": has_slack_token,
        "arcade": has_arcade_key,
        "slack_available": has_slack_token or has_arcade_key,
    }


def _build_capability_prompt(caps: dict) -> str:
    """Build an addendum to the system prompt based on available capabilities."""
    lines = ["\nCURRENT SESSION CAPABILITIES:"]
    if caps.get("slack"):
        lines.append("- Slack: CONNECTED (SLACK_BOT_TOKEN via --slack flag)")
    elif caps.get("arcade"):
        lines.append("- Slack: AVAILABLE via Arcade OAuth (text messaging + avatars)")
        lines.append("  -> MeowMe_SendCatFact, MeowMe_GetUserAvatar, MeowMe_MeowMe (text-only) work.")
        lines.append("  -> MeowMe_SendCatImage does NOT work (Arcade doesn't support files:write scope).")
        lines.append("  -> For images: MeowMe_GenerateCatImage + MeowMe_SaveImageLocally (saves to disk).")
    else:
        lines.append("- Slack: NOT AVAILABLE (use --slack flag or set ARCADE_API_KEY)")
        lines.append("  -> Do NOT call MeowMe_MeowMe, MeowMe_SendCatFact, MeowMe_SendCatImage, or MeowMe_GetUserAvatar.")
        lines.append("  -> Instead: display facts in chat, generate images and save locally.")
    if caps.get("openai"):
        lines.append("- Image generation: AVAILABLE (OPENAI_API_KEY set)")
    else:
        lines.append("- Image generation: NOT AVAILABLE (no OPENAI_API_KEY)")
        lines.append("  -> Do NOT call MeowMe_GenerateCatImage. Stick to text facts.")
    lines.append("")
    lines.append("Adapt your behavior to what's available. Be upfront about limitations.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Interactive agent loop (LLM decides which tools to call via Arcade SDK)
# ---------------------------------------------------------------------------


async def run_agent() -> None:
    """Run the interactive LLM-powered agent.

    Architecture: The agent is a thin client. All tool logic runs on the
    Arcade cloud — the agent never imports or executes tool code directly.
    The LLM (gpt-4o-mini) decides which tools to call based on user input
    and the system prompt. Tool execution is handled by the Arcade platform.
    """
    from agents import Agent, Runner
    from arcadepy import AsyncArcade
    from agents_arcade import get_arcade_tools

    caps = _detect_capabilities()

    print()
    print("=" * 55)
    print("  MEOW ART - Cat Fact Art Generator")
    print("  Powered by OpenAI + Arcade.dev")
    print("=" * 55)
    print()

    # Resolve Arcade user ID for auth
    user_id = os.getenv("ARCADE_USER_ID", "")
    if not user_id:
        user_id = input("  Enter your Arcade account email: ").strip()
        if not user_id:
            print("  No email provided. Arcade tools require authentication.")
            sys.exit(1)

    # Handle --slack mode: resolve human user for bot token
    if caps["slack"]:
        slack_token = os.getenv("SLACK_BOT_TOKEN", "")
        print("  Slack:  connected (direct token via --slack)", flush=True)
        target = await _resolve_human_user(slack_token)
        print(f"  User:   {target['display_name']} ({target['user_id']})", flush=True)
    elif caps["arcade"]:
        print("  Slack:  available via Arcade OAuth", flush=True)
    else:
        print("  Slack:  not connected (use --slack flag, or set ARCADE_API_KEY)")
    if caps["openai"]:
        print("  Images: enabled")
    else:
        print("  Images: disabled (set OPENAI_API_KEY for image generation)")
    print()

    # Connect to Arcade-deployed tools via SDK
    print("  Connecting to Arcade tools...", flush=True)
    client = AsyncArcade()
    tools = await get_arcade_tools(client, toolkits=["MeowMe"])
    print(f"  Loaded {len(tools)} tools from Arcade", flush=True)
    print()
    print("  Try: 'Meow me!' or 'Give me a cat fact'")
    print("  Type 'exit' or 'quit' to leave.")
    print()

    # Build system prompt with capabilities
    instructions = SYSTEM_PROMPT + _build_capability_prompt(caps)

    # If --slack mode with a resolved user, inform the LLM
    if _slack_config.get("target_user_id"):
        instructions += (
            f"\nSLACK USER CONTEXT: The user's Slack ID is {_slack_config['target_user_id']} "
            f"(display name: {_slack_config.get('target_display_name', 'unknown')}). "
            f"Use this when tools need a user_id parameter."
        )

    agent = Agent(
        name="Meow Art",
        instructions=instructions,
        model="gpt-4o-mini",
        tools=tools,
    )

    history = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            print("Bye!")
            break

        history.append({"role": "user", "content": user_input})

        try:
            print("  >> Thinking...", flush=True)
            result = await Runner.run(
                starting_agent=agent,
                input=history,
                context={"user_id": user_id},
            )
            history = result.to_input_list()
            print(f"\nMeow Art: {result.final_output}\n")
        except Exception as e:
            print(f"\nError: {e}\n")


# ---------------------------------------------------------------------------
# Scripted demo mode (no API keys needed)
# ---------------------------------------------------------------------------

DEMO_FACTS = [
    "A group of cats is called a clowder.",
    "Cats can rotate their ears 180 degrees.",
    "Cats sleep 12-16 hours per day.",
    "A cat's purr vibrates at 25-150 Hz.",
    "Cats have over 20 vocalizations.",
    "Cats can't taste sweetness.",
    "A cat can jump up to 6 times its length.",
]


def run_demo() -> None:
    """Run the scripted demo showing all agent scenarios."""
    print()
    print("=" * 60)
    print("  MEOW ART - Scripted Demo Mode")
    print("  (No API keys needed - simulates full agent behavior)")
    print("=" * 60)

    # Scenario 1: "Meow me!" (one-shot)
    print("\n" + "-" * 60)
    print("SCENARIO 1: 'Meow me!' (one-shot pipeline)")
    print("-" * 60)
    print()
    print("  User: Meow me!")
    print()
    print("  Agent: Calling MeowMe_MeowMe()...")
    print("    [1] auth.test -> user_id: U012ABC")
    print("    [2] conversations.open -> dm_channel: D0123456789")
    print(f"    [3] Fetched fact: \"{DEMO_FACTS[0]}\"")
    print("    [4] users.info -> avatar: https://avatars.slack-edge.com/.../image_512.png")
    print("    [5] MeowMe_GenerateCatImage(fact, avatar, style='cartoon')")
    print("        -> Prompt: 'Transform this photo into a whimsical cartoon...'")
    print("        -> Generated 1024x1024 PNG image")
    print("    [6] files.getUploadURLExternal -> upload_url")
    print("    [7] Uploaded image bytes")
    print("    [8] files.completeUploadExternal -> shared to DM")
    print()
    print(f"  Agent: Done! I've sent you a cat-themed image with the fact:")
    print(f"         \"{DEMO_FACTS[0]}\"")
    print("         Check your Slack DMs!")

    # Scenario 2: Browse facts, text only
    print("\n" + "-" * 60)
    print("SCENARIO 2: Browse facts -> text only -> #general")
    print("-" * 60)
    print()
    print("  User: Give me 3 cat facts")
    print()
    print("  Agent: Calling MeowMe_GetCatFact(count=3)...")
    print("    Here are 3 cat facts:")
    for i, fact in enumerate(DEMO_FACTS[1:4], 1):
        print(f"      {i}. \"{fact}\"")
    print("    Want to keep one, or get more?")
    print()
    print("  User: I like #2")
    print()
    print(f"  Agent: Great pick! \"{DEMO_FACTS[2]}\"")
    print("    Want me to generate an image with it, or just the text?")
    print()
    print("  User: Just text")
    print()
    print("  Agent: Where should I send it?")
    print()
    print("  User: #general")
    print()
    print("  Agent: Calling MeowMe_SendCatFact(channel='#general')...")
    print(f"    Sent to #general: :cat: *Meow Fact:*")
    print(f"    {DEMO_FACTS[2]}")

    # Scenario 3: Image pipeline
    print("\n" + "-" * 60)
    print("SCENARIO 3: Cat art -> image pipeline -> #random")
    print("-" * 60)
    print()
    print("  User: Make me cat art")
    print()
    print("  Agent: Calling MeowMe_GetCatFact()...")
    print(f"    Got: \"{DEMO_FACTS[4]}\"")
    print("    Good fact, or want a different one?")
    print()
    print("  User: That's good")
    print()
    print("  Agent: Calling MeowMe_GetUserAvatar()...")
    print("    -> avatar_url: https://avatars.slack-edge.com/.../image_512.png")
    print(f"  Agent: Calling MeowMe_GenerateCatImage(fact, avatar, style='cartoon')...")
    print("    -> Generated 1024x1024 cat-themed art!")
    print("    Where should I send it?")
    print()
    print("  User: #random")
    print()
    print("  Agent: Calling MeowMe_SendCatImage(channel='#random')...")
    print("    Uploaded image to #random with caption:")
    print(f"    :cat: *Meow Fact:* {DEMO_FACTS[4]}")

    # Scenario 4: Browse only
    print("\n" + "-" * 60)
    print("SCENARIO 4: Browse facts only (no send)")
    print("-" * 60)
    print()
    print("  User: Tell me a cat fact")
    print()
    print("  Agent: Calling MeowMe_GetCatFact()...")
    print(f"    \"{DEMO_FACTS[5]}\"")
    print("    Want another, an image, or send it somewhere?")
    print()
    print("  User: Another")
    print()
    print("  Agent: Calling MeowMe_GetCatFact()...")
    print(f"    \"{DEMO_FACTS[6]}\"")
    print("    Want another, an image, or send it somewhere?")
    print()
    print("  User: That's all, thanks")
    print()
    print("  Agent: Happy to help! Come back anytime for more cat facts.")

    # Summary
    print("\n" + "=" * 60)
    print("  DEMO COMPLETE")
    print()
    print("  Tools demonstrated (called via Arcade SDK):")
    print("    - MeowMe_GetCatFact      (fetch random facts)")
    print("    - MeowMe_GetUserAvatar   (Slack avatar retrieval)")
    print("    - MeowMe_GenerateCatImage (OpenAI gpt-image-1 art)")
    print("    - MeowMe_SendCatFact      (text to Slack channel)")
    print("    - MeowMe_SendCatImage     (image upload to Slack)")
    print("    - MeowMe_SaveImageLocally (save image to local file)")
    print("    - MeowMe_MeowMe          (one-shot full pipeline)")
    print()
    print("  To run the live agent:")
    print("    OPENAI_API_KEY=sk-... ARCADE_API_KEY=arc-... uv run python -m meow_me")
    print()
    print("  To run as MCP server:")
    print("    uv run arcade mcp -p meow_me stdio")
    print("=" * 60)
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="meow_me",
        description="Meow Art: cat-fact-inspired art agent powered by OpenAI + Arcade",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run scripted demo mode (no API keys needed)",
    )
    parser.add_argument(
        "--slack",
        action="store_true",
        help="Use SLACK_BOT_TOKEN from .env (enables all Slack features incl. image upload)",
    )

    args = parser.parse_args()

    if args.demo:
        run_demo()
    elif os.getenv("OPENAI_API_KEY"):
        if args.slack:
            if not os.getenv("SLACK_BOT_TOKEN"):
                print("\nError: --slack flag requires SLACK_BOT_TOKEN in .env")
                print("See .env.example for setup instructions.\n")
                sys.exit(1)
            _slack_config["use_direct_token"] = True
        if not os.getenv("ARCADE_API_KEY"):
            print("\nError: ARCADE_API_KEY is required to connect to Arcade-deployed tools.")
            print("Sign up at https://api.arcade.dev and set ARCADE_API_KEY in .env\n")
            sys.exit(1)
        asyncio.run(run_agent())
    else:
        print()
        print("OPENAI_API_KEY not set. Options:")
        print()
        print("  1. Set OPENAI_API_KEY + ARCADE_API_KEY and run the interactive agent:")
        print("     uv run python -m meow_me")
        print()
        print("  2. With Slack bot token (all features incl. image upload):")
        print("     uv run python -m meow_me --slack")
        print()
        print("  3. Run the scripted demo (no keys needed):")
        print("     uv run python -m meow_me --demo")
        print()
        print("  4. Run as MCP server (for Claude Desktop / Cursor):")
        print("     uv run arcade mcp -p meow_me stdio")
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()
