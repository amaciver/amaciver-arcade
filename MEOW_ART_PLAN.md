# Meow Art: Project Plan

**Concept:** An LLM-powered agent that fetches cat facts, retrieves the user's Slack
avatar, generates a stylized cat-themed image using OpenAI's image-to-image API
(with the avatar as the input image), and sends the result back to Slack.

---

## 1. What We're Building

### MCP Server: Extended `meow_me`

Extend the existing meow_me MCP server with new tools (keeping the 3 existing ones):

| Tool | Module | Auth | Description |
|------|--------|------|-------------|
| `get_cat_fact` | facts.py | None | **Existing** - Fetch 1-5 random cat facts |
| `meow_me` | slack.py | Slack OAuth | **Upgrade** - Full pipeline: fact + avatar + image + DM to self |
| `send_cat_fact` | slack.py | Slack OAuth | **Existing** - Send text-only facts to any channel |
| `get_user_avatar` | avatar.py | Slack OAuth | **New** - Get user's Slack profile photo URL + display name |
| `generate_cat_image` | image.py | API key (Stability) | **New** - img2img: avatar + cat fact prompt -> stylized image |
| `send_cat_image` | slack.py | Slack OAuth | **New** - Upload generated image + fact caption to any channel |

### Agent: OpenAI Agents SDK (`agents-arcade`)

Uses Arcade's recommended agent framework. Two modes:

- **Live mode:** OpenAI LLM orchestrates tools via `agents-arcade`, full Slack/Stability integration
- **Scripted demo mode (`--demo`):** No LLM or API keys needed. Walks through
  pre-scripted scenarios with example inputs and bundled sample images, showing
  exactly what the agent would do at each step.

---

## 2. Agent Interaction Model

Two categories of behavior:

1. **`meow_me`** — One-shot, no prompts. Full pipeline fires automatically and DMs self.
2. **Everything else** — The agent always follows a two-phase flow:
   - **Phase 1 (Fact):** Fetch fact(s), present to user, let them rotate/approve.
   - **Phase 2 (Deliver):** Ask "with image or text only?" Then ask where to send.

The LLM chains the right tools based on user choices at each decision point.

### Intent 1: "Meow me" (one-shot, no prompts)

```
User: "Meow me!"
Agent: -> meow_me()
       Internally: fact + avatar + image + DM self. No questions asked.
```

### Intent 2: Interactive flow (everything else)

Every non-meow-me request follows the same pattern:

```
User: "Give me a cat fact" / "Send something to #random" / "Make me cat art"

  PHASE 1 — FACT SELECTION
  Agent: -> get_cat_fact(count=1..5)
         -> "Here's your fact: '...'. Want to keep it, or get a new one?"
         -> (user rotates until happy)

  PHASE 2 — DELIVERY OPTIONS
  Agent: -> "Want me to include a generated image, or just send the text?"

    PATH A: Text only
    Agent: -> "Where should I send it? (a channel, DM, or just display here)"
           -> send_cat_fact(channel="...") or just display

    PATH B: With image
    Agent: -> get_user_avatar()
           -> generate_cat_image(cat_fact="...", avatar_url="...")
           -> "Where should I send it?"
           -> send_cat_image(channel="...") or just display
```

### Example conversations

**Browse facts, then decide:**
```
User: "Give me 3 cat facts"
Agent: -> get_cat_fact(count=3)
       "Here are 3 facts:
        1. A group of cats is called a clowder.
        2. Cats can rotate their ears 180 degrees.
        3. Cats sleep 12-16 hours per day.
        Want to keep one, or get more?"

User: "I like #2"
Agent: "Great pick! Want me to generate an image with it, or just the text?"

User: "Make an image"
Agent: -> get_user_avatar() -> generate_cat_image(fact=#2, avatar)
       "Here's your cat art! Where should I send it — a channel, your DMs, or just here?"

User: "Send it to #cats"
Agent: -> send_cat_image(channel="#cats")
```

**Quick send, text only:**
```
User: "Send a cat fact to #general"
Agent: -> get_cat_fact()
       "Got: 'Cats have over 20 vocalizations.' Send this to #general with or without an image?"

User: "Just text"
Agent: -> send_cat_fact(channel="#general")
```

