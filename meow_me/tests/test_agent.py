"""Tests for the Meow Art agent (agent.py).

After the cloud-first refactor, the agent is a thin client that calls tools
remotely via the Arcade platform. Tests focus on:
- System prompt correctness (MCP-namespaced tool names, async image flow)
- Demo mode (scripted output)
- Capability detection and prompt adaptation
"""

import pytest
from unittest.mock import patch

from meow_me.agent import (
    SYSTEM_PROMPT,
    DEMO_FACTS,
    _detect_capabilities,
    _build_capability_prompt,
    run_demo,
)


# --- System prompt validation ---

class TestSystemPrompt:
    def test_mentions_all_mcp_tools(self):
        """System prompt references all tools with MeowMe_ prefix."""
        for tool_name in [
            "MeowMe_GetCatFact", "MeowMe_GetUserAvatar",
            "MeowMe_StartCatImageGeneration", "MeowMe_CheckImageStatus",
            "MeowMe_SendCatFact", "MeowMe_SendCatImage",
            "MeowMe_MeowMe",
        ]:
            assert tool_name in SYSTEM_PROMPT, f"{tool_name} not found in SYSTEM_PROMPT"

    def test_does_not_reference_removed_tools(self):
        """System prompt should not reference old tools."""
        assert "MeowMe_GenerateCatImage" not in SYSTEM_PROMPT
        assert "MeowMe_SaveImageLocally" not in SYSTEM_PROMPT

    def test_contains_routing_rules(self):
        assert "ROUTING RULES" in SYSTEM_PROMPT
        assert "MeowMe_MeowMe()" in SYSTEM_PROMPT

    def test_meow_me_one_shot_instruction(self):
        assert "standalone, no modifiers" in SYSTEM_PROMPT

    def test_two_phase_flow(self):
        assert "FACT PHASE" in SYSTEM_PROMPT
        assert "DELIVERY PHASE" in SYSTEM_PROMPT

    def test_interactive_modifiers_documented(self):
        assert "Meow me to #random" in SYSTEM_PROMPT
        assert "INTERACTIVE" in SYSTEM_PROMPT

    def test_mentions_arcade_deployment(self):
        """System prompt indicates tools are Arcade-deployed."""
        assert "Arcade" in SYSTEM_PROMPT

    def test_async_image_flow_documented(self):
        """System prompt documents the async start/poll pattern."""
        assert "StartCatImageGeneration" in SYSTEM_PROMPT
        assert "CheckImageStatus" in SYSTEM_PROMPT
        assert "poll" in SYSTEM_PROMPT.lower()

    def test_handling_tool_responses_section(self):
        """System prompt has guidance for interpreting tool fallbacks."""
        assert "HANDLING TOOL RESPONSES" in SYSTEM_PROMPT
        assert "image_sent=false" in SYSTEM_PROMPT


# --- Demo mode validation ---

class TestDemoMode:
    def test_demo_facts_are_populated(self):
        assert len(DEMO_FACTS) >= 5

    def test_demo_facts_are_strings(self):
        for fact in DEMO_FACTS:
            assert isinstance(fact, str)
            assert len(fact) > 10

    def test_demo_runs_without_error(self, capsys):
        run_demo()
        captured = capsys.readouterr()
        assert "SCENARIO 1" in captured.out
        assert "SCENARIO 2" in captured.out
        assert "SCENARIO 3" in captured.out
        assert "SCENARIO 4" in captured.out
        assert "DEMO COMPLETE" in captured.out

    def test_demo_shows_all_mcp_tools(self, capsys):
        """Demo references tools by MCP-namespaced names."""
        run_demo()
        captured = capsys.readouterr()
        for tool_name in [
            "MeowMe_GetCatFact", "MeowMe_GetUserAvatar",
            "MeowMe_StartCatImageGeneration", "MeowMe_CheckImageStatus",
            "MeowMe_SendCatFact", "MeowMe_SendCatImage",
            "MeowMe_MeowMe",
        ]:
            assert tool_name in captured.out, f"{tool_name} not in demo output"

    def test_demo_does_not_reference_removed_tools(self, capsys):
        """Demo should not mention old tools."""
        run_demo()
        captured = capsys.readouterr()
        assert "MeowMe_GenerateCatImage" not in captured.out
        assert "MeowMe_SaveImageLocally" not in captured.out

    def test_demo_shows_async_polling(self, capsys):
        """Demo scenario 3 should show the start/poll pattern."""
        run_demo()
        captured = capsys.readouterr()
        assert "StartCatImageGeneration" in captured.out
        assert "CheckImageStatus" in captured.out


