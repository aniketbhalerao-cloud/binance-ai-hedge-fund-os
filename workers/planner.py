"""Worker planner.

:class:`DefaultPlanner` plans a raw job batch into immutable job entries: it
assigns each entry a worker queue, resolves whether it clears the priority
threshold for dispatch, and produces the planned batch whose entries carry
their routing. It is deterministic and stateless, and it **never applies
changes** — it only constructs the job entries.
"""

from __future__ import annotations

from workers.context import WorkerContext
from workers.exceptions import PlanningError
from workers.models import (
    SUPPORTED_WORKER_QUEUES,
    JobBatch,
    JobEntry,
    JobSource,
    WorkerParameters,
)

__all__ = ["DefaultPlanner"]


class DefaultPlanner:
    """Stateless batch planning (entry construction only, never applied)."""

    def plan(self, batch: JobBatch, context: WorkerContext) -> JobBatch:
        """Return the planned batch (entries carry their routing).

        Raises:
            PlanningError: If an unexpected failure occurs.
        """
        try:
            entries = tuple(
                _entry(s, context.parameters) for s in batch.sources
            )
            return JobBatch(sources=batch.sources, entries=entries)
        except PlanningError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise PlanningError(str(exc)) from exc


def _entry(source: JobSource, parameters: WorkerParameters) -> JobEntry:
    if source.priority >= parameters.priority_threshold:
        dispatch, detail = True, "eligible for dispatch"
    else:
        dispatch, detail = False, "below priority threshold"
    queue = (
        source.category if source.category in SUPPORTED_WORKER_QUEUES else "immediate"
    )
    return JobEntry(source=source, dispatch=dispatch, queue=queue, detail=detail)
