"""Worker dispatcher.

:class:`DefaultDispatcher` turns the dispatch-eligible entries in a planned
batch into deterministic :class:`~workers.models.WorkerRequest` domain
objects — a subject, its source, its worker queue, and the dispatch detail.
It is stateless and deterministic, and it **never executes, runs, or
triggers** anything and never modifies strategies, agents, or portfolios; it
only produces immutable worker request objects.
"""

from __future__ import annotations

from workers.context import WorkerContext
from workers.exceptions import DispatchError
from workers.models import JobBatch, WorkerRequest

__all__ = ["DefaultDispatcher"]


class DefaultDispatcher:
    """Stateless, deterministic worker request generation (domain objects only)."""

    def dispatch(
        self, batch: JobBatch, context: WorkerContext
    ) -> tuple[WorkerRequest, ...]:
        """Return one worker request per dispatch-eligible entry in ``batch``.

        Raises:
            DispatchError: If an unexpected failure occurs.
        """
        try:
            return tuple(
                WorkerRequest(
                    subject=entry.source.name,
                    source=entry.source.source,
                    queue=entry.queue,
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
