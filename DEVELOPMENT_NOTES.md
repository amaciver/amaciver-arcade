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

✅ **VIABLE OPTIONS (Real Data):**

1. **Google Places API (New) - PRIMARY CHOICE**
   - ✅ Has actual structured menu data with prices
   - Access via Place Details endpoint with "Business Menus" field
   - Pricing: $32-40 per 1000 requests ($0.032-0.04 per call)
   - $200/month free credit available
   - Self-serve signup
   - Best option for real menu + pricing data

2. **Yelp Fusion API - SECONDARY CHOICE**
   - Restaurant search, ratings, price levels ($, $$, $$$)
   - Limited structured menu data
   - Pricing: $7.99-14.99 per 1000 calls
   - Good for restaurant discovery and validation

3. **Foursquare Places API - BACKUP**
   - 100M+ POI database
   - Has 'hasMenu' field
   - Rich metadata (photos, reviews, popularity)

4. **OpenMenu API - NICHE**
   - 550K+ menus, 25M+ menu items
   - Nutrition info and pricing
   - API details not fully researched yet

❌ **NOT VIABLE (Merchant-Only APIs):**
- DoorDash Marketplace API - Not accepting new partners
- Uber Eats API - Requires partner manager approval
- Grubhub API - Merchant integrations only

**Recommended Architecture (Updated):**
```
Primary: Google Places API
├─ Search restaurants by location + radius
├─ Get Place Details with menu data
└─ Extract tuna roll prices from structured menus

Secondary: Yelp Fusion API
├─ Validate restaurant quality (ratings/reviews)
├─ Get additional metadata
└─ Cross-reference results

Fallback: Synthetic data for demo
└─ If API limits hit or restaurants lack menu data
```

**Cost Analysis:**
- Google Places: ~$0.035/request × 10 restaurants = $0.35 per search
- Yelp: ~$0.008/request × 10 restaurants = $0.08 per search
- **Total per search: ~$0.43** (reasonable for demos)
- With $200 Google credit: ~5,700 searches free

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
- Ready to continue API research and validation

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
- Confirmed Arcade supports Google auth with Context.get_oauth_token()
- Decided to use Arcade Google OAuth as PRIMARY auth (not API key)
- Updated claude.md with finalized 3-layer architecture
- Updated all resolved decisions

**Architecture Decision: Arcade Google OAuth**
This was a pivotal decision. Instead of hardcoding a shared API key:
1. User authenticates via Arcade's built-in Google OAuth
2. Tool retrieves token at runtime via `context.get_oauth_token("google")`
3. Calls Google Places API with user's identity
4. No shared secrets in repo
5. Demonstrates Arcade's core auth value proposition

---

#### User Prompt 7: Scaffold and Implement
```
ok sorted. let's get back to work now that the newest version is installed and
i have successfully logged in
```
```
great
```

**Actions Taken:**
- Installed `arcade-mcp` v1.9.0 via `uv tool install` (replaced old `arcade-ai` v2.2.3)
- `arcade-mcp` brings newer core: arcade-core 4.2.3, arcade-tdk 3.4.0, arcade-mcp-server 1.15.2
- Ran `arcade new sushi_scout` - generated scaffold at `sushi_scout/`
- Analyzed scaffold: learned `MCPApp`, `@app.tool`, `Context`, auth provider patterns
- Confirmed `Google` auth provider available with custom scopes
- Implemented 6 tools across 3 modules:
  - `tools/search.py`: search_nearby_restaurants, get_restaurant_details (Google OAuth)
  - `tools/menu.py`: get_restaurant_menu, find_cheapest_tuna_roll (synthetic data)
  - `tools/ordering.py`: place_order, check_order_status (mock)
- All tools registered successfully, ruff lint passing clean

**Scaffold Discovery:**
The `arcade new` scaffold provided a clear pattern:
```python
from arcade_mcp_server import Context, MCPApp
from arcade_mcp_server.auth import Google  # (was Reddit in scaffold)

app = MCPApp(name="sushi_scout", version="0.1.0")

@app.tool(requires_auth=Google(scopes=["..."]))
async def my_tool(context: Context, ...) -> dict:
    token = context.get_auth_token_or_empty()
    # use token for API calls
```

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

**Test Coverage Breakdown:**
- `test_search.py`: Miles-to-meters conversion, place formatting (complete/missing/empty), detail formatting (reviews, hours, caps)
- `test_menu.py`: Tuna roll generation, determinism, price calibration per tier, delivery info, cheapest-finding logic
- `test_ordering.py`: Order ID format/uniqueness, cost breakdown math
- `test_evals.py`: Urban high-density scenario, suburban limited options, price tier ordering validation, delivery total ranking, edge cases (single restaurant, no delivery, no metadata, 50-restaurant performance)

