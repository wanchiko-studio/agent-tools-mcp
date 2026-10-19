"""search_documents, called the way an agent calls it — through the MCP layer.

One test per row of the plan's outcomes table, plus the three guards. rag-service never runs:
every exchange goes through an `httpx.MockTransport` built from responses recorded from the
real service on the public petroleum paper (`tests/fixtures/`).

🔑 The four outcomes must never look alike. "Nothing matched", "the index is empty" and "the
service is down" all arrive at an agent as an absence of passages unless the tool says which one
it is — and an agent that cannot tell will tell the user the documents say nothing.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import httpx
import pytest
from mcp import Client

from agent_tools_mcp import rag_client
from agent_tools_mcp.server import mcp

FIXTURES = Path(__file__).parent / "fixtures"
ASK = json.loads((FIXTURES / "ask.json").read_text(encoding="utf-8"))
HEALTH = json.loads((FIXTURES / "health.json").read_text(encoding="utf-8"))
QUESTION = ASK["question"]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    async with Client(mcp, raise_exceptions=True) as connected:
        yield connected


def serve(monkeypatch, ask=None, health=None, error=None, status=200):
    """Point the rag-service client at a fake service; record every request it receives."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if error is not None:
            raise error
        if request.url.path == "/health":
            return httpx.Response(status, json=health if health is not None else HEALTH)
        return httpx.Response(status, json=ask if ask is not None else ASK)

    monkeypatch.setattr(rag_client, "TRANSPORT", httpx.MockTransport(handler))
    return seen


def text_of(result) -> str:
    return "\n".join(block.text for block in result.content)


@pytest.mark.anyio
async def test_hits_come_back_cited_and_scored(client, monkeypatch):
    serve(monkeypatch)
    result = await client.call_tool("search_documents", {"question": QUESTION})

    assert result.is_error is False
    hits = result.structured_content["hits"]
    assert [hit["rank"] for hit in hits] == [1, 2, 3]
    assert hits[0]["citation"] == ASK["hits"][0]["citation"]
    assert ASK["hits"][0]["citation"] in text_of(result)


@pytest.mark.anyio
async def test_a_hit_below_the_weak_match_line_says_so(client, monkeypatch):
    """The recorded rank-1 hit scores 0.4455 — the right passage, and still a weak match."""
    serve(monkeypatch)
    result = await client.call_tool("search_documents", {"question": QUESTION})

    first = result.structured_content["hits"][0]
    assert first["score"] < rag_client.WEAK_MATCH
    assert first["weak_match"] is True
    assert "слабое совпадение" in text_of(result)


@pytest.mark.anyio
async def test_no_hits_on_a_populated_index_is_an_answer_not_an_error(client, monkeypatch):
    empty = {**ASK, "hits": []}
    serve(monkeypatch, ask=empty)
    result = await client.call_tool("search_documents", {"question": QUESTION})

    assert result.is_error is False
    assert result.structured_content["hits"] == []
    assert "не ошибка" in text_of(result)


@pytest.mark.anyio
async def test_an_empty_index_is_a_tool_error(client, monkeypatch):
    serve(monkeypatch, ask={**ASK, "hits": []}, health={**HEALTH, "points": 0})
    result = await client.call_tool("search_documents", {"question": QUESTION})

    assert result.is_error is True
    assert "индекс пуст" in text_of(result).lower()
    assert "index_pdf.py" in text_of(result)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "error, status",
    [
        (httpx.ConnectError("refused"), 200),
        (httpx.ReadTimeout("slow"), 200),
        (None, 500),
    ],
    ids=["refused", "timeout", "5xx"],
)
async def test_an_unreachable_service_is_a_tool_error_naming_the_url(client, monkeypatch, error, status):
    monkeypatch.setenv("RAG_SERVICE_URL", "http://127.0.0.1:8765")
    serve(monkeypatch, error=error, status=status)
    result = await client.call_tool("search_documents", {"question": QUESTION})

    assert result.is_error is True
    assert "http://127.0.0.1:8765" in text_of(result)
    assert "uvicorn app.api:app" in text_of(result)


@pytest.mark.anyio
@pytest.mark.parametrize("top_k", [0, 21])
async def test_top_k_out_of_bounds_is_refused_before_any_http(client, monkeypatch, top_k):
    seen = serve(monkeypatch)
    result = await client.call_tool("search_documents", {"question": QUESTION, "top_k": top_k})

    assert result.is_error is True
    assert seen == []


@pytest.mark.anyio
async def test_unknown_fields_and_a_generated_mode_do_not_break_the_tool(client, monkeypatch):
    """When rag-service gains generation it adds `answer` and changes `mode`. Hits still count."""
    future = copy.deepcopy(ASK)
    future["mode"] = "generated"
    future["answer"] = {"text": "FIXTURE"}
    future["hits"][0]["new_field"] = 1
    serve(monkeypatch, ask=future)
    result = await client.call_tool("search_documents", {"question": QUESTION})

    assert result.is_error is False
    assert len(result.structured_content["hits"]) == 3


@pytest.mark.anyio
async def test_the_service_url_is_read_at_call_time(client, monkeypatch):
    seen = serve(monkeypatch)
    monkeypatch.setenv("RAG_SERVICE_URL", "http://127.0.0.1:9999")
    await client.call_tool("search_documents", {"question": QUESTION})

    assert str(seen[0].url).startswith("http://127.0.0.1:9999/")
