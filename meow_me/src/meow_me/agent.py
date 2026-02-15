#!/usr/bin/env python3
"""Meow Art agent - LLM-powered CLI that creates cat-fact-inspired art.

Usage:
    uv run python -m meow_me              # Interactive agent (requires OPENAI_API_KEY)
    uv run python -m meow_me --demo       # Scripted demo (no API keys needed)

For MCP server mode (used by Claude Desktop, Cursor, etc.):
    uv run arcade mcp -p meow_me stdio    # STDIO transport
    uv run arcade mcp -p meow_me http     # HTTP transport
"""

import argparse
import asyncio
import json
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

TOOLS AVAILABLE:
- get_cat_fact(count)         — Fetch 1-5 random cat facts (always works)
- get_user_avatar()           — Get your Slack avatar URL (needs Slack auth)
- generate_cat_image(fact, avatar_url, style) — Create stylized art from avatar + fact (needs OPENAI_API_KEY)
- send_cat_fact(channel, count) — Send text fact(s) to a Slack channel (needs Slack auth)
- send_cat_image(image_base64, cat_fact, channel) — Upload image + caption to Slack (needs Slack auth)
- save_image_locally(image_base64, cat_fact) — Save generated image to local file (no auth needed)
- meow_me()                   — One-shot: fact + avatar + image + DM self (needs Slack auth + OPENAI_API_KEY)

ROUTING RULES:

1. "Meow me" (standalone, no modifiers) → call meow_me() immediately.
   No questions asked. It handles everything internally and DMs the user.
   - "Meow me" ✓  "Meow me!" ✓  "Hit me with a meow" ✓
   - IMPORTANT: If the user adds ANY modifier (a channel, a style, a count,
     a specific fact), it is NOT a meow_me call. Treat it as interactive.
   - "Meow me to #random" → INTERACTIVE (channel specified)
   - "Meow me in watercolor" → INTERACTIVE (style specified)
   - "Meow me 3 facts" → INTERACTIVE (count specified)

2. Everything else → follow this two-phase flow:
   a. FACT PHASE: Call get_cat_fact. Present the fact(s). Let the user rotate
      (call get_cat_fact again) until they're happy.
   b. DELIVERY PHASE: Ask "with image or just text?"
      - Text only → ask where to send → send_cat_fact(channel)
      - With image → get_user_avatar → generate_cat_image → ask where → send_cat_image(channel)
      - Display only (no send) → just show the fact/image in chat

3. If the user says "another" / "new one" / "different fact" → call get_cat_fact again.

4. If the user specifies a channel upfront, remember it but still ask about image vs text.

5. If the user just says "tell me a fact" with no send intent, display the fact
   and offer: another fact, an image, or send it somewhere.

6. When Slack is NOT available:
   - "Meow me" → get_cat_fact → generate_cat_image → save_image_locally (display path)
   - Skip send_cat_fact, send_cat_image, meow_me, get_user_avatar entirely.
   - For generate_cat_image without an avatar, use a placeholder URL like
     "https://placecats.com/512/512" as the avatar_url.

7. After generate_cat_image, always call save_image_locally() to save the image
   to a local file so the user can view it. It automatically uses the last generated image.