**Quick send, with image:**
```
User: "Send a cat fact image to #random"
Agent: -> get_cat_fact()
       "Got: 'A cat can jump up to 6x its length.' Good, or want a different one?"

User: "That's good"
Agent: -> get_user_avatar() -> generate_cat_image() -> send_cat_image(channel="#random")
```

**Just browsing, no send:**
```
User: "Tell me a cat fact"
Agent: -> get_cat_fact()
       "Here you go: 'Cats can't taste sweetness.'
        Want another, want an image, or want to send it somewhere?"

User: "That's all, thanks"
Agent: "Happy to help!"
```

### System Prompt (guides LLM tool selection)

```
You are Meow Art, a fun agent that creates cat-fact-inspired art and sends it via Slack.

TOOLS:
- get_cat_fact(count)         — Fetch 1-5 random cat facts (no auth)
- get_user_avatar()           — Get user's Slack avatar URL (Slack OAuth)
- generate_cat_image(fact, avatar_url, style) — Create stylized art from avatar + fact (OpenAI gpt-image-1)
- send_cat_fact(channel, count) — Send text-only fact(s) to a Slack channel (Slack OAuth)
- send_cat_image(image_base64, cat_fact, channel) — Upload image + caption to Slack (Slack OAuth)
- meow_me()                   — One-shot: fact + avatar + image + DM self (Slack OAuth)

ROUTING RULES:

1. "Meow me" (standalone, no modifiers) → call meow_me() immediately.
   No questions asked. It handles everything internally and DMs the user.
   - "Meow me" ✓  "Meow me!" ✓  "Hit me with a meow" ✓
   - IMPORTANT: If the user adds ANY modifier (a channel, a style, a count,
     a specific fact), it is NOT a meow_me call. Treat it as interactive.
   - "Meow me to #random" → INTERACTIVE (they specified a channel)
   - "Meow me in watercolor" → INTERACTIVE (they specified a style)
   - "Meow me 3 facts" → INTERACTIVE (they specified a count)

2. Everything else → follow this two-phase flow:
   a. FACT PHASE: Call get_cat_fact. Present the fact(s). Let the user rotate
      (call get_cat_fact again) until they're happy.
   b. DELIVERY PHASE: Ask "with image or just text?"
      - Text only → ask where to send → send_cat_fact(channel)
      - With image → get_user_avatar → generate_cat_image → ask where → send_cat_image(channel)
      - Display only (no send) → just show the fact/image in chat

3. If the user says "another" / "new one" / "different fact" → call get_cat_fact again.

4. If the user specifies a channel upfront (e.g. "send to #random"), remember it
   but still ask about image vs text before sending.

5. If the user just says "tell me a fact" with no send intent, display the fact
   and offer: another fact, an image, or send it somewhere.
```

---

## 3. Tool Specifications

### Tool: `get_cat_fact` (existing, unchanged)

Fetch 1-5 random cat facts from MeowFacts API. Used by the agent for fact browsing
and rotation.

### Tool: `meow_me` (existing, UPGRADED)

**Change:** Upgrade from "text-only DM" to "full pipeline DM."

```
Input:  (none - identifies user from OAuth token)
Output: {
    "success": true,
    "fact": "Cats can rotate their ears 180 degrees",
    "image_generated": true,        # false if OpenAI image API unavailable
    "image_sent": true,             # false if image generation was skipped
    "recipient": "U012ABC",
    "channel": "D0123456789"
}
```

**Implementation:**
1. auth.test -> get own user ID
2. conversations.open -> get DM channel
3. Fetch cat fact from MeowFacts
4. users.info -> get own avatar URL
5. generate_cat_image (internally) -> stylized image
   - If OPENAI_API_KEY missing: graceful fallback, send text-only fact
6. Upload image + fact caption to DM channel
7. Return result

**Scopes:** `chat:write`, `im:write`, `files:write`, `users:read`

### Tool: `send_cat_fact` (existing, unchanged)

Send text-only cat facts to a channel. No image involved.

### Tool: `get_user_avatar` (NEW)

**Module:** `tools/avatar.py`
**Auth:** Slack OAuth with `users:read` scope

```
Input:  (none - identifies user from OAuth token)
Output: {
    "user_id": "U012ABC",
    "display_name": "Alex",
    "avatar_url": "https://avatars.slack-edge.com/.../image_512.png",
    "avatar_size": 512
}
```

**Implementation:**
1. auth.test -> get user ID
2. users.info -> get profile
3. Extract profile.image_512 (or image_original)
4. Return avatar URL + display name

