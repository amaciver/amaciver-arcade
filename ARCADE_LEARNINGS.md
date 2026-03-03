# Arcade.dev Platform Learnings

Lessons from building an MCP server + LLM agent that fetches cat facts, generates cat-themed art from Slack avatars, and sends results to Slack — all orchestrated through Arcade's tool platform.

---

## Where Arcade Shines

The core value proposition of Arcade became clear through building this project: **it removes the infrastructure between "I wrote a tool function" and "an LLM can call it securely with user auth."**

**OAuth is the killer feature.** Without Arcade, connecting an LLM tool to Slack means: register an OAuth app, build a redirect handler, exchange codes for tokens, store tokens securely, handle refresh flows, manage scopes per user. With Arcade, it's one decorator: `@tool(requires_auth=Slack(scopes=["chat:write"]))`. The user clicks a link in the browser, authorizes, and the tool gets a valid token via `context.get_auth_token_or_empty()`. That's the entire auth implementation. For a project with four Slack-authenticated tools, this saved hundreds of lines of OAuth plumbing and — more importantly — eliminated an entire category of security concerns around token storage.

**Agent-tool separation becomes trivial.** The `agents-arcade` library turns Arcade-deployed tools into OpenAI Agents SDK-compatible `FunctionTool` instances with a single call: `tools = await get_arcade_tools(client, toolkits=["MeowMe"])`. The agent doesn't import tool code, doesn't know how tools work internally, and doesn't handle auth. It's a thin LLM client that asks Arcade "what tools exist?" and lets the model decide which to call. My agent went from 940 lines of reimplemented tool logic to 280 lines of pure agent behavior.

**The `@tool` decorator does a lot of work.** A single decorator declaration handles: MCP protocol compliance, typed parameter/return schemas, auth requirement enforcement, secret injection, tool discovery for both local and cloud runtimes, and automatic PascalCase namespacing for MCP clients. The gap between "Python function" and "production MCP tool" is genuinely small.

**Secrets management is centralized.** `arcade deploy --secrets all` uploads your `.env` to the platform; `context.get_secret("KEY")` retrieves them at runtime. Tools deployed to Arcade Cloud don't need access to the host filesystem or environment. Secrets are injected per-tool based on declared requirements. For a multi-tool server where different tools need different API keys, this is cleaner than managing env vars across deployment environments.

**Two deployment modes from the same code.** The same `@tool`-decorated functions run locally via `arcade mcp -p meow_me stdio` (for Claude Desktop / Cursor with full capabilities) or remotely via `arcade deploy` (for cloud-hosted agent access). No code changes between modes. This let me develop and test locally with instant feedback, then deploy for the agent to consume remotely — same tools, different runtime.

**The eval framework tests the right thing.** Arcade's evaluation framework tests whether an LLM selects the correct tools for natural language prompts — a fundamentally different dimension from unit tests. Unit tests verify "does the tool work?"; evals verify "does the model pick the right tool?" Having both in the same ecosystem, with `ExpectedMCPToolCall` aware of the tool's actual MCP-namespaced name, means the evals test against the real tool interface, not a mock.

**User identity comes free with OAuth.** When a user authorizes via Arcade's Slack OAuth, `auth.test` returns their human user ID — not a bot, not an app. Tools automatically know who they're acting on behalf of. I initially built ~100 lines of user-resolution logic (prompt for username, search `users.list`, cache the ID) before realizing Arcade OAuth already solved this. The platform acts as an identity broker, not just a token broker.

---

## The Image Upload Chain: A Case Study in Compounding Constraints

The full image-to-Slack pipeline exposed how multiple platform constraints compound into a single unsolvable problem on Arcade Cloud — and how two unexplored paths could have resolved it.

**The goal:** Generate cat-themed art from a user's Slack avatar, then upload it to their Slack DMs.

**Constraint 1 — OAuth scopes are fixed.** Arcade's built-in Slack provider doesn't support `files:write`. You can't request it. So uploading images through the OAuth token is impossible. The workaround: upload a separate `SLACK_BOT_TOKEN` as a cloud secret and use it specifically for file uploads — the dual-token pattern.

