# Meow Me - Development Notes

Development log for the Meow Me MCP server, built as a second Arcade.dev interview submission.

## Session 1: Project Setup & Implementation

### Approach
Built as a focused complement to Sushi Scout - demonstrating Arcade's **built-in OAuth provider** (Slack) rather than a custom OAuth2 provider (Google Places). Kept intentionally small (3 tools) to show clean code, good tests, and clear documentation.

### Steps
1. Scaffolded with `arcade new meow_me`
2. Implemented `get_cat_fact` tool (MeowFacts API, no auth)
3. Implemented `meow_me` tool (Slack OAuth - self-DM pattern)
4. Implemented `send_cat_fact` tool (Slack OAuth - channel send)
5. Created CLI demo agent (`--demo` mode prints facts without Slack)
6. Wrote 34 tests across 3 test files
7. Created README with Claude Desktop config, architecture diagram

### Key Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| API | MeowFacts | Free, no auth needed, clean JSON response |
| Auth | Arcade built-in Slack | Shows the simplest OAuth path (vs custom provider in Sushi Scout) |
| Self-DM | `auth.test` → `conversations.open` → `chat.postMessage` | Proper DM channel creation via Slack API |
| Count limits | 1-5 for facts, 1-3 for Slack sends | Balance between useful and not-spammy |
| Demo mode | Print facts to terminal | Lets reviewers try it without Slack setup |

### Gotchas

1. **`arcade new` via `uv tool run`**: `uv tool run arcade new` installs the `arcade` game library (depends on pymunk/C++). Use `arcade new` directly after `uv tool install arcade-mcp`.

2. **Module-level `@tool`**: Same as Sushi Scout - tools must use `@tool` at module level, not `@app.tool` inside closures. The `arcade mcp` CLI discovers tools by scanning module-level decorators.

3. **`conftest.py` import**: pytest's conftest.py is auto-loaded but can't be imported as a regular module (`from conftest import ...` fails). Define test constants directly in each test file instead.

### Tools & Frameworks

