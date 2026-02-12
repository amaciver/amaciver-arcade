# Development Notes: Sushi-Scout Project

## Project Overview
**Goal:** Build an MCP server and agentic application that finds the cheapest plain tuna sushi roll available for delivery within a specified radius, with optional ordering capability.

**Context:** Arcade.dev engineering interview project - 6-hour time limit

**Repository:** amaciver-arcade

---

## Session Log

### Session 1: Planning & API Research
**Date:** 2026-02-10

#### User Prompt 1: Initial Project Brief
```
ok now here's a big picture plan. i have to come up with an agent toolkit that
leverages arcade's mcp servers. i'm going to want everything to be pushed up into
the git project we just created. (amaciver-arcade) we also have an instructions
guide for reference https://docs.google.com/document/d/1hx_me4SfLAFkGl22h3A77oFJ8ZjBGkolsFU6GyyjK08/edit?tab=t.0
as well as the whole arcade-mcp git project and these https://docs.arcade.dev/llms.txt
which contains some examples. we are going to want to not only develop the overall
toolkit and mcp servers, but also make sure we have really good tests and evals.
My idea will focus around a new toolkit that can be used to find the cheapest plain
tuna sushi roll within a given radius at any one time that's available for delivery,
and then optionally order it. let's start with a plan and decide what we need to
write to claude.md. ready to start thinking through this problem?
```

**Actions Taken:**
- Fetched Arcade documentation from https://docs.arcade.dev/llms.txt
- Analyzed interview requirements from provided instructions
- Drafted comprehensive project plan in claude.md

**Key Decisions Made:**
1. **Project Name:** sushi-scout (finalized by user)
2. **Initial Architecture Approach:**
   - MCP Server with 3-4 tools (search, menu fetch, price comparison, ordering)
   - Agent layer (OpenAI SDK, LangChain, or custom)
   - Initially proposed synthetic menu data + mock ordering

#### User Prompt 2: API Preference
```
the synthetic approach sounds ok, but i would like to figure out if there is an
alternative with real APIs. i like the name sushi-scout. let's dial in our APIs
and data sources first since this will guide our overall viability and approach.
the md file looks good and overall the plan is sound. Let's start working through
each portion starting with these next steps
```

**Actions Taken:**
- Comprehensive API research across multiple platforms
- Evaluated real-world API availability and pricing

**API Research Findings:**

| API | Menu Items? | Prices? | Access | Verdict |
|-----|------------|---------|--------|---------|
| Google Places (New) | No | Price range only | Self-serve | **Use for discovery** |
| Google Business Profile | Yes | Yes | Owner-only | Can't read others' menus |
| OpenMenu | Yes (25M items) | Likely | "Contact us" | No free tier |
| Yelp Fusion | No | $/$$/$$$ | Paid ($8-15/1K) | Supplement only |
| Foursquare | No | No | Free tier | Similar to Google |
| DoorDash/UberEats/Grubhub | N/A | N/A | Merchant-only | Not viable |

**Conclusion:** No free public API provides structured menu items with prices for arbitrary restaurants.

#### User Prompt 3: Documentation Request
```
before i answer that question i want to start a notes file in this repo to capture
our whole process, could you start a notes file which contains my prompts and a
running summary of what we are working on and achieving together. after that i want
to return to this step about API research
```

**Actions Taken:**
- Created DEVELOPMENT_NOTES.md (this file)
- Captured all prompts and decision-making process

#### User Prompt 4: API Testing
```
key is in there, can you run these next commands?
```

**Actions Taken:**
- Set up `.env` file with Google Places API key (gitignored)
- Fixed Windows cp1252 encoding issue in test script
- Fixed hatchling build config (added `[tool.hatch.build.targets.wheel]`)
- Ran comprehensive Google Places API test against SF sushi restaurants

**Google Places API Test Results:**
```
Restaurants found:       10
Restaurants tested:      5
Have delivery flag:      2/5
Have website URL:        5/5
Have reviews:            5/5
Have price level:        3/5
Have price range:        4/5 (e.g. {"startPrice": {"currencyCode": "USD", "units": "20"}, "endPrice": {"currencyCode": "USD", "units": "30"}})
Have structured menus:   0/5 (field does NOT exist in API)
```

**Critical Finding:** Google Places API does NOT provide structured menu data.
The `menuItems` and `menu` fields don't exist. However, `priceRange` gives us
actual dollar ranges we can use to calibrate synthetic menu data.

#### User Prompt 5: Explore More APIs
```
sure we can proceed with this layered approach. question -- let's put a flag in
trying to find real menu data, any other approaches we could consider on top of
google places?
```

