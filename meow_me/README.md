# Meow Me

**Slack yourself a random cat fact** - an MCP server built with [Arcade.dev](https://arcade.dev).

Meow Me fetches random cat facts from the [MeowFacts API](https://meowfacts.herokuapp.com/) and can send them to you via Slack DM using Arcade's built-in Slack OAuth. All 3 tools are exposed via MCP for use with Claude Desktop, Cursor, or any MCP client.

---

## Quick Start

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- [Arcade CLI](https://docs.arcade.dev) (`uv tool install arcade-mcp`)

### 1. Clone and install

```bash
git clone https://github.com/amaciver/amaciver-arcade.git
cd amaciver-arcade/meow_me
uv sync --all-extras
```

### 2. Try the demo (no Slack needed)

```bash
uv run python -m meow_me --demo
```

This fetches 3 random cat facts from the MeowFacts API and prints them to the terminal. No authentication required.

### 3. Connect to a real MCP client

**Option A: Claude Desktop**

Add to your Claude Desktop config (`%APPDATA%\Claude\claude_desktop_config.json`):

> **Windows Store install?** The config is at `%LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "meow-me": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/amaciver-arcade/meow_me", "arcade", "mcp", "-p", "meow_me", "stdio"],
      "env": {
        "PYTHONIOENCODING": "utf-8"
      }
    }
  }
}
```

Restart Claude Desktop, then ask: *"Meow me!"* or *"Send a cat fact to #random"*

> **Note:** On Windows, use the absolute path to `uv.exe` (e.g. `C:\\Users\\you\\...\\uv.exe`) if `uv` isn't on the system PATH.

**Option B: HTTP transport (Cursor, VS Code, etc.)**

```bash
uv run arcade mcp -p meow_me http --debug
```

Server starts at `http://127.0.0.1:8000`. Connect your MCP client to that URL.

### 4. Run tests

```bash
uv run pytest -v
```

31 tests, all passing:

```
tests/test_facts.py  - 11 tests (parsing, count clamping, API URL, empty responses)
tests/test_slack.py  - 12 tests (formatting, auth, message sending, payloads)
tests/test_evals.py  -  8 tests (end-to-end workflows, edge cases, formatting)
```

---

## Architecture

```
┌──────────────────────────────────────────┐
│              MCP Clients                  │
│  Claude Desktop | Cursor | VS Code | CLI │
└──────────────────┬───────────────────────┘
                   │ MCP Protocol (STDIO or HTTP)
┌──────────────────▼───────────────────────┐
│         Meow Me MCP Server                │
│  (arcade-mcp-server, 3 tools)             │
├──────────────────────────────────────────┤
│                                           │
│  get_cat_fact        (no auth)            │
│    └── MeowFacts API → random cat facts   │
│                                           │
│  meow_me             (Slack OAuth)        │
│    ├── auth.test → get your user ID       │
│    ├── MeowFacts → fetch a fact           │
│    └── chat.postMessage → DM yourself     │
│                                           │
│  send_cat_fact       (Slack OAuth)        │
│    ├── MeowFacts → fetch N facts          │
│    └── chat.postMessage → send to channel │
│                                           │
└──────────────────────────────────────────┘
```

---

## MCP Tools

| Tool | Auth | Description |
|------|------|-------------|
| `get_cat_fact` | None | Fetch 1-5 random cat facts from MeowFacts API |
| `meow_me` | Slack OAuth (`chat:write`, `users:read`) | Fetch a cat fact and DM it to yourself |
| `send_cat_fact` | Slack OAuth (`chat:write`) | Send 1-3 cat facts to a specific channel |

---

## Project Structure

```
meow_me/
├── src/meow_me/
│   ├── server.py          # MCPApp entry point
│   ├── agent.py           # CLI demo agent (--demo mode)
│   ├── __main__.py        # python -m meow_me support
│   └── tools/
│       ├── facts.py       # MeowFacts API (1 tool, no auth)
│       └── slack.py       # Slack OAuth tools (2 tools)
├── tests/
│   ├── conftest.py        # Shared fixtures (API response samples)
│   ├── test_facts.py      # Fact parsing & fetching tests
│   ├── test_slack.py      # Slack formatting & API tests
│   └── test_evals.py      # End-to-end evaluation scenarios
├── pyproject.toml
└── .env.example
```

---

## Slack OAuth Setup

The Slack tools use Arcade's **built-in Slack OAuth provider** - no manual app creation needed.

1. Run `arcade login` to authenticate with the Arcade platform
2. When an MCP client calls `meow_me` or `send_cat_fact`, Arcade handles the Slack OAuth flow
3. The user authenticates via browser, and Arcade injects the token at runtime

### Required Slack Scopes

| Scope | Used by |
|-------|---------|
| `chat:write` | `meow_me`, `send_cat_fact` - post messages to channels/DMs |
| `users:read` | `meow_me` - look up your own user ID for self-DM |

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| External API | MeowFacts | Free, no auth, returns structured JSON |
| Slack auth | Arcade built-in Slack provider | Zero setup - demonstrates Arcade's core OAuth value |
| Self-DM pattern | `auth.test` → `chat.postMessage(user_id)` | Posting to a user ID opens a DM automatically |
| Count limits | get_cat_fact: 1-5, send_cat_fact: 1-3 | Prevent spam while allowing batch sends |

---

## Built With

- [Arcade MCP Server](https://docs.arcade.dev) - MCP server framework with OAuth
- [MeowFacts API](https://meowfacts.herokuapp.com/) - Random cat facts
- [httpx](https://www.python-httpx.org/) - Async HTTP client
- [uv](https://docs.astral.sh/uv/) - Python package management
- [Claude Code](https://claude.com/claude-code) - AI-assisted development (Claude Opus 4.6)