**Constraint 2 — Image generation times out.** `gpt-image-1` takes 30-60 seconds. Arcade Cloud workers time out at ~30 seconds. The image never finishes generating. The workaround: split into an async start/poll pattern — `start_cat_image_generation` kicks off a background thread and returns immediately, `check_image_status` polls for completion.

**Constraint 3 — Workers are ephemeral.** The poll call lands on a different worker than the start call. The background thread and in-memory job dictionary don't exist on the new worker. The job ID is meaningless. There is no workaround within Arcade Cloud's execution model.

**The result:** Even though the bot token was sitting there ready to upload, the pipeline never produced an image to upload. Three constraints chained together — fixed scopes forced the bot token, timeouts forced the async pattern, ephemeral workers broke the async pattern.

**Two paths not taken that could have solved this:**

1. **Custom OAuth2 provider.** Registering a custom Slack OAuth app with `files:write` in its scope list would have eliminated the need for a separate bot token entirely. One token for everything — identity, messaging, and file uploads. Arcade supports this via `OAuth2(id="my-slack", scopes=["chat:write", "files:write", ...])`, but it requires creating and managing your own Slack app (client ID, client secret, redirect URIs). I chose the built-in provider for simplicity, which meant accepting its scope limitations.

2. **Self-hosted tool server.** Running the MCP server on your own infrastructure (a VPS, a container, etc.) instead of Arcade Cloud would eliminate both the timeout and ephemeral worker problems. A long-running process has no 30-second ceiling, background threads persist, and in-memory state survives between calls. The `arcade mcp` local mode already proves this works — image generation completes reliably every time. The trade-off is that you lose Arcade Cloud's zero-ops deployment and need to manage infrastructure yourself.

Either path alone would have unblocked the full pipeline on the remote agent. Combined, they would have given a single OAuth token with full scopes running on a persistent server — no dual-token pattern, no async workaround, no capability degradation. The project chose to stay within Arcade's managed offerings and accept text-only for the CLI agent, which was the right call for a demo project but wouldn't be for production.

---

## The Gotchas (and They're Worth It)

The sections below document the rough edges I hit. Every platform has them. What matters is whether the value outweighs the friction — and for Arcade, it clearly does. The OAuth flow alone justified the platform choice. The gotchas are real but learnable, and most only bite once.

---

## Local Tools vs Remote Tools: Two Very Different Worlds

The biggest architectural decision is where your tools run. Arcade supports both, but they have fundamentally different capabilities and failure modes.

**Local MCP server** (`arcade mcp -p meow_me stdio`): Tools run as a long-lived process on your machine. Background threads persist between calls, in-memory state survives, and you have direct access to env vars and the local filesystem. This is the mode that "just works" — image generation that takes 60 seconds is fine because there's no external timeout.

**Arcade Cloud** (`arcade deploy` + `get_arcade_tools()`): Tools run on ephemeral workers. Each tool invocation may hit a different worker process. Background threads started in one call are gone by the next. In-memory dicts are empty. `os.getenv()` returns nothing because cloud secrets aren't env vars. The platform has a ~30-second worker timeout that you can't configure.

I started with a monolithic agent that imported tool code directly and ran everything in-process. A reviewer correctly pointed out this wasn't real separation — the agent reimplemented tool logic in 7 `@function_tool` wrappers (~400 lines of duplicate code). After refactoring to use `get_arcade_tools()` from the `agents-arcade` library, the agent shrunk from 940 to 280 lines with zero imports from the tools package. The LLM decides what to call; the agent is just a thin client.

The trade-off is real: local mode gives you full capabilities but couples agent and tools. Cloud mode gives you true separation but introduces timeout constraints, ephemeral state, and a different secrets model.

---

## Token Scopes: You Don't Get What You Ask For

Arcade's built-in Slack OAuth provider supports a fixed set of scopes: `chat:write`, `im:write`, `users:read`, `channels:read`. Requesting `files:write` returns `400 malformed_request: requesting unsupported scopes`. You can't negotiate — the provider's scope list is hardcoded on Arcade's side.