**Actions Taken:**
- Deep research into 7+ additional APIs
- Found Google Business Profile has menu data but is owner-only (can't read others' menus)
- OpenMenu has 25M items but requires contacting sales for access
- FoodSpark is a commercial scraping service (too expensive)
- **Conclusion: No free public API provides structured menu items with prices**

#### User Prompt 6: OAuth Approach
```
sure we can proceed with this layered approach. question -- what if we searched
the maps using the users identity instead of our own api key, is that possible?
```

```
yes let's use this approach instead of api key for sure...
```

**Actions Taken:**
- Researched Arcade's Google OAuth provider support
- Confirmed Arcade supports Google auth with `context.get_auth_token_or_empty()`
- Decided to use Arcade Google OAuth as PRIMARY auth (not API key)
- Updated claude.md with finalized 3-layer architecture

**Architecture Decision: Arcade Google OAuth**
This was a pivotal decision at the time. Instead of hardcoding a shared API key:
1. User authenticates via Arcade's built-in Google OAuth
2. Tool retrieves token at runtime via `context.get_auth_token_or_empty()`
3. Calls Google Places API with user's identity
4. No shared secrets in repo

*Note: This decision was later revised in Session 2 when we discovered the
`cloud-platform` scope is not supported by Arcade's default Google provider.*

---

#### User Prompt 7: Scaffold and Implement
```
ok sorted. let's get back to work now that the newest version is installed and
i have successfully logged in
```

**Actions Taken:**
- Installed `arcade-mcp` v1.9.0 via `uv tool install` (replaced old `arcade-ai` v2.2.3)
- `arcade-mcp` brings newer core: arcade-core 4.2.3, arcade-tdk 3.4.0, arcade-mcp-server 1.15.2
- Ran `arcade new sushi_scout` - generated scaffold at `sushi_scout/`
- Analyzed scaffold: learned `MCPApp`, `@app.tool`, `Context`, auth provider patterns
- Confirmed `Google` auth provider available with custom scopes
- Implemented 6 tools across 3 modules:
  - `tools/search.py`: search_nearby_restaurants, get_restaurant_details (initially with Google OAuth)
  - `tools/menu.py`: get_restaurant_menu, find_cheapest_tuna_roll (synthetic data)
  - `tools/ordering.py`: place_order, check_order_status (mock)
- All tools registered successfully, ruff lint passing clean

#### User Prompt 8: Tests and Evals
```
tests and evals (and make sure we are updates our dev notes along the way please)
```

**Actions Taken:**
- Created comprehensive test suite: 44 tests across 4 files
- All 44 tests passing in 1.68s

**Test Structure:**
```
tests/
├── conftest.py          # Shared fixtures (real SF API response data)
├── test_search.py       # 14 tests: formatting, conversion, edge cases
├── test_menu.py         # 14 tests: generation, calibration, delivery, ranking
├── test_ordering.py     #  6 tests: order IDs, cost math, response structure
└── test_evals.py        #  9 tests: price tiers, ranking, edge cases, performance
```

#### User Prompt 9: Agent Application & Checkpoint
```
yep let's get this first version dialed in and finished so we can test it end to end,
push a checkpoint and then ideate about next steps
```

**Actions Taken:**
- Built CLI agent application (`agent.py` + `__main__.py`)
- Implemented demo mode with 5 sample SF restaurants spanning 3 price tiers
- Full workflow: discovery -> menu analysis -> price comparison -> optional ordering
- User corrected approach when API key fallback was used as primary
- CLI entry: `uv run python -m sushi_scout --demo` (sample data, no API needed)
- Demo output verified: 5 restaurants, 7 tuna rolls, cheapest at $4.99

**Key User Correction:**
User explicitly rejected API key approach for the agent, saying:
```
hey i thought we were going with an oauth approach?
```
Response: Refactored agent to be a demo/testing tool only. The real user experience
uses the MCP server with Arcade OAuth - no API keys needed.

**Commits Made:**
1. `aa67498` - Initial commit (26 files, 3546 lines)

---

### Session 2: End-to-End Testing & Auth Refactoring
**Date:** 2026-02-11

#### User Prompt 10: End-to-End MCP Testing
```
let's test it end-to-end
```

**Actions Taken:**
- Started MCP server with `arcade mcp http --package sushi_scout --port 9000`
- Hit first bug: `module 'sushi_scout.tools.menu' has no attribute 'get_restaurant_menu'`

**Critical Discovery: Tool Registration Pattern**
The `arcade mcp` CLI discovers tools at **module level**. Tools defined inside
`register_tools(app)` closures using `@app.tool` are NOT discoverable. The fix
was to refactor all tools from:
```python
# BROKEN: arcade mcp can't discover these
def register_tools(app):
    @app.tool(requires_auth=...)
    async def my_tool(context, ...):
        ...
```
to:
```python
# WORKS: module-level @tool decorator
from arcade_mcp_server import tool
@tool(requires_secrets=["KEY"])
async def my_tool(context, ...):
    ...
```

