# Claude Code Context for Meow Me Project

**Purpose:** This file contains Claude Code-specific context, gotchas, and quick reference information for working on this codebase. See [README.md](README.md) and [meow_me/README.md](meow_me/README.md) for comprehensive project documentation.

---

## Arcade.dev Documentation

**Primary References:**
- **https://docs.arcade.dev/llms.txt** - Preferred reference for Arcade platform
- **https://arcade.dev** - Main website
- **https://docs.arcade.dev** - Full documentation

---

## Interview Project Requirements

This is an **Arcade.dev Engineering Interview Project** with these requirements:

**Deliverables:**
- Original MCP Server using `arcade-mcp` (not derived from existing toolkits)
- Agentic application that consumes the MCP server
- Tests and evaluations equivalent to production development
- Public GitHub repository with clear documentation

**Evaluation Criteria:**
- **Functionality:** Tools and agent work as intended
- **Code Quality:** Follows best practices and linting standards
- **Testing:** Comprehensive validation of toolkit functionality
- **Documentation:** Clear instructions provided
- **Originality:** Unique from existing Arcade toolkits

---

## Project Context

**Interview Project for Arcade.dev** - Demonstrating MCP server development, OAuth integration, LLM agent orchestration, and comprehensive testing.

**What This Project Does:** MCP server + CLI agent that fetches cat facts, generates cat-themed art from Slack avatars using OpenAI's gpt-image-1, and sends results to Slack.

**Tech Stack:**
- `arcade-mcp-server` - MCP framework with built-in OAuth (tools deployed to Arcade Cloud)
- `arcadepy` + `agents-arcade` - Agent connects to deployed tools via Arcade SDK
- `openai-agents` - Agent framework (gpt-4o-mini, thin LLM client)
- `openai` - Image generation (gpt-image-1)
- Slack API - Messaging and file uploads

---

## Critical Architecture Patterns

### Two Runtime Modes
The project supports two modes with different capabilities:

**MCP Server Mode** (Claude Desktop, Cursor) — Full features:
- Tools run as a local long-running process (`arcade mcp -p meow_me stdio`)
- Background threads persist → async image generation works
- Uses local `OPENAI_API_KEY` and `SLACK_BOT_TOKEN` from `.env`
- Recommended for image generation

**CLI Agent Mode** — Text-only:
- Agent calls tools remotely via Arcade SDK (`get_arcade_tools()`)
- Arcade Cloud uses ephemeral workers → background threads lost between calls
- Image generation (`start_cat_image_generation` + `check_image_status`) does NOT work
- Agent system prompt explicitly tells the LLM not to call image tools

### Agent-Tool Separation (Arcade SDK)
The CLI agent is a **thin LLM client** that calls tools remotely via the Arcade SDK.
- Agent (`agent.py`) has **zero imports** from `meow_me.tools.*`
- Tools are deployed to Arcade Cloud via `arcade deploy -e server.py`
- Agent uses `agents-arcade.get_arcade_tools()` to discover and call tools
- All tool execution happens on the Arcade platform, not in the agent process
- Auth is handled entirely by Arcade (OAuth flow managed server-side)

### Auth Model (Single Mode)
- **Arcade OAuth** handles user identity and basic Slack operations (DMs, text messages)
- **Optional cloud secrets** (`OPENAI_API_KEY`, `SLACK_BOT_TOKEN`) enhance capabilities when configured
- No `--slack` flag; auth mode is unified
- **Dual-token pattern:** OAuth token for user identity, bot token secret (via `_try_get_secret`) for file uploads requiring `files:write`

### MCP Tool Naming
**Important:** MCP server exposes tools with namespace prefix in PascalCase:
- `get_cat_fact` → `MeowMe_GetCatFact`
- `send_cat_fact` → `MeowMe_SendCatFact`
- `meow_me` → `MeowMe_MeowMe`

Pattern: `{ServerName}_{PascalCaseToolName}`

This matters for:
- Arcade evaluations (`ExpectedMCPToolCall` must use prefixed names)
- MCP client integration
- Tool discovery and registration

### Arcade Cloud Secrets
Tools access secrets via `context.get_secret("KEY")`, NOT `os.getenv()`.
- `@tool(requires_secrets=["OPENAI_API_KEY"])` is required for Arcade Engine to inject secrets
- Secrets uploaded during `arcade deploy --secrets all` or via `arcade secret set`
- `os.getenv()` fallback only works locally (env vars are NOT injected on Arcade Cloud)

### Image Generation Flow (Async Start/Poll)
1. `start_cat_image_generation` kicks off async generation, returns a `job_id` immediately
2. `check_image_status` polls for completion using the `job_id`
3. On completion, PNG stashed in `_last_generated_image` dict (referenced as `"__last__"`) and JPEG thumbnail built
4. Agent uploads to Slack or sends thumbnail via MCP `ImageContent`

---

## Critical Gotchas

