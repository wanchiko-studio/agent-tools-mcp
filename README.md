# agent-tools-mcp

An agent answering questions about your documents needs to search them and cite the page it took each claim from.
This MCP server gives it that tool, over your own [rag-service](https://github.com/wanchiko-studio/rag-service) index.

[![CI](https://github.com/wanchiko-studio/agent-tools-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/wanchiko-studio/agent-tools-mcp/actions/workflows/ci.yml)

**It never confuses three kinds of silence.** "Nothing matched", "the index is empty" and "the
service is down" all look like an empty answer unless a tool says which one it is — and an agent
that cannot tell will tell the user the documents say nothing, or answer from memory as if nothing
went wrong. Each of the three reaches the agent as a distinct, tested outcome.

---

## What it exposes

| Tool | What the agent gets |
|---|---|
| `search_documents(question, top_k=3)` | Ranked passages from rag-service, each with its score and a citation such as «file.pdf, стр. 8». Passages, not an answer: the agent writes the answer and cites the page. A passage scoring below rag-service's documented weak-match line (~0.5) is flagged as a weak match. |
| `index_status()` | Which store rag-service is using (embedded or container), which collection, and how many passages are indexed — so "bad retrieval" and "empty index" can be told apart in one call. |
| `ping()` | Returns "pong". Proves the connection, and nothing more. |

### The four outcomes of `search_documents`

| Situation | What the agent receives |
|---|---|
| Passages found | The passages, scores and citations; any below the weak-match line carries a note saying so |
| No passage close enough, index not empty | A normal result saying no passage matched, and that this is not an error |
| Index empty | A **tool error** saying the index is empty and how to index a PDF |
| rag-service unreachable, timed out, or 5xx | A **tool error** naming the URL tried and the command that starts the service |

The weak-match line is rag-service's own (documented in its `app/api.py` and `scripts/ask.py`). It is
a fixed constant here, not a tuning knob.

## Requirements

- **rag-service running**, with at least one document indexed. This server talks to it over HTTP
  only (`POST /ask`, `GET /health`) and never imports its code.
- **Python 3.11 or 3.12** — the versions CI runs.
- An MCP client. The instructions below are for Claude Code.

## Install

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
```

Dependencies are pinned: `mcp` 2.2.0 (the 2.x SDK, `MCPServer`), `httpx` 0.28.1, `pytest` 9.1.1.

## Run

Start rag-service first, from its own folder (it listens on `http://127.0.0.1:8000` by default):

```bash
cd ../rag-service && .venv/bin/python -m uvicorn app.api:app
```

The server itself speaks **stdio** and is normally launched by the MCP client, not by hand:

```bash
.venv/bin/python -m agent_tools_mcp
```

Two settings, read each time a tool is called rather than once at start-up:

| Variable | Default | Meaning |
|---|---|---|
| `RAG_SERVICE_URL` | `http://127.0.0.1:8000` | Where rag-service is listening |
| `RAG_TIMEOUT_SECONDS` | `10` | How long to wait for it before reporting it as down |

## Attach it to Claude Code

The repository ships a project-scoped `.mcp.json`:

```json
{
  "mcpServers": {
    "agent-tools": {
      "type": "stdio",
      "command": ".venv/bin/python",
      "args": ["-m", "agent_tools_mcp"],
      "env": {}
    }
  }
}
```

**Launch Claude Code from inside this folder.** The command is a relative path, so it only resolves
here, and a session started elsewhere simply has no tool and does not say so. Check it with:

```bash
claude mcp list
```

which should show `agent-tools: .venv/bin/python -m agent_tools_mcp - ✓ Connected`. The first
interactive session asks once to approve the project's servers. To point at a rag-service on another
address, set `RAG_SERVICE_URL` in the `env` block.

## Worked example

> **PLACEHOLDER — to be filled from a real, live Claude Code session, not written by hand.**
> It will show: the question asked, the `search_documents` call the agent made, the passage that came
> back, and the answer citing the page — quoted as the session produced it, on the public petroleum
> engineering paper that `rag-eval` uses.

## When rag-service is down

> **PLACEHOLDER — to be filled from a real session with rag-service stopped.**
> It will show the agent receiving the "rag-service is not answering" tool error and telling the user
> the service is down, instead of answering from memory.

## Tests

```bash
pytest
```

21 tests, with **no API key, no network and no rag-service**. Every tool is called through the MCP
layer (the SDK's in-process `Client` against the server object), and every exchange with rag-service
goes through an `httpx.MockTransport` built from responses recorded from the real service. A guard in
`tests/conftest.py` makes any outbound TCP connection fail the test, so "no network" is enforced rather
than assumed. CI runs the same suite on Python 3.11 and 3.12.