Be concise, fun, and cat-themed in your responses. Use cat emoji sparingly.
If a tool fails because of missing auth, explain what's needed and suggest alternatives.
"""

# ---------------------------------------------------------------------------
# Tool wrappers (bridge our MCP tool implementations → openai-agents)
# ---------------------------------------------------------------------------


_last_generated_image: dict = {}  # Stash for the latest generated image base64


def _build_tools():
    """Build function_tool wrappers around our MCP tool implementations."""
    from agents import function_tool

    from meow_me.tools.facts import get_cat_fact as _get_cat_fact
    from meow_me.tools.image import (
        generate_cat_image as _generate_cat_image,
    )

    @function_tool
    async def get_cat_fact(count: int = 1) -> str:
        """Fetch 1-5 random cat facts from the MeowFacts API. No auth required.

        Args:
            count: Number of cat facts to fetch (1-5).
        """
        result = await _get_cat_fact(count=count)
        return json.dumps(result)

    @function_tool
    async def generate_cat_image(
        cat_fact: str,
        avatar_url: str,
        style: str = "cartoon",
    ) -> str:
        """Generate a cat-themed image by transforming a user's avatar.

        Downloads the avatar, composes a prompt from the cat fact and style,
        and uses OpenAI's gpt-image-1 to create stylized cat art.
        Returns base64-encoded PNG image data.
        Falls back to a placeholder if OPENAI_API_KEY is not set.

        Args:
            cat_fact: The cat fact to incorporate into the image.
            avatar_url: URL of the user's avatar image.
            style: Art style: cartoon, watercolor, anime, or photorealistic.
        """
        result = await _generate_cat_image(
            cat_fact=cat_fact, avatar_url=avatar_url, style=style
        )
        # Stash the full base64 for save_image_locally / send_cat_image
        _last_generated_image["base64"] = result.get("image_base64", "")
        _last_generated_image["cat_fact"] = cat_fact
        # Don't dump the full base64 to the LLM — just summarize
        summary = {
            "style": result["style"],
            "cat_fact": result["cat_fact"],
            "fallback": result.get("fallback", False),
            "image_size_bytes": len(result.get("image_base64", "")),
            "hint": "Use save_image_locally() or send_cat_image() with image_base64='__last__' to use this image.",
        }
        return json.dumps(summary)

    @function_tool
    async def get_user_avatar() -> str:
        """Get the authenticated user's Slack avatar URL and display name.

        Requires Slack auth (SLACK_BOT_TOKEN env var or Arcade platform).
        """
        token = os.getenv("SLACK_BOT_TOKEN", "")
        if not token:
            return json.dumps({
                "error": "Slack auth required. Set SLACK_BOT_TOKEN or use Arcade platform.",
            })
        from meow_me.tools.avatar import (
            _get_own_user_id,
            _get_user_info,
            _extract_avatar_url,
            _extract_display_name,
        )

        user_id = await _get_own_user_id(token)
        user_info = await _get_user_info(token, user_id)
        return json.dumps({
            "user_id": user_id,
            "display_name": _extract_display_name(user_info),
            "avatar_url": _extract_avatar_url(user_info),
        })

    @function_tool
    async def send_cat_fact(channel: str, count: int = 1) -> str:
        """Send text-only cat fact(s) to a Slack channel.

        Requires Slack auth (SLACK_BOT_TOKEN env var or Arcade platform).

        Args:
            channel: Slack channel ID or name (e.g. #general).
            count: Number of cat facts to send (1-3).
        """
        token = os.getenv("SLACK_BOT_TOKEN", "")
        if not token:
            return json.dumps({
                "error": "Slack auth required. Set SLACK_BOT_TOKEN or use Arcade platform.",
            })
        from meow_me.tools.slack import (
            _fetch_one_fact,
            _format_cat_fact_message,
            _send_slack_message,
        )

        count = max(1, min(count, 3))
        results = []
        for _ in range(count):
            fact = await _fetch_one_fact()
            message = _format_cat_fact_message(fact)
            result = await _send_slack_message(token, channel, message)
            result["fact"] = fact
            results.append(result)
        return json.dumps({"facts_sent": len(results), "channel": channel, "results": results})

    @function_tool
    async def send_cat_image(channel: str, image_base64: str = "__last__", cat_fact: str = "") -> str:
        """Upload a cat-themed image with a fact caption to a Slack channel.

        Requires Slack auth (SLACK_BOT_TOKEN env var or Arcade platform).
        Automatically uses the last generated image if image_base64 is '__last__'.

        Args:
            channel: Slack channel ID or name.
            image_base64: Base64-encoded PNG data, or '__last__' to use the most recent generated image.
            cat_fact: The cat fact caption.
        """
        token = os.getenv("SLACK_BOT_TOKEN", "")
        if not token:
            return json.dumps({
                "error": "Slack auth required. Set SLACK_BOT_TOKEN or use Arcade platform.",
            })

        if image_base64 == "__last__" and _last_generated_image.get("base64"):
            image_base64 = _last_generated_image["base64"]
            cat_fact = cat_fact or _last_generated_image.get("cat_fact", "")
        elif image_base64 == "__last__":
            return json.dumps({"error": "No image generated yet. Call generate_cat_image first."})

        import base64 as b64

        from meow_me.tools.slack import (
            _format_cat_fact_message,
            _get_upload_url,
            _upload_file_bytes,
            _complete_upload,
        )

        image_bytes = b64.b64decode(image_base64)
        upload_info = await _get_upload_url(token, "meow_art.png", len(image_bytes))
        await _upload_file_bytes(upload_info["upload_url"], image_bytes)
        caption = _format_cat_fact_message(cat_fact)
        await _complete_upload(token, upload_info["file_id"], channel, caption)
        return json.dumps({
            "success": True, "channel": channel, "file_id": upload_info["file_id"],
        })

    @function_tool
    async def save_image_locally(image_base64: str = "__last__", cat_fact: str = "") -> str:
        """Save a generated cat image to a local file and display the path.

        Use this when Slack is not available but the user wants to see a generated image.
        Call this after generate_cat_image - it automatically uses the last generated image.

        Args:
            image_base64: Base64-encoded PNG data, or '__last__' to use the most recent generated image.
            cat_fact: The cat fact used to generate the image.
        """
        import base64 as b64
        import tempfile
        import pathlib

        if image_base64 == "__last__" and _last_generated_image.get("base64"):
            image_base64 = _last_generated_image["base64"]
            cat_fact = cat_fact or _last_generated_image.get("cat_fact", "")
        elif image_base64 == "__last__":
            return json.dumps({"error": "No image generated yet. Call generate_cat_image first."})

        image_bytes = b64.b64decode(image_base64)
        output_dir = pathlib.Path(tempfile.gettempdir()) / "meow_art"
        output_dir.mkdir(exist_ok=True)

        # Use a short hash to avoid filename collisions
        import hashlib
        name_hash = hashlib.md5(cat_fact.encode()).hexdigest()[:8]
        filepath = output_dir / f"meow_art_{name_hash}.png"
        filepath.write_bytes(image_bytes)

        return json.dumps({
            "saved": True,
            "path": str(filepath),
            "size_bytes": len(image_bytes),
            "cat_fact": cat_fact,
        })

    @function_tool
    async def meow_me() -> str:
        """One-shot: fetch cat fact + avatar + generate image + DM self.

        Requires Slack auth and OPENAI_API_KEY. Falls back to text-only if
        image generation fails.
        """
        token = os.getenv("SLACK_BOT_TOKEN", "")
        if not token:
            return json.dumps({
                "error": "Slack auth required. Set SLACK_BOT_TOKEN or use Arcade platform.",
            })
        from meow_me.tools.slack import (
            _get_own_user_id,
            _open_dm_channel,
            _fetch_one_fact,
            _format_cat_fact_message,
            _send_slack_message,
            _get_upload_url,
            _upload_file_bytes,
            _complete_upload,
        )
        from meow_me.tools.avatar import _get_user_info, _extract_avatar_url
        from meow_me.tools.image import _download_avatar, _generate_image_openai, _compose_prompt

        user_id = await _get_own_user_id(token)
        dm_channel = await _open_dm_channel(token, user_id)
        fact = await _fetch_one_fact()

        image_generated = False
        image_sent = False

        if os.getenv("OPENAI_API_KEY"):
            try:
                user_info = await _get_user_info(token, user_id)
                avatar_url = _extract_avatar_url(user_info)
                avatar_bytes = await _download_avatar(avatar_url)
                prompt = _compose_prompt(fact, "cartoon")
                image_b64 = _generate_image_openai(avatar_bytes, prompt)
                image_generated = True

                import base64 as b64
                image_bytes = b64.b64decode(image_b64)
                upload_info = await _get_upload_url(token, "meow_art.png", len(image_bytes))
                await _upload_file_bytes(upload_info["upload_url"], image_bytes)
                caption = _format_cat_fact_message(fact)
                await _complete_upload(token, upload_info["file_id"], dm_channel, caption)
                image_sent = True
            except Exception:
                pass

        if not image_sent:
            message = _format_cat_fact_message(fact)
            await _send_slack_message(token, dm_channel, message)

        return json.dumps({
            "success": True, "fact": fact,
            "image_generated": image_generated, "image_sent": image_sent,
            "recipient": user_id, "channel": dm_channel,
        })

    return [get_cat_fact, generate_cat_image, get_user_avatar,
            send_cat_fact, send_cat_image, save_image_locally, meow_me]


# ---------------------------------------------------------------------------
# Interactive agent loop
# ---------------------------------------------------------------------------


def _detect_capabilities() -> dict:
    """Detect which API capabilities are available based on env vars."""
    return {
        "openai": bool(os.getenv("OPENAI_API_KEY")),
        "slack": bool(os.getenv("SLACK_BOT_TOKEN")),
    }


def _build_capability_prompt(caps: dict) -> str:
    """Build an addendum to the system prompt based on available capabilities."""
    lines = ["\nCURRENT SESSION CAPABILITIES:"]
    if caps["slack"]:
        lines.append("- Slack: CONNECTED (SLACK_BOT_TOKEN set)")
    else:
        lines.append("- Slack: NOT AVAILABLE (no SLACK_BOT_TOKEN)")
        lines.append("  -> Do NOT call meow_me, send_cat_fact, send_cat_image, or get_user_avatar.")
        lines.append("  -> Instead: display facts in chat, generate images and save locally.")
    if caps["openai"]:
        lines.append("- Image generation: AVAILABLE (OPENAI_API_KEY set)")
    else:
        lines.append("- Image generation: NOT AVAILABLE (no OPENAI_API_KEY)")
        lines.append("  -> Do NOT call generate_cat_image. Stick to text facts.")
    lines.append("")
    lines.append("Adapt your behavior to what's available. Be upfront about limitations.")
    return "\n".join(lines)


async def run_agent() -> None:
    """Run the interactive LLM-powered agent."""
    from agents import Agent, Runner

    caps = _detect_capabilities()
    tools = _build_tools()

    instructions = SYSTEM_PROMPT + _build_capability_prompt(caps)

    agent = Agent(
        name="Meow Art",
        instructions=instructions,
        model="gpt-4o-mini",
        tools=tools,
    )

    print()
    print("=" * 55)
    print("  MEOW ART - Cat Fact Art Generator")
    print("  Powered by OpenAI + Arcade.dev")
    print("=" * 55)
    print()
    if caps["slack"]:
        print("  Slack:  connected")
    else:
        print("  Slack:  not connected (set SLACK_BOT_TOKEN for Slack features)")
    if caps["openai"]:
        print("  Images: enabled")
    else:
        print("  Images: disabled (set OPENAI_API_KEY for image generation)")
    print()
    print("  Try: 'Meow me!' or 'Give me a cat fact'")
    print("  Type 'exit' or 'quit' to leave.")
    print()

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
            result = await Runner.run(starting_agent=agent, input=history)
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
    print("  Agent: Calling meow_me()...")
    print("    [1] auth.test -> user_id: U012ABC")
    print("    [2] conversations.open -> dm_channel: D0123456789")
    print(f"    [3] Fetched fact: \"{DEMO_FACTS[0]}\"")
    print("    [4] users.info -> avatar: https://avatars.slack-edge.com/.../image_512.png")
    print("    [5] generate_cat_image(fact, avatar, style='cartoon')")
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
    print("  Agent: Calling get_cat_fact(count=3)...")
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
    print("  Agent: Calling send_cat_fact(channel='#general')...")
    print(f"    Sent to #general: :cat: *Meow Fact:*")
    print(f"    {DEMO_FACTS[2]}")

    # Scenario 3: Image pipeline
    print("\n" + "-" * 60)
    print("SCENARIO 3: Cat art -> image pipeline -> #random")
    print("-" * 60)
    print()
    print("  User: Make me cat art")
    print()
    print("  Agent: Calling get_cat_fact()...")
    print(f"    Got: \"{DEMO_FACTS[4]}\"")
    print("    Good fact, or want a different one?")
    print()
    print("  User: That's good")
    print()
    print("  Agent: Calling get_user_avatar()...")
    print("    -> avatar_url: https://avatars.slack-edge.com/.../image_512.png")
    print(f"  Agent: Calling generate_cat_image(fact, avatar, style='cartoon')...")
    print("    -> Generated 1024x1024 cat-themed art!")
    print("    Where should I send it?")
    print()
    print("  User: #random")
    print()
    print("  Agent: Calling send_cat_image(channel='#random')...")
    print("    Uploaded image to #random with caption:")
    print(f"    :cat: *Meow Fact:* {DEMO_FACTS[4]}")

    # Scenario 4: Browse only
    print("\n" + "-" * 60)
    print("SCENARIO 4: Browse facts only (no send)")
    print("-" * 60)
    print()
    print("  User: Tell me a cat fact")
    print()
    print("  Agent: Calling get_cat_fact()...")
    print(f"    \"{DEMO_FACTS[5]}\"")
    print("    Want another, an image, or send it somewhere?")
    print()
    print("  User: Another")
    print()
    print("  Agent: Calling get_cat_fact()...")
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
    print("  Tools demonstrated:")
    print("    - get_cat_fact      (fetch random facts)")
    print("    - get_user_avatar   (Slack avatar retrieval)")
    print("    - generate_cat_image (OpenAI gpt-image-1 art)")
    print("    - send_cat_fact      (text to Slack channel)")
    print("    - send_cat_image     (image upload to Slack)")
    print("    - save_image_locally (save image to local file)")
    print("    - meow_me            (one-shot full pipeline)")
    print()
    print("  To run the live agent:")
    print("    OPENAI_API_KEY=sk-... uv run python -m meow_me")
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
        asyncio.run(run_agent())
    else:
        print()
        print("OPENAI_API_KEY not set. Options:")
        print()
        print("  1. Set OPENAI_API_KEY and run the interactive agent:")
        print("     OPENAI_API_KEY=sk-... uv run python -m meow_me")
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
