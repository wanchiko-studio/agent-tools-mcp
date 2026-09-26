"""The MCP server: one `MCPServer`, and the tools registered on it.

🔑 NOTHING RUNS AT IMPORT. Everything that loads the server imports this module — the stdio
entry point, the in-process test client, later the tools themselves — so starting a transport
here would start it in every one of them. `__main__.py` is the only place that calls `run()`.

`MCPServer` is the 2.x name of what 1.x called `FastMCP`. The import below was checked against
the installed SDK (`mcp/server/__init__.py`), not written from memory of the old API.
"""

from __future__ import annotations

from mcp.server import MCPServer

mcp = MCPServer("agent-tools")


@mcp.tool()
def ping() -> str:
    """Check that the agent-tools server is reachable. Always returns "pong".

    Use it only to confirm the connection works. It does not contact rag-service and does
    not read any document, so a "pong" says nothing about whether search will succeed.
    """
    return "pong"
