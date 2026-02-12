# Arcade.dev Interview Projects

Two MCP server toolkits built with [Arcade.dev](https://arcade.dev), demonstrating API integration, OAuth authentication, and agentic workflows.

## Projects

### [Sushi Scout](sushi_scout/) - Find the Cheapest Tuna Roll

MCP server (7 tools, 46 tests) that searches for real sushi restaurants via Google Places API, generates price-calibrated menus, ranks tuna rolls by price, and simulates ordering. Demonstrates `requires_secrets` for API keys and dual auth (API key + custom OAuth2 provider).

### [Meow Me](meow_me/) - Slack Yourself a Cat Fact

MCP server (3 tools, 34 tests) that fetches random cat facts from the MeowFacts API and sends them to you via Slack DM. Demonstrates Arcade's built-in Slack OAuth provider (`requires_auth=Slack`).

## Quick Start

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- [Arcade CLI](https://docs.arcade.dev) (`uv tool install arcade-mcp`)

### Clone and try the demos

The `--demo` commands run standalone in the terminal - no MCP client or API keys needed.

```bash
git clone https://github.com/amaciver/amaciver-arcade.git
cd amaciver-arcade

# Sushi Scout demo - shows restaurant search + menu + ranking
cd sushi_scout && uv sync --all-extras && uv run python -m sushi_scout --demo

# Meow Me demo - fetches and prints random cat facts
cd ../meow_me && uv sync --all-extras && uv run python -m meow_me --demo
```

### Run all tests

```bash
# Sushi Scout (46 tests)
cd sushi_scout && uv run pytest -v

# Meow Me (34 tests)
cd ../meow_me && uv run pytest -v
```

### Connect to Claude Desktop

To use these as MCP servers with Claude Desktop (or Cursor, VS Code, etc.), see the setup instructions in each project's README:

- [Sushi Scout - Claude Desktop setup](sushi_scout/README.md#3-connect-to-a-real-mcp-client)
- [Meow Me - Claude Desktop setup](meow_me/README.md#3-connect-to-a-real-mcp-client)

## Built With

- [Arcade MCP Server](https://docs.arcade.dev) - MCP server framework with OAuth
- [Claude Code](https://claude.com/claude-code) - AI-assisted development (Claude Opus 4.6)
