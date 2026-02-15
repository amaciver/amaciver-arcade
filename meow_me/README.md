# Meow Art (meow_me)

**Cat-fact-inspired art agent** - an MCP server + LLM-powered CLI agent built with [Arcade.dev](https://arcade.dev) and [OpenAI](https://openai.com).

Meow Art fetches random cat facts, retrieves your Slack avatar, generates stylized cat-themed images using OpenAI's gpt-image-1, and sends the results to Slack. It exposes 6 MCP tools and includes an interactive agent powered by the OpenAI Agents SDK.

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

### 2. Try the demo (no API keys needed)

```bash
uv run python -m meow_me --demo
```

Walks through 4 scripted scenarios showing exactly what the agent does: one-shot "meow me", fact browsing with text delivery, image pipeline, and browse-only mode.

### 3. Run the interactive agent

```bash
# Add your OpenAI API key to .env
echo "OPENAI_API_KEY=sk-..." > .env

# Start the agent
uv run python -m meow_me
```

The agent uses `gpt-4o-mini` to reason about which tools to call based on your input. Try:
- `"Meow me!"` - one-shot: fetches fact + avatar + generates image + DMs you
- `"Give me 3 cat facts"` - browse facts, pick one, choose image or text, choose where to send
- `"Make me cat art"` - fetches a fact, generates cat-themed art from your avatar

### 4. Connect as MCP server

**Option A: Claude Desktop**

Add to your Claude Desktop config (`%APPDATA%\Claude\claude_desktop_config.json`):

> **Windows Store install?** Config is at `%LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude\claude_desktop_config.json`

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

> **Note:** On Windows, use the absolute path to `uv.exe` if it isn't on the system PATH.

**Option B: HTTP transport (Cursor, VS Code, etc.)**

```bash
uv run arcade mcp -p meow_me http --debug
```

Server starts at `http://127.0.0.1:8000`.

### 5. Run tests

```bash
uv run pytest -v
```

83 tests, all passing:

```
tests/test_facts.py   - 11 tests (parsing, count clamping, API URL, empty responses)
tests/test_slack.py   - 22 tests (formatting, auth.test, conversations.open, message sending, file upload)
tests/test_avatar.py  - 13 tests (auth.test, users.info, avatar extraction, fallbacks)
tests/test_image.py   - 14 tests (prompt composition, OpenAI mock, fallback placeholder, styles)
tests/test_agent.py   - 15 tests (system prompt, demo mode, tool wrappers, auth checks)
tests/test_evals.py   -  8 tests (end-to-end workflows, edge cases, formatting)
```

---

## Architecture

```
                        ┌─────────────────────────┐
                        │     Interactive Agent    │
                        │  (OpenAI Agents SDK)     │
                        │  gpt-4o-mini + 6 tools   │
                        └────────────┬────────────┘
                                     │ @function_tool wrappers
┌────────────────────────────────────▼────────────────────────────────────┐
│                        Meow Art MCP Server                             │
│                    (arcade-mcp-server, 6 tools)                        │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  get_cat_fact          (no auth)                                       │
│    └── MeowFacts API → random cat facts                                │
│                                                                        │
│  get_user_avatar       (Slack OAuth: users:read)                       │
│    ├── auth.test → get your user ID                                    │
│    └── users.info → avatar URL + display name                          │
│                                                                        │
│  generate_cat_image    (no auth, uses OPENAI_API_KEY env)              │
│    ├── Download avatar from URL                                        │
│    ├── Compose style prompt + cat fact                                  │
│    └── OpenAI gpt-image-1 images.edit → 1024x1024 PNG                  │
│                                                                        │
│  meow_me               (Slack OAuth: chat:write, im:write,             │
│    ├── auth.test → get user ID                files:write, users:read) │
│    ├── conversations.open → open DM                                    │
│    ├── MeowFacts → fetch a fact                                        │
│    ├── users.info → get avatar URL                                     │
│    ├── gpt-image-1 → generate cat art (fallback: text-only)            │
│    └── files.upload → DM image + caption                               │
│                                                                        │
│  send_cat_fact         (Slack OAuth: chat:write)                       │
│    ├── MeowFacts → fetch N facts                                       │
│    └── chat.postMessage → send to channel                              │
│                                                                        │
│  send_cat_image        (Slack OAuth: chat:write, files:write)          │
│    ├── files.getUploadURLExternal → get upload URL                     │
│    ├── Upload image bytes                                              │
│    └── files.completeUploadExternal → share to channel                 │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
                                     │ MCP Protocol (STDIO or HTTP)
                        ┌────────────▼────────────┐
                        │       MCP Clients        │
                        │ Claude Desktop | Cursor  │
                        └─────────────────────────┘
```

---

## Agent Interaction Model

The agent has two modes of behavior:

### 1. "Meow me" (one-shot, no prompts)

Standalone trigger fires the full pipeline automatically:

```
User: "Meow me!"
Agent: → meow_me()
       Internally: fact + avatar + image gen + DM self. No questions asked.
```

Any modifier breaks it into interactive mode: `"Meow me to #random"`, `"Meow me in watercolor"`, `"Meow me 3 facts"`.

### 2. Everything else (two-phase interactive flow)

```
Phase 1 — Fact Selection
  Agent fetches fact(s), presents them, lets you rotate until happy.

Phase 2 — Delivery Options
  Agent asks: "With image or just text?"
  → Text only: asks where to send → send_cat_fact(channel)
  → With image: get_user_avatar → generate_cat_image → asks where → send_cat_image(channel)
  → Display only: shows fact/image in chat, no Slack send
```

---

## MCP Tools

| Tool | Auth | Description |
|------|------|-------------|
| `get_cat_fact` | None | Fetch 1-5 random cat facts from MeowFacts API |
| `get_user_avatar` | Slack OAuth (`users:read`) | Get your Slack avatar URL and display name |
| `generate_cat_image` | None (uses `OPENAI_API_KEY`) | Transform avatar into cat-themed art via gpt-image-1 |
| `meow_me` | Slack OAuth (full scopes) | One-shot: fact + avatar + image + DM self |
| `send_cat_fact` | Slack OAuth (`chat:write`) | Send 1-3 text cat facts to a channel |
| `send_cat_image` | Slack OAuth (`chat:write`, `files:write`) | Upload image + caption to a channel |

---

## Environment Variables

```bash
# .env (gitignored)
OPENAI_API_KEY=sk-...          # For agent LLM (gpt-4o-mini) AND image generation (gpt-image-1)
SLACK_BOT_TOKEN=xoxb-...       # Optional: direct Slack auth for agent mode
ARCADE_API_KEY=arc-...         # Optional: for Arcade platform (Slack OAuth routing)
```

The MCP server tools get Slack tokens via Arcade's OAuth. The standalone agent checks `SLACK_BOT_TOKEN` for direct Slack access.

---

## Project Structure

```
meow_me/
├── src/meow_me/
│   ├── server.py          # MCPApp entry point (registers all tool modules)
│   ├── agent.py           # LLM agent (OpenAI Agents SDK) + demo mode
│   ├── __main__.py        # python -m meow_me support
│   └── tools/
│       ├── facts.py       # MeowFacts API (get_cat_fact, no auth)
│       ├── avatar.py      # Slack avatar retrieval (get_user_avatar)
│       ├── image.py       # OpenAI image generation (generate_cat_image)
│       └── slack.py       # Slack messaging + file upload (meow_me, send_cat_fact, send_cat_image)
├── tests/
│   ├── test_facts.py      # Fact parsing & fetching
│   ├── test_avatar.py     # Slack avatar extraction & fallbacks
│   ├── test_image.py      # Prompt composition, OpenAI mock, placeholder fallback
│   ├── test_slack.py      # Message sending, file upload flow
│   ├── test_agent.py      # System prompt, demo mode, tool wrappers
│   └── test_evals.py      # End-to-end evaluation scenarios
├── pyproject.toml
└── .env                   # API keys (gitignored)
```

---

## Slack OAuth Setup

The MCP server tools use Arcade's **built-in Slack OAuth provider** - no manual app creation needed.

1. Run `arcade login` to authenticate with the Arcade platform
2. When an MCP client calls a Slack tool, Arcade handles the OAuth flow
3. The user authenticates via browser, and Arcade injects the token at runtime

### Required Slack Scopes

| Scope | Used by |
|-------|---------|
| `chat:write` | `meow_me`, `send_cat_fact`, `send_cat_image` - post messages |
| `im:write` | `meow_me` - open DM conversation via `conversations.open` |
| `files:write` | `meow_me`, `send_cat_image` - upload images via file upload API |
| `users:read` | `meow_me`, `get_user_avatar` - retrieve avatar via `users.info` |

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent framework | OpenAI Agents SDK | Arcade's recommended framework; clean function_tool integration |
| Agent LLM | gpt-4o-mini | Fast, cheap, sufficient for tool routing |
| Image generation | OpenAI gpt-image-1 (`images.edit`) | Same API key as agent LLM; accepts avatar as input image |
| Image delivery | Slack file upload API (`getUploadURLExternal` flow) | Modern Slack file sharing; `files.upload` is deprecated |
| Fallback behavior | Text-only when OPENAI_API_KEY missing | Full pipeline still completes; placeholder PNG for `generate_cat_image` |
| Avatar input | BytesIO with `.name = "avatar.png"` | OpenAI SDK needs named file-like object for MIME type detection |
| External API | MeowFacts | Free, no auth, structured JSON |
| Slack auth | Arcade built-in Slack provider | Zero setup - demonstrates Arcade's core OAuth value |
| Count limits | get_cat_fact: 1-5, send_cat_fact: 1-3 | Prevent spam while allowing batch sends |

---

## Built With

- [Arcade MCP Server](https://docs.arcade.dev) - MCP server framework with OAuth
- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) - Agent framework with function tools
- [OpenAI gpt-image-1](https://platform.openai.com/docs/guides/image-generation) - Image-to-image generation
- [MeowFacts API](https://meowfacts.herokuapp.com/) - Random cat facts
- [httpx](https://www.python-httpx.org/) - Async HTTP client
- [uv](https://docs.astral.sh/uv/) - Python package management
- [Claude Code](https://claude.com/claude-code) - AI-assisted development (Claude Opus 4.6)
