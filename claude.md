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
Testing: Your tests are comprehensive and accurately validate your toolkit’s functionality.
Documentation: Clear instructions and documentation are provided.
Originality: Your toolkit is unique from existing Arcade AI toolkits, and your application does something useful or interesting.
Tips for Success
Plan Before Coding: Outline the functionality you want to build; plan how the arcade new generated scaffold can help you.
Focus on Core Features: Due to the 6-hour limit, implement the features with the highest impact.
Ensure Reproducibility: Anyone should be able to clone your repo and run the toolkit without issues.
Document Your Work: Clear, concise documentation will help others understand your toolkit’s usage and benefits. Provide images or videos if that helps.
On Site or Remote
If you are interested in compressing your interview experience to a single day, you can do the take-home assignment from our office in San Francisco! You can work on the assignment in the morning, and then we can review it with you in the afternoon. Lunch will be included.

---

# PROJECT PLAN: Cheap Sushi Finder & Orderer

## Project Concept
**Name:** `sushi-scout` (or `tuna-hunter`, `sushi-deal-finder`)

**Goal:** Build an MCP server and agentic application that finds the cheapest plain tuna sushi roll available for delivery within a specified radius, with optional ordering capability.

**Value Prop:** Combines location-based search, price comparison, and real-time availability checking - showcases API integration, data processing, and actionable decision-making in a practical use case.

---

## Architecture

### MCP Server: `sushi-scout-mcp`
**Tools to Expose:**
1. `search_nearby_restaurants(location, radius_miles, cuisine_filter)`
   - Returns list of Japanese/sushi restaurants in radius
   - Uses Google Places API or similar

2. `get_restaurant_menu(restaurant_id, platform)`
   - Fetches menu data from delivery platform
   - Extracts sushi roll items with prices

3. `find_cheapest_tuna_roll(location, radius_miles)`
   - Orchestrates search → menu fetch → price comparison
   - Returns ranked list with availability, price, delivery time

4. `place_order(restaurant_id, item_id, delivery_address)` *(stretch goal)*
   - Initiates order through delivery platform
   - Requires OAuth authentication
   - Returns order confirmation

### Agent/Application Layer
**Framework:** Choose between:
- **OpenAI Agents SDK** (simple, well-documented)
- **LangChain** (more mature ecosystem)
- **Custom implementation** (lightweight, full control)

**Flow:**
```
User: "Find me the cheapest tuna roll within 2 miles of 123 Main St"
  ↓
Agent uses MCP tools:
  1. search_nearby_restaurants(location="123 Main St", radius_miles=2, cuisine="sushi")
  2. For each restaurant → get_restaurant_menu(restaurant_id)
  3. find_cheapest_tuna_roll() to aggregate & rank
  ↓
Agent responds: "Found 5 options. Cheapest: $6.99 at Sushi Palace (15 min delivery)"
  ↓
User: "Order it"
  ↓
Agent: place_order() [if implemented]
```

---

## API Integration Strategy (FINALIZED)

### Research Completed
We tested all viable APIs for real menu/pricing data:

| API | Menu Items? | Prices? | Access | Verdict |
|-----|------------|---------|--------|---------|
| Google Places (New) | No | Price range only | Self-serve | **Use for discovery** |
| Google Business Profile | Yes | Yes | Owner-only | Can't read others' menus |
| OpenMenu | Yes (25M items) | Likely | "Contact us" | No free tier |
| Yelp Fusion | No | $/$$/$$$  | Paid ($8-15/1K) | Supplement only |
| DoorDash/UberEats/Grubhub | N/A | N/A | Merchant-only | Not viable |

**Conclusion:** No free public API provides structured menu items with prices for arbitrary restaurants.

### Finalized 3-Layer Architecture

**Layer 1: Restaurant Discovery (REAL DATA - Google Places API via Arcade OAuth)**
- Search sushi restaurants by location + radius
- Get ratings, delivery flags, price ranges ($20-30, $100+), hours
- User authenticates via Arcade's Google OAuth provider
- No shared API key needed - uses per-user identity
- Tested and confirmed: 10 restaurants found in SF with rich metadata

**Layer 2: Menu Data (SYNTHETIC - Context-Aware)**
- Seeded menu database with realistic sushi items and prices
- Prices calibrated to restaurant's real `priceRange` from Google Places
  - PRICE_LEVEL_MODERATE ($20-30) -> tuna rolls $8-12
  - PRICE_LEVEL_EXPENSIVE ($100+) -> tuna rolls $16-24
- Includes availability, delivery time estimates, variations (regular/spicy/deluxe)

**Layer 3: Ordering (SIMULATED)**
- Mock order placement with realistic confirmation flow
- Shows OAuth patterns, multi-step workflows, error handling

