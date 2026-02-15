# Meow Art (meow_me)

**Cat-fact-inspired art agent** - an MCP server + LLM-powered CLI agent built with [Arcade.dev](https://arcade.dev) and [OpenAI](https://openai.com).

Meow Art fetches random cat facts, retrieves your Slack avatar, generates stylized cat-themed images using OpenAI's gpt-image-1, and sends the results to Slack. It exposes 6 MCP tools, includes an interactive agent powered by the OpenAI Agents SDK (with 7 tool wrappers including local save + ASCII preview), and supports both direct Slack tokens and Arcade OAuth for authentication.

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
# Create .env with your keys
cat > .env <<EOF
OPENAI_API_KEY=sk-...
# Option A: Direct Slack token (supports all features including image upload)
SLACK_BOT_TOKEN=xoxb-...
# Option B: Arcade OAuth (text messaging + avatars, no image upload)
ARCADE_API_KEY=arc-...
ARCADE_USER_ID=your-email@example.com
EOF

# Start the agent
uv run python -m meow_me
```

The agent uses `gpt-4o-mini` to reason about which tools to call based on your input. Try:
- `"Meow me!"` - one-shot: fetches fact + avatar + generates image + DMs you
- `"Give me 3 cat facts"` - browse facts, pick one, choose image or text, choose where to send
- `"Make me cat art"` - fetches a fact, generates cat-themed art from your avatar

The agent shows real-time progress indicators as tools execute and displays ASCII art previews of generated images directly in the terminal.

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

101 tests, all passing:

```
tests/test_facts.py   - 11 tests (parsing, count clamping, API URL, empty responses)
tests/test_slack.py   - 22 tests (formatting, auth.test, conversations.open, message sending, file upload)
tests/test_avatar.py  - 13 tests (auth.test, users.info, avatar extraction, fallbacks)
tests/test_image.py   - 14 tests (prompt composition, OpenAI mock, fallback placeholder, styles)
tests/test_agent.py   - 33 tests (system prompt, demo mode, tool wrappers, auth, Arcade OAuth, capabilities)
tests/test_evals.py   -  8 tests (end-to-end workflows, edge cases, formatting)
```

---

## Architecture

```
                        ┌─────────────────────────┐
                        │     Interactive Agent    │
                        │  (OpenAI Agents SDK)     │
                        │  gpt-4o-mini + 7 tools   │
                        └────────────┬────────────┘
                                     │ @function_tool wrappers
                                     │ (includes save_image_locally,
                                     │  agent-only tool)
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
│        (runs in asyncio.to_thread to avoid blocking)                   │
│                                                                        │
│  meow_me               (Slack OAuth: chat:write, im:write,             │
│    ├── auth.test → get user ID                files:write, users:read) │
│    ├── conversations.open → open DM                                    │
│    ├── MeowFacts → fetch a fact                                        │
│    ├── users.info → get avatar URL                                     │
│    ├── gpt-image-1 → generate cat art (fallback: text-only)            │
│    └── files.upload → DM image + caption                               │
│        (or save locally + text DM when files:write unavailable)        │
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

Auth Resolution (CLI Agent):
  1. Cached token (session-level)
  2. SLACK_BOT_TOKEN env var (full access including file uploads)
  3. Arcade OAuth (ARCADE_API_KEY → browser auth → token)
     ⚠ Arcade's Slack provider does NOT support files:write
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

### Progress & ASCII Preview

The agent prints real-time progress during tool execution (`>> Fetching cat fact...`, `>> Generating cartoon cat art...`) and renders ASCII art previews of generated images in the terminal using Pillow.

---

## MCP Tools (6 server + 1 agent-only)

| Tool | Auth | Description |
|------|------|-------------|
| `get_cat_fact` | None | Fetch 1-5 random cat facts from MeowFacts API |
| `get_user_avatar` | Slack OAuth (`users:read`) | Get your Slack avatar URL and display name |
| `generate_cat_image` | None (uses `OPENAI_API_KEY`) | Transform avatar into cat-themed art via gpt-image-1 |
| `meow_me` | Slack OAuth (full scopes) | One-shot: fact + avatar + image + DM self |
| `send_cat_fact` | Slack OAuth (`chat:write`) | Send 1-3 text cat facts to a channel |
| `send_cat_image` | Slack OAuth (`chat:write`, `files:write`) | Upload image + caption to a channel |
| `save_image_locally` | None (agent-only) | Save generated image to local file + show ASCII preview |

---

## Environment Variables

```bash
# .env (gitignored)
OPENAI_API_KEY=sk-...          # For agent LLM (gpt-4o-mini) AND image generation (gpt-image-1)
SLACK_BOT_TOKEN=xoxb-...       # Optional: direct Slack auth (supports ALL features incl. image upload)
ARCADE_API_KEY=arc-...         # Optional: Arcade platform auth (Slack OAuth, text + avatars only)
ARCADE_USER_ID=you@email.com   # Optional: skip the email prompt during Arcade OAuth
```

### Slack Auth in Agent Mode

The CLI agent resolves Slack tokens using a 3-tier strategy:

1. **Session cache** - reuses token within a session
2. **`SLACK_BOT_TOKEN` env var** - direct token, supports all features including `files:write` for image uploads
3. **Arcade OAuth** (`ARCADE_API_KEY`) - opens browser for Slack authorization. Supports `chat:write`, `im:write`, `users:read`. **Does NOT support `files:write`** (Arcade platform limitation), so image uploads to Slack are unavailable; images are saved locally + shown as ASCII art instead.

The MCP server tools get Slack tokens via Arcade's built-in OAuth provider at runtime.

---

## Known Limitations

- **Arcade OAuth + image upload**: Arcade's Slack provider does not support the `files:write` scope. When using Arcade OAuth (instead of a direct `SLACK_BOT_TOKEN`), the `send_cat_image` tool and image upload in `meow_me` are unavailable. The agent falls back to: generate image → save locally → show ASCII preview → send text-only fact to DM.
- **Image generation time**: `gpt-image-1` takes 30-60 seconds per image. The agent shows a progress indicator while generating.
- **`send_cat_image` requires `SLACK_BOT_TOKEN`**: Since Arcade OAuth can't grant `files:write`, image uploads to Slack channels only work with a direct bot token.

---

## Project Structure

```
meow_me/
├── src/meow_me/
│   ├── server.py          # MCPApp entry point (registers all tool modules)
│   ├── agent.py           # LLM agent (OpenAI Agents SDK) + demo mode + ASCII preview
│   ├── __main__.py        # python -m meow_me support
│   └── tools/
│       ├── facts.py       # MeowFacts API (get_cat_fact, no auth)
│       ├── avatar.py      # Slack avatar retrieval (get_user_avatar)
│       ├── image.py       # OpenAI image generation (generate_cat_image)
│       └── slack.py       # Slack messaging + file upload (meow_me, send_cat_fact, send_cat_image)
├── tests/
│   ├── test_facts.py      # Fact parsing & fetching (11 tests)
│   ├── test_avatar.py     # Slack avatar extraction & fallbacks (13 tests)
│   ├── test_image.py      # Prompt composition, OpenAI mock, placeholder fallback (14 tests)
│   ├── test_slack.py      # Message sending, file upload flow (22 tests)
│   ├── test_agent.py      # System prompt, demo, tool wrappers, auth, Arcade OAuth (33 tests)
│   └── test_evals.py      # End-to-end evaluation scenarios (8 tests)
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

| Scope | Used by | Arcade OAuth? |
|-------|---------|---------------|
| `chat:write` | `meow_me`, `send_cat_fact`, `send_cat_image` - post messages | Supported |
| `im:write` | `meow_me` - open DM conversation via `conversations.open` | Supported |
| `users:read` | `meow_me`, `get_user_avatar` - retrieve avatar via `users.info` | Supported |
| `files:write` | `meow_me`, `send_cat_image` - upload images via file upload API | **NOT supported** by Arcade |

> **Note:** `files:write` is only available with a direct `SLACK_BOT_TOKEN`. When using Arcade OAuth, image uploads are replaced with local save + ASCII preview.

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent framework | OpenAI Agents SDK | Arcade's recommended framework; clean function_tool integration |
| Agent LLM | gpt-4o-mini | Fast, cheap, sufficient for tool routing |
| Image generation | OpenAI gpt-image-1 (`images.edit`) | Same API key as agent LLM; accepts avatar as input image |
| Async image gen | `asyncio.to_thread()` | gpt-image-1 uses sync `OpenAI()` client; thread avoids blocking the event loop |
| Image delivery | Slack file upload API (`getUploadURLExternal` flow) | Modern Slack file sharing; `files.upload` is deprecated |
| Arcade OAuth fallback | Text DM + local save + ASCII preview | Graceful degradation when `files:write` is unavailable |
| ASCII art preview | Pillow grayscale → character mapping | Immediate visual feedback in terminal without needing an image viewer |
| Progress output | `_progress()` helper with `flush=True` | `Runner.run()` is non-streaming; progress prints keep the user informed |
| 3-tier Slack auth | Cache → env var → Arcade OAuth | Maximum flexibility; works with or without Arcade platform |
| Fallback behavior | Text-only when OPENAI_API_KEY missing | Full pipeline still completes; placeholder PNG for `generate_cat_image` |
| Avatar input | BytesIO with `.name = "avatar.png"` | OpenAI SDK needs named file-like object for MIME type detection |
| External API | MeowFacts | Free, no auth, structured JSON |
| Slack auth (MCP) | Arcade built-in Slack provider | Zero setup - demonstrates Arcade's core OAuth value |
| Count limits | get_cat_fact: 1-5, send_cat_fact: 1-3 | Prevent spam while allowing batch sends |

---

## Built With

- [Arcade MCP Server](https://docs.arcade.dev) - MCP server framework with OAuth
- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) - Agent framework with function tools
- [OpenAI gpt-image-1](https://platform.openai.com/docs/guides/image-generation) - Image-to-image generation
- [Pillow](https://python-pillow.org/) - Image processing (ASCII art preview)
- [MeowFacts API](https://meowfacts.herokuapp.com/) - Random cat facts
- [httpx](https://www.python-httpx.org/) - Async HTTP client
- [uv](https://docs.astral.sh/uv/) - Python package management
- [Claude Code](https://claude.com/claude-code) - AI-assisted development (Claude Opus 4.6)
