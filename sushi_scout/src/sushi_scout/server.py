#!/usr/bin/env python3
"""sushi_scout MCP server - Find the cheapest tuna sushi roll nearby."""

import sys

from arcade_mcp_server import MCPApp

app = MCPApp(name="sushi_scout", version="0.1.0", log_level="DEBUG")

# Import tool modules so @tool decorators register with the framework
import sushi_scout.tools.search  # noqa: E402, F401
import sushi_scout.tools.menu  # noqa: E402, F401
import sushi_scout.tools.ordering  # noqa: E402, F401

# Run with specific transport
if __name__ == "__main__":
    # - "stdio" (default): Standard I/O for Claude Desktop, CLI tools, etc.
    # - "http": HTTPS streaming for Cursor, VS Code, etc.
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    app.run(transport=transport, host="127.0.0.1", port=8000)
