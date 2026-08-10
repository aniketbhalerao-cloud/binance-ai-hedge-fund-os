"""Memory planner.

:class:`DefaultPlanner` plans a raw memory batch into immutable memory
entries: it assigns each entry a memory scope, resolves whether it clears
the priority threshold for commitment, and produces the planned batch whose
entries carry their routing. It is deterministic and stateless, and it
**never applies changes** — it only constructs the memory entries.
"""

from __future__ import annotations

from memory.context import MemoryContext
from memory.exceptions import PlanningError
from memory.models import (
    SUPPORTED_MEMORY_SCOPES,
    MemoryBatch,
    MemoryEntry,
    MemoryParameters,
    MemorySource,
)

__all__ = ["DefaultPlanner"]


class DefaultPlanner:
    """Stateless batch planning (entry construction only, never applied)."""

    def plan(self, batch: MemoryBatch, context: MemoryContext) -> MemoryBatch:
        """Return the planned batch (entries carry their routing).

        Raises:
            PlanningError: If an unexpected failure occurs.
        """
        try:
            entries = tuple(
                _entry(s, context.parameters) for s in batch.sources
            )
            return MemoryBatch(sources=batch.sources, entries=entries)
        except PlanningError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise PlanningError(str(exc)) from exc


def _entry(source: MemorySource, parameters: MemoryParameters) -> MemoryEntry:
    if source.priority >= parameters.priority_threshold:
        commit, detail = True, "eligible for commitment"
    else:
        commit, detail = False, "below priority threshold"
    scope = (
        source.category if source.category in SUPPORTED_MEMORY_SCOPES else "working"
    )
    return MemoryEntry(source=source, commit=commit, scope=scope, detail=detail)
