"""index_status, called through the MCP layer against the recorded /health response.

It exists so an agent can tell "bad retrieval" from "empty index" in one call. That is why an
empty index is a plain report here, not an error: for this tool it is the answer.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from mcp import Client

from agent_tools_mcp import rag_client
from agent_tools_mcp.server import mcp

HEALTH = json.loads((Path(__file__).parent / "fixtures" / "health.json").read_text(encoding="utf-8"))


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    async with Client(mcp, raise_exceptions=True) as connected:
        yield connected


def serve(monkeypatch, health=None, error=None, status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        if error is not None:
            raise error
        return httpx.Response(status, json=health if health is not None else HEALTH)

    monkeypatch.setattr(rag_client, "TRANSPORT", httpx.MockTransport(handler))


def text_of(result) -> str:
    return "\n".join(block.text for block in result.content)


@pytest.mark.anyio
async def test_a_populated_index_reports_store_collection_and_count(client, monkeypatch):
    serve(monkeypatch)
    result = await client.call_tool("index_status", {})

    assert result.is_error is False
    assert result.structured_content == {
        "store": "embedded (qdrant_storage)",
        "collection": "rag_eval_1200",
        "points": 55,
    }
    for part in ("embedded", "rag_eval_1200", "55"):
        assert part in text_of(result)


@pytest.mark.anyio
async def test_an_empty_index_is_reported_plainly_not_as_an_error(client, monkeypatch):
    serve(monkeypatch, health={**HEALTH, "points": 0})
    result = await client.call_tool("index_status", {})

    assert result.is_error is False
    assert result.structured_content["points"] == 0
    assert "индекс пуст" in text_of(result).lower()
    assert "index_pdf.py" in text_of(result)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "error, status",
    [(httpx.ConnectError("refused"), 200), (httpx.ReadTimeout("slow"), 200), (None, 500)],
    ids=["refused", "timeout", "5xx"],
)
async def test_an_unreachable_service_is_a_tool_error_naming_the_url(client, monkeypatch, error, status):
    monkeypatch.setenv("RAG_SERVICE_URL", "http://127.0.0.1:8765")
    serve(monkeypatch, error=error, status=status)
    result = await client.call_tool("index_status", {})

    assert result.is_error is True
    assert "http://127.0.0.1:8765" in text_of(result)
    assert "uvicorn app.api:app" in text_of(result)


@pytest.mark.anyio
async def test_the_local_store_path_is_never_echoed(client, monkeypatch):
    """The real /health reports `embedded (<absolute path>)`: a home directory and folder names."""
    serve(monkeypatch, health={**HEALTH, "mode": "embedded (/Users/someone/Work/rag-service/qdrant_storage)"})
    result = await client.call_tool("index_status", {})

    assert result.structured_content["store"] == "embedded (qdrant_storage)"
    assert "/Users/" not in text_of(result)


@pytest.mark.anyio
async def test_a_container_url_is_kept(client, monkeypatch):
    serve(monkeypatch, health={**HEALTH, "mode": "container (http://localhost:6333)"})
    result = await client.call_tool("index_status", {})

    assert result.structured_content["store"] == "container (http://localhost:6333)"
