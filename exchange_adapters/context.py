"""Exchange coordination context.

An :class:`ExchangeContext` is the single, immutable input the framework uses to
coordinate an exchange request. It bundles the upstream
:class:`~execution.models.ExecutionResult` plus the current authentication and
connection state, so framework components never access infrastructure directly.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from exchange_adapters.state import AuthenticationState, ConnectionState
from execution.models import ExecutionResult

__all__ = ["ExchangeContext"]


@dataclass(frozen=True, slots=True)
class ExchangeContext:
    """Immutable input for exchange-request coordination.

    Attributes:
        execution_result: The execution result (holds request + route).
        exchange: Neutral exchange label.
        symbol: Instrument.
        authentication_state: Current authentication state.
        connection_state: Current connection state.
        timestamp: When the context was assembled (UTC).
        metadata: Optional read-only extra context (e.g. target adapter).
    """

    execution_result: ExecutionResult
    exchange: str
    symbol: str
    authentication_state: AuthenticationState = AuthenticationState.UNAUTHENTICATED
    connection_state: ConnectionState = ConnectionState.DISCONNECTED
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
