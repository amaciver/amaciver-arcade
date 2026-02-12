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
Tips for Success
Plan Before Coding: Outline the functionality you want to build; plan how the arcade new generated scaffold can help you.
Focus on Core Features: Due to the 6-hour limit, implement the features with the highest impact.
Ensure Reproducibility: Anyone should be able to clone your repo and run the toolkit without issues.
Document Your Work: Clear, concise documentation will help others understand your toolkit's usage and benefits. Provide images or videos if that helps.
On Site or Remote
If you are interested in compressing your interview experience to a single day, you can do the take-home assignment from our office in San Francisco! You can work on the assignment in the morning, and then we can review it with you in the afternoon. Lunch will be included.

---

# PROJECT: Sushi Scout - Cheap Tuna Roll Finder & Orderer

## Project Concept

**Name:** `sushi-scout`

**Goal:** MCP server and CLI agent that finds the cheapest plain tuna sushi roll available for delivery within a specified radius, with optional simulated ordering.

**Value Prop:** Combines real location-based restaurant search (Google Places API), synthetic price-calibrated menus, and mock ordering into a multi-tool MCP server that demonstrates API integration, data processing, Arcade's `requires_secrets` and OAuth patterns, and actionable decision-making.

---

## Architecture (Implemented)

### 3-Layer Design

```
Layer 1: Restaurant Discovery (REAL DATA - Google Places API)
  - search_nearby_restaurants (lat, lng, radius -> 10 sushi restaurants)
  - get_restaurant_details   (place_id -> hours, reviews, delivery info)
  - Auth: requires_secrets=["GOOGLE_PLACES_API_KEY"] (API key via X-Goog-Api-Key header)

Layer 2: Menu & Pricing (SYNTHETIC, CALIBRATED)
  - get_restaurant_menu      (place_id + price_level -> deterministic menu)
  - find_cheapest_tuna_roll  (restaurants JSON -> ranked price comparison)
  - Auth: None (pure computation)

Layer 3: Ordering (SIMULATED)
  - place_order              (restaurant + item + address -> mock confirmation)
  - check_order_status       (order_id -> mock timeline)
  - Auth: None (mock data)

OAuth Demo:
  - get_user_profile         (Google OAuth -> user email/name)
  - Auth: requires_auth=Google(scopes=["userinfo.email", "openid"])
```

### Auth Strategy (Evolved)

**What we planned:** Use Arcade's Google OAuth (`cloud-platform` scope) for Places API calls.

**What we discovered:** The `cloud-platform` scope is NOT supported by Arcade's default Google provider. Supported scopes are limited to: calendar, contacts, drive.file, gmail, userinfo, openid.

**What we implemented:**
- **Search tools** use `requires_secrets=["GOOGLE_PLACES_API_KEY"]` - Google Maps APIs authenticate with API keys, not OAuth tokens. The secret is injected via Arcade's `context.get_secret()` mechanism (reads from `.env` or environment variables).
- **`get_user_profile`** uses `requires_auth=Google(scopes=["userinfo.email", "openid"])` - demonstrates Arcade's OAuth flow with a supported scope. Calls the Google userinfo endpoint to return the authenticated user's email and profile.

```python
# Search tools: API key via requires_secrets
@tool(requires_secrets=["GOOGLE_PLACES_API_KEY"])
async def search_nearby_restaurants(context: Context, latitude: float, longitude: float, radius_miles: float = 2.0):
    api_key = context.get_secret("GOOGLE_PLACES_API_KEY")
    headers = {"X-Goog-Api-Key": api_key, ...}

# OAuth demo: Arcade Google OAuth with supported scope
@tool(requires_auth=Google(scopes=["https://www.googleapis.com/auth/userinfo.email", "openid"]))
async def get_user_profile(context: Context):
    token = context.get_auth_token_or_empty()
    headers = {"Authorization": f"Bearer {token}"}
```

### Tool Registration Pattern

Tools use the **module-level `@tool` decorator** from `arcade_mcp_server`. We originally used `@app.tool` inside `register_tools(app)` closures (from the scaffold), but discovered that `arcade mcp` CLI cannot discover tools defined inside closures - they must be at module scope.

