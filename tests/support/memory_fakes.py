"""Helpers for Memory Framework tests.

Standalone support module (existing support files unchanged). Builds
deterministic memory contexts from normalized source readings. No network,
no sleeps, no randomness, and no model training.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from memory.context import MemoryContext
from memory.models import MemoryParameters, MemorySource

__all__ = [
    "make_source",
    "make_context",
]


def make_source(
    name: str,
    priority: str,
    *,
    source: str = "learning",
    category: str = "working",
    samples: int = 5,
) -> MemorySource:
    """Build a normalized source reading with a given priority."""
    return MemorySource(
        name=name,
        source=source,
        category=category,
        priority=Decimal(priority),
        samples=samples,
    )


def make_context(
    *,
    memory_id: str = "memory-1",
    agent: Sequence[MemorySource] | None = None,
    learning: Sequence[MemorySource] | None = None,
    reporting: Sequence[MemorySource] | None = None,
    storage: Sequence[MemorySource] | None = None,
    parameters: MemoryParameters | None = None,
    cancel: bool = False,
) -> MemoryContext:
    """Build a deterministic memory context."""
    metadata = {"cancel": True} if cancel else {}
    return MemoryContext(
        memory_id=memory_id,
        agent_sources=tuple(agent) if agent is not None else (),
        learning_sources=tuple(learning) if learning is not None
        else (make_source("cpu", "5"), make_source("mem", "-3")),
        reporting_sources=tuple(reporting) if reporting is not None else (),
        storage_sources=tuple(storage) if storage is not None else (),
        parameters=parameters or MemoryParameters(),
        correlation_id="memory-corr",
        metadata=metadata,
    )
