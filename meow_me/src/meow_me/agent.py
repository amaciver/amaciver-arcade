#!/usr/bin/env python3
"""CLI demo agent for meow_me - fetches and displays cat facts.

Usage:
    uv run python -m meow_me --demo       # Print cat facts (no Slack needed)
    uv run python -m meow_me --help       # Show options

For MCP server mode (used by Claude Desktop, Cursor, etc.):
    uv run arcade mcp -p meow_me stdio    # STDIO transport
    uv run arcade mcp -p meow_me http     # HTTP transport
"""

import argparse
import asyncio
import sys

import httpx

MEOWFACTS_URL = "https://meowfacts.herokuapp.com/"


async def fetch_facts(count: int = 1) -> list[str]:
    """Fetch cat facts from MeowFacts API."""
    async with httpx.AsyncClient() as client:
        response = await client.get(MEOWFACTS_URL, params={"count": count})
        response.raise_for_status()
        data = response.json()
    return data.get("data", [])


def print_banner() -> None:
    """Print the meow_me banner."""
    print()
    print("=" * 50)
    print("  MEOW ME - Random Cat Facts")
    print("  Powered by MeowFacts API + Arcade.dev")
    print("=" * 50)
    print()


async def run_demo() -> None:
    """Run the demo: fetch and display cat facts."""
    print_banner()

    print("Fetching 3 random cat facts...\n")
    facts = await fetch_facts(count=3)

    for i, fact in enumerate(facts, 1):
        print(f"  {i}. {fact}")
        print()

    print("-" * 50)
    print()
    print("To send facts via Slack DM, connect to an MCP client:")
    print()
    print("  Claude Desktop / Cursor:")
    print("    uv run arcade mcp -p meow_me stdio")
    print()
    print("  HTTP transport:")
    print("    uv run arcade mcp -p meow_me http --debug")
    print()
    print("Then ask: 'Meow me!' or 'Send a cat fact to #general'")
    print()


def main() -> None:
    """Entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="meow_me",
        description="Slack yourself a random cat fact via MCP",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run demo mode (fetch and display cat facts, no Slack needed)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=3,
        help="Number of facts to fetch in demo mode (default: 3)",
    )

    args = parser.parse_args()

    if args.demo:
        asyncio.run(run_demo())
    else:
        parser.print_help()
        print("\nTip: Run with --demo to see cat facts, or use as MCP server:")
        print("  uv run arcade mcp -p meow_me stdio")
        sys.exit(0)


if __name__ == "__main__":
    main()
