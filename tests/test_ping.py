"""The ping tool, called the way an agent calls it: through the MCP layer.

`Client(mcp)` connects to the server object in-process — no subprocess, no port — so this
exercises tool listing, argument validation and result wrapping exactly as Claude Code sees
them over stdio, minus the pipe. Session 2's whole suite stands on this idiom; this file is
where it is proved to work against the installed SDK.

Async tests run on the anyio pytest plugin, which `mcp` already depends on. `anyio_backend`
pins it to asyncio, the loop the SDK itself runs on under stdio.
"""

from __future__ import annotations

import pytest
from mcp import Client

from agent_tools_mcp.server import mcp


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    # raise_exceptions: a bug inside a tool surfaces as a traceback in the test rather than as
    # an `is_error` result that a careless assertion might accept.
    async with Client(mcp, raise_exceptions=True) as connected:
        yield connected


@pytest.mark.anyio
async def test_the_server_exposes_its_three_tools(client):
    tools = await client.list_tools()

    assert sorted(tool.name for tool in tools.tools) == ["index_status", "ping", "search_documents"]


@pytest.mark.anyio
async def test_ping_answers_pong_through_the_mcp_layer(client):
    result = await client.call_tool("ping", {})

    assert result.is_error is False
    assert [block.text for block in result.content] == ["pong"]
    # The SDK wraps a bare return value as {"result": ...} and publishes an output schema for
    # it. Asserted here because session 2's search results travel the same way.
    assert result.structured_content == {"result": "pong"}
