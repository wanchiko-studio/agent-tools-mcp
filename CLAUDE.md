# Working notes for this repo

Context an assistant needs before touching anything here. The README (session 3) is written for a
reviewer; this file is for whoever codes next. The build plan is `../agent-tools-mcp-PLAN.md` — the
source of truth for scope and sessions. Read it first.

## What this is

An **MCP server** that gives an MCP client (Claude Code, Claude Desktop, another agent) a tool to
search documents through `../rag-service`, with passages, scores and page citations — and that tells
the agent the difference between **"nothing matched"**, **"the index is empty"** and **"the service
is down"** instead of letting all three look like an empty answer.

## Architecture — decided, do not relitigate

```
Claude Code ──stdio / MCP──▶ agent-tools-mcp ──HTTP──▶ rag-service (FastAPI) ──▶ Qdrant
                                (this repo)              POST /ask, GET /health
```

| Decision | Choice | Why |
|---|---|---|
| SDK | The official MCP Python SDK, **`mcp` 2.x** (`MCPServer`) | Same language as rag-service |
| Transport | **stdio only** | What Claude Code and Claude Desktop launch locally. Streamable HTTP is a later, separate decision |
| Reaching rag-service | **Over HTTP, against its public contract. NEVER by importing `app.*`** | Its embedded Qdrant holds an exclusive lock on its folder; a second process importing the store would fight the API for it. HTTP also keeps the repos independent |
| HTTP client | **`httpx`**, added in session 2 | `MockTransport` makes the no-network tests trivial |
| Config | `RAG_SERVICE_URL` (default `http://127.0.0.1:8000`), `RAG_TIMEOUT_SECONDS` (default 10) | Read **at call time, not import time** — rag-service already found and fixed exactly this bug with `QDRANT_COLLECTION` |
| Generation | **None.** Tools return passages; the agent writes the answer | No API key anywhere in this repo |
| Python | 3.11 and 3.12 (CI, session 3); built on 3.12 | Same claim as rag-service |

## Two facts the plan did not know, found in session 1

1. **The SDK is on its 2.x line, and 2.x renamed things.** Checked against the installed source
   (`.venv/lib/python3.12/site-packages/mcp/`), not memory — re-check it before using anything new:
   - The decorator server is **`from mcp.server import MCPServer`**. `FastMCP` is the 1.x name.
   - `@mcp.tool(name, title, description, annotations, icons, meta, structured_output)`. The
     docstring is the description the model sees. Sync tools run in a thread; async are awaited.
   - `MCPServer.run(transport='stdio')` — stdio is the default. Only `__main__.py` calls it.
   - Tests connect in-process: **`from mcp import Client`; `async with Client(mcp,
     raise_exceptions=True) as client`** — no subprocess, no port.
   - Results are snake_case: `result.content`, `result.structured_content`, `result.is_error`.
     A bare `str` return arrives as one text block **and** as `structured_content={"result": ...}`.
   - Tool errors: `from mcp.server.mcpserver.exceptions import ToolError` → the client gets
     `is_error=True` with the message. An ordinary exception also becomes `is_error=True`, but its
     text is withheld from the client. Session 2's two "tool error" outcomes must raise `ToolError`
     deliberately, or the agent receives an error with no explanation.
   - **The SDK's own HTTP dependency is `httpx2`, not `httpx`.** Never import it; it is the SDK's
     internal. This repo's rag-service client uses `httpx`, pinned separately.
2. **Registration is project-scoped.** `claude mcp add --scope project` wrote the committed
   `.mcp.json`, with the relative command `.venv/bin/python -m agent_tools_mcp`. Nothing is
   registered in `~/.claude.json` (checked: no user-scope entry, no project entry, no mention).

## 🔑 Launch Claude Code from INSIDE this folder

`.mcp.json` is only read when Claude Code starts in this folder, and its `.venv/bin/python` is
relative, so it only resolves here. Measured on 26 Sept:

```
agent-tools-mcp/     $ claude mcp list
agent-tools: .venv/bin/python -m agent_tools_mcp - ✓ Connected

30-Day-Build-Plan/   $ claude mcp list
No MCP servers configured. Use `claude mcp add` to add a server.
```

A session opened in the parent folder has no server and will not say so — the agent simply has no
tool. The first interactive session here asks once to approve the project's servers.

## Verifying against Claude Code

- Connection: `claude mcp list` from this folder must show `✓ Connected`.
- A real call, headless, loading only this server and pre-approving only the named tool:
  `claude -p "…" --mcp-config .mcp.json --strict-mcp-config --allowedTools mcp__agent-tools__ping --output-format stream-json --verbose`
  `stream-json` shows the `tool_use` and its `tool_result`, which is the proof the tool was called
  rather than the model guessing its output. `--verbose` is required with `stream-json` in `-p` mode.
- `claude -p` authenticates with the **CLI's own login**, which can expire independently of any other
  Claude session. A `401 OAuth access token is invalid` there is an account problem, not a server one.
- ⚠️ Under stdio, **stdout is the protocol channel.** Nothing may `print()` to it; a stray line
  corrupts the JSON-RPC stream and the client drops the connection with no useful error.

## rag-service's contract — read `../rag-service/app/api.py`, not this summary

