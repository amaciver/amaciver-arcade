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

### Test Coverage

```
tests/test_facts.py  - 11 tests (parsing, count clamping, API URL, empty responses)
tests/test_slack.py  - 15 tests (formatting, auth.test, conversations.open, message sending)
tests/test_evals.py  -  8 tests (end-to-end workflows, edge cases, formatting)
Total: 34 tests, all passing
```
