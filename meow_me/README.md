# Meow Art (meow_me)

**Cat-fact-inspired art agent** - an MCP server + LLM-powered CLI agent built with [Arcade.dev](https://arcade.dev) and [OpenAI](https://openai.com).

Meow Art fetches random cat facts, retrieves your Slack avatar, generates stylized cat-themed images using OpenAI's gpt-image-1, and sends the results to Slack. It includes 7 MCP tools and a thin interactive CLI agent powered by the OpenAI Agents SDK.

The project supports two runtime modes:

- **MCP Server Mode** (Claude Desktop, Cursor) — Full features including image generation. Tools run as a local long-running process with your own API keys.
- **CLI Agent Mode** — Text-only features (cat facts, Slack messaging). Tools run on Arcade Cloud. Image generation is not available because Arcade Cloud uses ephemeral workers that can't support the async start/poll pattern.

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

### 2. Run tests (no API keys needed)

```bash
# Run all unit tests
uv run pytest -v
```

All tests use mocks — no API keys or network access required. Tests cover:

```
tests/test_facts.py   - Fact parsing & fetching (11 tests)
tests/test_slack.py   - Messaging, file upload, channel resolution, token helpers (43 tests)
tests/test_avatar.py  - Slack avatar extraction & fallbacks (13 tests)
tests/test_image.py   - Prompts, validation, thumbnail, async start/poll (31 tests)
tests/test_agent.py   - System prompt, demo, capabilities, Arcade SDK integration (30 tests)
tests/test_evals.py   - Evaluation scenario structure (8 tests)
```

### 3. Try the demo (no API keys needed)

```bash
uv run python -m meow_me --demo
```

Walks through 4 scripted scenarios showing exactly what the agent does: one-shot "meow me", fact browsing with text delivery, image pipeline, and browse-only mode.

### 4. Run evaluations (requires OPENAI_API_KEY)

```bash
export OPENAI_API_KEY=sk-...
uv run arcade evals evals/
```

12 evaluation cases across 2 suites test whether AI models correctly select and invoke tools. See [evals/README.md](evals/README.md) for details.

### 5. Set up your secrets

Create a `.env` file with your API keys:

```bash
cat > .env <<EOF
OPENAI_API_KEY=sk-...          # Required: agent LLM (gpt-4o-mini) + image generation (gpt-image-1)
ARCADE_API_KEY=arc-...         # Required for CLI agent mode
ARCADE_USER_ID=you@example.com # Optional: skip email prompt during Arcade OAuth
EOF
```

### 6. Connect as MCP server (full features including image generation)

This is the recommended mode for full functionality. The MCP server runs as a local long-running process, so the async image generation pipeline works correctly.

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
        "PYTHONIOENCODING": "utf-8",
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

Restart Claude Desktop, then ask: *"Meow me!"* or *"Make me cat art"*

> **Note:** On Windows, use the absolute path to `uv.exe` if it isn't on the system PATH. Image generation takes 30-60 seconds — the async start/poll pattern lets Claude check progress periodically.

**Option B: HTTP transport (Cursor, VS Code, etc.)**

```bash
uv run arcade mcp -p meow_me http --debug
```

Server starts at `http://127.0.0.1:8000`.

### 7. Run the CLI agent (text features only)

```bash
uv run python -m meow_me
```

The CLI agent connects to Arcade Cloud for tool execution. Text tools work (cat facts, Slack messaging), but image generation is not available in this mode — Arcade Cloud's ephemeral workers can't support the background threads needed for the async image pipeline.

![Agent demo (Arcade OAuth)](examples/meow-me-cli-example.gif)
*CLI agent: text-only cat facts and Slack messaging via Arcade Cloud*

Try:
- `"Meow me!"` - sends a text cat fact to your Slack DMs
- `"Give me 3 cat facts"` - browse facts, choose where to send
- `"Send a cat fact to #random"` - sends a fact to a Slack channel

For image generation, use MCP server mode (step 6).

### 8. Deploy your own tools to Arcade Cloud (optional)

If you want to deploy the tools to your own Arcade Cloud account:

```bash
# Deploy tools (uses server.py as entry point)
uv run arcade deploy -e src/meow_me/server.py

# Set cloud secrets for image generation and Slack file uploads
arcade secret set OPENAI_API_KEY sk-...
arcade secret set SLACK_BOT_TOKEN xoxb-...

# Verify tools are deployed
arcade tools list
```

Cloud secrets are injected into the tool execution context at runtime via `context.get_secret()`. Tools that depend on optional secrets (like `meow_me`) gracefully fall back to text-only when secrets aren't configured.

---

## Example Output

Here are some images generated by the image generation tools, transforming a Slack avatar into cat-themed art:

| | |
|---|---|
| ![Orange Cats](examples/orange_cats.png) | ![Siamese Cats](examples/siamese_cats.png) |
| *"80% of orange cats are male"* | *"The color of the points in Siamese cats is heat related. Cool areas are darker."* |
| ![Sleeping Cats](examples/sleeping_cats.png) | |
| *"Cats sleep 16 to 18 hours per day"* | |

Each image is generated by `gpt-image-1` using your Slack avatar as the input image, combined with a cat fact and an art style (cartoon, watercolor, anime, or photorealistic).

---

## Architecture

```
┌─────────────────────────────────┐
│       Interactive Agent          │
│    (OpenAI Agents SDK)           │
│    gpt-4o-mini                   │
│                                  │
│  ┌─ NO tool logic here ──────┐  │
│  │ Agent is a thin LLM client│  │
│  │ LLM decides which tools   │  │
│  │ to call based on user     │  │
│  │ input + system prompt     │  │
│  └───────────────────────────┘  │
└───────────────┬─────────────────┘
                │ Arcade SDK (arcadepy + agents-arcade)
                │ get_arcade_tools() → remote tool execution
                ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    Arcade Cloud (deployed tools)                       │
│                    arcade deploy -e server.py                          │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  MeowMe_GetCatFact       (no auth)                                    │
│    └── MeowFacts API → random cat facts                                │
│                                                                        │
│  MeowMe_GetUserAvatar    (Slack OAuth: users:read)                    │
│    ├── auth.test → get your user ID                                    │
│    └── users.info → avatar URL + display name                          │
│                                                                        │
│  MeowMe_StartCatImageGeneration (requires_secrets: OPENAI_API_KEY)    │
│    ├── Download avatar from URL                                        │
│    ├── Compose style prompt + cat fact                                  │
│    ├── Launch async gpt-image-1 images.edit → 1024x1024 PNG            │
│    └── Return task_id for polling                                      │
│                                                                        │
│  MeowMe_CheckImageStatus  (no auth)                                   │
│    ├── Poll task_id for completion                                      │
│    ├── When done: stash full-res PNG, compress JPEG thumbnail          │
│    └── Return status + MCP ImageContent preview when ready             │
│                                                                        │
│  MeowMe_MeowMe          (Slack OAuth: chat:write, im:write,           │
│    ├── auth.test → get user ID   users:read + OPENAI_API_KEY)         │
│    ├── conversations.open → open DM                                    │
│    ├── MeowFacts → fetch a fact                                        │
│    ├── users.info → get avatar URL                                     │
│    ├── gpt-image-1 → generate cat art (fallback: text-only)            │
│    └── files.upload → DM image + caption                               │
│                                                                        │
│  MeowMe_SendCatFact     (Slack OAuth: chat:write)                     │
│    ├── MeowFacts → fetch N facts                                       │
│    └── chat.postMessage → send to channel                              │
│                                                                        │
│  MeowMe_SendCatImage    (Slack OAuth: chat:write, files:write)        │
│    ├── Resolve channel name → ID                                       │
│    ├── files.getUploadURLExternal → get upload URL                     │
│    └── files.completeUploadExternal → share to channel                 │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
                                     │ Also accessible via MCP Protocol
                        ┌────────────▼────────────┐
                        │       MCP Clients        │
                        │ Claude Desktop | Cursor  │
                        └─────────────────────────┘

Key Separation:
  • Agent (agent.py) has ZERO imports from meow_me.tools.*
  • All tool calls go through AsyncArcade → Arcade Cloud → deployed MCP server
  • Auth handled entirely by Arcade platform (OAuth flow managed server-side)
  • Dual-token pattern: OAuth for identity (users:read), bot token secret for uploads (files:write)
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
  → With image: get_user_avatar → start_cat_image_generation → poll check_image_status → send_cat_image(channel)
  → Display only: shows fact/image in chat, no Slack send
```

### Agent-Tool Separation

The agent (`agent.py`) contains **zero tool logic** — it's a thin LLM client that:
1. Connects to Arcade-deployed tools via `get_arcade_tools()`
2. Creates an `Agent` with the discovered tools
3. Runs `Runner.run()` in an interactive loop

All tool implementations live in the MCP server (`tools/*.py`), deployed to Arcade Cloud. The agent never imports from `meow_me.tools` — complete process and network isolation.

---

## MCP Tools (7 deployed tools)

| Tool (MCP name) | Auth | Description |
|------|------|-------------|
| `MeowMe_GetCatFact` | None | Fetch 1-5 random cat facts from MeowFacts API |
| `MeowMe_GetUserAvatar` | Slack OAuth (`users:read`) | Get your Slack avatar URL and display name |
| `MeowMe_StartCatImageGeneration` | `requires_secrets: OPENAI_API_KEY` | Start async avatar-to-cat-art transformation via gpt-image-1; returns task_id |
| `MeowMe_CheckImageStatus` | None | Poll task_id for completion; returns status + image preview when ready |
| `MeowMe_MeowMe` | Slack OAuth (full scopes) | One-shot: fact + avatar + image + DM self (image generation optional) |
| `MeowMe_SendCatFact` | Slack OAuth (`chat:write`) | Send 1-3 text cat facts to a channel |
| `MeowMe_SendCatImage` | Slack OAuth (`chat:write`, `files:write`) | Upload image + caption to a channel |

---

## Environment Variables

```bash
# .env (gitignored) — see src/meow_me/.env.example
OPENAI_API_KEY=sk-...          # For agent LLM (gpt-4o-mini) AND image generation (gpt-image-1)
ARCADE_API_KEY=arc-...         # Required: connects agent to Arcade-deployed tools
ARCADE_USER_ID=you@email.com   # Optional: skip the email prompt during Arcade OAuth
```

### Slack Auth

Auth is fully managed by the Arcade platform. When tools need Slack access, Arcade handles the OAuth flow (browser-based). The agent never touches tokens directly.

**Cloud secrets model:** `OPENAI_API_KEY` and `SLACK_BOT_TOKEN` are configured as Arcade Cloud secrets (via `arcade deploy --secrets all`). Tools declare `requires_secrets` to access them at runtime. The bot token is used server-side for file uploads (`files:write`) while Arcade OAuth provides user identity (`users:read`). The agent itself never sees or handles these secrets.

---

## Known Limitations

- **Image generation requires MCP server mode**: The async start/poll pattern (`StartCatImageGeneration` + `CheckImageStatus`) uses background threads and in-memory state that only work in a long-running process. Arcade Cloud uses ephemeral workers — each tool call runs in a fresh process, so the background thread and job state are lost between calls. Use Claude Desktop or Cursor (MCP server mode) for image generation. The CLI agent mode is text-only.
- **Arcade OAuth lacks `files:write`**: Arcade's Slack provider does not support the `files:write` scope. Image uploads require a `SLACK_BOT_TOKEN` configured as a cloud secret (or local env var in MCP server mode). When unavailable, `meow_me` falls back to text-only DMs.
- **Image generation time**: `gpt-image-1` takes 30-60 seconds per image. The async start/poll pattern lets the MCP client check progress periodically rather than blocking.
- **Claude Desktop image preview**: Generated images appear as compressed JPEG thumbnails via MCP `ImageContent` in tool results. The full-res PNG is stored server-side and can be sent to Slack via `send_cat_image`.
- **arcade-mcp-server ImageContent**: Arcade `@tool` functions must return dicts. The framework's `convert_to_mcp_content()` only emits `TextContent` by default. We monkey-patch it in `__init__.py` to detect a `_mcp_image` key and also emit `ImageContent` blocks for inline image previews.

---

## Project Structure

```
meow_me/
├── src/meow_me/
│   ├── __init__.py        # load_dotenv, debug logging, ImageContent monkey-patch
│   ├── server.py          # MCPApp entry point (registers all tool modules)
│   ├── agent.py           # Thin LLM agent (calls tools via Arcade SDK, no tool logic)
│   ├── __main__.py        # python -m meow_me support
│   └── tools/
│       ├── facts.py       # MeowFacts API (get_cat_fact, no auth)
│       ├── avatar.py      # Slack avatar retrieval (get_user_avatar)
│       ├── image.py       # OpenAI image generation (async start/poll) + thumbnail + server-side stash
│       └── slack.py       # Slack messaging + file upload (meow_me, send_cat_fact, send_cat_image)
├── examples/
│   ├── orange_cats.png    # "80% of orange cats are male"
│   ├── siamese_cats.png   # "The color of the points in Siamese cats is heat related..."
│   └── sleeping_cats.png  # "Cats sleep 16 to 18 hours per day"
├── tests/
│   ├── test_facts.py      # Fact parsing & fetching (11 tests)
│   ├── test_avatar.py     # Slack avatar extraction & fallbacks (13 tests)
│   ├── test_image.py      # Prompts, validation, thumbnail, ImageContent patch, async start/poll (31 tests)
│   ├── test_slack.py      # Messaging, file upload, channel resolution, bot membership (34 tests)
│   ├── test_agent.py      # System prompt, demo, Arcade SDK integration, capabilities (31 tests)
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
| `files:write` | Image upload via Slack file upload API (not requested by MCP tools) | **NOT supported** by Arcade |
| `channels:read` | `send_cat_image` - resolve channel names to IDs for file uploads | N/A (bot token only) |
| `channels:join` | `send_cat_image` - ensure bot is in the target channel before upload | N/A (bot token only) |

> **Note:** The MCP tools no longer request `files:write` in their OAuth scopes since Arcade doesn't support it. Image upload is attempted at runtime using a `SLACK_BOT_TOKEN` configured as an Arcade Cloud secret, and falls back to text-only if the token is unavailable.

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent framework | OpenAI Agents SDK + agents-arcade | Arcade's official integration; tools discovered via `get_arcade_tools()` |
| Agent-tool separation | Arcade SDK (remote calls) | Agent has zero imports from tool modules; complete process/network isolation |
| Agent LLM | gpt-4o-mini | Fast, cheap, sufficient for tool routing |
| Image generation | OpenAI gpt-image-1 (`images.edit`) | Same API key as agent LLM; accepts avatar as input image |
| Async image gen | Start/poll pattern (`StartCatImageGeneration` + `CheckImageStatus`) | Splits long-running gpt-image-1 call into non-blocking start + polling to work within Arcade Cloud worker timeouts |
| Image delivery | Slack file upload API (`getUploadURLExternal` flow) | Modern Slack file sharing; `files.upload` is deprecated |
| Arcade OAuth fallback | Text-only DM | Graceful degradation when `files:write` or image generation is unavailable |
| Tool deployment | `arcade deploy -e server.py --secrets all` | Tools run on Arcade Cloud; agent connects via SDK |
| Cloud secrets | `requires_secrets=["OPENAI_API_KEY"]` on `@tool` | Arcade Engine injects secrets into context; `os.getenv()` doesn't work on cloud |
| Dual-token pattern | OAuth for identity + bot token secret for uploads | Arcade OAuth provides user identity (`users:read`); cloud-stored bot token enables `files:write` for image uploads |
| Fallback behavior | Text-only when OPENAI_API_KEY missing | Full pipeline still completes; image generation is optional |
| Avatar input | BytesIO with `.name = "avatar.png"` | OpenAI SDK needs named file-like object for MIME type detection |
| External API | MeowFacts | Free, no auth, structured JSON |
| Slack auth (MCP) | Arcade built-in Slack provider | Zero setup - demonstrates Arcade's core OAuth value |
| Count limits | get_cat_fact: 1-5, send_cat_fact: 1-3 | Prevent spam while allowing batch sends |
| Server-side image stash | `_last_generated_image` dict | Avoids sending ~2MB base64 through LLM context; tools reference via `"__last__"` |
| Thumbnail compression | 512x512 JPEG at 80% quality | Claude Desktop has ~1MB MCP content limit; thumbnail is ~50-100KB |
| ImageContent monkey-patch | Patch `convert_to_mcp_content` | Arcade tools must return dicts; patch extends framework to emit ImageContent from dict values |
| `__init__.py` initialization | `load_dotenv()` + patch in `__init__.py` | `arcade mcp` never executes `server.py`; `__init__.py` runs for any import |
| Input validation | Error messages reference prerequisite tools | Guides the LLM to call `get_user_avatar`/`get_cat_fact` before `start_cat_image_generation` |

> **MCP Tools vs Resources for Images:** We use **tools** (not resources) because our use case requires LLM-controlled orchestration, inline previews, and single-operation generation. Resources would require URI-based retrieval and fit better for pre-existing image galleries. See [DEVELOPMENT_NOTES.md](DEVELOPMENT_NOTES.md#mcp-architecture-tools-vs-resources-for-images) for full comparison. **2026 Update:** [MCP Apps](http://blog.modelcontextprotocol.io/posts/2026-01-26-mcp-apps/) now enable tools to return interactive UI components beyond static images.

---

## Built With

- [Arcade MCP Server](https://docs.arcade.dev) - MCP server framework with OAuth
- [Arcade Python SDK (arcadepy)](https://github.com/ArcadeAI/arcade-py) - Remote tool execution via Arcade Cloud
- [agents-arcade](https://github.com/ArcadeAI/openai-agents-arcade) - Arcade ↔ OpenAI Agents bridge
- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) - Agent framework
- [OpenAI gpt-image-1](https://platform.openai.com/docs/guides/image-generation) - Image-to-image generation
- [Pillow](https://python-pillow.org/) - Image processing (thumbnail compression)
- [MeowFacts API](https://meowfacts.herokuapp.com/) - Random cat facts
- [httpx](https://www.python-httpx.org/) - Async HTTP client
- [uv](https://docs.astral.sh/uv/) - Python package management
- [Claude Code](https://claude.com/claude-code) - AI-assisted development (Claude Opus 4.6)
