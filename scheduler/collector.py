"""Scheduler collector.

:class:`DefaultCollector` gathers the standardized source readings in a
context, normalizes them into :class:`~scheduler.models.ScheduleSource`
entries (highest-priority-first, capped by ``max_items``), and builds a raw
:class:`~scheduler.models.ScheduleBatch` with one unplanned entry per source.
Cadence typing and dispatch routing are the Planner and Dispatcher stages'
job. It is deterministic and stateless, and it only *collects* — it never
modifies any subject.
"""

from __future__ import annotations

from scheduler.context import SchedulerContext
from scheduler.exceptions import CollectionError
from scheduler.models import ScheduleBatch, ScheduleEntry, ScheduleSource

__all__ = ["DefaultCollector"]


class DefaultCollector:
    """Stateless source collection and batch construction."""

    def collect(self, context: SchedulerContext) -> ScheduleBatch:
        """Return the raw :class:`ScheduleBatch` for ``context``.

        Raises:
            CollectionError: If an unexpected failure occurs.
        """
        try:
            sources = self._sources(context)
            entries = tuple(ScheduleEntry(source=s) for s in sources)
            return ScheduleBatch(sources=sources, entries=entries)
        except CollectionError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise CollectionError(str(exc)) from exc

    @staticmethod
    def _sources(
        context: SchedulerContext,
    ) -> tuple[ScheduleSource, ...]:
        candidates = [
            *context.storage_sources,
            *context.reporting_sources,
            *context.notification_sources,
            *context.monitoring_sources,
            *context.optimization_sources,
        ]
        # Highest-priority-first, with a stable tiebreak by name for determinism.
        candidates.sort(key=lambda s: (-s.priority, s.source, s.name))
        return tuple(candidates[: context.parameters.max_items])
