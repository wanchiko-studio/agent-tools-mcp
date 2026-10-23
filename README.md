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

**What the model actually reads depends on the client.** Each successful call returns two things: a
readable text block (in Russian) and the same passages as `structured_content`. In the live Claude Code
sessions below, Claude Code handed the model the `structured_content` JSON, not the text block — so the
readable text is what other MCP clients show. A tool error reaches the model as its message text.

## Requirements

- **[rag-service](https://github.com/wanchiko-studio/rag-service) running**, with at least one PDF
  indexed. It is a separate repository: clone it into the **same parent folder** as this one (the run
  command below does `cd ../rag-service`) and follow its Quick start. Until a PDF is indexed,
  `search_documents` reports an empty index. To index one, from rag-service's folder:
  `.venv/bin/python scripts/index_pdf.py <file.pdf> --reset`. This server talks to it over HTTP only
  (`POST /ask`, `GET /health`) and never imports its code.
- **Python 3.11 or 3.12** — the versions CI runs. On macOS: `brew install python@3.12`.
- An MCP client. The instructions below are for Claude Code.

## Install

```bash
git clone https://github.com/wanchiko-studio/agent-tools-mcp.git
cd agent-tools-mcp
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
```

With Python 3.11, use `python3.11` in the third line.

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

Captured from a live Claude Code session on 23 Oct 2026, run headless from this folder with only
this server attached, against the public petroleum engineering paper that `rag-eval` uses. Nothing
below was written or tidied by hand; long passage text is cut with […], and the lost spaces are the
PDF extractor's, as the model received them.

**The question**

> What program was used to model proppant migration?

**The tool call the agent made**

```json
{"question": "What program was used to model proppant migration?", "top_k": 3}
```

**What the model received** — Claude Code hands the model the tool's `structured_content`, so this
JSON is what it read (passage text cut with […]):

```json
{"question":"What program was used to model proppant migration?","hits":[{"rank":1,"score":0.3634566816076189,"citation":"petroleum-science-2022-self-generated-proppant.pdf, стр. 8","text":"[…]3.2.2. Simulationofproppantmigration (3) Initialandboundaryconditions\nCOMSOLVersion5.5wasusedtoestablishamodelforsimula-\ntionofproppantmigrationtoevaluatethemigrationcapabilityof ThemodelboundaryfollowsDirichletconditions.Leftandright\ntheself-generatedproppantwithinarealfracture.[…]","weak_match":true},{"rank":2,"score":0.3451660657685419,"citation":"petroleum-science-2022-self-generated-proppant.pdf, стр. 9","text":"[…]","weak_match":true},{"rank":3,"score":0.2647139167439335,"citation":"petroleum-science-2022-self-generated-proppant.pdf, стр. 1","text":"[…]","weak_match":true}]}
```

**The answer**

> **COMSOL (Version 5.5)** was used to model proppant migration — specifically to simulate the migration capability of the self-generated proppant within a real fracture (`petroleum-science-2022-self-generated-proppant.pdf, стр. 8`).
>
> Note: all three passages came back flagged as weak matches (top score 0.36, below the 0.5 line), but passage 1 does state the answer directly.

## When rag-service is down

Captured from a live Claude Code session on 23 Oct 2026, same question, same command, with
rag-service stopped (port 8000 refusing connections). Nothing below was written or tidied by hand.

**The tool call the agent made**

```json
{"question": "What program was used to model proppant migration?"}
```

**The tool error the model received**

```
Error executing tool search_documents: rag-service не отвечает по адресу http://127.0.0.1:8000 (connection failed (ConnectError)). Ответа из документов нет — не отвечайте по памяти. Запустите сервис: cd rag-service && .venv/bin/python -m uvicorn app.api:app
```

**The agent's reply** — it reports the service as down and does not answer from memory. Its closing
paragraph, an aside about this repository's own to-do list, is cut with […]:

> The `search_documents` tool returned a service-down error — rag-service isn't running at `http://127.0.0.1:8000`, so I have no indexed passages to cite. I won't answer from memory.
>
> To get the answer, start rag-service in another terminal:
>
> ```
> cd ../rag-service && .venv/bin/python -m uvicorn app.api:app
> ```
>
> Then re-ask the question and I'll call `search_documents` again.
>
> […]

## Tests

```bash
.venv/bin/pytest
```

21 tests, with **no API key, no network and no rag-service**. Every tool is called through the MCP
layer (the SDK's in-process `Client` against the server object), and every exchange with rag-service
goes through an `httpx.MockTransport` built from responses recorded from the real service. A guard in
`tests/conftest.py` makes any outbound TCP connection fail the test, so "no network" is enforced rather
than assumed. CI runs the same suite on Python 3.11 and 3.12.