### Tool: `generate_cat_image` (NEW)

**Module:** `tools/image.py`
**Auth:** OpenAI API key (same key as the agent LLM — no extra credentials)

```
Input: {
    "cat_fact": "Cats can rotate their ears 180 degrees",
    "avatar_url": "https://avatars.slack-edge.com/.../image_512.png",
    "style": "cartoon"  (optional: "cartoon", "watercolor", "anime", "photorealistic")
}
Output: {
    "image_base64": "<base64-encoded PNG>",
    "prompt_used": "A playful cat rotating its ears...",
    "style": "cartoon",
    "cat_fact": "Cats can rotate their ears 180 degrees"
}
```

**OpenAI Images Edit API:**
```python
from openai import OpenAI
client = OpenAI()  # uses OPENAI_API_KEY env var

# Download avatar bytes first, then:
response = client.images.edit(
    model="gpt-image-1",
    image=avatar_bytes,          # PNG/WebP/JPG, <50MB
    prompt="...",                 # cat-themed prompt incorporating the fact
    size="1024x1024",
)
image_base64 = response.data[0].b64_json
```

**Prompt composition example:**
```
fact: "Cats can rotate their ears 180 degrees"
style: "cartoon"
-> "Transform this photo into a whimsical cartoon illustration featuring a cat
   rotating its ears 180 degrees. The person in the photo should be reimagined
   as a cartoon character watching the cat in amazement. Vibrant colors, fun
   and playful style."
```

**Fallback when no OPENAI_API_KEY:**
- Return a bundled placeholder image (a small pre-made PNG)
- Set `"fallback": true` in the response so the agent can inform the user
- The tool still "works" — it just returns a placeholder instead of a real generation
- This lets the full pipeline complete without errors

**Avatar sizing:** Slack avatars are 512x512 PNG. OpenAI accepts PNG/WebP/JPG
up to 50MB, so no resizing needed. The output will be 1024x1024.

### Tool: `send_cat_image` (NEW)

**Module:** `tools/slack.py` (extend existing module)
**Auth:** Slack OAuth with `chat:write`, `files:write` scopes

```
Input: {
    "image_base64": "<base64 PNG data>",
    "cat_fact": "Cats can rotate their ears 180 degrees",
    "channel": "C1234567890"
}
Output: {
    "success": true,
    "channel": "C1234567890",
    "file_id": "F0123456789"
}
```

**Implementation (new Slack file upload flow):**
1. Decode base64 image to bytes
2. Call `files.getUploadURLExternal(filename, length)` -> get upload URL + file_id
3. POST image bytes to the upload URL
4. Call `files.completeUploadExternal(file_id, channel, initial_comment=fact)`
5. Return success + file info

**Scopes:** `files:write`, `chat:write`

Note: This tool always requires an explicit channel. The `meow_me` tool handles
the "DM to self" case internally.

---

## 4. Agent Design

### Framework: OpenAI Agents SDK + `agents-arcade`

```
┌──────────────────────────────────────────────┐
│  CLI Agent (agent.py)                        │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │  OpenAI Agents SDK                     │  │
│  │  Agent(                                │  │
│  │    name="Meow Art",                    │  │
│  │    model="gpt-4o-mini",                │  │
│  │    tools=get_arcade_tools(client),     │  │
│  │    instructions=SYSTEM_PROMPT          │  │
│  │  )                                     │  │
│  └──────────┬─────────────────────────────┘  │
│             │ tool calls                     │
│  ┌──────────▼─────────────────────────────┐  │
│  │  agents-arcade tool bridge             │  │
│  │  - Converts Arcade tools to OAI format │  │
│  │  - Handles auth (Slack OAuth, API key) │  │
│  │  - Executes via Arcade Engine          │  │
│  └──────────┬─────────────────────────────┘  │
│             │                                │
└─────────────┼────────────────────────────────┘
              │
┌─────────────▼────────────────────────────────┐
│  MCP Tools (meow_me package)                 │
│  get_cat_fact | get_user_avatar              │
│  generate_cat_image | send_cat_image         │
│  meow_me | send_cat_fact                     │
└──────────────────────────────────────────────┘
```

### Live Mode