### Auth Strategy: Arcade Google OAuth (PRIMARY)
```python
@tool
async def search_nearby_restaurants(context: Context, location: str, radius_miles: float):
    # Get user's Google OAuth token from Arcade's auth framework
    token = await context.get_oauth_token("google")
    headers = {"Authorization": f"Bearer {token}"}
    # Call Google Places API with user identity - no shared API key
```

**Why this approach:**
- Demonstrates Arcade's core auth value proposition
- Per-user authorization (production pattern)
- No secrets in the repo
- Shows understanding of Arcade's Context/OAuth model
- API key fallback available for testing/CI via env var

### What This Demonstrates
- Real API integration (Google Places)
- Arcade's OAuth framework (Google auth provider)
- Data modeling and price estimation logic
- Clear separation of real vs simulated layers
- Production-ready auth patterns

---

## Repository Structure

```
amaciver-arcade/
├── sushi-scout-mcp/           # MCP Server (created with `arcade new`)
│   ├── src/
│   │   ├── sushi_scout/
│   │   │   ├── __init__.py
│   │   │   ├── server.py      # MCPApp definition
│   │   │   ├── tools/         # Tool implementations
│   │   │   │   ├── search.py
│   │   │   │   ├── menu.py
│   │   │   │   ├── ordering.py
│   │   │   ├── services/      # External API clients
│   │   │   │   ├── yelp_client.py
│   │   │   │   ├── places_client.py
│   │   │   ├── models/        # Data models
│   │   │   │   ├── restaurant.py
│   │   │   │   ├── menu_item.py
│   │   ├── tests/
│   │   │   ├── test_tools.py
│   │   │   ├── test_services.py
│   │   │   ├── fixtures/      # Mock API responses
│   │   ├── evals/
│   │   │   ├── test_scenarios.py
│   │   │   ├── eval_results/
│   ├── pyproject.toml
│   ├── README.md
│   ├── .env.example
│
├── sushi-agent/               # Agent application
│   ├── src/
│   │   ├── agent.py           # Main agent logic
│   │   ├── config.py
│   ├── tests/
│   ├── requirements.txt
│   ├── README.md
│
├── README.md                  # Root README
├── claude.md                  # This file
├── demo/                      # Screenshots, video
├── ARCHITECTURE.md            # Design decisions
```

---

## Development Workflow

### Phase 1: Setup (30 min)
- [ ] Run `arcade new sushi-scout-mcp`
- [ ] Set up Yelp Fusion API account & key
- [ ] Set up Google Places API account & key (optional)
- [ ] Configure environment variables
- [ ] Initialize agent application structure

### Phase 2: MCP Server - Core Tools (2 hours)
- [ ] Implement `search_nearby_restaurants` tool
  - Integrate Yelp API client
  - Handle location geocoding
  - Filter by cuisine type
- [ ] Create synthetic menu database
  - Seed with realistic sushi restaurant menus
  - Include tuna roll variants with prices
- [ ] Implement `get_restaurant_menu` tool
  - Query synthetic data
  - Return structured menu items
- [ ] Implement `find_cheapest_tuna_roll` tool
  - Orchestrate search + menu fetch
  - Price comparison logic
  - Rank by price, availability, delivery time

### Phase 3: Agent Application (1 hour)
- [ ] Set up MCP client connection
- [ ] Implement conversational flow
- [ ] Handle user queries (location, radius)
- [ ] Display results in readable format
- [ ] Add follow-up actions (order simulation)

### Phase 4: Testing (1.5 hours)
- [ ] Unit tests for each tool
  - Mock API responses
  - Test edge cases (no results, API errors)
- [ ] Integration tests
  - End-to-end tool orchestration
  - Agent + MCP server integration
- [ ] Create eval scenarios
  - Different locations (urban, suburban)
  - Different radius sizes
  - Price variance scenarios
  - Availability edge cases

### Phase 5: Documentation & Polish (1 hour)
- [ ] Write comprehensive README
  - Installation instructions
  - API key setup
  - Usage examples
  - Screenshots/demo video
- [ ] Document architecture decisions
- [ ] Code cleanup & linting
- [ ] Add inline documentation
- [ ] Create demo materials

### Phase 6: Stretch Goals (if time permits)
- [ ] Real OAuth implementation (Yelp)
- [ ] Actual ordering flow (simulated)
- [ ] Multi-platform support
- [ ] Caching layer for API responses
- [ ] Web UI for the agent

---

## Testing & Evaluation Strategy

### Unit Tests
**Coverage:** Each tool independently
```python
# tests/test_tools.py
def test_search_nearby_restaurants_success()
def test_search_nearby_restaurants_no_results()
def test_search_nearby_restaurants_invalid_location()
def test_get_restaurant_menu_success()
def test_find_cheapest_tuna_roll_ranking()
```

### Integration Tests
**Coverage:** Multi-tool workflows
```python
# tests/test_integration.py
def test_full_search_and_compare_workflow()
def test_agent_completes_order_flow()
```