This created a concrete problem: text messages work fine through OAuth, but uploading images to Slack requires `files:write`. The solution was a **dual-token pattern**:

- **OAuth token** (from `context.get_auth_token_or_empty()`): Used for user identity (`auth.test`), sending DMs, posting text messages. Always available when the user authorizes.
- **Bot token** (from `context.get_secret("SLACK_BOT_TOKEN")`): A separate Slack bot token uploaded as a cloud secret. Used exclusively for `files:write` operations. Optional — when missing, the tool gracefully degrades to text-only delivery.

This means a single tool (`meow_me`) has two code paths: one for "I have both tokens and can upload images" and one for "I only have OAuth and will send text + save the image locally." The tool returns structured fields like `image_sent: false, fallback_reason: "files:write scope not available"` so the LLM can explain what happened to the user.

---

## Secrets: Three Ways to Not Find Your API Key

Accessing secrets on Arcade Cloud requires getting three things right simultaneously, and each one silently fails if wrong:

1. **Upload the secret**: `arcade deploy --secrets all` pushes `.env` values to the platform. But if you used `--skip-validate` (common on Windows where validation times out), the `--secrets` flag silently defaults to `skip`. You must explicitly pass `--secrets all`.

2. **Declare the requirement**: `@tool(requires_secrets=["OPENAI_API_KEY"])` tells Arcade Engine to inject the secret into the tool's context. Without this decorator, `context.get_secret()` raises a ValueError even though the secret exists on the platform. Locally, `os.getenv()` masks the problem completely.

3. **Access it correctly**: `context.get_secret("KEY")`, not `os.getenv("KEY")`. Environment variables are not injected on cloud workers.

There's an additional subtlety: `requires_secrets` is mandatory (Arcade won't execute the tool without the secret), while some secrets are optional. For the `meow_me` tool, `OPENAI_API_KEY` enables image generation but shouldn't block text-only operation. The fix was removing `requires_secrets` from the decorator and using a `_try_get_secret()` helper that catches exceptions and falls back gracefully.

---

## User Identity: Who Am I Talking To?

When a human authorizes via Arcade's Slack OAuth, `auth.test` returns **their** user ID — the human who clicked "Allow." This is straightforward and correct.

But when using a bot token (`SLACK_BOT_TOKEN`), `auth.test` returns the **bot's** user ID. If your tool calls `auth.test` to figure out who to DM, it DMs the bot instead of the human. I initially built an elaborate user-resolution flow: prompt for a Slack username at agent startup, call `users.list` to search, cache the resolved ID for the session. This was ~100 lines of code in the agent.

The insight that simplified everything: OAuth inherently identifies the human. Once I committed to Arcade OAuth as the identity layer and the bot token as just a capability enhancer for file uploads, the entire user-resolution flow became unnecessary. The dual-token pattern solved identity and capabilities simultaneously.

---

## Timeouts and Ephemeral Workers

`gpt-image-1` takes 30-60 seconds per image. Arcade Cloud workers time out at ~30 seconds. This isn't configurable. Fast tools (fetching cat facts, looking up avatars) work perfectly; slow tools don't.

My first attempt was an async start/poll pattern: `start_cat_image_generation` kicks off a background thread and returns a `job_id` immediately (~5 seconds), then the LLM calls `check_image_status` to poll. This works beautifully in MCP server mode where the process persists. On Arcade Cloud, the poll call hits a fresh worker where the background thread and job dictionary don't exist — instant 503.

The honest answer is that some operations just don't fit the ephemeral worker model. The project documents this as a known limitation and uses the agent's system prompt to explicitly gate the LLM: in CLI agent mode (cloud), the prompt says "Do NOT call image generation tools"; in MCP server mode (local), everything is available.

---

## Prompting the LLM About Capabilities

