"""Exchange Adapter Framework domain models.

Immutable, broker-independent value objects: the exchange request the framework
prepares, the adapter response/validation records, and the result. They reuse the
Execution Framework's :class:`~execution.models.ExecutionRequest` /
:class:`~execution.models.ExecutionRoute` and add no broker-specific fields.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any

from execution.models import ExecutionRequest, ExecutionRoute

from exchange_adapters.state import AuthenticationState, ConnectionState

__all__ = [
    "ExchangeStatus",
    "ExchangeIdentifier",
    "ExchangeMetadata",
    "ExchangeRequest",
    "ExchangeResponse",
    "ExchangeValidationResult",
    "ExchangeRoute",
    "ExchangeResult",
]


class ExchangeStatus(str, Enum):
    """Coarse outcome of framework coordination for an exchange request."""

    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ExchangeIdentifier:
    """A neutral, application-level exchange-request identifier."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    adapter_name: str | None = None


@dataclass(frozen=True, slots=True)
class ExchangeMetadata:
    """Immutable, free-form metadata attached to exchange models."""

    data: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", MappingProxyType(dict(self.data)))

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


@dataclass(frozen=True, slots=True)
class ExchangeRequest:
    """A standardized, broker-independent request handed to an adapter.

    Attributes:
        identifier: Application-level identifier.
        execution_request: The upstream execution request (translated input).
        execution_route: The execution's prepared route, if any.
        exchange: Neutral exchange label.
        symbol: Instrument.
        adapter_name: Target adapter name (set during routing).
        metadata: Optional metadata.
    """

    identifier: ExchangeIdentifier
    execution_request: ExecutionRequest
    exchange: str
    symbol: str
    execution_route: ExecutionRoute | None = None
    adapter_name: str | None = None
    metadata: ExchangeMetadata = field(default_factory=ExchangeMetadata)


@dataclass(frozen=True, slots=True)
class ExchangeResponse:
    """The abstract response an adapter produces (no broker payload)."""

    accepted: bool
    message: str = ""
    metadata: ExchangeMetadata = field(default_factory=ExchangeMetadata)


@dataclass(frozen=True, slots=True)
class ExchangeValidationResult:
    """The outcome of validating an :class:`ExchangeRequest`."""

    valid: bool
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExchangeRoute:
    """Prepared routing (which adapter receives the request; no connection)."""

    adapter_name: str
    metadata: ExchangeMetadata = field(default_factory=ExchangeMetadata)


@dataclass(frozen=True, slots=True)
class ExchangeResult:
    """The immutable outcome of coordinating an exchange request."""

    status: ExchangeStatus
    request: ExchangeRequest | None = None
    response: ExchangeResponse | None = None
    authentication_state: AuthenticationState = AuthenticationState.UNAUTHENTICATED
    connection_state: ConnectionState = ConnectionState.DISCONNECTED
    route: ExchangeRoute | None = None
    errors: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        """Return ``True`` when coordination succeeded (ready for the adapter)."""
        return self.status is ExchangeStatus.READY
