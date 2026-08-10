"""Memory context.

An immutable input carrying standardized outputs from across the running
system — agent decisions, learning records, report objects, and storage
requests — plus the memory parameters. Memory components never access
infrastructure directly; they read only from this context and the models it
carries, and they never modify any subject. Upstream frameworks are
responsible for normalizing their outputs into
:class:`~memory.models.MemorySource` readings; this framework only plans and
dispatches immutable memory requests from them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from memory.models import MemoryParameters, MemorySource

__all__ = ["MemoryContext"]


@dataclass(frozen=True, slots=True)
class MemoryContext:
    """Immutable input for producing memory requests.

    Attributes:
        memory_id: Identifier of the memory record to update.
        agent_sources: Agent memory readings to plan.
        learning_sources: Learning memory readings to plan.
        reporting_sources: Reporting memory readings to plan.
        storage_sources: Storage memory readings to plan.
        parameters: Deterministic memory parameters.
        correlation_id: Optional correlation id propagated to events.
        timestamp: When the context was assembled (UTC).
        metadata: Optional read-only extra context.
    """

    memory_id: str = "memory"
    agent_sources: tuple[MemorySource, ...] = ()
    learning_sources: tuple[MemorySource, ...] = ()
    reporting_sources: tuple[MemorySource, ...] = ()
    storage_sources: tuple[MemorySource, ...] = ()
    parameters: MemoryParameters = field(default_factory=MemoryParameters)
    correlation_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "agent_sources", tuple(self.agent_sources))
        object.__setattr__(self, "learning_sources", tuple(self.learning_sources))
        object.__setattr__(self, "reporting_sources", tuple(self.reporting_sources))
        object.__setattr__(self, "storage_sources", tuple(self.storage_sources))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