Verified against its code at commit `8463ad9`: `POST /ask` `{question: 1–1000 chars, top_k: 1–20,
default 3}` → `{question, mode: "retrieval-only", top_k, hits: [{rank, score, citation, source_file,
page_start, page_end, text}]}`; an empty `hits` list is a **200**. `GET /health` → `{status, mode,
collection, points}`; `points == 0` means the index is empty. Validation failures are 422.

Three things that are easy to get wrong later:

- **The "~0.5 is a weak match" figure is documented only in Russian**, in `api.py`'s `score` field
  description and `scripts/ask.py` — not in rag-service's README. Cite those when defining the
  constant. **It is not a tuning knob:** changing it needs a measurement.
- **`/health`'s `mode` is `embedded (<absolute local path>)`** in embedded mode — a home directory and
  folder names. `index_status` must not echo it raw; `rag-eval` hit exactly this and had to redact it.
- **`mode` is the discriminator.** When rag-service gains generation, responses add an `answer` object
  and `mode` becomes `"generated"`. Ignore unknown fields and branch on `mode`; never break on it.

## Conventions — non-negotiable

- Commits: **bare single-line subjects, no trailers, no `Co-Authored-By`.** The history reads as one
  author's.
- Commit email is the **GitHub noreply address** `278246409+wanchiko-studio@users.noreply.github.com`,
  set repo-local — it was set before the first commit here.
- **`pwd` before any `git` command.** An accidental `git init` in `$HOME` has cost an hour before.
- **Nothing private in the repo** — no private documents or quotes from them, and no names of people
  or organisations other than the tools used, in files, comments or commit messages. Test fixtures
  and demos come **only** from the public petroleum paper `rag-eval` uses. When starting rag-service
  to record fixtures, point `QDRANT_COLLECTION` at a `rag_eval_*` collection, never `tenders`.
- Credentials never in the repo; `SET_YOUR_OWN` placeholders in `.env.example`.
- Comments and docstrings explain **why**, especially where a simpler option was rejected.
- Russian for text a user reads in tool output; English for README and code.

## Environment

- **Intel macOS (x86_64).** Python 3.12 at `/usr/local/opt/python@3.12/bin/python3.12` (keg-only).
- Always invoke as `.venv/bin/python`, never through an activated shell.
- Pins are the versions pip actually installed: `mcp==2.2.0`, `pytest==9.1.1`. Async tests use the
  anyio pytest plugin that `mcp` brings; no other async plugin is installed or needed.
- `pytest.ini` sets `pythonpath = .`, so bare `pytest` works — the trap rag-service lost an evening to.

## Current state

Sessions 1 and 2 of 4 are done. `ping`, and `search_documents` over HTTP with the four outcomes kept
distinct (hits with a weak-match flag below `WEAK_MATCH = 0.5` · nothing matched is a normal result ·
empty index is a `ToolError` · service down is a `ToolError` naming the URL and the start command),
the socket guard, and real `/health` + `/ask` fixtures from `rag_eval_1200`. Session 3 has
started: `index_status` is done. 21 tests.

## Where session 2 stopped (19 Oct, 11:41 MSK)

**Done-when met.** All four outcome rows are tested and green, and a live headless session answered
"what program was used to model proppant migration?" with «COMSOL (Version 5.5) … стр. 8» — calling
`search_documents` and citing the page without being told to. Session 1 was closed the same morning:
a real `ping` call returned «pong».

Three things learned, for session 3:

1. **Claude Code shows the model the `structured_content`, not the readable text.** The tool result
   it received was the JSON (`hits`, `score`, `weak_match`), so the Russian notes in the text block
   are what *other* clients read. The model still acted on `weak_match`. If the README's worked
   example quotes tool output, quote what Claude Code actually showed.
2. **The correct passage is itself a weak match.** rag-eval's q9 answer ranks 1st at 0.4455 (0.4310
   with the agent's reworded query) — below the ~0.5 line. The flag is right to fire; do not move the
   constant.
3. **rag-service's embedding model lives in a temp cache that macOS clears.** The first `/ask` after a
   clear downloads ~0.22 GB, and with `HF_HUB_OFFLINE=1` it fails with a 500 instead. Start the
   service online the first time.

**Session 3, 19 Oct 11:55 MSK — `index_status` is done.** It reports store, collection and passage
count from `/health`; an empty index is a plain report naming `scripts/index_pdf.py`, not an error
(for this tool it is the answer); refused / timeout / 5xx raise the same `ToolError` as
`search_documents`, now built by one shared `_service_down()` so the two cannot drift. The store's
absolute local path is cut to its folder name (`embedded (qdrant_storage)`); a container URL is kept.

**What session 3 still needs, in order:**

1. **CI** — GitHub Actions on 3.11 + 3.12, mirroring `../rag-service/.github/workflows/ci.yml`
   without its compose step. Bare `pytest`; the socket guard must hold on the runner.
2. **README** — the problem in the first two lines; a worked example with real output (the Claude
   Code session, the tool call, the passage, the cited page) **and** the failure case: rag-service
   stopped → the agent says the service is down instead of inventing an answer.
3. **Decide the structured-JSON-vs-readable-text finding** (point 1 above): Claude Code passed the
   model the `structured_content`, not the Russian text block. The README must quote what the model
   actually saw; whether the text block still earns its place is a decision, not an assumption.
4. **Clean-clone check** — clone into `/tmp`, follow only the README, `pytest` green.

First command: `cd "02 — Demos & Builds/30-Day-Build-Plan/agent-tools-mcp" && .venv/bin/python -m pytest`
