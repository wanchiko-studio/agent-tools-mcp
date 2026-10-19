"""The guard that makes "no network" a property of the suite rather than a promise.

Matched on the message, not the class: a conftest can be imported under two module names
depending on how pytest is invoked, and `isinstance` then fails against what is the same class.
"""

from __future__ import annotations

import socket

import pytest


def test_an_outbound_connection_is_refused():
    with socket.socket() as sock, pytest.raises(RuntimeError, match="no network"):
        sock.connect(("192.0.2.1", 80))  # TEST-NET-1: reserved, never routable
