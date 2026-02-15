Here is the overall instructions for the project: Arcade Engineering Interview Project
Thank you for your interest in joining Arcade.dev!
This project is designed to assess your engineering skills by examining how you would use our products to develop a new MCP Server, and see how you would use it in an agentic application.
Project Overview
Create a sample application or agent. As part of this work, create at least one new MCP Server using arcade-mcp. Share your work with us via a stand-alone Github Repository with instructions about what the project should accomplish and how we can run it. The project you deliver should have tests and evaluations equivalent to how you would develop on the job.
Guidelines
Independent Development: Your toolkit should be completely original and not derived from existing Arcade toolkits / MCP Servers.
GitHub Delivery: The toolkit should be in a public GitHub repository, where others can easily clone and run it.
Project Generation: Use the command line interface tool arcade new to create your MCP Server scaffold. This utility will provide initial files, directories, and structure. The agent/application which consumes the MCP server can use any framework (or not) that you like to accomplish your goal.
OAuth Use: Including OAuth is optional but can be added if it aligns with your tool's design and functionality.
Time Management: Please limit your work on this project to no more than 6 hours in total.
External Resources: Use any appropriate, public resources at your disposal. If you rely on external code or libraries (including LLMs), please cite them and share how you used them (prompts, MCP server, skills, etc). Using LLMs/Coding Agents is encouraged, but be expected to explain everything they generate - from architectural choices to dependencies… just as if you did it by hand.
References
For examples of existing toolkits and to understand the general approach: Arcade AI GitHub Repository, and of course, our docs (note that we offer an llms.txt as well).
Deliverables
GitHub Repository: Host your toolkit in a public GitHub repository on your own account.
Email Submission: Send an email with the repository link to evan@arcade.dev for review.
Evaluation Criteria
Your project will be evaluated based on:
Functionality: The tool(s) and application/agent work as you intended and deliver meaningful features.
Code Quality: Follows best practices and the linting/editorconfig standards provided by your arcade new project scaffold, and your application follows similar standards.
Testing: Your tests are comprehensive and accurately validate your toolkit's functionality.
Documentation: Clear instructions and documentation are provided.
Originality: Your toolkit is unique from existing Arcade AI toolkits, and your application does something useful or interesting.

---

# PROJECT: Sushi Scout

**Name:** `sushi-scout`
**Goal:** MCP server + CLI agent that finds the cheapest tuna sushi roll nearby, with simulated ordering.

---

## Architecture

### 3-Layer Design

```
Layer 1: Restaurant Discovery (REAL DATA - Google Places API)
  - search_nearby_restaurants  (lat, lng, radius -> sushi restaurants)
  - get_restaurant_details     (place_id -> hours, reviews, delivery info)
  - Auth: API key (default) or OAuth via custom Arcade provider

Layer 2: Menu & Pricing (SYNTHETIC, CALIBRATED)
  - get_restaurant_menu        (place_id + price_level -> deterministic menu)
  - find_cheapest_tuna_roll    (restaurants JSON -> ranked price comparison)

Layer 3: Ordering (SIMULATED)
  - place_order                (restaurant + item + address -> mock confirmation)
  - check_order_status         (order_id -> mock timeline)

OAuth Demo:
  - get_user_profile           (Google OAuth -> user email/name)
```

### Auth Strategy

Search tools support two auth modes via `SUSHI_SCOUT_AUTH_MODE` env var:

| Mode | Default? | Mechanism | User setup |
|------|----------|-----------|------------|
| `api_key` | Yes | `requires_secrets` + `X-Goog-Api-Key` header | Add key to `.env` |
| `oauth` | No | Custom `OAuth2(id="google-places")` + Bearer token | Register provider in Arcade |

`get_user_profile` uses Arcade's built-in Google OAuth with `userinfo.email` scope.

### Tool Registration

