"""Memory Framework domain models.

Immutable, exchange-independent value objects. The rest of the application
consumes only these standardized models. Scores use :class:`~decimal.Decimal`;
timestamps are timezone-aware UTC. Every model is frozen — batches, memory
requests, and the running record are never mutated; each remembered input
produces a **new** record.

The framework only *plans and dispatches domain objects*: ``MemoryRequest``
carries scope detail as an immutable domain object and is never persisted to
a database, embedded, or sent to a vector store anywhere, and the framework
never modifies a strategy, agent, or portfolio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from memory.state import MemoryState

__all__ = [
    "MemoryResultStatus",
    "SUPPORTED_MEMORY_SCOPES",
    "MemoryParameters",
    "MemorySource",
    "MemoryEntry",
    "MemoryBatch",
    "MemoryRequest",
    "MemoryHistory",
    "MemoryRecord",
    "MemoryMetrics",
    "MemorySnapshot",
    "MemoryResult",
]

_ZERO = Decimal("0")

#: The memory scopes the framework recognizes and can route (domain only).
SUPPORTED_MEMORY_SCOPES: frozenset[str] = frozenset(
    {"working", "episodic", "semantic"}
)


class MemoryResultStatus(str, Enum):
    """Coarse outcome of remembering one input."""

    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class MemoryParameters:
    """Deterministic memory configuration.

    Attributes:
        priority_threshold: Priority at or above which an entry is committed.
        max_items: Maximum number of entries to plan per input.
    """

    priority_threshold: Decimal = _ZERO
    max_items: int = 5


@dataclass(frozen=True, slots=True)
class MemorySource:
    """A normalized memory datum feeding one entry."""

    name: str
    source: str
    category: str = "unknown"
    priority: Decimal = _ZERO
    samples: int = 0


@dataclass(frozen=True, slots=True)
class MemoryEntry:
    """A planned entry within a batch (an immutable domain object, never embedded)."""

    source: MemorySource
    commit: bool = True
    scope: str = "working"
    detail: str = ""


@dataclass(frozen=True, slots=True)
class MemoryBatch:
    """An immutable batch: the collected sources and their planned entries."""

    sources: tuple[MemorySource, ...] = ()
    entries: tuple[MemoryEntry, ...] = ()


@dataclass(frozen=True, slots=True)
class MemoryRequest:
    """A deterministic memory request (an immutable object, never persisted)."""

    subject: str
    source: str
    scope: str
    category: str = "unknown"
    priority: Decimal = _ZERO
    detail: str = ""


@dataclass(frozen=True, slots=True)
class MemoryHistory:
    """Append-only record of produced batches."""

    batches: tuple[MemoryBatch, ...] = ()

    def append(self, batch: MemoryBatch) -> MemoryHistory:
        """Return a new history with ``batch`` appended (never mutates)."""
        return MemoryHistory(self.batches + (batch,))


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """The durable, immutable running state of one memory session.

    The Registry owns the current ``MemoryRecord``; the Manager loads it,
    processes one input, and writes back a **new** ``MemoryRecord``.
    """

    id: str
    state: MemoryState
    history: MemoryHistory = field(default_factory=MemoryHistory)
    batch: MemoryBatch = field(default_factory=MemoryBatch)
    requests: tuple[MemoryRequest, ...] = ()
    entry_count: int = 0
    request_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class MemoryMetrics:
    """Derived metrics over a memory record."""

    total_entries: int = 0
    total_requests: int = 0
    average_memory_score: Decimal = _ZERO
    highest_priority_entry: str = ""
    lowest_priority_entry: str = ""
    commit_ratio: Decimal = _ZERO
    pending_requests_count: int = 0
    suppressed_requests_count: int = 0


@dataclass(frozen=True, slots=True)
class MemorySnapshot:
    """A complete, immutable record of one memory update."""

    record: MemoryRecord
    metrics: MemoryMetrics
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class MemoryResult:
    """The immutable outcome of remembering one input."""

    status: MemoryResultStatus
    record: MemoryRecord | None = None
    snapshot: MemorySnapshot | None = None
    batch: MemoryBatch | None = None
    requests: tuple[MemoryRequest, ...] = ()
    metrics: MemoryMetrics | None = None
    errors: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        """Return ``True`` when the input was remembered successfully."""
        return self.status is MemoryResultStatus.SUCCESS