- **[Claude Code](https://claude.com/claude-code)** (Claude Opus 4.6) - Full implementation, tests, and documentation
- **[Arcade MCP Server](https://docs.arcade.dev)** v1.15.2 - MCP framework with OAuth
- **[MeowFacts API](https://meowfacts.herokuapp.com/)** - Random cat facts
- **[httpx](https://www.python-httpx.org/)** - Async HTTP client
- **[pytest](https://pytest.org/)** + **pytest-asyncio** - Test framework

### Gotcha: Slack Self-DM

4. **Self-DM requires `conversations.open`**: Initially tried posting directly to the user ID, but the correct Slack API flow is: `auth.test` (get user ID from token) → `conversations.open` (create DM channel) → `chat.postMessage` (send to DM channel). Requires `im:write` scope in addition to `chat:write`.

### Test Coverage (Session 1)

```
tests/test_facts.py  - 11 tests (parsing, count clamping, API URL, empty responses)
tests/test_slack.py  - 15 tests (formatting, auth.test, conversations.open, message sending)
tests/test_evals.py  -  8 tests (end-to-end workflows, edge cases, formatting)
Total: 34 tests, all passing
```

---

## Session 2: Image Generation, Avatar Retrieval & LLM Agent

### Objective
Extend meow_me from a 3-tool MCP server into a full **6-tool MCP server + LLM-powered agent**. The Arcade interview assignment requires an agent/application that consumes the MCP server, not just the server alone.

### Spike: OpenAI Image API
Tested `gpt-image-1` `images.edit` with a downloaded Slack avatar. Critical discovery: raw bytes fail with MIME type errors. The fix is wrapping bytes in a named `BytesIO`:

```python
buf = io.BytesIO(data)
buf.name = "avatar.png"  # SDK uses .name for MIME type detection
```

Tested 3 approaches — all passed after the fix:
- `dall-e-2` images.edit (fixed MIME) ✓
- `gpt-image-1` images.edit (fixed MIME) ✓
- `gpt-image-1` images.generate (text-described avatar) ✓

### New Tools (3 added → 6 total)

| Tool | Module | What it does |
|------|--------|-------------|
| `get_user_avatar` | avatar.py | Slack `auth.test` → `users.info` → avatar URL + display name |
| `generate_cat_image` | image.py | Download avatar + compose style prompt + `gpt-image-1` `images.edit` → base64 PNG |
| `send_cat_image` | slack.py | 3-step Slack file upload: `getUploadURLExternal` → upload bytes → `completeUploadExternal` |

### Upgraded `meow_me` Tool
The one-shot `meow_me` tool now runs the full pipeline: fetch fact → get avatar → generate cat art → upload image to DM. Falls back to text-only if image generation fails (no OPENAI_API_KEY or API error).

New scopes: `chat:write`, `im:write`, `files:write`, `users:read`

### Agent Implementation (OpenAI Agents SDK)

**Framework:** OpenAI Agents SDK (`openai-agents` v0.0.17) with `gpt-4o-mini` for tool routing.

**Why this approach:** Arcade recommends the OpenAI Agents SDK. Used `@function_tool` wrappers (not `MCPServerStdio`) so the agent is self-contained — no subprocess needed. Slack-auth tools check `SLACK_BOT_TOKEN` env var directly.

**Key design:**
- `SYSTEM_PROMPT` with explicit routing rules
- `_build_tools()` creates 6 `@function_tool` wrappers bridging MCP tool implementations → agent SDK
- `generate_cat_image` wrapper sends only a summary to the LLM (not the full base64 image)
- Multi-turn chat loop using `Runner.run()` + `result.to_input_list()` for history
- Scripted `--demo` mode with 4 scenarios for reviewers

**Agent routing model:**
- `"Meow me!"` (standalone, no modifiers) → one-shot `meow_me()` tool
- Any modifier (`"Meow me to #random"`, `"Meow me in watercolor"`) → interactive two-phase flow
- Everything else → FACT PHASE (browse facts) → DELIVERY PHASE (text or image, choose destination)

### Steps
1. Wrote spike script testing OpenAI `images.edit` with avatar input
2. Created `tools/avatar.py` — `get_user_avatar` + 4 helper functions
3. Created `tools/image.py` — `generate_cat_image` with 4 styles + placeholder fallback
4. Extended `tools/slack.py` — added `send_cat_image` (3-step file upload) + upgraded `meow_me` to full pipeline
5. Registered new modules in `server.py`
6. Installed `openai-agents` dependency
7. Rewrote `agent.py` — system prompt, 6 tool wrappers, interactive chat loop, demo mode
8. Created `test_agent.py` — 15 tests covering system prompt, demo mode, tool wrappers, auth checks
9. Updated README, pyproject.toml description, CLAUDE.md

### Gotchas

5. **OpenAI `images.edit` MIME type**: Sending raw `bytes` to the SDK results in `"unsupported mimetype ('application/octet-stream')"`. Must wrap in `io.BytesIO` with `.name = "avatar.png"` so the SDK detects the PNG MIME type. This became the `_make_png_file()` helper in `tools/image.py`.

6. **Slack file upload API**: `files.upload` is deprecated. The modern flow is 3 steps: `files.getUploadURLExternal` (get pre-signed URL) → HTTP PUT to that URL → `files.completeUploadExternal` (share to channel). Requires `files:write` scope.

7. **Agent tool `on_invoke_tool` input format**: The OpenAI Agents SDK passes `{"input": json.dumps({...})}` to `on_invoke_tool`. For parameterless tools, use `{"input": "{}"}`. For tools with required parameters, the SDK validates inputs before calling the function body — so testing auth failures on parameterized tools requires the parameters to be included.

8. **`generate_cat_image` output size**: The base64 PNG from gpt-image-1 is ~1.5MB. The `@function_tool` wrapper returns only a summary dict (style, fact, fallback flag, image_size_bytes) to keep the LLM context small.

### Test Coverage (Session 2)

```
tests/test_facts.py   - 11 tests (parsing, count clamping, API URL, empty responses)
tests/test_slack.py   - 22 tests (formatting, auth.test, conversations.open, message sending, file upload)
tests/test_avatar.py  - 13 tests (auth.test, users.info, avatar extraction, fallbacks)
tests/test_image.py   - 14 tests (prompt composition, OpenAI mock, fallback placeholder, styles)
tests/test_agent.py   - 15 tests (system prompt, demo mode, tool wrappers, auth checks)
tests/test_evals.py   -  8 tests (end-to-end workflows, edge cases, formatting)
Total: 83 tests, all passing
```

### Tools & Frameworks (Session 2 additions)

- **[OpenAI Agents SDK](https://github.com/openai/openai-agents-python)** v0.0.17 - Agent framework with `@function_tool`
- **[OpenAI gpt-image-1](https://platform.openai.com/docs/guides/image-generation)** - Image-to-image generation via `images.edit`
- **[OpenAI gpt-4o-mini](https://platform.openai.com/docs/models)** - Agent LLM for tool routing
