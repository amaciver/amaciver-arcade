"""Tests for the Meow Art agent (agent.py)."""

import json

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from meow_me.agent import (
    SYSTEM_PROMPT,
    DEMO_FACTS,
    _build_tools,
    _detect_capabilities,
    _build_capability_prompt,
    _get_slack_token,
    _slack_token,
    run_demo,
)


# --- System prompt validation ---

class TestSystemPrompt:
    def test_mentions_all_tools(self):
        for tool_name in [
            "get_cat_fact", "get_user_avatar", "generate_cat_image",
            "send_cat_fact", "send_cat_image", "save_image_locally", "meow_me",
        ]:
            assert tool_name in SYSTEM_PROMPT

    def test_contains_routing_rules(self):
        assert "ROUTING RULES" in SYSTEM_PROMPT
        assert "meow_me()" in SYSTEM_PROMPT

    def test_meow_me_one_shot_instruction(self):
        assert "standalone, no modifiers" in SYSTEM_PROMPT

    def test_two_phase_flow(self):
        assert "FACT PHASE" in SYSTEM_PROMPT
        assert "DELIVERY PHASE" in SYSTEM_PROMPT

    def test_interactive_modifiers_documented(self):
        assert "Meow me to #random" in SYSTEM_PROMPT
        assert "INTERACTIVE" in SYSTEM_PROMPT


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

    def test_demo_shows_all_tools(self, capsys):
        run_demo()
        captured = capsys.readouterr()
        for tool_name in [
            "get_cat_fact", "get_user_avatar", "generate_cat_image",
            "send_cat_fact", "send_cat_image", "save_image_locally", "meow_me",
        ]:
            assert tool_name in captured.out


# --- Tool wrapper validation ---

class TestToolWrappers:
    def test_build_tools_returns_seven_tools(self):
        tools = _build_tools()
        assert len(tools) == 7

    def test_tool_names(self):
        tools = _build_tools()
        names = {t.name for t in tools}
        assert names == {
            "get_cat_fact", "generate_cat_image", "get_user_avatar",
            "send_cat_fact", "send_cat_image", "save_image_locally", "meow_me",
        }

    @pytest.mark.asyncio
    async def test_get_cat_fact_wrapper_calls_implementation(self):
        tools = _build_tools()
        get_cat_fact_tool = next(t for t in tools if t.name == "get_cat_fact")

        mock_response = MagicMock()
        mock_response.json.return_value = {"data": ["Test fact"]}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("meow_me.tools.facts.httpx.AsyncClient", return_value=mock_client):
            # Call the tool's on_invoke_tool method
            result_str = await get_cat_fact_tool.on_invoke_tool(
                {"input": json.dumps({"count": 1})}, ""
            )

        result = json.loads(result_str)
        assert result["facts"] == ["Test fact"]

    def test_all_tools_have_descriptions(self):
        tools = _build_tools()
        for tool in tools:
            assert tool.description, f"{tool.name} should have a description"

    @pytest.mark.asyncio
    async def test_get_user_avatar_requires_token(self):
        """get_user_avatar should return error when no Slack auth is available."""
        tools = _build_tools()
        tool = next(t for t in tools if t.name == "get_user_avatar")

        _slack_token["token"] = ""  # Clear cached token
        with patch.dict("os.environ", {}, clear=True):
            result_str = await tool.on_invoke_tool({"input": "{}"}, "")

        result = json.loads(result_str)
        assert "error" in result
        assert "Slack auth" in result["error"]

    @pytest.mark.asyncio
    async def test_meow_me_requires_token(self):
        """meow_me should return error when no Slack auth is available."""
        tools = _build_tools()
        tool = next(t for t in tools if t.name == "meow_me")

        _slack_token["token"] = ""  # Clear cached token
        with patch.dict("os.environ", {}, clear=True):
            result_str = await tool.on_invoke_tool({"input": "{}"}, "")

        result = json.loads(result_str)
        assert "error" in result
        assert "Slack auth" in result["error"]

    @pytest.mark.asyncio
    async def test_save_image_locally_no_image(self):
        """save_image_locally should error when no image has been generated."""
        from meow_me import agent as agent_mod
        agent_mod._last_generated_image.clear()

        tools = _build_tools()
        tool = next(t for t in tools if t.name == "save_image_locally")

        result_str = await tool.on_invoke_tool({"input": "{}"}, "")
        result = json.loads(result_str)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_save_image_locally_with_stashed_image(self):
        """save_image_locally should save the stashed image to a file."""
        import base64
        from meow_me import agent as agent_mod

        fake_png = base64.b64encode(b"fake_png_data").decode()
        agent_mod._last_generated_image["base64"] = fake_png
        agent_mod._last_generated_image["cat_fact"] = "Test fact"

        tools = _build_tools()
        tool = next(t for t in tools if t.name == "save_image_locally")

        result_str = await tool.on_invoke_tool({"input": "{}"}, "")
        result = json.loads(result_str)
        assert result["saved"] is True
        assert "meow_art" in result["path"]
        assert result["size_bytes"] > 0

        # Clean up
        import pathlib
        pathlib.Path(result["path"]).unlink(missing_ok=True)
        agent_mod._last_generated_image.clear()


