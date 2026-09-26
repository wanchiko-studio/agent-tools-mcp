"""`python -m agent_tools_mcp` — serve over stdio. This is what Claude Code launches.

Stdio is `MCPServer.run()`'s default transport in the installed SDK (its signature is
`run(transport='stdio')`). It is spelled out anyway, so the one thing this file does is visible
in it — and so a future default change in the SDK cannot silently move the server onto a port.

⚠️ Under stdio, stdout IS the protocol channel. Nothing in this package may print to it; a stray
`print()` corrupts the JSON-RPC stream and the client drops the connection with no useful error.
"""

from agent_tools_mcp.server import mcp

mcp.run(transport="stdio")
