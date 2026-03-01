"""Tests for the Meow Art agent (agent.py).

After the Arcade SDK refactor, the agent is a thin client that calls tools
remotely via the Arcade platform. Tests focus on:
- System prompt correctness (MCP-namespaced tool names)
- Demo mode (scripted output)
- Capability detection and prompt adaptation
- --slack mode user resolution
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from meow_me.agent import (
    SYSTEM_PROMPT,
    DEMO_FACTS,
    _detect_capabilities,
    _build_capability_prompt,
    _match_users,
    _resolve_human_user,
    _slack_config,
    run_demo,
)


# --- System prompt validation ---

class TestSystemPrompt:
    def test_mentions_all_mcp_tools(self):
        """System prompt references all tools with MeowMe_ prefix."""
        for tool_name in [
            "MeowMe_GetCatFact", "MeowMe_GetUserAvatar", "MeowMe_GenerateCatImage",
            "MeowMe_SendCatFact", "MeowMe_SendCatImage", "MeowMe_SaveImageLocally",
            "MeowMe_MeowMe",
        ]:
            assert tool_name in SYSTEM_PROMPT, f"{tool_name} not found in SYSTEM_PROMPT"

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
            "MeowMe_GetCatFact", "MeowMe_GetUserAvatar", "MeowMe_GenerateCatImage",
            "MeowMe_SendCatFact", "MeowMe_SendCatImage", "MeowMe_SaveImageLocally",
            "MeowMe_MeowMe",
        ]:
            assert tool_name in captured.out, f"{tool_name} not in demo output"


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


# --- Capability detection ---

class TestCapabilityDetection:
    def setup_method(self):
        _slack_config["use_direct_token"] = False

    def teardown_method(self):
        _slack_config["use_direct_token"] = False

    def test_detects_no_keys(self):
        with patch.dict("os.environ", {}, clear=True):
            caps = _detect_capabilities()
        assert caps["openai"] is False
        assert caps["slack"] is False
        assert caps["arcade"] is False
        assert caps["slack_available"] is False

    def test_detects_openai_key(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=True):
            caps = _detect_capabilities()
        assert caps["openai"] is True
        assert caps["slack"] is False
        assert caps["slack_available"] is False

    def test_detects_slack_token_with_flag(self):
        _slack_config["use_direct_token"] = True
        with patch.dict("os.environ", {"SLACK_BOT_TOKEN": "xoxb-test"}, clear=True):
            caps = _detect_capabilities()
        assert caps["slack"] is True
        assert caps["openai"] is False
        assert caps["slack_available"] is True

    def test_ignores_slack_token_without_flag(self):
        _slack_config["use_direct_token"] = False
        with patch.dict("os.environ", {"SLACK_BOT_TOKEN": "xoxb-test"}, clear=True):
            caps = _detect_capabilities()
        assert caps["slack"] is False
        assert caps["slack_available"] is False

    def test_detects_arcade_key(self):
        with patch.dict("os.environ", {"ARCADE_API_KEY": "arc-test"}, clear=True):
            caps = _detect_capabilities()
        assert caps["arcade"] is True
        assert caps["slack"] is False
        assert caps["slack_available"] is True

    def test_slack_available_with_both(self):
        _slack_config["use_direct_token"] = True
        with patch.dict("os.environ", {
            "SLACK_BOT_TOKEN": "xoxb-test", "ARCADE_API_KEY": "arc-test"
        }, clear=True):
            caps = _detect_capabilities()
        assert caps["slack"] is True
        assert caps["arcade"] is True
        assert caps["slack_available"] is True

    def test_capability_prompt_no_slack(self):
        prompt = _build_capability_prompt({
            "openai": True, "slack": False, "arcade": False, "slack_available": False,
        })
        assert "NOT AVAILABLE" in prompt
        assert "Do NOT call MeowMe_MeowMe" in prompt

    def test_capability_prompt_all_available(self):
        prompt = _build_capability_prompt({
            "openai": True, "slack": True, "arcade": False, "slack_available": True,
        })
        assert "CONNECTED" in prompt
        assert "AVAILABLE" in prompt

    def test_capability_prompt_arcade_only(self):
        prompt = _build_capability_prompt({
            "openai": True, "slack": False, "arcade": True, "slack_available": True,
        })
        assert "Arcade OAuth" in prompt
        assert "AVAILABLE" in prompt
        assert "Do NOT call MeowMe_MeowMe" not in prompt
        assert "MeowMe_SendCatImage does NOT work" in prompt


# --- User resolution (--slack mode) ---

# Sample workspace members for testing
_SAMPLE_MEMBERS = [
    {
        "id": "U001",
        "name": "andrew",
        "deleted": False,
        "is_bot": False,
        "profile": {"display_name": "Andrew M", "real_name": "Andrew MacIver"},
    },
    {
        "id": "U002",
        "name": "jane",
        "deleted": False,
        "is_bot": False,
        "profile": {"display_name": "Jane", "real_name": "Jane Doe"},
    },
    {
        "id": "U003",
        "name": "testbot",
        "deleted": False,
        "is_bot": True,
        "profile": {"display_name": "Test Bot", "real_name": "Test Bot"},
    },
    {
        "id": "U004",
        "name": "deleted_user",
        "deleted": True,
        "is_bot": False,
        "profile": {"display_name": "Gone", "real_name": "Deleted User"},
    },
    {
        "id": "U005",
        "name": "andy",
        "deleted": False,
        "is_bot": False,
        "profile": {"display_name": "Andy", "real_name": "Andy Smith"},
    },
]


class TestMatchUsers:
    def _active_users(self):
        """Return non-bot, non-deleted users (what _fetch_slack_users would return)."""
        return [m for m in _SAMPLE_MEMBERS if not m.get("is_bot") and not m.get("deleted")]

    def test_exact_name_match(self):
        matches = _match_users(self._active_users(), "andrew")
        assert len(matches) == 1
        assert matches[0]["id"] == "U001"

    def test_display_name_match(self):
        matches = _match_users(self._active_users(), "Jane")
        assert len(matches) == 1
        assert matches[0]["id"] == "U002"

    def test_case_insensitive(self):
        matches = _match_users(self._active_users(), "ANDREW")
        assert len(matches) == 1
        assert matches[0]["id"] == "U001"

    def test_strips_at_sign(self):
        matches = _match_users(self._active_users(), "@jane")
        assert len(matches) == 1
        assert matches[0]["id"] == "U002"

    def test_partial_match(self):
        """'and' matches both 'andrew' and 'andy'."""
        matches = _match_users(self._active_users(), "and")
        ids = {m["id"] for m in matches}
        assert "U001" in ids
        assert "U005" in ids

    def test_no_match(self):
        matches = _match_users(self._active_users(), "nonexistent")
        assert len(matches) == 0


class TestResolveHumanUser:
    def setup_method(self):
        _slack_config.pop("target_user_id", None)
        _slack_config.pop("target_display_name", None)

    def teardown_method(self):
        _slack_config.pop("target_user_id", None)
        _slack_config.pop("target_display_name", None)

    @pytest.mark.asyncio
    async def test_single_match_resolves(self):
        active = [m for m in _SAMPLE_MEMBERS if not m.get("is_bot") and not m.get("deleted")]
        with patch("meow_me.agent._fetch_slack_users", new_callable=AsyncMock, return_value=active):
            with patch("builtins.input", return_value="jane"):
                result = await _resolve_human_user("xoxb-test")
        assert result["user_id"] == "U002"
        assert _slack_config["target_user_id"] == "U002"

    @pytest.mark.asyncio
    async def test_multiple_matches_user_picks(self):
        active = [m for m in _SAMPLE_MEMBERS if not m.get("is_bot") and not m.get("deleted")]
        # "and" matches andrew and andy; user picks #2 (andy)
        with patch("meow_me.agent._fetch_slack_users", new_callable=AsyncMock, return_value=active):
            with patch("builtins.input", side_effect=["and", "2"]):
                result = await _resolve_human_user("xoxb-test")
        assert result["user_id"] == "U005"
        assert _slack_config["target_user_id"] == "U005"

    @pytest.mark.asyncio
    async def test_no_match_retries(self):
        active = [m for m in _SAMPLE_MEMBERS if not m.get("is_bot") and not m.get("deleted")]
        # First try fails, second succeeds
        with patch("meow_me.agent._fetch_slack_users", new_callable=AsyncMock, return_value=active):
            with patch("builtins.input", side_effect=["nobody", "jane"]):
                result = await _resolve_human_user("xoxb-test")
        assert result["user_id"] == "U002"
