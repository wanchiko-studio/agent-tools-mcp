"""The MCP server: one `MCPServer`, and the tools registered on it.

🔑 NOTHING RUNS AT IMPORT. Everything that loads the server imports this module — the stdio
entry point, the in-process test client, later the tools themselves — so starting a transport
here would start it in every one of them. `__main__.py` is the only place that calls `run()`.

`MCPServer` is the 2.x name of what 1.x called `FastMCP`. The import below was checked against
the installed SDK (`mcp/server/__init__.py`), not written from memory of the old API.
"""

from __future__ import annotations

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult, TextContent

from agent_tools_mcp import rag_client

mcp = MCPServer("agent-tools")


@mcp.tool()
def ping() -> str:
    """Check that the agent-tools server is reachable. Always returns "pong".

    Use it only to confirm the connection works. It does not contact rag-service and does
    not read any document, so a "pong" says nothing about whether search will succeed.
    """
    return "pong"


MAX_TOP_K = 20  # rag-service's own bound; above it, /ask answers 422


@mcp.tool()
def search_documents(question: str, top_k: int = 3) -> CallToolResult:
    """Search the user's indexed documents through rag-service and return the passages.

    Use this for any question about the documents the user has indexed. It returns ranked
    PASSAGES, not an answer: read them, write the answer yourself, and cite the page given in
    each passage's citation (for example «file.pdf, стр. 4–5») for every claim you take from it.
    A passage marked as a weak match may not answer the question; say so rather than present it
    as the answer. If no passage comes back, the documents do not cover the question.
    """
    # Refused here, before any HTTP: a bad top_k should not cost a round trip or become a 422.
    if not 1 <= top_k <= MAX_TOP_K:
        raise ToolError(f"top_k должен быть от 1 до {MAX_TOP_K}, получено {top_k}.")

    try:
        body = rag_client.ask(question, top_k)
        hits = [_passage(hit) for hit in body.get("hits", [])]
        # Only an empty result needs /health: a non-empty one already proves the index has points.
        if not hits and rag_client.health().get("points", 0) == 0:
            raise ToolError(
                "Индекс пуст: в rag-service не проиндексировано ни одного документа, поэтому "
                "искать не в чем. Это не значит, что в документах нет ответа. Проиндексируйте PDF: "
                "cd rag-service && .venv/bin/python scripts/index_pdf.py <файл.pdf> --reset"
            )
    except rag_client.ServiceUnavailable as exc:
        # Raised deliberately as a ToolError: an ordinary exception would reach the agent with its
        # text withheld, and the agent would improvise an answer as if nothing were wrong.
        raise ToolError(
            f"rag-service не отвечает по адресу {exc.url} ({exc.cause}). Ответа из документов нет — "
            f"не отвечайте по памяти. Запустите сервис: {rag_client.START_COMMAND}"
        ) from exc

    if not hits:
        text = (
            "Ни один отрывок не оказался достаточно близок к вопросу. Это не ошибка: индекс не пуст, "
            "но в проиндексированных документах ответа на этот вопрос, по-видимому, нет."
        )
    else:
        text = "\n\n".join(_render(hit) for hit in hits)
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        structured_content={"question": question, "hits": hits},
    )


def _passage(hit: dict) -> dict:
    """Keep only the fields this server relies on, so new ones from rag-service cannot break it."""
    score = float(hit["score"])
    return {
        "rank": hit["rank"],
        "score": score,
        "citation": hit["citation"],
        "text": hit["text"],
        "weak_match": score < rag_client.WEAK_MATCH,
    }


def _render(hit: dict) -> str:
    note = " — слабое совпадение, может не отвечать на вопрос" if hit["weak_match"] else ""
    return f"#{hit['rank']} · {hit['citation']} · score {hit['score']:.4f}{note}\n{hit['text']}"
