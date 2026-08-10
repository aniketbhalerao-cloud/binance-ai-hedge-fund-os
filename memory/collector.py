"""Memory collector.

:class:`DefaultCollector` gathers the standardized source readings in a
context, normalizes them into :class:`~memory.models.MemorySource` entries
(highest-priority-first, capped by ``max_items``), and builds a raw
:class:`~memory.models.MemoryBatch` with one unplanned entry per source.
Scope typing and commit routing are the Planner and Dispatcher stages' job.
It is deterministic and stateless, and it only *collects* — it never
modifies any subject.
"""

from __future__ import annotations

from memory.context import MemoryContext
from memory.exceptions import CollectionError
from memory.models import MemoryBatch, MemoryEntry, MemorySource

__all__ = ["DefaultCollector"]


class DefaultCollector:
    """Stateless source collection and batch construction."""

    def collect(self, context: MemoryContext) -> MemoryBatch:
        """Return the raw :class:`MemoryBatch` for ``context``.

        Raises:
            CollectionError: If an unexpected failure occurs.
        """
        try:
            sources = self._sources(context)
            entries = tuple(MemoryEntry(source=s) for s in sources)
            return MemoryBatch(sources=sources, entries=entries)
        except CollectionError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise CollectionError(str(exc)) from exc

    @staticmethod
    def _sources(
        context: MemoryContext,
    ) -> tuple[MemorySource, ...]:
        candidates = [
            *context.agent_sources,
            *context.learning_sources,
            *context.reporting_sources,
            *context.storage_sources,
        ]
        # Highest-priority-first, with a stable tiebreak by name for determinism.
        candidates.sort(key=lambda s: (-s.priority, s.source, s.name))
        return tuple(candidates[: context.parameters.max_items])