```python
from agents import Agent, Runner
from arcadepy import AsyncArcade
from agents_arcade import get_arcade_tools

async def main():
    client = AsyncArcade()
    tools = await get_arcade_tools(client, toolkits=["meow_me"])

    agent = Agent(
        name="Meow Art",
        model="gpt-4o-mini",
        tools=tools,
        instructions=SYSTEM_PROMPT,
    )

    # Interactive loop
    while True:
        user_input = input("\n🐱 > ")
        result = await Runner.run(
            starting_agent=agent,
            input=user_input,
            context={"user_id": "user@example.com"},
        )
        print(result.final_output)
```

### Scripted Demo Mode (`--demo`)

No LLM, no API keys. Walks through pre-scripted scenarios:

```
$ python -m meow_me --demo

=== MEOW ART DEMO ===

Scenario 1: "Meow me!"
  [Step 1] get_cat_fact() -> "A group of cats is called a clowder."
  [Step 2] get_user_avatar() -> avatar_url: (demo placeholder)
  [Step 3] generate_cat_image(fact, avatar) -> (bundled sample image)
  [Step 4] meow_me() -> Would DM you: image + "A group of cats is called a clowder."
  [Saved demo image to: demo_output/meow_me_1.png]

Scenario 2: "Give me 3 cat facts" -> user picks one -> text only to #general
  [Step 1] get_cat_fact(count=3) ->
    1. "Cats sleep 12-16 hours per day."
    2. "A cat's purr vibrates at 25-150 Hz."
    3. "Cats have over 20 vocalizations."
  [Agent: "Want to keep one, or get more?"]
  [User picks #2]
  [Agent: "With an image, or just the text?"]
  [User: "Just text"]
  [Agent: "Where should I send it?"]
  [User: "#general"]
  [Step 2] send_cat_fact(channel="#general") -> Would post fact #2

Scenario 3: "Send a cat fact image to #random" (image path)
  [Step 1] get_cat_fact() -> "Cats can jump up to 6 times their length."
  [Agent: "Good fact, or want a new one?"]
  [User: "That's good"]
  [Agent: "With image or just text?"]
  [User: "Image please"]
  [Step 2] get_user_avatar() -> (demo placeholder)
  [Step 3] generate_cat_image() -> (bundled sample image)
  [Step 4] send_cat_image(channel="#random") -> Would post image + fact
  [Saved demo image to: demo_output/meow_art_3.png]

Scenario 4: "Tell me a cat fact" (browse only, no send)
  [Step 1] get_cat_fact() -> "Cats can't taste sweetness."
  [Agent: "Want another, an image, or send it somewhere?"]
  [User: "That's all, thanks"]
  [Agent: "Happy to help!"]
```

Demo includes 2-3 bundled sample images in `demo_assets/` directory so the
evaluator can see what the output looks like.

---

## 5. Environment Variables

```bash
# .env (gitignored)
OPENAI_API_KEY=sk-...                  # For agent LLM AND image generation (single key)
ARCADE_API_KEY=arc-...                 # For Arcade platform (Slack OAuth routing)
```

---

## 6. Slack OAuth Scopes

| Tool | Scopes |
|------|--------|
| `meow_me` | `chat:write`, `im:write`, `files:write`, `users:read` |
| `send_cat_fact` | `chat:write` |
| `get_user_avatar` | `users:read` |
| `send_cat_image` | `chat:write`, `files:write` |

---

## 7. Implementation Steps

### Phase 1: New MCP Tools (4 steps)

- [ ] **Step 1:** Create `tools/avatar.py` with `get_user_avatar` tool
  - Slack auth.test -> user ID -> users.info -> avatar URL
  - Tests: mock Slack responses, test extraction, missing profile, error handling

- [ ] **Step 2:** Create `tools/image.py` with `generate_cat_image` tool
  - Download avatar, compose prompt, call OpenAI img2img
  - Fallback: return bundled placeholder image when no API key
  - Tests: mock OpenAI image API, prompt composition, fallback behavior, style variants

- [ ] **Step 3:** Add `send_cat_image` to `tools/slack.py`
  - files.getUploadURLExternal -> upload -> files.completeUploadExternal
  - Tests: mock upload flow, base64 decode, error cases

- [ ] **Step 4:** Upgrade `meow_me` tool in `tools/slack.py`
  - Full pipeline: fact + avatar + image gen + DM to self
  - Graceful fallback if Stability key missing (send text-only)
  - Tests: full pipeline mock, fallback behavior

