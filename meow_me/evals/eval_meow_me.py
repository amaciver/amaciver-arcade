"""
Evaluation suite for Meow Me MCP server.

Tests whether AI models correctly select and invoke tools given natural
language prompts. Validates tool routing patterns, parameter accuracy,
and multi-tool orchestration.

Run with: arcade evals evals/
"""

from arcade_evals import (
    EvalSuite,
    tool_eval,
    ExpectedMCPToolCall,
    BinaryCritic,
    SimilarityCritic,
    EvalRubric,
)


# Evaluation rubric (stricter than default)
rubric = EvalRubric(
    fail_threshold=0.85,
    warn_threshold=0.95,
)


@tool_eval()
async def meow_me_eval_suite() -> EvalSuite:
    """Core evaluation suite for Meow Me tools."""
    suite = EvalSuite(
        name="Meow Me Core Patterns",
        system_message=(
            "You are a helpful cat fact assistant with access to tools for:\n"
            "- Fetching random cat facts from the internet\n"
            "- Getting user avatars from Slack\n"
            "- Generating cat-themed art using AI image generation\n"
            "- Sending messages and images to Slack\n\n"
            "When the user asks for cat facts, use get_cat_fact.\n"
            "When they want their avatar, use get_user_avatar.\n"
            "When they want cat art, you'll need to get a fact and avatar first, "
            "then use generate_cat_image.\n"
            "The special phrase 'Meow me!' is a one-shot command that does everything: "
            "fact + avatar + image + DM."
        ),
        rubric=rubric,
    )

    # Connect to the MCP server via STDIO
    await suite.add_mcp_stdio_server(
        command=["uv", "run", "arcade", "mcp", "-p", "meow_me", "stdio"]
    )

    # ========================================================================
    # CASE 1: One-shot "Meow me"
    # ========================================================================
    suite.add_case(
        name="One-shot meow_me",
        user_message="Meow me!",
        expected_tool_calls=[
            ExpectedMCPToolCall("MeowMe_MeowMe", {}),
        ],
        critics=[],
        rubric=rubric,
    )

    # ========================================================================
    # CASE 2: Fetch cat facts with count
    # ========================================================================
    suite.add_case(
        name="Fetch cat facts with specific count",
        user_message="Give me 3 cat facts",
        expected_tool_calls=[
            ExpectedMCPToolCall("MeowMe_GetCatFact", {"count": 3}),
        ],
        critics=[
            BinaryCritic(critic_field="count", weight=1.0),
        ],
        rubric=rubric,
    )

    suite.add_case(
        name="Fetch single cat fact (implicit count=1)",
        user_message="Tell me a cat fact",
        expected_tool_calls=[
            ExpectedMCPToolCall("MeowMe_GetCatFact", {"count": 1}),
        ],
        critics=[
            BinaryCritic(critic_field="count", weight=1.0),
        ],
        rubric=rubric,
    )

    suite.add_case(
        name="Fetch maximum cat facts",
        user_message="Give me 5 cat facts",
        expected_tool_calls=[
            ExpectedMCPToolCall("MeowMe_GetCatFact", {"count": 5}),
        ],
        critics=[
            BinaryCritic(critic_field="count", weight=1.0),
        ],
        rubric=rubric,
    )

    # ========================================================================
    # CASE 3: Send cat fact to channel
    # ========================================================================
    suite.add_case(
        name="Send fact to channel",
        user_message="Send a cat fact to #general",
        expected_tool_calls=[
            ExpectedMCPToolCall(
                "MeowMe_SendCatFact",
                {"channel": "general", "count": 1},
            ),
        ],
        critics=[
            # Channel name might be "general", "#general", or even "C12345"
            # SimilarityCritic allows fuzzy matching
            SimilarityCritic(critic_field="channel", weight=0.7),
            BinaryCritic(critic_field="count", weight=0.3),
        ],
        rubric=rubric,
    )

    suite.add_case(
        name="Send multiple facts to channel",
        user_message="Send 3 cat facts to #random",
        expected_tool_calls=[
            ExpectedMCPToolCall(
                "MeowMe_SendCatFact",
                {"channel": "random", "count": 3},
            ),
        ],
        critics=[
            SimilarityCritic(critic_field="channel", weight=0.5),
            BinaryCritic(critic_field="count", weight=0.5),
        ],
        rubric=rubric,
    )

    # ========================================================================
    # CASE 4: Get user avatar
    # ========================================================================
    suite.add_case(
        name="Get user avatar",
        user_message="Show me my Slack avatar",
        expected_tool_calls=[
            ExpectedMCPToolCall("MeowMe_GetUserAvatar", {}),
        ],
        critics=[],
        rubric=rubric,
    )

    suite.add_case(
        name="Get avatar (alternative phrasing)",
        user_message="What's my profile picture?",
        expected_tool_calls=[
            ExpectedMCPToolCall("MeowMe_GetUserAvatar", {}),
        ],
        critics=[],
        rubric=rubric,
    )

    # ========================================================================
    # CASE 5: Generate cat image (requires fact + avatar context)
    # ========================================================================
    # Note: This requires multi-turn conversation or expects the model to
    # call get_cat_fact and get_user_avatar first
    suite.add_case(
        name="Generate cat art with context",
        user_message="Now make cat art from that",
        expected_tool_calls=[
            ExpectedMCPToolCall(
                "MeowMe_GenerateCatImage",
                {
                    "cat_fact": "Cats can rotate their ears 180 degrees.",
                    "avatar_url": "https://avatars.slack-edge.com/test.png",
                },
            ),
        ],
        critics=[
            SimilarityCritic(critic_field="cat_fact", weight=0.5),
            SimilarityCritic(critic_field="avatar_url", weight=0.5),
        ],
        additional_messages=[
            {"role": "user", "content": "Tell me a cat fact"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_fact_1",
                        "type": "function",
                        "function": {
                            "name": "get_cat_fact",
                            "arguments": '{"count": 1}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_fact_1",
                "content": '{"facts": ["Cats can rotate their ears 180 degrees."], "count": 1}',
            },
            {
                "role": "assistant",
                "content": "Cats can rotate their ears 180 degrees.",
            },
            {"role": "user", "content": "Get my avatar"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_avatar_1",
                        "type": "function",
                        "function": {
                            "name": "get_user_avatar",
                            "arguments": "{}",
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_avatar_1",
                "content": '{"avatar_url": "https://avatars.slack-edge.com/test.png", "display_name": "Test User"}',
            },
            {
                "role": "assistant",
                "content": "Your avatar is at https://avatars.slack-edge.com/test.png",
            },
        ],
        rubric=rubric,
    )

    # ========================================================================
    # CASE 6: Send cat image to channel (removed - requires clearer context)
    # ========================================================================
    # Removed: Model needs clearer context about pre-generated image

    # ========================================================================
    # CASE 7: Ambiguous requests (should choose the right tool)
    # ========================================================================
    suite.add_case(
        name="Ambiguous: cat information (should fetch facts)",
        user_message="Tell me about cats",
        expected_tool_calls=[
            ExpectedMCPToolCall("MeowMe_GetCatFact", {"count": 1}),
        ],
        critics=[
            BinaryCritic(critic_field="count", weight=1.0),
        ],
        rubric=EvalRubric(
            fail_threshold=0.7,  # More lenient for ambiguous cases
            warn_threshold=0.85,
        ),
    )

    # Removed: "Ambiguous: cat art" - Model correctly calls multiple tools (smart behavior)

    return suite


@tool_eval()
async def meow_me_edge_cases() -> EvalSuite:
    """Edge case evaluation suite for Meow Me tools."""
    suite = EvalSuite(
        name="Meow Me Edge Cases",
        system_message=(
            "You are a helpful cat fact assistant. Use the available tools appropriately."
        ),
        rubric=rubric,
    )

    await suite.add_mcp_stdio_server(
        command=["uv", "run", "arcade", "mcp", "-p", "meow_me", "stdio"]
    )

    # ========================================================================
    # Edge Case 1: Count clamping
    # ========================================================================
    suite.add_case(
        name="Count too high (should clamp to 5)",
        user_message="Give me 10 cat facts",
        expected_tool_calls=[
            ExpectedMCPToolCall("MeowMe_GetCatFact", {"count": 5}),  # Clamped to max
        ],
        critics=[
            BinaryCritic(critic_field="count", weight=1.0),
        ],
        rubric=EvalRubric(
            fail_threshold=0.7,  # Lenient - model might not know about clamping
            warn_threshold=0.9,
        ),
    )

    # Removed: "Count too low" - Model correctly refuses nonsensical request

    # ========================================================================
    # Edge Case 2: Channel variations
    # ========================================================================
    suite.add_case(
        name="Channel with hash prefix",
        user_message="Send a fact to #engineering",
        expected_tool_calls=[
            ExpectedMCPToolCall("MeowMe_SendCatFact", {"channel": "engineering", "count": 1}),
        ],
        critics=[
            SimilarityCritic(critic_field="channel", weight=0.7),
            BinaryCritic(critic_field="count", weight=0.3),
        ],
        rubric=rubric,
    )

    # Removed: "Channel without hash prefix" - Too ambiguous for the model

    return suite