After refactoring all 3 tool modules and updating `server.py` to use bare imports
instead of `register_tools()` calls, all 6 tools loaded correctly.

**MCP Protocol Testing (HTTP Transport):**
- Full JSON-RPC handshake: `initialize` -> `notifications/initialized` -> `tools/list` -> `tools/call`
- `tools/list` returned all 6 tools with correct schemas and OAuth metadata
- Called `GetRestaurantMenu` and `FindCheapestTunaRoll` successfully via MCP protocol
- Budget Sushi ($4.99) vs Fancy Omakase ($18.99+) - price calibration confirmed working

**Commits Made:**
2. `4d03d02` - Refactor tools to module-level @tool decorators for arcade CLI discovery

#### User Prompt 11: OAuth Verification
```
can we verify the oauth part next?
```

**Actions Taken:**
- First tried HTTP transport for OAuth tools: got "Unsupported transport" error
- Discovered OAuth-requiring tools can only run via STDIO transport (security restriction)
- Switched to `arcade mcp stdio --package sushi_scout`

**STDIO Transport Debugging:**
Multiple issues discovered and fixed:
1. **Wrong framing**: First tried Content-Length LSP-style framing; `arcade mcp stdio` uses raw JSON + newline framing
2. **Windows encoding**: cp1252 can't encode Unicode chars (checkmarks, etc.) in Arcade's output; fixed with `PYTHONIOENCODING=utf-8` env var
3. Created `test_oauth_flow.py` - interactive STDIO MCP test script

**Critical OAuth Scope Discovery:**
When calling the search tool (which used `requires_auth=Google(scopes=["cloud-platform"])`), Arcade returned:
```
invalid authorization challenge: requesting unsupported scopes: https://www.googleapis.com/auth/cloud-platform
```

Researched Arcade's default Google OAuth provider supported scopes:
- **Supported:** calendar, contacts, drive.file, gmail, userinfo, openid
- **NOT supported:** cloud-platform, maps-platform

This meant our entire auth approach needed to change. Google Maps APIs use API keys
(not OAuth tokens), so OAuth was never the right pattern for Places API anyway.

#### Auth Refactoring

**Actions Taken:**
1. Changed `search_nearby_restaurants` and `get_restaurant_details` from
   `requires_auth=Google(scopes=["cloud-platform"])` to `requires_secrets=["GOOGLE_PLACES_API_KEY"]`
2. Changed from `context.get_auth_token_or_empty()` + `Authorization: Bearer` header
   to `context.get_secret("GOOGLE_PLACES_API_KEY")` + `X-Goog-Api-Key` header
3. Added new `get_user_profile` tool using `requires_auth=Google(scopes=["userinfo.email", "openid"])`
   to demonstrate Arcade's OAuth flow with a supported scope
4. Updated `test_oauth_flow.py` to test the new OAuth demo tool instead
5. All 44 tests still passing
6. Server now loads 7 tools (6 original + `get_user_profile`)

**Commits Made:**
3. `3b62460` - Fix auth: use API key for Places, add OAuth demo with supported scope

#### User Prompt 12: Documentation Sync
```
let's take a pause and recap where we are at, importantly i really want to make
sure the claude.md file and the dev notes are really good and in sync
```

**Actions Taken:**
- Comprehensive audit of all 3 docs (claude.md, DEVELOPMENT_NOTES.md, README.md)
- Identified major discrepancies between docs and reality
- Updated all 3 documents to match actual implementation

---

## Current Status

### Completed
- [x] Project planning and architecture design
- [x] Comprehensive API research (10+ APIs evaluated)
- [x] Google Places API testing (confirmed: search works, no menu data)
- [x] Menu data API exhaustive search (no free option exists)
- [x] Architecture finalized (3-layer: real discovery + synthetic menus + mock ordering)
- [x] MCP server scaffolded with `arcade new sushi_scout`
- [x] 7 tools implemented (search, menu, ordering, OAuth demo)
- [x] Tool registration refactored from `@app.tool` closures to module-level `@tool`
- [x] Auth refactored: API key for Places, OAuth demo with `userinfo.email`
- [x] 44 tests written and all passing
- [x] Eval scenarios covering price calibration, ranking, and edge cases
- [x] Agent application built with demo mode
- [x] End-to-end MCP protocol testing (HTTP transport) - all tools work
- [x] STDIO transport debugging (framing, encoding) - working
- [x] README.md written with setup and usage instructions
- [x] `test_oauth_flow.py` created for interactive OAuth testing
- [x] Documentation synced (claude.md, DEVELOPMENT_NOTES.md, README.md)
- [x] All commits pushed to remote

