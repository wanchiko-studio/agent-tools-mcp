"""Talking to rag-service over HTTP — its public contract, never its code.

🔑 HTTP ONLY. rag-service's embedded Qdrant holds an exclusive lock on its folder, so importing
its store from a second process would fight the API for it. The contract this reads is
`POST /ask` and `GET /health` in `../rag-service/app/api.py`.

Configuration is read at CALL time, not import time. rag-service found and fixed exactly that bug
with `QDRANT_COLLECTION`: a module-level `os.getenv` freezes the value at first import, and a
later change is silently ignored.
"""

from __future__ import annotations

import os

import httpx

DEFAULT_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT_SECONDS = 10.0

# 🔑 The weak-match line is rag-service's, not ours, and it is NOT a tuning knob. rag-service
# documents "~0.5 — слабое совпадение" in the `score` field of `app/api.py` and in
# `scripts/ask.py`. Changing it needs a measurement, the same rule as its `max_chars`.
WEAK_MATCH = 0.5

# Tests replace this with an httpx.MockTransport. None means a real connection.
TRANSPORT: httpx.BaseTransport | None = None

START_COMMAND = "cd rag-service && .venv/bin/python -m uvicorn app.api:app"


class ServiceUnavailable(Exception):
    """rag-service could not be reached, timed out, or failed with a 5xx."""

    def __init__(self, url: str, cause: str) -> None:
        super().__init__(f"{url}: {cause}")
        self.url = url
        self.cause = cause


def service_url() -> str:
    return (os.getenv("RAG_SERVICE_URL") or DEFAULT_URL).rstrip("/")


def timeout_seconds() -> float:
    return float(os.getenv("RAG_TIMEOUT_SECONDS") or DEFAULT_TIMEOUT_SECONDS)


def _request(method: str, path: str, **kwargs) -> dict:
    url = service_url()
    try:
        with httpx.Client(base_url=url, timeout=timeout_seconds(), transport=TRANSPORT) as http:
            response = http.request(method, path, **kwargs)
    except httpx.TimeoutException as exc:
        raise ServiceUnavailable(url, f"no answer within {timeout_seconds():g} s") from exc
    except httpx.TransportError as exc:
        raise ServiceUnavailable(url, f"connection failed ({type(exc).__name__})") from exc
    if response.status_code >= 500:
        raise ServiceUnavailable(url, f"HTTP {response.status_code}")
    response.raise_for_status()
    return response.json()


def ask(question: str, top_k: int) -> dict:
    """`POST /ask`. Unknown fields are ignored by the caller, so a future `answer` is harmless."""
    return _request("POST", "/ask", json={"question": question, "top_k": top_k})


def health() -> dict:
    """`GET /health` — the only way to tell an empty index from a question nothing matched."""
    return _request("GET", "/health")