# --- Arcade SDK integration ---

class TestArcadeIntegration:
    """Tests that the agent connects to tools via Arcade SDK (not direct imports)."""

    def test_agent_does_not_import_tool_modules(self):
        """Verify agent.py has no imports from meow_me.tools.*"""
        import inspect
        import meow_me.agent as agent_mod
        source = inspect.getsource(agent_mod)
        assert "from meow_me.tools" not in source
        assert "import meow_me.tools" not in source

    def test_agent_uses_arcade_sdk(self):
        """Verify agent.py references Arcade SDK components."""
        import inspect
        import meow_me.agent as agent_mod
        source = inspect.getsource(agent_mod)
        assert "AsyncArcade" in source
        assert "get_arcade_tools" in source

    def test_agent_has_no_function_tool_wrappers(self):
        """Verify agent.py doesn't define @function_tool wrappers."""
        import inspect
        import meow_me.agent as agent_mod
        source = inspect.getsource(agent_mod)
        assert "@function_tool" not in source

    def test_agent_has_no_slack_flag(self):
        """Verify agent.py doesn't have --slack flag (removed in cloud-first refactor)."""
        import inspect
        import meow_me.agent as agent_mod
        source = inspect.getsource(agent_mod)
        assert '"--slack"' not in source
        assert "_slack_config" not in source
        assert "_resolve_human_user" not in source


# --- Capability detection ---

class TestCapabilityDetection:
    def test_detects_no_keys(self):
        with patch.dict("os.environ", {}, clear=True):
            caps = _detect_capabilities()
        assert caps["arcade"] is False

    def test_detects_arcade_key(self):
        with patch.dict("os.environ", {"ARCADE_API_KEY": "arc-test"}, clear=True):
            caps = _detect_capabilities()
        assert caps["arcade"] is True

    def test_only_has_arcade_key(self):
        """Capability dict should only have arcade (secrets are cloud-side)."""
        with patch.dict("os.environ", {}, clear=True):
            caps = _detect_capabilities()
        assert set(caps.keys()) == {"arcade"}

    def test_openai_key_not_in_capabilities(self):
        """OPENAI_API_KEY is a cloud secret, not detected locally."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=True):
            caps = _detect_capabilities()
        assert "openai" not in caps


class TestCapabilityPrompt:
    def test_arcade_connected_prompt(self):
        prompt = _build_capability_prompt({"arcade": True})
        assert "CONNECTED" in prompt
        assert "Image generation" in prompt

    def test_no_arcade_prompt(self):
        prompt = _build_capability_prompt({"arcade": False})
        assert "NOT CONNECTED" in prompt

    def test_arcade_connected_shows_image_limitation(self):
        prompt = _build_capability_prompt({"arcade": True})
        assert "MCP server mode" in prompt
        assert "Image generation" in prompt

    def test_arcade_connected_disables_image_tools(self):
        """Agent should not call image gen tools via Arcade Cloud."""
        prompt = _build_capability_prompt({"arcade": True})
        assert "StartCatImageGeneration" in prompt
        assert "Do NOT call" in prompt

    def test_tools_mention_mcp_alternative(self):
        prompt = _build_capability_prompt({"arcade": True})
        assert "Claude Desktop" in prompt or "Cursor" in prompt

    def test_no_slack_config_references(self):
        """Capability prompt should not mention --slack flag."""
        prompt = _build_capability_prompt({"arcade": True})
        assert "--slack" not in prompt
        assert "SLACK_BOT_TOKEN" not in prompt

    def test_meow_me_falls_back_to_text(self):
        """MeowMe_MeowMe should still work but fall back to text."""
        prompt = _build_capability_prompt({"arcade": True})
        assert "MeowMe_MeowMe" in prompt
        assert "text-only" in prompt.lower()
