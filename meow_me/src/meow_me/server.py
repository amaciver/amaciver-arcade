#!/usr/bin/env python3
"""meow_me MCP server - Slack yourself a random cat fact."""

import sys

from arcade_mcp_server import MCPApp

app = MCPApp(name="meow_me", version="0.1.0", log_level="DEBUG")

# Module-level imports register tools with the app via @tool decorator
import meow_me.tools.facts  # noqa: E402, F401
import meow_me.tools.slack  # noqa: E402, F401

# Run with specific transport
if __name__ == "__main__":
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    app.run(transport=transport, host="127.0.0.1", port=8000)