Tools use **module-level `@tool` decorator** (NOT `@app.tool` inside closures - arcade CLI can't discover those).

---

## MCP Tools (7 total)

| Tool | Module | Auth | Description |
|------|--------|------|-------------|
| `search_nearby_restaurants` | search.py | API key or OAuth | Find sushi restaurants by location |
| `get_restaurant_details` | search.py | API key or OAuth | Get hours, reviews, delivery info |
| `get_user_profile` | search.py | Google OAuth | Get authenticated user's email/name |
| `get_restaurant_menu` | menu.py | None | Generate price-calibrated menu |
| `find_cheapest_tuna_roll` | menu.py | None | Rank tuna rolls across restaurants |
| `place_order` | ordering.py | None | Simulate delivery order |
| `check_order_status` | ordering.py | None | Check simulated order status |

---

## Commands

```bash
# Run tests
cd sushi_scout && uv run pytest -v

# Demo mode (no API key needed)
uv run python -m sushi_scout --demo

# MCP server (STDIO for Claude Desktop)
uv run arcade mcp -p sushi_scout stdio

# MCP server (HTTP for Cursor/VS Code)
uv run arcade mcp -p sushi_scout http --debug
```

---

## Environment Variables

```bash
# .env (gitignored)
SUSHI_SCOUT_AUTH_MODE=api_key          # "api_key" (default) or "oauth"
GOOGLE_PLACES_API_KEY=your_key         # Required for api_key mode
GCP_PROJECT_ID=your_project_id         # Required for oauth mode
ARCADE_API_KEY=your_arcade_key         # For Arcade platform access
```

---

## Development Guidelines

1. **Always run tests after changes** - `cd sushi_scout && uv run pytest -v`
2. **Use module-level `@tool` decorator** - NOT `@app.tool` inside closures
3. **`arcade mcp` arg order** - `-p package` comes BEFORE transport: `arcade mcp -p sushi_scout stdio`
4. **Windows encoding** - Set `PYTHONIOENCODING=utf-8` for subprocess calls
5. **MCP transports** - STDIO for Claude Desktop/OAuth flows, HTTP for Cursor/VS Code
6. **Claude Desktop (Windows Store)** - Config at `%LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude\`

---

## Testing (46 tests, all passing)

```
tests/test_search.py    - 14 tests (formatting, conversion, edge cases)
tests/test_menu.py      - 15 tests (generation, calibration, delivery consistency, ranking)
tests/test_ordering.py  -  6 tests (order IDs, cost math, response structure)
tests/test_evals.py     - 10 tests (price tiers, ranking, real API patterns, performance)
```

---

# PROJECT: Meow Me (Meow Art)

**Name:** `meow-me`
**Goal:** MCP server + LLM-powered CLI agent that fetches cat facts, generates cat-themed art from your Slack avatar, and sends results to Slack.

---

## Architecture

```
Interactive Agent (OpenAI Agents SDK, gpt-4o-mini + 6 tools)
  │ @function_tool wrappers
  ▼
MCP Server (arcade-mcp-server, 6 tools)
  get_cat_fact        (no auth)        → MeowFacts API → random facts
  get_user_avatar     (Slack OAuth)    → auth.test + users.info → avatar URL + display name
  generate_cat_image  (no auth)        → download avatar + gpt-image-1 images.edit → base64 PNG
  meow_me             (Slack OAuth)    → fact + avatar + image gen + file upload → DM self
  send_cat_fact       (Slack OAuth)    → MeowFacts + chat.postMessage → send to channel
  send_cat_image      (Slack OAuth)    → file upload API → upload image to channel
```

### Auth

Slack tools use Arcade's **built-in Slack provider**: `from arcade_mcp_server.auth import Slack`
- `meow_me`: `Slack(scopes=["chat:write", "im:write", "files:write", "users:read"])`
- `get_user_avatar`: `Slack(scopes=["users:read"])`
- `send_cat_fact`: `Slack(scopes=["chat:write"])`
- `send_cat_image`: `Slack(scopes=["chat:write", "files:write"])`

---

## MCP Tools (6 total)

| Tool | Module | Auth | Description |
|------|--------|------|-------------|
| `get_cat_fact` | facts.py | None | Fetch 1-5 random cat facts |
| `get_user_avatar` | avatar.py | Slack OAuth (`users:read`) | Get Slack avatar URL and display name |
| `generate_cat_image` | image.py | None (uses `OPENAI_API_KEY`) | Transform avatar into cat-themed art via gpt-image-1 |
| `meow_me` | slack.py | Slack OAuth (full scopes) | One-shot: fact + avatar + image + DM self |
| `send_cat_fact` | slack.py | Slack OAuth (`chat:write`) | Send 1-3 text cat facts to a channel |
| `send_cat_image` | slack.py | Slack OAuth (`chat:write`, `files:write`) | Upload image + caption to a channel |

---

## Commands

```bash
# Run tests
cd meow_me && uv run pytest -v

# Demo mode (no API keys needed)
uv run python -m meow_me --demo

# Interactive agent (requires OPENAI_API_KEY in .env)
uv run python -m meow_me

# MCP server (STDIO for Claude Desktop)
uv run arcade mcp -p meow_me stdio

# MCP server (HTTP for Cursor/VS Code)
uv run arcade mcp -p meow_me http --debug
```

---

## Testing (83 tests, all passing)

```
tests/test_facts.py   - 11 tests (parsing, count clamping, API URL, empty responses)
tests/test_slack.py   - 22 tests (formatting, auth.test, conversations.open, message sending, file upload)
tests/test_avatar.py  - 13 tests (auth.test, users.info, avatar extraction, fallbacks)
tests/test_image.py   - 14 tests (prompt composition, OpenAI mock, fallback placeholder, styles)
tests/test_agent.py   - 15 tests (system prompt, demo mode, tool wrappers, auth checks)
tests/test_evals.py   -  8 tests (end-to-end workflows, edge cases, formatting)
```
