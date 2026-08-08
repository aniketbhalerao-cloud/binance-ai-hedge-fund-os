"""Scheduler planner.

:class:`DefaultPlanner` plans a raw schedule batch into immutable schedule
entries: it assigns each entry a schedule cadence, resolves whether it clears
the priority threshold for dispatch, and produces the planned batch whose
entries carry their routing. It is deterministic and stateless, and it
**never applies changes** — it only constructs the schedule entries.
"""

from __future__ import annotations

from scheduler.context import SchedulerContext
from scheduler.exceptions import PlanningError
from scheduler.models import (
    SUPPORTED_SCHEDULE_CADENCES,
    ScheduleBatch,
    ScheduleEntry,
    SchedulerParameters,
    ScheduleSource,
)

__all__ = ["DefaultPlanner"]


class DefaultPlanner:
    """Stateless batch planning (entry construction only, never applied)."""

    def plan(
        self, batch: ScheduleBatch, context: SchedulerContext
    ) -> ScheduleBatch:
        """Return the planned batch (entries carry their routing).

        Raises:
            PlanningError: If an unexpected failure occurs.
        """
        try:
            entries = tuple(
                _entry(s, context.parameters) for s in batch.sources
            )
            return ScheduleBatch(sources=batch.sources, entries=entries)
        except PlanningError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise PlanningError(str(exc)) from exc


def _entry(source: ScheduleSource, parameters: SchedulerParameters) -> ScheduleEntry:
    if source.priority >= parameters.priority_threshold:
        dispatch, detail = True, "eligible for dispatch"
    else:
        dispatch, detail = False, "below priority threshold"
    cadence = (
        source.category if source.category in SUPPORTED_SCHEDULE_CADENCES else "once"
    )
    return ScheduleEntry(
        source=source, dispatch=dispatch, cadence=cadence, detail=detail
    )
