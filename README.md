# Arcade.dev Interview Projects

Two MCP server toolkits built with [Arcade.dev](https://arcade.dev), demonstrating API integration, OAuth authentication, and agentic workflows.

## Projects

### [Sushi Scout](sushi_scout/) - Find the Cheapest Tuna Roll

MCP server (7 tools) that searches for real sushi restaurants via Google Places API, generates price-calibrated menus, ranks tuna rolls by price, and simulates ordering. Demonstrates `requires_secrets` for API keys, dual auth (API key + custom OAuth2 provider), and comprehensive testing (46 tests).

```bash
cd sushi_scout && uv sync --all-extras && uv run python -m sushi_scout --demo
```

### [Meow Me](meow_me/) - Slack Yourself a Cat Fact

MCP server (3 tools) that fetches random cat facts from the MeowFacts API and sends them to you via Slack DM. Demonstrates Arcade's built-in Slack OAuth provider (`requires_auth=Slack`), making it a clean example of the full OAuth flow.

```bash
cd meow_me && uv sync --all-extras && uv run python -m meow_me --demo
```

## Quick Start

Each project is self-contained with its own `pyproject.toml`, tests, and README. Pick either one:

```bash
git clone https://github.com/amaciver/amaciver-arcade.git
cd amaciver-arcade

# Try Sushi Scout
cd sushi_scout && uv sync --all-extras && uv run pytest -v

# Try Meow Me
cd meow_me && uv sync --all-extras && uv run pytest -v
```

## Built With

- [Arcade MCP Server](https://docs.arcade.dev) - MCP server framework
- [Claude Code](https://claude.com/claude-code) - AI-assisted development (Claude Opus 4.6)