# --- Capability detection ---

class TestCapabilityDetection:
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

    def test_detects_slack_token(self):
        with patch.dict("os.environ", {"SLACK_BOT_TOKEN": "xoxb-test"}, clear=True):
            caps = _detect_capabilities()
        assert caps["slack"] is True
        assert caps["openai"] is False
        assert caps["slack_available"] is True

    def test_detects_arcade_key(self):
        with patch.dict("os.environ", {"ARCADE_API_KEY": "arc-test"}, clear=True):
            caps = _detect_capabilities()
        assert caps["arcade"] is True
        assert caps["slack"] is False
        assert caps["slack_available"] is True

    def test_slack_available_with_both(self):
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
        assert "Do NOT call meow_me" in prompt

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
        assert "Do NOT call meow_me" not in prompt
        assert "send_cat_image does NOT work" in prompt


# --- Slack token resolution ---

class TestGetSlackToken:
    def setup_method(self):
        """Clear token cache before each test."""
        _slack_token["token"] = ""

    def test_returns_cached_token(self):
        _slack_token["token"] = "xoxb-cached"
        assert _get_slack_token() == "xoxb-cached"

    def test_returns_env_var_token(self):
        with patch.dict("os.environ", {"SLACK_BOT_TOKEN": "xoxb-env"}, clear=True):
            token = _get_slack_token()
        assert token == "xoxb-env"
        assert _slack_token["token"] == "xoxb-env"

    def test_caches_env_var_token(self):
        with patch.dict("os.environ", {"SLACK_BOT_TOKEN": "xoxb-env"}, clear=True):
            _get_slack_token()
        # Token should be cached even after env is restored
        assert _slack_token["token"] == "xoxb-env"

    def test_returns_empty_when_no_auth(self):
        with patch.dict("os.environ", {}, clear=True):
            token = _get_slack_token()
        assert token == ""

    def test_arcade_oauth_flow(self):
        """Test Arcade OAuth flow with mocked arcadepy client."""
        mock_auth_response = MagicMock()
        mock_auth_response.status = "completed"
        mock_auth_response.context.token = "xoxb-arcade"

        mock_client = MagicMock()
        mock_client.auth.start.return_value = mock_auth_response
        mock_client.auth.wait_for_completion.return_value = mock_auth_response

        mock_arcade_class = MagicMock(return_value=mock_client)

        with patch.dict("os.environ", {
            "ARCADE_API_KEY": "arc-test",
            "ARCADE_USER_ID": "test@example.com",
        }, clear=True):
            with patch.dict("sys.modules", {"arcadepy": MagicMock(Arcade=mock_arcade_class)}):
                with patch("meow_me.agent.Arcade", mock_arcade_class, create=True):
                    # We need to reimport to pick up the mock - instead just call directly
                    # The function does `from arcadepy import Arcade` inside the try block
                    import importlib
                    import meow_me.agent as agent_mod
                    # Patch at the import level
                    with patch("builtins.__import__", side_effect=lambda name, *args, **kwargs: (
                        MagicMock(Arcade=mock_arcade_class) if name == "arcadepy"
                        else importlib.__import__(name, *args, **kwargs)
                    )):
                        token = _get_slack_token()

        assert token == "xoxb-arcade"
        assert _slack_token["token"] == "xoxb-arcade"

    def test_arcade_oauth_prompts_for_email(self):
        """Test that Arcade OAuth prompts for email when ARCADE_USER_ID is not set."""
        mock_auth_response = MagicMock()
        mock_auth_response.status = "completed"
        mock_auth_response.context.token = "xoxb-prompted"

        mock_client = MagicMock()
        mock_client.auth.start.return_value = mock_auth_response
        mock_client.auth.wait_for_completion.return_value = mock_auth_response

        mock_arcade_class = MagicMock(return_value=mock_client)

        with patch.dict("os.environ", {"ARCADE_API_KEY": "arc-test"}, clear=True):
            with patch("builtins.input", return_value="user@example.com"):
                import importlib
                with patch("builtins.__import__", side_effect=lambda name, *args, **kwargs: (
                    MagicMock(Arcade=mock_arcade_class) if name == "arcadepy"
                    else importlib.__import__(name, *args, **kwargs)
                )):
                    token = _get_slack_token()

        assert token == "xoxb-prompted"

    def test_arcade_oauth_empty_email_returns_empty(self):
        """Test that empty email input skips Arcade OAuth."""
        with patch.dict("os.environ", {"ARCADE_API_KEY": "arc-test"}, clear=True):
            with patch("builtins.input", return_value=""):
                token = _get_slack_token()
        assert token == ""

    def test_arcade_oauth_failure_returns_empty(self):
        """Test that Arcade OAuth failure returns empty string gracefully."""
        with patch.dict("os.environ", {"ARCADE_API_KEY": "arc-test"}, clear=True):
            with patch("builtins.__import__", side_effect=lambda name, *args, **kwargs: (
                (_ for _ in ()).throw(Exception("connection failed")) if name == "arcadepy"
                else __import__(name, *args, **kwargs)
            )):
                token = _get_slack_token()
        assert token == ""

    def teardown_method(self):
        """Clean up token cache after each test."""
        _slack_token["token"] = ""