### Phase 2: Agent (3 steps)

- [ ] **Step 5:** Create agent with OpenAI Agents SDK + `agents-arcade`
  - `agents-arcade` integration with `get_arcade_tools`
  - System prompt with routing rules
  - Interactive chat loop
  - Proper auth error handling (AuthorizationError -> print login URL)

- [ ] **Step 6:** Create scripted demo mode (`--demo`)
  - Pre-scripted scenarios (4 scenarios covering all intents)
  - Bundled sample images in `demo_assets/`
  - Save demo output to `demo_output/` directory
  - No API keys needed at all

- [ ] **Step 7:** Agent tests
  - Test tool definitions are valid
  - Test demo mode runs without errors
  - Test system prompt routing (eval-style tests)

### Phase 3: Registration & Polish (2 steps)

- [ ] **Step 8:** Register new modules in `server.py`, update `pyproject.toml`
  - Add imports for avatar.py and image.py
  - Add openai, agents-arcade dependencies
  - Update .env.example

- [ ] **Step 9:** Update documentation and run full test suite
  - Update meow_me README
  - Update CLAUDE.md
  - Run all tests (old + new), lint, verify

---

## 8. Testing Plan

### Unit Tests

| Test file | Count | What's tested |
|-----------|-------|---------------|
| test_facts.py | 11 | **Existing**, unchanged |
| test_slack.py | ~23 | **Extended**: existing 15 + ~8 new (send_cat_image upload flow, meow_me upgrade, fallback) |
| test_avatar.py | ~8 | **New**: auth.test mock, users.info mock, avatar extraction, missing fields, errors |
| test_image.py | ~10 | **New**: prompt composition, OpenAI image API mock, fallback placeholder, avatar download, style variants, base64 output |
| test_agent.py | ~6 | **New**: tool definitions, demo mode e2e, system prompt validation |

### Eval Tests (agent routing)

#### Category 1: "Meow me" — One-shot triggers (should call `meow_me()`)

| # | User input | Expected | Why it's one-shot |
|---|------------|----------|-------------------|
| 1 | "Meow me" | `meow_me()` | Canonical trigger |
| 2 | "Meow me!" | `meow_me()` | Punctuation variant |
| 3 | "meow me" | `meow_me()` | Lowercase |
| 4 | "MEOW ME" | `meow_me()` | Uppercase |
| 5 | "Hit me with a meow" | `meow_me()` | Colloquial, same intent |
| 6 | "Surprise me with a cat thing" | `meow_me()` | Implicit "I don't want choices" |

#### Category 2: "Meow me" with modifiers — should NOT trigger one-shot

| # | User input | Expected first call | Why it's interactive |
|---|------------|--------------------|--------------------|
| 7 | "Meow me to #random" | `get_cat_fact()` | Channel specified → user has a preference |
| 8 | "Meow me in watercolor style" | `get_cat_fact()` | Style specified → user has a preference |
| 9 | "Meow me 3 facts" | `get_cat_fact(count=3)` | Count specified → user wants to browse |
| 10 | "Meow me but with a different fact" | `get_cat_fact()` | "Different" implies selection |
| 11 | "Meow me to #general and #random" | `get_cat_fact()` | Multiple channels → needs confirmation |
| 12 | "Can you meow me something about sleep?" | `get_cat_fact()` | Topic preference → not random surprise |

#### Category 3: Fact browsing — get facts, no send intent yet

| # | User input | Expected first call | Then agent should... |
|---|------------|--------------------|--------------------|
| 13 | "Give me a cat fact" | `get_cat_fact()` | Present, offer: another / image / send / done |
| 14 | "Tell me something about cats" | `get_cat_fact()` | Present, offer choices |
| 15 | "Give me 3 cat facts" | `get_cat_fact(count=3)` | Present all, ask to pick or get more |
| 16 | "What's a fun cat fact?" | `get_cat_fact()` | Present, offer choices |
| 17 | "I want to learn about cats" | `get_cat_fact()` | Present, offer choices |
| 18 | "Cat fact please" | `get_cat_fact()` | Present, offer choices |

#### Category 4: Send intent with destination — fact phase then delivery choice

