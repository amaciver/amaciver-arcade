#!/usr/bin/env python3
"""Meow Art agent - LLM-powered CLI that creates cat-fact-inspired art.

This agent connects to Arcade-deployed MCP tools remotely via the Arcade SDK.
The LLM (gpt-4o-mini) decides which tools to call based on user input —
there is no hardcoded orchestration logic in the agent itself.

Usage:
    uv run python -m meow_me              # Interactive agent (requires OPENAI_API_KEY + ARCADE_API_KEY)
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
- MeowMe_GetCatFact(count)                                    — Fetch 1-5 random cat facts (always works)
- MeowMe_GetUserAvatar()                                      — Get your Slack avatar URL (needs Slack auth)
- MeowMe_StartCatImageGeneration(cat_fact, avatar_url, style)  — Start async image generation (returns job_id)
- MeowMe_CheckImageStatus(job_id)                             — Poll image generation status (~30-60s total)
- MeowMe_SendCatFact(channel, count)                          — Send text fact(s) to a Slack channel (needs Slack auth)
- MeowMe_SendCatImage(cat_fact, channel, image_base64)        — Upload image to Slack (needs files:write)
- MeowMe_MeowMe()                                             — One-shot: fact + image attempt + DM self (needs Slack auth)

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
      - With image → MeowMe_GetUserAvatar → MeowMe_StartCatImageGeneration →
        poll MeowMe_CheckImageStatus every ~10 seconds until 'complete' or 'failed' →
        MeowMe_SendCatImage(channel)
      - Display only (no send) → just show the fact/image in chat

3. If the user says "another" / "new one" / "different fact" → call MeowMe_GetCatFact again.

4. If the user specifies a channel upfront, remember it but still ask about image vs text.

5. If the user just says "tell me a fact" with no send intent, display the fact
   and offer: another fact, an image, or send it somewhere.

6. IMAGE GENERATION IS ASYNC: After calling MeowMe_StartCatImageGeneration,
   you MUST poll MeowMe_CheckImageStatus with the returned job_id every ~10 seconds.
   Tell the user "Generating your cat art... this takes about 30-60 seconds."
   When status is 'complete', call MeowMe_SendCatImage with image_base64='__last__'.

HANDLING TOOL RESPONSES:
- If MeowMe_MeowMe returns image_sent=false, tell the user: "I sent you a text
  cat fact! Image features aren't available right now."
- If MeowMe_CheckImageStatus returns status='failed', explain the error and offer
  to send a text-only fact instead.
- If MeowMe_SendCatImage returns image_uploaded=false, explain that the image
  couldn't be uploaded and a text fact was sent instead.
- Never tell the user about internal details like "cloud secrets" or "SLACK_BOT_TOKEN".
  Instead say "image features aren't available right now" or "I'll send you a text
  version instead."

Be concise, fun, and cat-themed in your responses. Use cat emoji sparingly.
If a tool fails because of missing auth, explain what's needed and suggest alternatives.
"""


# ---------------------------------------------------------------------------
# Capability detection (drives system prompt adaptation)
# ---------------------------------------------------------------------------


def _detect_capabilities() -> dict:
    """Detect which API capabilities are available based on env vars."""
    return {
        "arcade": bool(os.getenv("ARCADE_API_KEY")),
    }


def _build_capability_prompt(caps: dict) -> str:
    """Build an addendum to the system prompt based on available capabilities."""
    lines = ["\nCURRENT SESSION CAPABILITIES:"]
    if caps.get("arcade"):
        lines.append("- Arcade: CONNECTED — text tools are available (GetCatFact, SendCatFact, MeowMe)")
        lines.append("- Slack: READY via Arcade OAuth")
        lines.append("- Image generation: NOT AVAILABLE in this mode")
        lines.append("  -> Image generation requires MCP server mode (long-running local process).")
        lines.append("  -> Arcade Cloud uses ephemeral workers, so the async start/poll pattern cannot work.")
        lines.append("  -> For image generation, use Claude Desktop or Cursor with the MCP server.")
        lines.append("  -> Do NOT call MeowMe_StartCatImageGeneration or MeowMe_CheckImageStatus.")
        lines.append("  -> MeowMe_MeowMe will still work but will fall back to text-only DMs.")
    else:
        lines.append("- Arcade: NOT CONNECTED (set ARCADE_API_KEY)")
        lines.append("  -> No tools are available. Can only chat.")
    lines.append("")
    lines.append("Use the tools that are available. If the user asks for image generation,")
    lines.append("explain that it requires MCP server mode (Claude Desktop or Cursor) and offer text alternatives.")
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

    if caps["arcade"]:
        print("  Arcade: connected (text tools available)", flush=True)
        print("  Slack:  available via Arcade OAuth", flush=True)
        print("  Images: MCP server mode only (use Claude Desktop/Cursor)", flush=True)
    else:
        print("  Arcade: not connected (set ARCADE_API_KEY)")
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
    print("    [5] Generating cat-themed art from avatar...")
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

    # Scenario 3: Image pipeline (async start/poll)
    print("\n" + "-" * 60)
    print("SCENARIO 3: Cat art -> async image pipeline -> #random")
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
    print(f"  Agent: Calling MeowMe_StartCatImageGeneration(fact, avatar, style='cartoon')...")
    print("    -> job_id: a1b2c3d4, status: generating")
    print("    Generating your cat art... this takes about 30-60 seconds.")
    print()
    print("  Agent: Calling MeowMe_CheckImageStatus(job_id='a1b2c3d4')...")
    print("    -> status: generating (poll again in ~10s)")
    print()
    print("  Agent: Calling MeowMe_CheckImageStatus(job_id='a1b2c3d4')...")
    print("    -> status: generating (poll again in ~10s)")
    print()
    print("  Agent: Calling MeowMe_CheckImageStatus(job_id='a1b2c3d4')...")
    print("    -> status: complete! 1024x1024 cat-themed art ready")
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
    print("    - MeowMe_GetCatFact            (fetch random facts)")
    print("    - MeowMe_GetUserAvatar         (Slack avatar retrieval)")
    print("    - MeowMe_StartCatImageGeneration (async image generation)")
    print("    - MeowMe_CheckImageStatus      (poll generation status)")
    print("    - MeowMe_SendCatFact           (text to Slack channel)")
    print("    - MeowMe_SendCatImage          (image upload to Slack)")
    print("    - MeowMe_MeowMe               (one-shot full pipeline)")
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

    args = parser.parse_args()

    if args.demo:
        run_demo()
    elif os.getenv("OPENAI_API_KEY"):
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
        print("  2. Run the scripted demo (no keys needed):")
        print("     uv run python -m meow_me --demo")
        print()
        print("  3. Run as MCP server (for Claude Desktop / Cursor):")
        print("     uv run arcade mcp -p meow_me stdio")
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()
