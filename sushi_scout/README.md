# Sushi Scout

**Find the cheapest tuna roll nearby** - an MCP server and CLI agent built with [Arcade.dev](https://arcade.dev).

Sushi Scout searches for real sushi restaurants near a location (via Google Places API), generates price-calibrated menus, ranks all tuna rolls by price, and optionally places a simulated order. All 7 tools are exposed via MCP for use with Claude Desktop, Cursor, or any MCP client.

---

## Quick Start

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- [Arcade CLI](https://docs.arcade.dev) (`uv tool install arcade-mcp`)

### 1. Clone and install

```bash
git clone https://github.com/amaciver/amaciver-arcade.git
cd amaciver-arcade/sushi_scout
uv sync --all-extras
```

### 2. Try the demo (no API key needed)

```bash
uv run python -m sushi_scout --demo
```

This runs the full workflow with sample SF restaurant data - discovery, menu generation, price comparison, and winner announcement. Add `--order` to see a simulated order placement.

### 3. Connect to a real MCP client

**Option A: Claude Desktop**

Add to your Claude Desktop config (`%APPDATA%\Claude\claude_desktop_config.json`):

> **Windows Store install?** The config is at `%LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "sushi-scout": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/amaciver-arcade/sushi_scout", "arcade", "mcp", "-p", "sushi_scout", "stdio"],
      "env": {
        "GOOGLE_PLACES_API_KEY": "your_key_here",
        "PYTHONIOENCODING": "utf-8"
      }
    }
  }
}
```

Restart Claude Desktop, then ask: *"Find me the cheapest tuna roll within 2 miles of downtown San Francisco"*

**Option B: HTTP transport (Cursor, VS Code, etc.)**

```bash
cp src/sushi_scout/.env.example .env
# Edit .env with your GOOGLE_PLACES_API_KEY

uv run arcade mcp -p sushi_scout http --debug
```

Server starts at `http://127.0.0.1:8000`. Connect your MCP client to that URL.

### 4. Run with real data from CLI

```bash
# Set up API key
cp src/sushi_scout/.env.example .env
# Edit .env: GOOGLE_PLACES_API_KEY=your_key

# Search real restaurants near SF
uv run python -m sushi_scout --lat 37.7749 --lng -122.4194 --radius 2.0
```

### 5. Run tests

```bash
uv run pytest -v
```

46 tests, all passing:

```
tests/test_search.py    - 14 tests (formatting, conversion, edge cases)
tests/test_menu.py      - 15 tests (generation, calibration, delivery consistency, ranking)
tests/test_ordering.py  -  6 tests (order IDs, cost math, response structure)
tests/test_evals.py     - 10 tests (price tiers, ranking, real API patterns, performance)
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     MCP Clients                         │
│   Claude Desktop  |  Cursor  |  VS Code  |  CLI Agent  │
└────────────────────────┬────────────────────────────────┘
                         │ MCP Protocol (STDIO or HTTP)
┌────────────────────────▼────────────────────────────────┐
│              Sushi Scout MCP Server                      │
│  (arcade-mcp-server, 7 tools)                            │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Layer 1: Restaurant Discovery (REAL DATA)               │
│  ├── search_nearby_restaurants  (Google Places API)      │
│  └── get_restaurant_details     (Google Places API)      │
│  Auth: API key (default) or OAuth (custom provider)      │
│                                                          │
│  Layer 2: Menu & Pricing (SYNTHETIC, CALIBRATED)         │
│  ├── get_restaurant_menu        (seeded RNG menus)       │
│  └── find_cheapest_tuna_roll    (cross-restaurant rank)  │
│  Prices calibrated to real priceRange from Google         │
│                                                          │
│  Layer 3: Ordering (SIMULATED)                           │
│  ├── place_order                (mock confirmation)      │
│  └── check_order_status         (mock timeline)          │
│                                                          │
│  OAuth Demo:                                             │
│  └── get_user_profile           (Google OAuth)           │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Why synthetic menus?

We evaluated 10+ APIs (Google Places, Yelp, Foursquare, OpenMenu, DoorDash, UberEats, Grubhub). No free public API provides structured menu items with prices for arbitrary restaurants. Our menus are calibrated to each restaurant's real `priceRange` from Google Places - an inexpensive restaurant generates $5-8 tuna rolls while an expensive one generates $14-20+.

---

## MCP Tools

| Tool | Description | Auth |
|------|-------------|------|
| `search_nearby_restaurants` | Find sushi restaurants by lat/lng + radius | API key or OAuth |
| `get_restaurant_details` | Get hours, reviews, delivery info for a restaurant | API key or OAuth |
| `get_user_profile` | Get authenticated user's Google profile | Google OAuth |
| `get_restaurant_menu` | Generate price-calibrated menu for a restaurant | None |
| `find_cheapest_tuna_roll` | Rank all tuna rolls across multiple restaurants | None |
| `place_order` | Simulate placing a delivery order | None |
| `check_order_status` | Check simulated order status | None |

---

## Project Structure

```
sushi_scout/
├── src/sushi_scout/
│   ├── server.py          # MCPApp entry point
│   ├── agent.py           # CLI demo agent (--demo and --live modes)
│   ├── __main__.py        # python -m sushi_scout support
│   └── tools/
│       ├── search.py      # Google Places API + OAuth demo (3 tools)
│       ├── menu.py        # Synthetic menu generation (2 tools)
│       └── ordering.py    # Mock ordering flow (2 tools)
├── tests/
│   ├── conftest.py        # Shared fixtures (real SF API response data)
│   ├── test_search.py     # Search tool formatting tests
│   ├── test_menu.py       # Menu generation & calibration tests
│   ├── test_ordering.py   # Order logic tests
│   └── test_evals.py      # End-to-end evaluation scenarios
├── test_oauth_flow.py     # Interactive OAuth test via STDIO MCP
├── pyproject.toml
└── .env.example
```

---

## Auth Setup

The search tools support two auth modes for the Google Places API, controlled by the `SUSHI_SCOUT_AUTH_MODE` environment variable.

### Option A: API Key (default, simplest)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable **Places API (New)**
3. Create an API key under **APIs & Services > Credentials**
4. Add it to your `.env`:

```bash
cd sushi_scout
cp src/sushi_scout/.env.example .env
# Edit .env:
GOOGLE_PLACES_API_KEY=your_key_here
```

The key is injected at runtime via Arcade's `context.get_secret()` pattern.

### Option B: OAuth (no API key needed for end users)

This mode uses a custom Arcade OAuth2 provider so end users authenticate via browser. Google Places API supports OAuth Bearer tokens with the `cloud-platform` scope.

> **Why a custom provider?** Arcade's built-in Google provider supports 15 scopes (calendar, contacts, gmail, etc.) but not `cloud-platform`. A custom OAuth2 provider lets you use any scope.

**Step 1: Create Google OAuth credentials**

1. In [Google Cloud Console](https://console.cloud.google.com/), enable **Places API (New)**
2. Create **OAuth client ID** (Web application)
3. Add redirect URI: `https://cloud.arcade.dev/api/v1/oauth/callback`
4. Add scope `https://www.googleapis.com/auth/cloud-platform` to consent screen
5. Note: `cloud-platform` is a sensitive scope. Use "Testing" mode (up to 100 users) for demos.

**Step 2: Register in Arcade**

Via Arcade Dashboard: **Connected Apps > Add OAuth Provider > OAuth 2.0**
- Provider ID: `google-places`
- Authorize: `https://accounts.google.com/o/oauth2/v2/auth`
- Token: `https://oauth2.googleapis.com/token`

Or via `engine.yaml` (self-hosted):
```yaml
auth:
  providers:
    - id: google-places
      type: oauth2
      client_id: ${env:GOOGLE_PLACES_CLIENT_ID}
      client_secret: ${env:GOOGLE_PLACES_CLIENT_SECRET}
      oauth2:
        authorize_request:
          endpoint: "https://accounts.google.com/o/oauth2/v2/auth"
        token_request:
          endpoint: "https://oauth2.googleapis.com/token"
        refresh_request:
          endpoint: "https://oauth2.googleapis.com/token"
```

**Step 3: Enable OAuth mode**

```bash
# In .env:
SUSHI_SCOUT_AUTH_MODE=oauth
GCP_PROJECT_ID=your-gcp-project-id
```

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Primary API | Google Places (New) | Rich restaurant data, real-time, self-serve |
| Search auth | Dual: API key or OAuth | API key is simpler; OAuth eliminates key setup for users |
| OAuth demo | `get_user_profile` | Demonstrates Arcade's OAuth with supported `userinfo.email` scope |
| Menu data | Synthetic, calibrated | No free public API has menu items; prices match real tiers |
| Ordering | Mock/simulated | Delivery platforms have no public ordering APIs |
| Determinism | Seeded RNG per place_id | Same restaurant always gets same menu (reproducible tests) |

## Testing Strategy

- **Unit tests**: Each helper function tested independently with real API response fixtures
- **Price calibration tests**: Verify INEXPENSIVE < MODERATE < EXPENSIVE < VERY_EXPENSIVE
- **Eval scenarios**: Urban high-density, suburban limited, edge cases (single restaurant, no delivery, missing metadata, 50-restaurant performance)
- **Determinism tests**: Same input always produces same output

---

## Development

This project was built as an Arcade.dev engineering interview submission. See [DEVELOPMENT_NOTES.md](DEVELOPMENT_NOTES.md) for a detailed log of the development process including all prompts, API research, architecture decisions, and gotchas encountered.

## Built With

- [Arcade MCP Server](https://docs.arcade.dev) - MCP server framework with OAuth and secrets management
- [Google Places API (New)](https://developers.google.com/maps/documentation/places/web-service) - Restaurant discovery
- [httpx](https://www.python-httpx.org/) - Async HTTP client
- [uv](https://docs.astral.sh/uv/) - Python package management
- [Claude Code](https://claude.com/claude-code) - AI-assisted development (Claude Opus 4.6)
