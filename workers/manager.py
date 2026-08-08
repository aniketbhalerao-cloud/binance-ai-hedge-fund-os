"""Worker manager.

:class:`DefaultWorkerManager` owns the background-worker workflow. For each
input it loads the running :class:`~workers.models.WorkerRecord` from the
Registry, collects a batch, plans it, generates worker requests, computes
metrics, builds a **new** immutable record, and writes it back. The whole
read-modify-write is synchronous (the components are pure — no ``await``
inside), so atomicity is provided by a :class:`threading.Lock`; events are
published only after a consistent update.

Any failure is translated to a framework exception, isolated, published as
:class:`~workers.events.WorkerErrorOccurred`, and returned as a FAILED
result — never a leaked internal exception, and never a partial record write.
The framework only plans and dispatches domain objects: it never executes,
runs, or triggers a background job, and never modifies a strategy, agent, or
portfolio.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from threading import Lock

from core.logging import LoggerFactory
from events.base import Event
from events.bus import EventBus
from workers.context import WorkerContext
from workers.events import (
    JobsCollected,
    JobsQueued,
    RequestsDispatched,
    WorkerCancelled,
    WorkerCompleted,
    WorkerErrorOccurred,
    WorkerMetricsUpdated,
    WorkerSnapshotCreated,
    WorkerStarted,
)
from workers.exceptions import WorkerError
from workers.interfaces import (
    Collector,
    Dispatcher,
    Planner,
    WorkerMetricsCalculator,
    WorkerRegistry,
)
from workers.models import (
    WorkerRecord,
    WorkerResult,
    WorkerResultStatus,
    WorkerSnapshot,
)
from workers.state import WorkerState

__all__ = ["DefaultWorkerManager"]

_TERMINAL = (
    WorkerState.COMPLETED,
    WorkerState.CANCELLED,
    WorkerState.FAILED,
)


class DefaultWorkerManager:
    """Coordinates the worker pipeline over a registry-owned record."""

    def __init__(
        self,
        bus: EventBus,
        registry: WorkerRegistry,
        collector: Collector,
        planner: Planner,
        dispatcher: Dispatcher,
        metrics: WorkerMetricsCalculator,
        logger: LoggerFactory | None = None,
    ) -> None:
        self._bus = bus
        self._registry = registry
        self._collector = collector
        self._planner = planner
        self._dispatcher = dispatcher
        self._metrics = metrics
        self._log = logger.get_logger("workers.manager") if logger else None
        self._lock = Lock()

    async def enqueue(self, context: WorkerContext) -> WorkerResult:
        """Enqueue one input and return a result."""
        worker_id = context.worker_id
        events: list[Event] = []
        try:
            result = self._compute(worker_id, context, events)
        except WorkerError as exc:
            return await self._fail(worker_id, str(exc))
        except Exception as exc:  # translate; never leak internals
            return await self._fail(worker_id, str(exc))

        for event in events:  # publish only after a consistent update
            await self._bus.publish(event)
        return result

    def _compute(
        self,
        worker_id: str,
        context: WorkerContext,
        events: list[Event],
    ) -> WorkerResult:
        events.append(WorkerStarted(worker_id=worker_id))
        now = datetime.now(UTC)
        with self._lock:  # synchronous, atomic read-modify-write
            if self._registry.exists(worker_id):
                record = self._registry.get(worker_id)
            else:
                record = _new_record(worker_id, now)
            if record.state in _TERMINAL:
                raise WorkerError(
                    f"worker record {worker_id!r} is {record.state.value}"
                )

            if context.metadata.get("cancel"):
                cancelled = replace(
                    record, state=WorkerState.CANCELLED, updated_at=now
                )
                self._registry.register(cancelled)
                events.append(WorkerCancelled(worker_id=worker_id))
                self._info(worker_id, cancelled, "cancelled")
                return WorkerResult(
                    status=WorkerResultStatus.CANCELLED, record=cancelled
                )

            batch = self._collector.collect(context)
            batch = self._planner.plan(batch, context)
            requests = self._dispatcher.dispatch(batch, context)

            new_record = replace(
                record,
                state=WorkerState.QUEUED,
                history=record.history.append(batch),
                batch=batch,
                requests=requests,
                job_count=record.job_count + len(batch.entries),
                request_count=record.request_count + len(requests),
                updated_at=now,
            )
            metrics = self._metrics.calculate(new_record)
            snapshot = WorkerSnapshot(
                record=new_record, metrics=metrics, timestamp=now
            )
            self._registry.register(new_record)

        events.extend(
            [
                JobsCollected(worker_id=worker_id, jobs=len(batch.entries)),
                JobsQueued(worker_id=worker_id),
                RequestsDispatched(worker_id=worker_id, count=len(requests)),
                WorkerSnapshotCreated(worker_id=worker_id),
                WorkerMetricsUpdated(worker_id=worker_id),
                WorkerCompleted(worker_id=worker_id),
            ]
        )
        self._info(worker_id, new_record, "enqueued")
        return WorkerResult(
            status=WorkerResultStatus.SUCCESS,
            record=new_record,
            snapshot=snapshot,
            batch=batch,
            requests=requests,
            metrics=metrics,
        )

    async def _fail(self, worker_id: str, message: str) -> WorkerResult:
        self._error(worker_id, message)
        await self._bus.publish(
            WorkerErrorOccurred(worker_id=worker_id, message=message)
        )
        return WorkerResult(
            status=WorkerResultStatus.FAILED, errors=(message,)
        )

    def _info(
        self, worker_id: str, record: WorkerRecord, status: str
    ) -> None:
        if self._log is not None:
            self._log.info(
                "Worker update",
                extra={
                    "worker_id": worker_id,
                    "status": status,
                    "jobs": record.job_count,
                },
            )

    def _error(self, worker_id: str, message: str) -> None:
        if self._log is not None:
            self._log.error(
                "Worker error",
                extra={"worker_id": worker_id, "error": message},
            )


def _new_record(worker_id: str, now: datetime) -> WorkerRecord:
    return WorkerRecord(
        id=worker_id,
        state=WorkerState.COLLECTING,
        created_at=now,
        updated_at=now,
    )