```python
# server.py - imports trigger @tool registration
from arcade_mcp_server import MCPApp
app = MCPApp(name="sushi_scout", version="0.1.0", log_level="DEBUG")
import sushi_scout.tools.search   # noqa: E402, F401
import sushi_scout.tools.menu     # noqa: E402, F401
import sushi_scout.tools.ordering # noqa: E402, F401
```

---

## MCP Tools (7 total)

| Tool | Module | Params | Auth | Description |
|------|--------|--------|------|-------------|
| `search_nearby_restaurants` | search.py | `latitude`, `longitude`, `radius_miles=2.0` | API key | Find sushi restaurants by location |
| `get_restaurant_details` | search.py | `place_id` | API key | Get hours, reviews, delivery info |
| `get_user_profile` | search.py | *(none)* | Google OAuth | Get authenticated user's email/name |
| `get_restaurant_menu` | menu.py | `restaurant_id`, `restaurant_name=""`, `price_level=None`, `price_range_low=None`, `delivery=None` | None | Generate price-calibrated menu |
| `find_cheapest_tuna_roll` | menu.py | `restaurants_json` (JSON string) | None | Rank tuna rolls across restaurants |
| `place_order` | ordering.py | `restaurant_id`, `restaurant_name`, `item_name`, `item_price`, `delivery_address`, `delivery_fee=0.0`, `special_instructions=""` | None | Simulate delivery order |
| `check_order_status` | ordering.py | `order_id` | None | Check simulated order status |

---

## Repository Structure (Actual)

```
amaciver-arcade/
├── sushi_scout/                  # MCP server package (scaffolded with `arcade new`)
│   ├── src/sushi_scout/
│   │   ├── __init__.py
│   │   ├── __main__.py           # python -m sushi_scout entry point
│   │   ├── server.py             # MCPApp, imports tool modules
│   │   ├── agent.py              # CLI demo agent (demo + live modes)
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── search.py         # Google Places API tools + OAuth demo
│   │       ├── menu.py           # Synthetic menu generation
│   │       └── ordering.py       # Mock ordering flow
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py           # Shared fixtures (real SF API response data)
│   │   ├── test_search.py        # 14 tests: formatting, conversion
│   │   ├── test_menu.py          # 14 tests: generation, calibration, ranking
│   │   ├── test_ordering.py      #  6 tests: order IDs, cost math
│   │   └── test_evals.py         #  9 tests: price tiers, edge cases, perf
│   ├── test_oauth_flow.py        # Interactive OAuth test via STDIO MCP
│   ├── pyproject.toml
│   └── .env.example
├── api_testing/                  # API validation scripts (from research phase)
├── README.md                     # User-facing documentation
├── DEVELOPMENT_NOTES.md          # Detailed development log
├── claude.md                     # This file
└── .gitignore
```

---

## API Research Summary

We evaluated 10+ APIs for real menu/pricing data:

| API | Menu Items? | Prices? | Access | Verdict |
|-----|------------|---------|--------|---------|
| Google Places (New) | No | Price range only | Self-serve | **Use for discovery** |
| Google Business Profile | Yes | Yes | Owner-only | Can't read others' menus |
| OpenMenu | Yes (25M items) | Likely | "Contact us" | No free tier |
| Yelp Fusion | No | $/$$/$$$ | Paid ($8-15/1K) | Supplement only |
| DoorDash/UberEats/Grubhub | N/A | N/A | Merchant-only | Not viable |

**Conclusion:** No free public API provides structured menu items with prices for arbitrary restaurants. Our synthetic menus are calibrated to each restaurant's real `priceRange` from Google Places.

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Primary API | Google Places (New) | Rich restaurant data; tested with 10 SF results |
| Search auth | `requires_secrets` (API key) | Google Maps uses API keys; `cloud-platform` OAuth scope isn't in Arcade's default Google provider |
| OAuth demo | `get_user_profile` with `userinfo.email` | Demonstrates Arcade's OAuth flow with a scope that actually works |
| Menu data | Synthetic, calibrated to `priceRange` | No free menu API exists; calibration makes prices realistic |
| Ordering | Mock/simulated | Delivery platforms have no public ordering APIs |
| Tool registration | Module-level `@tool` | `arcade mcp` CLI can't discover tools inside closures |
| Agent framework | Custom CLI | Lightweight, focused on demonstrating MCP tool usage |
| Determinism | Seeded RNG per `place_id` | Same restaurant always gets same menu (reproducible tests) |

