# Sushi Scout

**Find the cheapest tuna roll nearby** - an MCP server and agent built with [Arcade.dev](https://arcade.dev).

Sushi Scout searches for sushi restaurants near a location, generates price-calibrated menus, ranks all available tuna rolls by price, and optionally places a simulated order - all exposed as MCP tools for use with Claude Desktop, Cursor, or any MCP client.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   MCP Clients                       │
│   Claude Desktop  |  Cursor  |  VS Code  |  CLI    │
└───────────────────────┬─────────────────────────────┘
                        │ MCP Protocol
┌───────────────────────▼─────────────────────────────┐
│              Sushi Scout MCP Server                  │
│  (arcade-mcp-server, 6 tools, Google OAuth)          │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Layer 1: Restaurant Discovery (REAL DATA)           │
│  ├── search_nearby_restaurants (Google Places API)   │
│  └── get_restaurant_details   (Google Places API)    │
│  Auth: Arcade Google OAuth (per-user identity)       │
│                                                      │
│  Layer 2: Menu & Pricing (SYNTHETIC, CALIBRATED)     │
│  ├── get_restaurant_menu      (seeded RNG menus)     │
│  └── find_cheapest_tuna_roll  (cross-restaurant)     │
│  Prices calibrated to real priceRange from Google     │
│                                                      │
│  Layer 3: Ordering (SIMULATED)                       │
│  ├── place_order              (mock confirmation)    │
│  └── check_order_status       (mock timeline)        │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### Why synthetic menus?

We evaluated 10+ APIs (Google Places, Yelp, Foursquare, OpenMenu, DoorDash, UberEats, Grubhub, etc.). No free public API provides structured menu items with prices for arbitrary restaurants. Our synthetic menus are calibrated to each restaurant's real `priceRange` from Google Places, so an inexpensive restaurant generates $5-8 tuna rolls while an expensive one generates $14-20+.

## Quick Start

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- [Arcade CLI](https://docs.arcade.dev) (`uv tool install arcade-mcp`)

### 1. Clone and install

```bash
git clone https://github.com/amaciver/amaciver-arcade.git
cd amaciver-arcade/sushi_scout
uv sync --all-extras
```

### 2. Run the demo (no API key needed)

```bash
uv run python -m sushi_scout --demo
```

This runs the full workflow with sample data:
- 5 SF sushi restaurants across 3 price tiers
- Menu generation with tuna roll pricing
- Price comparison and ranking
- Winner announcement

Add `--order` to see a simulated order:

```bash
uv run python -m sushi_scout --demo --order
```

### 3. Run the MCP server (full experience)

The primary way to use Sushi Scout is through the MCP server with Arcade OAuth:

```bash
# Start the MCP server (HTTP transport for Cursor/VS Code)
cd sushi_scout
uv run arcade mcp http --package sushi_scout --debug

# Or stdio transport for Claude Desktop
uv run arcade mcp stdio --package sushi_scout
```

Then connect from your MCP client (Claude Desktop, Cursor, etc.) and ask:

> "Find me the cheapest tuna roll within 2 miles of downtown San Francisco"

The server handles Google OAuth automatically - no API keys needed for end users.

### 4. Run tests

```bash
cd sushi_scout
uv run pytest -v
```

All 44 tests should pass:

```
tests/test_search.py    - 14 tests (formatting, conversion, edge cases)
tests/test_menu.py      - 14 tests (generation, calibration, delivery, ranking)
tests/test_ordering.py  -  6 tests (order IDs, cost math, response structure)
tests/test_evals.py     -  9 tests (price tiers, ranking, edge cases, performance)
```

## MCP Tools

| Tool | Description | Auth |
|------|-------------|------|
| `search_nearby_restaurants` | Find sushi restaurants by location + radius | Google OAuth |
| `get_restaurant_details` | Get hours, reviews, delivery info for a restaurant | Google OAuth |
| `get_restaurant_menu` | Generate price-calibrated menu for a restaurant | None |
| `find_cheapest_tuna_roll` | Rank all tuna rolls across multiple restaurants | None |
| `place_order` | Simulate placing a delivery order | None |
| `check_order_status` | Check simulated order status | None |

## Project Structure

```
sushi_scout/
├── src/sushi_scout/
│   ├── server.py          # MCPApp entry point, registers all tools
│   ├── agent.py           # CLI demo agent
│   ├── __main__.py        # python -m sushi_scout support
│   └── tools/
│       ├── search.py      # Google Places API integration (OAuth)
│       ├── menu.py        # Synthetic menu generation (price-calibrated)
│       └── ordering.py    # Mock ordering flow
├── tests/
│   ├── conftest.py        # Shared fixtures (real SF API response data)
│   ├── test_search.py     # Search tool formatting tests
│   ├── test_menu.py       # Menu generation & calibration tests
│   ├── test_ordering.py   # Order logic tests
│   └── test_evals.py      # End-to-end evaluation scenarios
├── pyproject.toml         # Dependencies and build config
└── .env.example           # Environment variable template
```

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Primary API | Google Places (New) | Rich restaurant data, real-time, via Arcade OAuth |
| Auth | Arcade Google OAuth | Demonstrates Arcade's core value prop, no shared secrets |
| Menu data | Synthetic, calibrated | No free public API has menu items; prices match real tiers |
| Ordering | Mock/simulated | Delivery platforms have no public ordering APIs |
| Agent framework | Custom CLI | Lightweight, focused on demonstrating MCP tool usage |
| Determinism | Seeded RNG per place_id | Same restaurant always gets same menu (reproducible tests) |

## Testing Strategy

- **Unit tests**: Each helper function tested independently with real API response fixtures
- **Price calibration tests**: Verify INEXPENSIVE < MODERATE < EXPENSIVE < VERY_EXPENSIVE
- **Eval scenarios**: Urban high-density, suburban limited, edge cases (single restaurant, no delivery, missing metadata, 50-restaurant performance)
- **Determinism tests**: Same input always produces same output

## Development

This project was built as an Arcade.dev engineering interview submission. See [DEVELOPMENT_NOTES.md](DEVELOPMENT_NOTES.md) for a detailed log of the development process, including all prompts, API research, architecture decisions, and implementation details.

### API key fallback (testing only)

For local testing without OAuth, set `GOOGLE_PLACES_API_KEY` in a `.env` file:

```bash
cp sushi_scout/.env.example sushi_scout/.env
# Edit .env with your Google Places API key
uv run python -m sushi_scout --lat 37.7749 --lng -122.4194 --radius 2.0
```

## Built With

- [Arcade MCP Server](https://docs.arcade.dev) - MCP server framework with OAuth
- [Google Places API (New)](https://developers.google.com/maps/documentation/places/web-service) - Restaurant discovery
- [httpx](https://www.python-httpx.org/) - Async HTTP client
- [uv](https://docs.astral.sh/uv/) - Python package management
- [Claude Code](https://claude.com/claude-code) - AI-assisted development (all code generated with Claude Opus 4.6)
