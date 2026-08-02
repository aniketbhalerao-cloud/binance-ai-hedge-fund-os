"""Execution Framework domain models.

Immutable, broker-independent value objects: the execution request the framework
coordinates, its validation/routing records, and the result. They reuse the
Order Framework's :class:`~order_management.models.OrderRequest` /
:class:`~order_management.models.OrderRoute` and add no broker-specific fields.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any

from execution.state import ExecutionState
from order_management.models import OrderRequest, OrderRoute

__all__ = [
    "ExecutionStatus",
    "ExecutionIdentifier",
    "ExecutionMetadata",
    "ExecutionRequest",
    "ExecutionValidationResult",
    "ExecutionRoute",
    "ExecutionResult",
]


class ExecutionStatus(str, Enum):
    """Coarse outcome of an execution's framework coordination."""

    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class ExecutionIdentifier:
    """A neutral, application-level execution identifier."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    order_id: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionMetadata:
    """Immutable, free-form metadata attached to execution models."""

    data: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", MappingProxyType(dict(self.data)))

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    """A standardized, immutable execution request (no broker fields).

    Attributes:
        identifier: Application-level identifier.
        order_request: The standardized order to execute (from Order Framework).
        order_route: The order's prepared route, if any.
        exchange: Neutral exchange label.
        symbol: Instrument to execute.
        state: Current lifecycle state.
        metadata: Optional metadata.
    """

    identifier: ExecutionIdentifier
    order_request: OrderRequest
    exchange: str
    symbol: str
    order_route: OrderRoute | None = None
    state: ExecutionState = ExecutionState.CREATED
    metadata: ExecutionMetadata = field(default_factory=ExecutionMetadata)


@dataclass(frozen=True, slots=True)
class ExecutionValidationResult:
    """The outcome of validating an :class:`ExecutionRequest`."""

    valid: bool
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExecutionRoute:
    """Prepared execution routing (no broker connection is made)."""

    destination: str
    metadata: ExecutionMetadata = field(default_factory=ExecutionMetadata)


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """The immutable outcome of coordinating an execution through the framework."""

    status: ExecutionStatus
    state: ExecutionState
    request: ExecutionRequest | None = None
    validation: ExecutionValidationResult | None = None
    route: ExecutionRoute | None = None
    errors: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        """Return ``True`` when coordination succeeded and is ready for the adapter."""
        return self.status is ExecutionStatus.READY

    @property
    def execution_id(self) -> str | None:
        """Return the execution id, if a request was created."""
        return self.request.identifier.id if self.request is not None else None