One of the subtler lessons: **LLMs take ambiguity as a reason to refuse.** When the system prompt said "Image generation: available via cloud secrets (tools detect at runtime)", gpt-4o-mini consistently told users "image features aren't currently available" and refused to try. It interpreted uncertainty as a signal to be cautious.

The fix was binary language: either "Image generation: READY — always attempt when asked" or "Do NOT call MeowMe_StartCatImageGeneration." No middle ground. The same principle applied to the agent checking `os.getenv("OPENAI_API_KEY")` locally — that key exists as a cloud secret, not in the agent's environment, so the check always failed and told the LLM the capability was missing. The agent should never gate cloud capabilities on local environment state.

---

## Built-In Integrations vs Writing Your Own

Arcade provides built-in OAuth providers for Slack, Google, GitHub, etc. The appeal is obvious: declare `requires_auth=Slack(scopes=[...])` and Arcade handles the entire OAuth flow — redirect, token exchange, refresh, storage. You get a valid token in one line of code.

The limitations are equally real: you're restricted to the scopes Arcade's provider supports, you can't customize the consent screen, and you can't add scopes at runtime. For Slack, this meant no `files:write` (image uploads), no `groups:read` (private channels), and no `channels:join` (auto-joining channels before upload).

The alternative — registering a custom `OAuth2` provider — gives full scope control but requires managing the OAuth app yourself (client ID, client secret, redirect URIs). For this project, the pragmatic choice was using the built-in provider for what it supports and supplementing with a bot token secret for what it doesn't.

The broader lesson: Arcade's built-in providers are excellent for getting started and for operations within their scope boundaries. Plan your architecture around those boundaries from the start rather than discovering them after you've built features that depend on unsupported scopes.

---

## Two Tool Discovery Mechanisms, Neither Obvious

Arcade has two ways to find your tools, and they work differently:

**`arcade mcp`** discovers tools by importing your Python package and scanning for module-level `@tool` decorators. It never executes `server.py`. This means any initialization — `load_dotenv()`, monkey-patches, logging setup — must live in `__init__.py`, because that's what runs when the package is imported. I lost time debugging missing env vars before realizing `server.py` simply never ran.

**`arcade deploy`** requires explicit `app.add_tool()` calls on your `MCPApp` instance. The implicit module-scan that works for `arcade mcp` isn't enough. Without `app.add_tool()`, your deployed server has zero tools and no error tells you why.

And then there's naming: Arcade automatically namespaces tools into PascalCase. `get_cat_fact` becomes `MeowMe_GetCatFact`. This bit in two places — all eval `ExpectedMCPToolCall` names were wrong until I figured out the pattern, and `get_arcade_tools(client, toolkits=["meow_me"])` silently returns zero tools because the toolkit name is `"MeowMe"`.

---

## Returning Images From Tools (The Monkey-Patch)

Arcade `@tool` functions must return dicts — the framework enforces typed return schemas. You cannot return MCP `ImageContent` directly; attempting it causes a validation error. But Claude Desktop needs `ImageContent` blocks to display inline image previews.

The solution was monkey-patching `convert_to_mcp_content()` in `__init__.py` to detect a special `_mcp_image` key in the returned dict and emit an `ImageContent` block alongside the normal `TextContent`. This required patching the function on **both** the `convert` module and the `server` module, because Python's `from .convert import convert_to_mcp_content` creates a local binding — patching one module doesn't affect the other's reference.

There's also a size constraint: Claude Desktop enforces roughly a 1MB limit on MCP tool result content. Full gpt-image-1 PNGs are ~2MB base64. The tool compresses to a 512x512 JPEG thumbnail (~50-100KB) for the `ImageContent` preview while stashing the full-res PNG server-side for Slack uploads. The `_mcp_image` key gets popped from the dict during the first conversion call, which is intentional — the structured content serialization that runs second doesn't need the image data.

---

## Slack API Surprises

**The file upload API is three steps now.** `files.upload` is deprecated. The modern flow is `files.getUploadURLExternal` (get a pre-signed URL) → HTTP PUT the bytes → `files.completeUploadExternal` (share to a channel). And `completeUploadExternal` requires a channel ID (`C01234567`) while `chat.postMessage` happily accepts channel names (`#general`). This asymmetry is barely documented and caused silent upload failures until I added a `_resolve_channel_id()` helper.