### Arcade Platform

1. **`arcade mcp` arg order:** `-p package` comes BEFORE transport
   ✅ `arcade mcp -p meow_me stdio`
   ❌ `arcade mcp stdio -p meow_me`

2. **`arcade evals` requires `uv run`:**
   ✅ `uv run arcade evals evals/`
   ❌ `arcade evals evals/` (can't find package)

3. **Tool registration:** Module-level `@tool` decorator only
   ✅ `@tool` at module level
   ❌ `@app.tool` inside closures (not discoverable)

4. **OAuth scope limitations:**
   - Arcade's Slack provider does NOT support `files:write`
   - Design for graceful degradation when scopes unavailable
   - Always check token capabilities at runtime

5. **`__init__.py` is entry point:**
   - `arcade mcp` never executes `server.py`
   - Put `load_dotenv()` and monkey-patches in `__init__.py`

6. **`arcade deploy` requires explicit `app.add_tool()`:**
   - Unlike `arcade mcp` (which discovers via module scan), `arcade deploy` needs explicit registration
   - Without `app.add_tool()`, the deployed server has no tools

7. **Toolkit names are PascalCase:**
   - `get_arcade_tools(client, toolkits=["meow_me"])` returns 0 tools
   - Correct: `toolkits=["MeowMe"]` — Arcade converts server name to PascalCase

8. **`--skip-validate` changes `--secrets` default to `skip`:**
   - Must explicitly pass `--secrets all` to upload `.env` secrets during deploy
   - Without this, secrets are not bound to the deployed server

9. **`requires_secrets` is mandatory for cloud secrets:**
   - `context.get_secret("KEY")` only works if `@tool(requires_secrets=["KEY"])` is declared
   - Without the decorator, Arcade Engine doesn't populate the secret in the context
   - `os.getenv()` masks this locally but fails on cloud

10. **Arcade Cloud worker timeout (~30s):**
    - `gpt-image-1` takes 30-60s, exceeds the platform's worker timeout
    - Fast tools (GetCatFact, etc.) work fine
    - Image generation works via local MCP transport (`arcade mcp -p meow_me stdio`)

11. **Ephemeral workers break async start/poll:**
    - `start_cat_image_generation` starts a background thread on Worker A
    - `check_image_status` runs on Worker B (fresh process) → `_pending_jobs` is empty → 503
    - Image generation only works in MCP server mode (long-running process)

12. **Don't gate agent on local env vars for cloud secrets:**
    - Agent should NOT check `os.getenv("OPENAI_API_KEY")` to decide capabilities
    - Cloud secrets exist on Arcade Cloud, not in the agent's local environment
    - Let tools report their own failures; don't preemptively disable features

13. **LLM prompt language must be definitive, not wishy-washy:**
    - "Available via cloud secrets (tools detect at runtime)" → LLM hedges and refuses
    - Use either "READY — always attempt" or "Do NOT call" — no middle ground
    - gpt-4o-mini errs on the side of caution with ambiguous capability descriptions

14. **`arcade deploy --skip-validate` requires `--server-name` and `--server-version`:**
    - Deploy verification can timeout even when server starts correctly
    - Use: `arcade deploy -e server.py --skip-validate --server-name meow_me --server-version 0.1.0`

### Slack API

11. **Channel resolution asymmetry:**
   - `chat.postMessage` accepts channel names (`#general`)
   - `files.completeUploadExternal` requires channel IDs (`C01234567`)
   - Must resolve names to IDs for file uploads

12. **Bot membership for file uploads:**
   - `files.completeUploadExternal` fails if bot not in channel
   - Use `conversations.join` before upload (requires `channels:join` scope)
   - Handle `missing_scope` gracefully

13. **`conversations.list` type filtering:**
   - Requesting `types: "public_channel,private_channel"` requires BOTH scopes
   - If missing `groups:read`, entire request fails (not partial results)
   - Only request types you have scopes for

14. **Self-DM flow:**
   - `auth.test` → get user ID
   - `conversations.open` → create DM channel
   - `chat.postMessage` → send to DM channel
   - Requires `im:write` scope

### OpenAI & Images

15. **`asyncio.to_thread` for sync OpenAI client:**
    - `gpt-image-1` uses sync `OpenAI()` client
    - Wrap in `asyncio.to_thread()` to avoid blocking event loop

16. **BytesIO naming:**
    - OpenAI SDK needs `file_like.name` for MIME type detection
    - Set `.name = "avatar.png"` on BytesIO objects

17. **ImageContent monkey-patch:**
    - Arcade `@tool` functions must return dicts (per typed schemas)
    - `convert_to_mcp_content()` converts dicts to MCP content (default: TextContent only)
    - Patched in `__init__.py` to detect `_mcp_image` key and emit ImageContent
    - Enables inline image previews in Claude Desktop from dict-returning tools

### Windows-Specific

18. **Encoding for subprocess:**
    - Set `PYTHONIOENCODING=utf-8` for `arcade mcp` calls
    - Windows cp1252 can't render Arcade's Unicode output

19. **Claude Desktop paths:**
    - Store install: `%APPDATA%\Claude\`
    - Windows Store install: `%LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude\`
    - Use `--directory` flag in uv args

---

## Testing Strategy

**pytest unit tests** - Implementation correctness
- Fast (~3 sec), deterministic, free
- Mocks all external APIs
- Tests edge cases, error handling, fallbacks

**12 Arcade evaluations** - LLM tool selection
- Slow (~30-60 sec), LLM-dependent, costs $0.05-0.10/run
- Tests if model chooses right tools for user prompts
- Complements unit tests (different dimension)

**Run both:**
```bash
cd meow_me
uv run pytest -v              # Unit tests
uv run arcade evals evals/    # Behavioral evals
```

---

## Code Patterns

### MCP Tool Template
```python
from arcade_mcp_server import tool, Context
from arcade_mcp_server.auth import Slack

async def _try_get_secret(context: Context, key: str) -> str | None:
    """Try to get a secret from Arcade Cloud, fall back to env var."""
    try:
        return context.get_secret(key)
    except Exception:
        return os.getenv(key)

@tool(requires_auth=Slack(scopes=["chat:write"]))
async def send_message(context: Context, channel: str, message: str):
    token = context.get_auth_token_or_empty()
    bot_token = await _try_get_secret(context, "SLACK_BOT_TOKEN")  # Optional enhancement
    # ... implementation ...
    return {"success": True}
```

### Agent Setup (Arcade SDK, no tool wrappers)
```python
from agents import Agent, Runner
from arcadepy import AsyncArcade
from agents_arcade import get_arcade_tools

client = AsyncArcade()  # Uses ARCADE_API_KEY env var
tools = await get_arcade_tools(client, toolkits=["MeowMe"])  # PascalCase!
agent = Agent(name="Meow Art", model="gpt-4o-mini", tools=tools)
result = await Runner.run(agent, input=history, context={"user_id": email})
```

### Evaluation Case Template
```python
suite.add_case(
    name="Test name",
    user_message="Natural language prompt",
    expected_tool_calls=[
        ExpectedMCPToolCall("MeowMe_ToolName", {"param": "value"}),
    ],
    critics=[
        BinaryCritic(critic_field="param", weight=1.0),
    ],
    rubric=rubric,
)
```

---

## Environment Variables

```bash
# Required for agent
OPENAI_API_KEY=sk-...          # gpt-4o-mini (agent) + gpt-image-1 (images)
ARCADE_API_KEY=arc-...         # Required: connects agent to Arcade-deployed tools

# Optional
ARCADE_USER_ID=you@email.com   # Skip email prompt in Arcade flow
```

---

## Quick Commands

```bash
cd meow_me

# Demo (no API keys)
uv run python -m meow_me --demo

# Agent mode
uv run python -m meow_me              # Arcade OAuth

# Testing
uv run pytest -v                      # All 137 unit tests
uv run arcade evals evals/            # All 12 evaluations

# MCP server
uv run arcade mcp -p meow_me stdio    # Claude Desktop
uv run arcade mcp -p meow_me http     # Cursor/VS Code
```

---

## File Organization

```
meow_me/
├── src/meow_me/
│   ├── __init__.py         # Entry point (load_dotenv, patches)
│   ├── agent.py            # Thin LLM agent (calls tools via Arcade SDK, zero tool logic)
│   └── tools/
│       ├── facts.py        # get_cat_fact
│       ├── avatar.py       # get_user_avatar
│       ├── image.py        # start_cat_image_generation, check_image_status (async pattern)
│       └── slack.py        # meow_me, send_cat_fact, send_cat_image
├── tests/                  # 137 pytest unit tests
├── evals/                  # 12 Arcade evaluations
└── examples/               # Sample generated images
```

---

## Known Limitations

1. **Image generation requires MCP server mode** - Async start/poll uses background threads + in-memory state. Arcade Cloud's ephemeral workers lose both between calls. Use Claude Desktop or Cursor for image generation.
2. **CLI agent is text-only** - When running via Arcade Cloud, only text tools work (GetCatFact, SendCatFact, MeowMe text fallback). Agent system prompt explicitly gates image tools.
3. **Arcade OAuth lacks `files:write`** - Image uploads require `SLACK_BOT_TOKEN` configured as a cloud secret or local env var
4. **Claude Desktop ~1MB MCP content limit** - Send JPEG thumbnail, not full PNG
5. **Image generation time** - gpt-image-1 takes 30-60 seconds per image

---

## Development Notes

See [meow_me/DEVELOPMENT_NOTES.md](meow_me/DEVELOPMENT_NOTES.md) for session-by-session development log with detailed gotchas and learnings from building this project.

---

**Last Updated:** Session 8 (Cloud-First Optimization)