| # | User input | Expected first call | Then agent should... |
|---|------------|--------------------|--------------------|
| 19 | "Send a cat fact to #general" | `get_cat_fact()` | Present fact, ask image or text |
| 20 | "Post something cat-related in #random" | `get_cat_fact()` | Present fact, ask image or text |
| 21 | "Share a cat fact with the team in #watercooler" | `get_cat_fact()` | Present fact, ask image or text |
| 22 | "DM me a cat fact" | `get_cat_fact()` | Present fact, ask image or text (not meow_me — they want choices) |
| 23 | "Send a cat fact image to #random" | `get_cat_fact()` | Present fact, confirm, then image pipeline |
| 24 | "I want cat art in #design" | `get_cat_fact()` | Present fact, confirm, then image pipeline |

#### Category 5: Image-first intent — user wants art, no destination yet

| # | User input | Expected first call | Then agent should... |
|---|------------|--------------------|--------------------|
| 25 | "Make me cat art" | `get_cat_fact()` | Present fact, confirm, then image pipeline, then ask where |
| 26 | "Generate a cat image" | `get_cat_fact()` | Need a fact first to base the image on |
| 27 | "I want a cat fact picture" | `get_cat_fact()` | Present fact, confirm, then image pipeline |
| 28 | "Create some cat-themed art" | `get_cat_fact()` | Present fact, confirm, then image pipeline |
| 29 | "Make me something with my avatar and cats" | `get_cat_fact()` | Present fact, confirm, then image pipeline |

#### Category 6: Mid-conversation fact rotation

| # | User input (after fact shown) | Expected behavior |
|---|-------------------------------|-------------------|
| 30 | "Another" | `get_cat_fact()` again |
| 31 | "Get a new one" | `get_cat_fact()` again |
| 32 | "I don't like that one" | `get_cat_fact()` again |
| 33 | "Something funnier" | `get_cat_fact()` again |
| 34 | "Next" | `get_cat_fact()` again |
| 35 | "Give me 5 more" | `get_cat_fact(count=5)` |
| 36 | "That's perfect" / "I like it" | Move to Phase 2 (delivery choice) |

#### Category 7: Mid-conversation delivery decisions

| # | User input (after fact approved) | Expected behavior |
|---|----------------------------------|-------------------|
| 37 | "With an image" | `get_user_avatar()` → `generate_cat_image()` → ask where |
| 38 | "Just text" | Ask where to send → `send_cat_fact()` |
| 39 | "No image, send to #general" | `send_cat_fact(channel="#general")` |
| 40 | "Image please, watercolor style" | `get_user_avatar()` → `generate_cat_image(style="watercolor")` → ask where |
| 41 | "Make it anime style" | `get_user_avatar()` → `generate_cat_image(style="anime")` → ask where |
| 42 | "Just show me, don't send" | Display fact (and image if requested) in chat only |

#### Category 8: Mid-conversation destination decisions

| # | User input (after image/text ready) | Expected behavior |
|---|--------------------------------------|-------------------|
| 43 | "Send it to #cats" | `send_cat_image(channel="#cats")` or `send_cat_fact(channel="#cats")` |
| 44 | "DM it to me" | Open DM channel, send there |
| 45 | "Post it in #general" | `send_cat_image(channel="#general")` or `send_cat_fact` |
| 46 | "Actually, don't send it" | Acknowledge, don't call send tool |
| 47 | "Send it and then meow me too" | Send to channel, then `meow_me()` separately |

#### Category 9: Multi-turn full conversation flows

| # | Conversation | Expected tool sequence |
|---|--------------|----------------------|
| 48 | "Cat fact" → "another" → "that one" → "with image" → "#random" | `get_cat_fact` → `get_cat_fact` → `get_user_avatar` → `generate_cat_image` → `send_cat_image` |
| 49 | "3 facts" → "I like #2" → "just text" → "#general" | `get_cat_fact(3)` → `send_cat_fact("#general")` |
| 50 | "Meow me" | `meow_me()` (just one call, done) |
| 51 | "Cat art" → "looks good" → "image" → "actually just text" → "#random" | `get_cat_fact` → ... → `send_cat_fact("#random")` (user changed mind) |
| 52 | "Fact for #general" → "nah new fact" → "that one" → "with image" → "send it" | `get_cat_fact` → `get_cat_fact` → `get_user_avatar` → `generate_cat_image` → `send_cat_image("#general")` |

#### Category 10: Edge cases and error handling