**Mixed channel type requests fail entirely.** Calling `conversations.list` with `types: "public_channel,private_channel"` requires both `channels:read` and `groups:read` scopes. If you only have one, the entire request fails with `missing_scope` — not partial results. You must only request the types you actually have scopes for.

**Self-DMs have a specific flow.** You can't just post a message to a user ID. The correct sequence is `auth.test` (get user ID from token) → `conversations.open` (create the DM channel) → `chat.postMessage` (send to that channel). Requires `im:write` in addition to `chat:write`.

**Bot membership isn't guaranteed for uploads.** Even if a bot was manually added to a channel, file uploads can fail. Calling `conversations.join` before each upload is idempotent and safe — it returns `ok: true` even if the bot is already in the channel. Handle `missing_scope` gracefully since `channels:join` may not be available.

---

## OpenAI SDK Gotchas

**BytesIO objects need a `.name` attribute.** Passing raw bytes to `images.edit` fails with `"unsupported mimetype ('application/octet-stream')"`. The SDK infers MIME type from the file-like object's `.name` property. Setting `.name = "avatar.png"` on a `BytesIO` wrapper fixes it.

**Image data should never flow through the LLM context.** A gpt-image-1 output is ~1.5MB of base64. Sending that back through the agent would bloat context and cost tokens for no reason. Tool wrappers should return a summary dict (style used, fact, dimensions, byte count) and stash the actual image data server-side for later use by upload tools.

**The sync client blocks async event loops.** Using `OpenAI()` (sync) inside an async tool wrapper freezes the entire event loop for the 30-60 seconds that image generation takes. Wrapping with `asyncio.to_thread()` moves the blocking call to a thread pool. This is easy to miss because it works fine in testing — the hang only manifests in the real async agent loop.

---

## Agent UX: Progress and Streaming

**`Runner.run()` from the OpenAI Agents SDK is non-streaming** — it returns only after all tool calls complete. There's no built-in progress callback. When image generation takes 60 seconds, the user sees nothing. The workaround was printing progress from inside `@function_tool` wrappers (`>> Fetching cat fact...`, `>> Generating image...`), and every `print()` needed `flush=True` because Python buffers stdout by default. Auth URLs and progress messages simply don't appear without explicit flushing.

---

## Writing Evals That Actually Pass

Arcade's evaluation framework tests whether an LLM selects the right tools given a natural language prompt. The gotcha is that **eval expectations must match reasonable LLM behavior**, not idealized behavior:

- "Get me 0 cat facts" — the model correctly refuses a nonsensical request rather than calling `GetCatFact(count=0)`. This isn't a failure; it's the right answer.
- "Make me cat art" — the model orchestrates multiple tools (get avatar, then generate image) rather than calling a single tool. Expecting exactly one tool call fails.
- Ambiguous prompts like "cat art" with no context — the model reasonably hedges between tools. These don't make good eval cases.

I started at 0% pass rate, got to 75% by fixing tool name prefixes (`MeowMe_GetCatFact` not `get_cat_fact`), then reached 100% by removing the 4 cases that expected unreasonable behavior. Writing fewer, better eval cases beats writing many fragile ones.

---

## Windows-Specific Pain

**`PYTHONIOENCODING=utf-8`** is required for any Arcade CLI subprocess. Arcade's output uses Unicode characters (checkmarks, progress spinners) that Windows cp1252 encoding can't render, causing crashes.

**Claude Desktop config paths differ for Windows Store installs.** The normal path is `%APPDATA%\Claude\claude_desktop_config.json`. The Windows Store version uses `%LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude\claude_desktop_config.json`. The `--directory` flag in uv args needs absolute paths on Windows.

**`logging.basicConfig()` is silently a no-op** when the root logger already has handlers — and Arcade sets up loguru + logging before your code runs. Use `force=True` to override, or write directly to files for guaranteed debug output.
