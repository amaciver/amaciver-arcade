#!/usr/bin/env python3
"""meow_me MCP server - Slack yourself a random cat fact."""

import sys

# load_dotenv() is handled in meow_me/__init__.py so env vars are available
# regardless of entry point (server.py, arcade mcp, or direct import).
from arcade_mcp_server import MCPApp

app = MCPApp(name="meow_me", version="0.1.0", log_level="DEBUG")

# Import tool functions and register with the MCPApp instance.
# The @tool decorator makes them discoverable by `arcade mcp -p` (entry point).
# app.add_tool() also registers them for `arcade deploy` / direct execution.
from meow_me.tools.facts import get_cat_fact  # noqa: E402
from meow_me.tools.avatar import get_user_avatar  # noqa: E402
from meow_me.tools.image import start_cat_image_generation, check_image_status  # noqa: E402
from meow_me.tools.slack import meow_me, send_cat_fact, send_cat_image  # noqa: E402

app.add_tool(get_cat_fact)
app.add_tool(get_user_avatar)
app.add_tool(start_cat_image_generation)
app.add_tool(check_image_status)
app.add_tool(meow_me)
app.add_tool(send_cat_fact)
app.add_tool(send_cat_image)

# Run with specific transport
if __name__ == "__main__":
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    app.run(transport=transport, host="127.0.0.1", port=8000)
