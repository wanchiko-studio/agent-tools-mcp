"""No API key, no network, no running rag-service — enforced, not trusted.

rag-service is never running in these tests. Every HTTP exchange goes through an
`httpx.MockTransport`, and this guard makes sure nothing slips past it: an outbound TCP
connection raises instead of quietly reaching a real service.

Loopback is allowed, as in rag-service's guard: the point is to catch a real network call, not
to forbid machinery a local test harness may use. It patches `socket.socket.connect` only, so
`connect_ex`, UDP and DNS lookups are not covered — a narrowing, stated rather than hidden.
"""

from __future__ import annotations

import socket

import pytest


class NetworkAccessAttempted(RuntimeError):
    """Raised instead of opening a socket, so the failure names its own cause."""


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    real_connect = socket.socket.connect

    def guard(self: socket.socket, address, *args, **kwargs):  # type: ignore[no-untyped-def]
        host = address[0] if isinstance(address, tuple) and address else None
        if host in {"127.0.0.1", "::1", "localhost"}:
            return real_connect(self, address, *args, **kwargs)
        raise NetworkAccessAttempted(
            f"The tests must run with no network. Something tried to reach {address!r}. "
            "Talk to rag-service through an httpx.MockTransport injected into the client."
        )

    monkeypatch.setattr(socket.socket, "connect", guard)
