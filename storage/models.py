"""Storage Framework domain models.

Immutable, exchange-independent value objects. The rest of the application
consumes only these standardized models. Scores use :class:`~decimal.Decimal`;
timestamps are timezone-aware UTC. Every model is frozen — batches, storage
requests, and the running record are never mutated; each stored input produces
a **new** record.

The framework only *serializes and plans domain objects*: ``StorageRequest``
carries persistence detail as an immutable domain object and is never written,
uploaded, or persisted anywhere, and the framework never modifies a strategy,
agent, or portfolio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from storage.state import StorageState

__all__ = [
    "StorageResultStatus",
    "SUPPORTED_STORAGE_TARGETS",
    "StorageParameters",
    "StorageSource",
    "StorageItem",
    "StorageBatch",
    "StorageRequest",
    "StorageHistory",
    "StorageRecord",
    "StorageMetrics",
    "StorageSnapshot",
    "StorageResult",
]

_ZERO = Decimal("0")

#: The storage targets the framework recognizes and can route (domain only).
SUPPORTED_STORAGE_TARGETS: frozenset[str] = frozenset(
    {"database", "file", "object_storage", "cache", "data_lake", "archive"}
)


class StorageResultStatus(str, Enum):
    """Coarse outcome of storing one input."""

    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class StorageParameters:
    """Deterministic storage configuration.

    Attributes:
        priority_threshold: Priority at or above which an item is persisted.
        max_items: Maximum number of items to serialize per input.
    """

    priority_threshold: Decimal = _ZERO
    max_items: int = 5


@dataclass(frozen=True, slots=True)
class StorageSource:
    """A normalized storage datum feeding one item."""

    name: str
    source: str
    category: str = "unknown"
    priority: Decimal = _ZERO
    samples: int = 0


@dataclass(frozen=True, slots=True)
class StorageItem:
    """A serialized item within a batch (an immutable domain object, never written)."""

    source: StorageSource
    persist: bool = True
    target: str = "database"
    detail: str = ""


@dataclass(frozen=True, slots=True)
class StorageBatch:
    """An immutable batch: the collected sources and their serialized items."""

    sources: tuple[StorageSource, ...] = ()
    items: tuple[StorageItem, ...] = ()


@dataclass(frozen=True, slots=True)
class StorageRequest:
    """A deterministic storage request (an immutable object, never persisted)."""

    subject: str
    source: str
    target: str
    category: str = "unknown"
    priority: Decimal = _ZERO
    detail: str = ""


@dataclass(frozen=True, slots=True)
class StorageHistory:
    """Append-only record of produced batches."""

    batches: tuple[StorageBatch, ...] = ()

    def append(self, batch: StorageBatch) -> StorageHistory:
        """Return a new history with ``batch`` appended (never mutates)."""
        return StorageHistory(self.batches + (batch,))


@dataclass(frozen=True, slots=True)
class StorageRecord:
    """The durable, immutable running state of one storage session.

    The Registry owns the current ``StorageRecord``; the Manager loads it,
    processes one input, and writes back a **new** ``StorageRecord``.
    """

    id: str
    state: StorageState
    history: StorageHistory = field(default_factory=StorageHistory)
    batch: StorageBatch = field(default_factory=StorageBatch)
    requests: tuple[StorageRequest, ...] = ()
    item_count: int = 0
    request_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class StorageMetrics:
    """Derived metrics over a storage record."""

    total_items: int = 0
    total_requests: int = 0
    average_storage_score: Decimal = _ZERO
    highest_priority_item: str = ""
    lowest_priority_item: str = ""
    persistence_ratio: Decimal = _ZERO
    pending_requests_count: int = 0
    suppressed_requests_count: int = 0


@dataclass(frozen=True, slots=True)
class StorageSnapshot:
    """A complete, immutable record of one storage update."""

    record: StorageRecord
    metrics: StorageMetrics
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class StorageResult:
    """The immutable outcome of storing one input."""

    status: StorageResultStatus
    record: StorageRecord | None = None
    snapshot: StorageSnapshot | None = None
    batch: StorageBatch | None = None
    requests: tuple[StorageRequest, ...] = ()
    metrics: StorageMetrics | None = None
    errors: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        """Return ``True`` when the input was stored successfully."""
        return self.status is StorageResultStatus.SUCCESS
