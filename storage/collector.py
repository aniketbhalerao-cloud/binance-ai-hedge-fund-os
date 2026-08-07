"""Storage collector.

:class:`DefaultCollector` gathers the standardized source readings in a
context, normalizes them into :class:`~storage.models.StorageSource` entries
(highest-priority-first, capped by ``max_items``), and builds a raw
:class:`~storage.models.StorageBatch` with one unserialized item per source.
Target typing and persistence routing are the Serializer and PersistencePlanner
stages' job. It is deterministic and stateless, and it only *collects* — it
never modifies any subject.
"""

from __future__ import annotations

from storage.context import StorageContext
from storage.exceptions import CollectionError
from storage.models import StorageBatch, StorageItem, StorageSource

__all__ = ["DefaultCollector"]


class DefaultCollector:
    """Stateless source collection and batch construction."""

    def collect(self, context: StorageContext) -> StorageBatch:
        """Return the raw :class:`StorageBatch` for ``context``.

        Raises:
            CollectionError: If an unexpected failure occurs.
        """
        try:
            sources = self._sources(context)
            items = tuple(StorageItem(source=s) for s in sources)
            return StorageBatch(sources=sources, items=items)
        except CollectionError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise CollectionError(str(exc)) from exc

    @staticmethod
    def _sources(
        context: StorageContext,
    ) -> tuple[StorageSource, ...]:
        candidates = [
            *context.reporting_sources,
            *context.notification_sources,
            *context.dashboard_sources,
            *context.monitoring_sources,
            *context.performance_sources,
        ]
        # Highest-priority-first, with a stable tiebreak by name for determinism.
        candidates.sort(key=lambda s: (-s.priority, s.source, s.name))
        return tuple(candidates[: context.parameters.max_items])
