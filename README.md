# Arcade.dev Interview Project

An MCP server toolkit and LLM-powered agent built with [Arcade.dev](https://arcade.dev), demonstrating OAuth integration, image generation, Slack API workflows, and agentic tool orchestration.

## The Project: [Meow Art (meow_me)](meow_me/)

MCP server (6 tools, 138 tests) + interactive CLI agent that fetches random cat facts, retrieves your Slack avatar, generates stylized cat-themed art via OpenAI's gpt-image-1, and sends the results to Slack. Supports both Arcade's built-in Slack OAuth and direct bot tokens.

See [meow_me/README.md](meow_me/README.md) for full documentation, architecture, and setup instructions.

## Quick Start

```bash
git clone https://github.com/amaciver/amaciver-arcade.git
cd amaciver-arcade/meow_me
uv sync --all-extras

# Try the demo (no API keys needed)
uv run python -m meow_me --demo

# Run all 138 tests
uv run pytest -v

# Start as MCP server (for Claude Desktop / Cursor)
uv run arcade mcp -p meow_me stdio
```

## Using the Agent

The CLI agent provides an interactive way to use the tools with natural language:

```bash
# Default: Arcade OAuth
# - Text + avatars work
# - Images saved locally (shows file path + ASCII preview)
# - Text-only DMs to Slack
uv run python -m meow_me

# With direct bot token: full Slack integration
# - Requires SLACK_BOT_TOKEN in .env and --slack flag
# - Uploads images directly to Slack channels
uv run python -m meow_me --slack
```

See [meow_me/README.md](meow_me/README.md) for full agent documentation, auth modes, and Slack setup.

## Development Journey

This project was built across multiple sessions, each exploring different aspects of the Arcade platform. The learnings from each phase directly shaped the next.

### Phase 1: Sushi Scout (archived)

Started with [Sushi Scout](https://github.com/amaciver/amaciver-arcade-archive) -- an MCP server that finds the cheapest tuna sushi roll nearby using real Google Places API data, synthetic price-calibrated menus, and simulated ordering (7 tools, 46 tests).

Sushi Scout was the learning ground for Arcade's core patterns:
- How `@tool` registration works (module-level decorators, not closures)
- How `requires_secrets` and `requires_auth` differ
- Dual auth: API key default + custom `OAuth2` provider for Google Places
- MCP protocol mechanics (STDIO vs HTTP transport, JSON-RPC framing)
- Claude Desktop integration and Windows-specific gotchas

The code is preserved in the [archive repo](https://github.com/amaciver/amaciver-arcade-archive) with full development notes.

### Phase 2: Meow Art

Armed with Arcade platform knowledge from Sushi Scout, built a more ambitious project combining:
- **Arcade's built-in Slack OAuth** (vs custom provider in Sushi Scout)
- **OpenAI image generation** (gpt-image-1 image-to-image with avatar input)
- **MCP ImageContent** (monkey-patched arcade-mcp-server to return image previews)
- **An interactive LLM agent** (OpenAI Agents SDK with 7 tool wrappers, progress output, ASCII art preview)
- **Dual Slack auth modes**: `--slack` flag for bot token (full Slack integration incl. channel image uploads) or default Arcade OAuth (text + avatars, saves images locally with file path output)

## Key Learnings: Arcade Platform

Insights discovered across both projects that would be useful for anyone building with Arcade:

| Learning | Detail |
|----------|--------|
| **Tool registration** | Use module-level `@tool` decorator. The `@app.tool` pattern inside `register_tools()` closures is NOT discoverable by `arcade mcp`. |
| **`arcade mcp` arg order** | `-p package` comes BEFORE transport: `arcade mcp -p meow_me stdio` |
| **OAuth scope limits** | Arcade's built-in providers support specific scopes only. Google: no `cloud-platform`. Slack: no `files:write`. Design for graceful degradation when scopes are unavailable. |
| **Custom OAuth2 providers** | For unsupported scopes, register a custom provider: `OAuth2(id="my-provider", scopes=[...])`. Use `id` parameter (not `provider_id`). |
| **STDIO for OAuth** | Tools with `requires_auth` can only run via STDIO transport, not HTTP. |
| **`__init__.py` is the real entry point** | `arcade mcp` discovers tools by importing the package. It never executes `server.py`. Put `load_dotenv()` and patches in `__init__.py`. |
| **ImageContent** | `arcade-mcp-server`'s `convert_to_mcp_content()` only returns `TextContent`. Monkey-patch to emit `ImageContent` for image-returning tools. |
| **Windows encoding** | Set `PYTHONIOENCODING=utf-8` for subprocess calls. Arcade's output contains Unicode that Windows cp1252 can't render. |
| **Claude Desktop paths** | Windows Store install uses `%LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude\` for config. Use `--directory` flag in uv args. |
| **Slack file upload API** | `files.completeUploadExternal` requires a channel ID (not name) and bot membership. `chat.postMessage` resolves names automatically -- this asymmetry is poorly documented. |

## Built With

- [Arcade MCP Server](https://docs.arcade.dev) - MCP server framework with OAuth
- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) - Agent framework with function tools
- [OpenAI gpt-image-1](https://platform.openai.com/docs/guides/image-generation) - Image-to-image generation
- [Claude Code](https://claude.com/claude-code) - AI-assisted development (Claude Opus 4.6)
