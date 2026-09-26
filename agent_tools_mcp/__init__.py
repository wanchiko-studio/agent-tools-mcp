"""agent-tools-mcp — gives an MCP client a tool to search documents through rag-service.

The server speaks stdio, which is what Claude Code and Claude Desktop launch locally, and it
reaches rag-service over HTTP only — never by importing that repo's code, because its embedded
vector store holds an exclusive lock that a second process would fight over.

Session 1 ships the skeleton and a single `ping` tool. Search and status arrive later.
"""

__version__ = "0.1.0"