### Evaluation Scenarios
**Using Arcade's eval framework:**
```python
# evals/test_scenarios.py
scenarios = [
    {
        "name": "urban_area_high_density",
        "location": "San Francisco, CA",
        "radius": 1.0,
        "expected_min_results": 5
    },
    {
        "name": "suburban_area_low_density",
        "location": "Suburb XYZ",
        "radius": 5.0,
        "expected_min_results": 2
    },
    {
        "name": "price_comparison_accuracy",
        "expected_cheapest": "Restaurant A",
        "expected_price": 6.99
    }
]
```

**Metrics to Track:**
- Tool selection accuracy
- Response time
- API error handling
- Price ranking correctness
- User satisfaction (qualitative)

---

## API Keys & Environment Variables

**Primary auth: Arcade Google OAuth (no API key needed for end users)**
- Users authenticate via Arcade's built-in Google auth provider
- Tool retrieves OAuth token at runtime via `context.get_oauth_token("google")`

**Fallback for testing/CI:**
```bash
# .env (gitignored - never committed)
GOOGLE_PLACES_API_KEY=your_google_key  # Fallback for local testing only
ARCADE_API_KEY=your_arcade_key         # For Arcade platform access
```

**Setup Instructions:**
1. Arcade: Register at arcade.dev, get API key
2. Google (fallback only): https://console.cloud.google.com -> Enable Places API (New) -> Create API key

---

## Key Design Decisions

### Why Synthetic Menu Data?
**Rationale:** No reliable public API for real-time menu/pricing from delivery platforms. Creating a seeded database allows us to:
- Demonstrate data processing logic
- Ensure reproducible test results
- Avoid API rate limits during demos
- Focus on the agent orchestration (core value)

**Trade-off:** Not production-ready, but perfect for interview/demo scope.

### Why Mock Ordering?
**Rationale:** Actual ordering requires:
- Production API access (limited availability)
- Payment processing (PCI compliance)
- Legal liability concerns
- Significantly more development time

**Mock implementation shows:**
- OAuth patterns
- Multi-step workflows
- Error handling
- User confirmation flows

### Agent Framework Choice
**Recommendation:** Start with OpenAI Agents SDK
- Simple, minimal boilerplate
- Good documentation
- Native MCP support
- Easy to explain in interview

---

## Success Criteria

**Must Have:**
✅ MCP server with 3+ working tools
✅ Agent that successfully orchestrates tool calls
✅ Real API integration (Yelp/Places)
✅ Comprehensive tests (>80% coverage)
✅ Clear documentation
✅ Runnable by cloning repo

**Nice to Have:**
⭐ OAuth implementation
⭐ Demo video
⭐ Eval harness with multiple scenarios
⭐ Clean, polished UI (if web-based)

---

## Time Allocation (6 hours)

| Phase | Time | Priority |
|-------|------|----------|
| Setup & scaffolding | 0.5h | P0 |
| MCP server core tools | 2.0h | P0 |
| Agent application | 1.0h | P0 |
| Testing | 1.5h | P0 |
| Documentation | 1.0h | P0 |
| **TOTAL** | **6.0h** | |

---

## Development Guidelines for Claude/LLM Assistants

When working on this project:

1. **Always run tests after changes** - Use `pytest` in the MCP server directory
2. **Follow Arcade's scaffold conventions** - Don't fight the generated structure
3. **Prefer composition over complexity** - Keep tools focused, single-purpose
4. **Document API decisions** - Note why we chose Yelp, why mock data, etc.
5. **Use type hints** - Critical for MCP server tools
6. **Handle errors gracefully** - Network failures, API limits, invalid inputs
7. **Keep agent prompts simple** - Don't over-engineer the agent logic
8. **Commit frequently** - Small, atomic commits with clear messages
9. **Update this file** - As decisions change, keep claude.md current

---

## Resolved Decisions

- [x] **Project name:** sushi-scout
- [x] **Primary API:** Google Places (New) via Arcade Google OAuth
- [x] **Menu data:** Synthetic, calibrated to real priceRange from Google Places
- [x] **Auth strategy:** Arcade Google OAuth (primary), API key fallback (testing/CI)
- [x] **No Yelp needed:** Google Places provides everything (ratings, delivery, price range, reviews)
- [x] **Ordering:** Mock/simulated with realistic flows

## Open Questions / TODOs

- [ ] Agent framework: OpenAI SDK vs LangChain vs custom?
- [ ] Demo format: CLI only, web UI, or video walkthrough?
- [ ] Arcade Google OAuth: confirm exact scope needed for Places API
- [ ] Confirm `arcade new` scaffold structure matches our needs

---

## Next Steps

1. Run `arcade new sushi-scout-mcp` to scaffold the MCP server
2. Explore the scaffold structure, understand conventions
3. Implement `search_nearby_restaurants` tool with Arcade Google OAuth
4. Build synthetic menu data layer
5. Implement `find_cheapest_tuna_roll` orchestration tool
6. Write tests
7. Build agent application
8. Documentation and polish

