"""meow_me - Cat fact art MCP server for Slack."""

# Load .env early so all tool modules can access env vars (e.g. OPENAI_API_KEY)
# regardless of entry point (server.py, arcade mcp, or direct import).
import logging
import os

from dotenv import load_dotenv

load_dotenv()

# Write debug logs to file when DEBUG_LOG env var is set, so we can
# troubleshoot MCP tool calls in Claude Desktop (no visible console).
_log_path = os.getenv("MEOW_ME_DEBUG_LOG")
if _log_path:
    # Use force=True so our handler is installed even if arcade already
    # configured the root logger (logging.basicConfig is a no-op otherwise).
    logging.basicConfig(
        filename=_log_path,
        level=logging.DEBUG,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        force=True,
    )


# ---------------------------------------------------------------------------
# Monkey-patch arcade-mcp-server to support MCP ImageContent in tool results.
#
# Arcade @tool decorated functions must return dicts (per their typed schemas).
# arcade-mcp-server's convert_to_mcp_content() converts these dicts to MCP
# content, but by default only emits TextContent. We patch it to detect a
# special `_mcp_image: {data, mimeType}` key in tool return dicts and emit
# an ImageContent block alongside the TextContent, enabling inline image
# previews in Claude Desktop.
# ---------------------------------------------------------------------------
def _install_image_content_patch() -> None:
    """Patch convert_to_mcp_content to emit ImageContent for _mcp_image keys."""
    _trace = os.getenv("MEOW_ME_DEBUG_LOG")

    def _trace_write(msg: str) -> None:
        """Write directly to trace file (bypasses logging framework)."""
        if _trace:
            try:
                with open(_trace, "a", encoding="utf-8") as f:
                    from datetime import datetime
                    f.write(f"{datetime.now().isoformat()} PATCH-TRACE {msg}\n")
            except Exception:
                pass

    try:
        import arcade_mcp_server.convert as _convert_mod
        import arcade_mcp_server.server as _server_mod
        from arcade_mcp_server.types import ImageContent, TextContent
    except ImportError:
        _trace_write("SKIP: arcade_mcp_server not installed")
        return  # arcade-mcp-server not installed; skip (e.g. lightweight test env)

    _original = _convert_mod.convert_to_mcp_content

    def _patched_convert(value):  # type: ignore[no-untyped-def]
        if isinstance(value, dict) and "_mcp_image" in value:
            _trace_write(f"INTERCEPT: found _mcp_image, data length={len(value['_mcp_image'].get('data', ''))}")
            image_info = value.pop("_mcp_image")
            # Convert the remaining dict to TextContent via the original func
            text_blocks = _original(value) if value else []
            # Append the image as a real ImageContent block
            img_content = ImageContent(
                type="image",
                data=image_info["data"],
                mimeType=image_info.get("mimeType", "image/png"),
            )
            text_blocks.append(img_content)
            _trace_write(f"RETURN: {len(text_blocks)} blocks ({[type(b).__name__ for b in text_blocks]})")
            return text_blocks
        return _original(value)

    # Patch on both modules (server.py uses a from-import, so it holds its own ref)
    _convert_mod.convert_to_mcp_content = _patched_convert
    _server_mod.convert_to_mcp_content = _patched_convert
    _trace_write("INSTALLED: patched convert_to_mcp_content on convert + server modules")


_install_image_content_patch()