---

## Testing (44 tests, all passing)

```
tests/test_search.py    - 14 tests (miles-to-meters, place formatting, detail formatting)
tests/test_menu.py      - 14 tests (menu generation, price calibration, delivery, cheapest-finding)
tests/test_ordering.py  -  6 tests (order ID format/uniqueness, cost breakdown math)
tests/test_evals.py     -  9 tests (urban/suburban scenarios, price tier ordering, edge cases, perf)
```

Run: `cd sushi_scout && uv run pytest -v`

---

## Environment Variables

```bash
# .env (gitignored)
GOOGLE_PLACES_API_KEY=your_key    # Required for search tools (via requires_secrets)
ARCADE_API_KEY=your_arcade_key    # For Arcade platform access
```

The API key is injected into tools via Arcade's `context.get_secret()` mechanism. It reads from `.env` files and environment variables automatically.

---

## Development Guidelines for Claude/LLM Assistants

1. **Always run tests after changes** - `cd sushi_scout && uv run pytest -v`
2. **Use module-level `@tool` decorator** - NOT `@app.tool` inside closures (arcade CLI can't discover those)
3. **Prefer composition over complexity** - Keep tools focused, single-purpose
4. **Use type hints with `Annotated`** - Critical for MCP server tool parameter descriptions
5. **Handle errors gracefully** - Network failures, API limits, invalid inputs
6. **Windows encoding** - Always set `PYTHONIOENCODING=utf-8` for subprocess calls; use `errors="replace"` for stdout
7. **MCP transports** - HTTP for browser-based testing, STDIO for OAuth flows (OAuth tools can't run over HTTP transport)
8. **Commit frequently** - Small, atomic commits with clear messages
9. **Update this file** - Keep claude.md current as decisions evolve

---

## Resolved Decisions

- [x] **Project name:** sushi-scout
- [x] **Primary API:** Google Places (New) via API key (`requires_secrets`)
- [x] **OAuth demo:** `get_user_profile` with `userinfo.email` scope (supported by Arcade)
- [x] **Menu data:** Synthetic, calibrated to real `priceRange` from Google Places
- [x] **Auth for search:** API key (not OAuth - `cloud-platform` scope unsupported)
- [x] **No Yelp needed:** Google Places provides everything (ratings, delivery, price range, reviews)
- [x] **Ordering:** Mock/simulated with realistic flows
- [x] **Agent framework:** Custom CLI (lightweight, no framework overhead)
- [x] **Demo format:** CLI demo mode with `--demo` flag
- [x] **Tool registration:** Module-level `@tool`, not `@app.tool` closures
- [x] **Scaffold:** `arcade new sushi_scout` works well, adapted structure

## Open Questions / Remaining Work

- [ ] Run full interactive OAuth test (`test_oauth_flow.py`) to confirm `userinfo.email` flow end-to-end
- [ ] Demo format: video walkthrough TBD
- [ ] Final polish: review README for accuracy, add any missing setup steps

---

## What This Project Demonstrates

1. **Real API integration** - Google Places (New) for restaurant discovery with live data
2. **Arcade's `requires_secrets` pattern** - API keys injected via `context.get_secret()`
3. **Arcade's OAuth framework** - Google auth via `requires_auth=Google(scopes=[...])` with supported scopes
4. **Data modeling** - Synthetic menu generation calibrated to real price tiers
5. **Deterministic computation** - Seeded RNG for reproducible menus per restaurant
6. **Multi-tool orchestration** - Search -> menu -> price comparison -> ordering workflow
7. **Comprehensive testing** - 44 tests covering units, calibration, evals, and edge cases
8. **MCP protocol** - Tested over both HTTP and STDIO transports