| # | User input | Expected behavior |
|---|------------|-------------------|
| 53 | "Send an image to #general" (no fact context) | Agent should get a fact first, not skip to image gen |
| 54 | "" (empty input) | Ask what they'd like to do |
| 55 | "What can you do?" | Describe capabilities, don't call any tools |
| 56 | "Meow me meow me meow me" | Treat as one `meow_me()` call |
| 57 | "Undo that" / "Cancel" | Acknowledge, don't send if not yet sent |
| 58 | "Send it again" (after a successful send) | Re-send same content to same channel |
| 59 | "Do the same thing but to #other-channel" | Re-send to different channel |
| 60 | "What was my last fact?" | Recall from conversation context, don't fetch new |

---

## 9. File Structure (Final)

```
meow_me/
  src/meow_me/
    __init__.py
    __main__.py
    server.py              (add imports for avatar, image)
    agent.py               (REWRITE: OpenAI Agents SDK agent)
    tools/
      __init__.py
      facts.py             (unchanged)
      slack.py             (add send_cat_image, upgrade meow_me)
      avatar.py            (NEW)
      image.py             (NEW)
    demo_assets/           (NEW: bundled sample images for demo mode)
      sample_cat_art_1.png
      sample_cat_art_2.png
  tests/
    test_facts.py          (unchanged)
    test_slack.py          (extend)
    test_avatar.py         (NEW)
    test_image.py          (NEW)
    test_agent.py          (NEW)
    test_evals.py          (extend with routing evals)
  pyproject.toml           (add openai, agents-arcade deps)
  .env.example             (add OPENAI_API_KEY, OPENAI_API_KEY)
  README.md                (update)
```

---

## 10. Dependencies

```toml
dependencies = [
    "arcade-mcp-server>=1.11.1,<2.0.0",
    "httpx>=0.28.0,<1.0.0",
    "openai>=1.30.0,<2.0.0",            # For image generation (gpt-image-1)
]

[project.optional-dependencies]
agent = [
    "openai-agents>=0.1.0",           # OpenAI Agents SDK
    "agents-arcade>=0.1.0",           # Arcade <-> OpenAI Agents bridge
    "arcadepy>=0.1.0",                # Arcade Python client
]
dev = [
    "arcade-mcp[all]>=1.9.0,<2.0.0",
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "mypy>=1.0.0",
    "ruff>=0.1.0",
]
```

MCP server tools only need `httpx` (and `openai` for image generation).
Agent dependencies are optional (`pip install meow_me[agent]`).
No Pillow needed — OpenAI accepts PNG up to 50MB, no resizing required.
Single OpenAI API key serves both the agent LLM and image generation.

---

## 11. Resolved Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| LLM provider | OpenAI (via agents-arcade) | Arcade's recommended framework |
| Agent framework | OpenAI Agents SDK + agents-arcade | Arcade's primary example pattern |
| Image gen API | OpenAI gpt-image-1 (images.edit) | Same API key as agent LLM, supports image input |
| Missing OpenAI key | Fully scripted demo mode + placeholder images in tools | No LLM or image gen needed |
| Image resizing | Not needed | OpenAI accepts PNG up to 50MB, outputs 1024x1024 |
| Fact rotation | Agent presents fact, user approves/rotates | Adds meaningful interactivity |
| meow_me behavior | One-shot full pipeline (fact+image+DM) | Only path that skips user prompts |
| Everything else | Two-phase: fact selection, then "image or text?" | User always gets the choice |
| Tool chaining | LLM chains get_cat_fact → (approve) → send_cat_fact OR avatar+image+send_cat_image | Two clear paths the LLM picks between |

---

## 12. Remaining Risks

1. **OpenAI gpt-image-1 edit endpoint:** Well-documented and tested by the community.
   Accepts PNG/WebP/JPG input, returns base64. Low risk.

2. **agents-arcade toolkit loading:** Need to verify that `get_arcade_tools(client,
   toolkits=["meow_me"])` can discover locally-registered tools (not just
   Arcade Cloud-hosted ones). May need to use the MCP gateway approach instead.

3. **Slack file upload flow:** The new `files.getUploadURLExternal` +
   `files.completeUploadExternal` is a 3-step process. Needs careful error handling
   if any step fails.

4. **Cost:** OpenAI images.edit ~$0.02-0.08/image, agent LLM ~$0.01-0.05/turn.
   Single API key for both. Demo mode avoids all costs.
