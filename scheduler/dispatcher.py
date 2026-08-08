"""Scheduler dispatcher.

:class:`DefaultDispatcher` turns the dispatch-eligible entries in a planned
batch into deterministic :class:`~scheduler.models.ScheduleRequest` domain
objects — a subject, its source, its schedule cadence, and the dispatch
detail. It is stateless and deterministic, and it **never executes, runs, or
triggers** anything and never modifies strategies, agents, or portfolios; it
only produces immutable schedule request objects.
"""

from __future__ import annotations

from scheduler.context import SchedulerContext
from scheduler.exceptions import DispatchError
from scheduler.models import ScheduleBatch, ScheduleRequest

__all__ = ["DefaultDispatcher"]


class DefaultDispatcher:
    """Stateless, deterministic schedule request generation (domain objects only)."""

    def dispatch(
        self, batch: ScheduleBatch, context: SchedulerContext
    ) -> tuple[ScheduleRequest, ...]:
        """Return one schedule request per dispatch-eligible entry in ``batch``.

        Raises:
            DispatchError: If an unexpected failure occurs.
        """
        try:
            return tuple(
                ScheduleRequest(
                    subject=entry.source.name,
                    source=entry.source.source,
                    cadence=entry.cadence,
                    category=entry.source.category,
                    priority=entry.source.priority,
                    detail=entry.detail,
                )
                for entry in batch.entries
                if entry.dispatch
            )
        except DispatchError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise DispatchError(str(exc)) from exc