### Remaining Work
- [ ] Run full interactive OAuth test (`test_oauth_flow.py`) to confirm `userinfo.email` flow end-to-end
- [ ] Demo format: video walkthrough TBD
- [ ] Final polish and review

---

## Key Technical Decisions (FINALIZED)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Project Name | sushi-scout | User preference, clear and descriptive |
| Primary API | Google Places API (New) | Confirmed: rich restaurant data (10 results in SF test) |
| Search Auth | `requires_secrets=["GOOGLE_PLACES_API_KEY"]` | Google Maps uses API keys; `cloud-platform` OAuth scope unsupported by Arcade |
| OAuth Demo | `get_user_profile` with `userinfo.email` scope | Demonstrates Arcade's OAuth flow with a scope that works |
| Menu Data | Synthetic (calibrated to real priceRange) | No public API exists for menu items; calibration makes it realistic |
| Ordering | Mock/simulated | Delivery platforms have no public ordering APIs |
| No Yelp | Dropped | Google Places provides everything needed |
| Tool Registration | Module-level `@tool` decorator | `arcade mcp` CLI can't discover tools inside closures |
| Agent Framework | Custom CLI | Lightweight, focused on MCP tool usage demo |

---

## Resolved Questions
- [x] Google Places has NO menu data (tested, confirmed)
- [x] No free API anywhere has structured menu items with prices
- [x] Google Places DOES have: priceRange, delivery flag, ratings, reviews, hours
- [x] Arcade DOES support Google OAuth providers (but only specific scopes)
- [x] `cloud-platform` scope is NOT supported by Arcade's default Google provider
- [x] Google Maps APIs use API keys, not OAuth tokens
- [x] Only Google Places needed (Yelp dropped - redundant)
- [x] Agent framework: Custom CLI (lightweight, no framework overhead)
- [x] Tool registration: Module-level `@tool` (not `@app.tool` inside closures)
- [x] `arcade mcp stdio` uses raw JSON + newline framing (not Content-Length LSP framing)
- [x] OAuth tools can only run via STDIO transport (not HTTP)
- [ ] Demo format: CLI demo working, video walkthrough TBD

---

## Gotchas & Lessons Learned

1. **`arcade mcp` tool discovery**: Tools must be at module level with `@tool` decorator. The `@app.tool` pattern inside `register_tools()` closures (from the scaffold example) is NOT discoverable by the CLI.

2. **Google Maps APIs use API keys, not OAuth**: The `cloud-platform` scope needed for Google Maps APIs is not in Arcade's default Google OAuth provider. Use `requires_secrets` + `context.get_secret()` instead.

3. **Arcade Google OAuth supported scopes**: Only calendar, contacts, drive.file, gmail, userinfo, openid. No maps/cloud-platform.

4. **STDIO transport framing**: `arcade mcp stdio` uses raw JSON + newline framing (NOT Content-Length LSP-style framing).

5. **HTTP transport blocks OAuth**: Tools with `requires_auth` can only be called via STDIO transport, not HTTP. Security restriction.

6. **Windows cp1252 encoding**: Arcade's output contains Unicode symbols that Windows console can't render. Always set `PYTHONIOENCODING=utf-8` for subprocess calls.

---

## Resources & References

### Documentation
- [Arcade MCP Python Overview](https://docs.arcade.dev/llms.txt)
- [Google Places API (New)](https://developers.google.com/maps/documentation/places/web-service/overview)
- [Google Business Profile Menus](https://developers.google.com/my-business/content/update-food-menus) (owner-only)

### APIs Evaluated (Exhaustive)
- Google Places API (New) - **USING** for restaurant discovery
- Google Business Profile - Menu data exists but owner-only access
- Yelp Fusion API - Redundant, dropped
- Foursquare Places API - Similar to Google, no menu items
- OpenMenu API - 25M items but no free tier
- FoodSpark - Commercial scraping service
- SerpAPI Google Food - Same data as Places, no menu items
- DoorDash API - Merchant-only
- Uber Eats API - Partner-only
- Grubhub API - Merchant-only

---

## Development Environment

**Current Directory:** `c:\Users\maciv\code\amaciver-arcade`

**Tools Installed:**
- `uv` v0.10.2 (package manager)
- Python 3.14.3 (via uv)
- `arcade-mcp` v1.9.0 (arcade-core 4.2.3, arcade-tdk 3.4.0, arcade-mcp-server 1.15.2)

**Git History:**
```
3b62460 Fix auth: use API key for Places, add OAuth demo with supported scope
4d03d02 Refactor tools to module-level @tool decorators for arcade CLI discovery
aa67498 Initial commit: Sushi Scout MCP server and agent
```

---

*This document is actively maintained. All prompts, decisions, and progress updates are logged here.*