**Key Eval Results:**
- Price tier ordering is correct: INEXPENSIVE avg < MODERATE avg < EXPENSIVE avg < VERY_EXPENSIVE avg
- Cheapest tuna roll consistently comes from INEXPENSIVE tier restaurants
- System handles 50 restaurants without issues
- Deterministic output confirmed (same restaurant = same menu every time)

---

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
- Refactored agent to emphasize OAuth via MCP as primary path
- CLI entry: `uv run python -m sushi_scout --demo` (sample data, no API needed)
- Demo output verified: 5 restaurants, 7 tuna rolls, cheapest at $4.99

**Agent Architecture:**
```
CLI Agent (agent.py)
├── Demo mode: 5 hardcoded SF restaurants (3 price tiers)
├── Live mode: API key fallback for testing (NOT primary)
├── Workflow: search -> generate menus -> rank by price -> optional order
└── Primary path: MCP server via `arcade mcp http --package sushi_scout`
```

**Key User Correction:**
User explicitly rejected API key approach for the agent, saying:
```
hey i thought we were going with an oauth approach?
```
Response: Refactored agent to be a demo/testing tool only. The real user experience
uses the MCP server with Arcade OAuth - no API keys needed.

---

## Current Status

### Completed
- [x] Project planning and architecture design
- [x] Comprehensive API research (8+ APIs evaluated)
- [x] Google Places API testing (confirmed: search works, no menu data)
- [x] Menu data API exhaustive search (no free option exists)
- [x] Auth strategy decided (Arcade Google OAuth)
- [x] Architecture finalized (3-layer: real discovery + synthetic menus + mock ordering)
- [x] claude.md fully updated with finalized decisions
- [x] MCP server scaffolded with `arcade new sushi_scout`
- [x] 6 tools implemented (search, menu, ordering)
- [x] 44 tests written and all passing
- [x] Eval scenarios covering price calibration, ranking, and edge cases
- [x] Agent application built with demo mode
- [x] Agent refactored to emphasize OAuth-first approach
- [x] README.md written with setup and usage instructions
- [x] Checkpoint commit pushed

### Next Steps
1. Test MCP server end-to-end via `arcade mcp http`
2. Ideate improvements (web UI, more tools, etc.)
3. Final polish and documentation

---

## Key Technical Decisions (FINALIZED)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Project Name | sushi-scout | User preference, clear and descriptive |
| Primary API | Google Places API (New) | Confirmed: rich restaurant data (10 results in SF test) |
| Auth Strategy | Arcade Google OAuth | Demonstrates Arcade's core value prop, no shared secrets |
| Menu Data | Synthetic (calibrated to real priceRange) | No public API exists for menu items; calibration makes it realistic |
| Ordering | Mock/simulated | Delivery platforms have no public ordering APIs |
| No Yelp | Dropped | Google Places provides everything needed |
| Auth Fallback | API key via .env | For testing/CI where OAuth isn't available |

---

## Resolved Questions
- [x] Google Places has NO menu data (tested, confirmed)
- [x] No free API anywhere has structured menu items with prices
- [x] Google Places DOES have: priceRange, delivery flag, ratings, reviews, hours
- [x] Arcade DOES support Google OAuth providers
- [x] Only Google Places needed (Yelp dropped - redundant)
- [x] OAuth is the primary auth approach (not API key)

## Open Questions
- [x] Agent framework choice: Custom CLI (lightweight, no framework overhead)
- [x] Exact Google OAuth scope: `https://www.googleapis.com/auth/cloud-platform`
- [x] `arcade new` scaffold: Works well, adapted with register_tools() pattern
- [ ] Demo format: CLI demo working, video walkthrough TBD

---

## Resources & References

### Documentation
- [Arcade MCP Python Overview](https://docs.arcade.dev/llms.txt)
- [Google Places API (New)](https://developers.google.com/maps/documentation/places/web-service/overview)
- [Google Business Profile Menus](https://developers.google.com/my-business/content/update-food-menus) (owner-only)
- [OpenMenu API](https://openmenu.com/api/) (requires sales contact)

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

**Files Created:**
- `claude.md` - Project plan and guidelines (updated with finalized architecture)
- `DEVELOPMENT_NOTES.md` - This file
- `api_testing/` - API validation scripts and environment
  - `google_places_test.py` - Tested, confirmed API capabilities
  - `pyproject.toml` - uv project config
  - `.env` - API key (gitignored)
- `API_SETUP_GUIDE.md` - API key setup instructions
- `SETUP_INSTRUCTIONS.md` - Quick start guide
- `.gitignore` - Protects secrets

---

*This document is actively maintained. All prompts, decisions, and progress updates are logged here.*
