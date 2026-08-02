"""Adapter, connection, and authentication lifecycle states.

Pure data: the state enumerations the framework tracks. No broker communication
lives here.
"""

from __future__ import annotations

from enum import Enum

__all__ = [
    "AdapterState",
    "ConnectionState",
    "AuthenticationState",
    "can_connection_transition",
]


class AdapterState(str, Enum):
    """Lifecycle state of an exchange adapter."""

    CREATED = "created"
    REGISTERED = "registered"
    READY = "ready"
    ACTIVE = "active"
    ERROR = "error"
    STOPPED = "stopped"


class ConnectionState(str, Enum):
    """Broker connectivity state (abstraction — no real socket)."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    CLOSED = "closed"


class AuthenticationState(str, Enum):
    """Authentication lifecycle state (abstraction — no credentials)."""

    UNAUTHENTICATED = "unauthenticated"
    AUTHENTICATING = "authenticating"
    AUTHENTICATED = "authenticated"
    FAILED = "failed"


#: Allowed connection transitions.
_CONNECTION_TRANSITIONS: dict[ConnectionState, frozenset[ConnectionState]] = {
    ConnectionState.DISCONNECTED: frozenset(
        {ConnectionState.CONNECTING, ConnectionState.CLOSED}
    ),
    ConnectionState.CONNECTING: frozenset(
        {ConnectionState.CONNECTED, ConnectionState.CLOSED}
    ),
    ConnectionState.CONNECTED: frozenset(
        {ConnectionState.RECONNECTING, ConnectionState.CLOSED}
    ),
    ConnectionState.RECONNECTING: frozenset(
        {ConnectionState.CONNECTED, ConnectionState.CLOSED}
    ),
    ConnectionState.CLOSED: frozenset(),
}


def can_connection_transition(
    source: ConnectionState, target: ConnectionState
) -> bool:
    """Return ``True`` if a connection may move from ``source`` to ``target``."""
    return target in _CONNECTION_TRANSITIONS.get(source, frozenset())
