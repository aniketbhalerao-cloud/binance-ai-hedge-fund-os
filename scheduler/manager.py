"""Scheduler manager.

:class:`DefaultSchedulerManager` owns the scheduler workflow. For each input
it loads the running :class:`~scheduler.models.SchedulerRecord` from the
Registry, collects a batch, plans it, generates schedule requests, computes
metrics, builds a **new** immutable record, and writes it back. The whole
read-modify-write is synchronous (the components are pure — no ``await``
inside), so atomicity is provided by a :class:`threading.Lock`; events are
published only after a consistent update.

Any failure is translated to a framework exception, isolated, published as
:class:`~scheduler.events.SchedulerErrorOccurred`, and returned as a FAILED
result — never a leaked internal exception, and never a partial record write.
The framework only plans and dispatches domain objects: it never executes,
runs, or triggers a scheduled job, and never modifies a strategy, agent, or
portfolio.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from threading import Lock

from core.logging import LoggerFactory
from events.base import Event
from events.bus import EventBus
from scheduler.context import SchedulerContext
from scheduler.events import (
    RequestsDispatched,
    ScheduleCollected,
    SchedulePlanned,
    SchedulerCancelled,
    SchedulerCompleted,
    SchedulerErrorOccurred,
    SchedulerMetricsUpdated,
    SchedulerSnapshotCreated,
    SchedulerStarted,
)
from scheduler.exceptions import SchedulerError
from scheduler.interfaces import (
    Collector,
    Dispatcher,
    Planner,
    SchedulerMetricsCalculator,
    SchedulerRegistry,
)
from scheduler.models import (
    SchedulerRecord,
    SchedulerResult,
    SchedulerResultStatus,
    SchedulerSnapshot,
)
from scheduler.state import SchedulerState

__all__ = ["DefaultSchedulerManager"]

_TERMINAL = (
    SchedulerState.COMPLETED,
    SchedulerState.CANCELLED,
    SchedulerState.FAILED,
)


class DefaultSchedulerManager:
    """Coordinates the scheduler pipeline over a registry-owned record."""

    def __init__(
        self,
        bus: EventBus,
        registry: SchedulerRegistry,
        collector: Collector,
        planner: Planner,
        dispatcher: Dispatcher,
        metrics: SchedulerMetricsCalculator,
        logger: LoggerFactory | None = None,
    ) -> None:
        self._bus = bus
        self._registry = registry
        self._collector = collector
        self._planner = planner
        self._dispatcher = dispatcher
        self._metrics = metrics
        self._log = logger.get_logger("scheduler.manager") if logger else None
        self._lock = Lock()

    async def schedule(self, context: SchedulerContext) -> SchedulerResult:
        """Schedule one input and return a result."""
        scheduler_id = context.scheduler_id
        events: list[Event] = []
        try:
            result = self._compute(scheduler_id, context, events)
        except SchedulerError as exc:
            return await self._fail(scheduler_id, str(exc))
        except Exception as exc:  # translate; never leak internals
            return await self._fail(scheduler_id, str(exc))

        for event in events:  # publish only after a consistent update
            await self._bus.publish(event)
        return result

    def _compute(
        self,
        scheduler_id: str,
        context: SchedulerContext,
        events: list[Event],
    ) -> SchedulerResult:
        events.append(SchedulerStarted(scheduler_id=scheduler_id))
        now = datetime.now(UTC)
        with self._lock:  # synchronous, atomic read-modify-write
            if self._registry.exists(scheduler_id):
                record = self._registry.get(scheduler_id)
            else:
                record = _new_record(scheduler_id, now)
            if record.state in _TERMINAL:
                raise SchedulerError(
                    f"scheduler record {scheduler_id!r} is {record.state.value}"
                )

            if context.metadata.get("cancel"):
                cancelled = replace(
                    record, state=SchedulerState.CANCELLED, updated_at=now
                )
                self._registry.register(cancelled)
                events.append(SchedulerCancelled(scheduler_id=scheduler_id))
                self._info(scheduler_id, cancelled, "cancelled")
                return SchedulerResult(
                    status=SchedulerResultStatus.CANCELLED, record=cancelled
                )

            batch = self._collector.collect(context)
            batch = self._planner.plan(batch, context)
            requests = self._dispatcher.dispatch(batch, context)

            new_record = replace(
                record,
                state=SchedulerState.PLANNED,
                history=record.history.append(batch),
                batch=batch,
                requests=requests,
                entry_count=record.entry_count + len(batch.entries),
                request_count=record.request_count + len(requests),
                updated_at=now,
            )
            metrics = self._metrics.calculate(new_record)
            snapshot = SchedulerSnapshot(
                record=new_record, metrics=metrics, timestamp=now
            )
            self._registry.register(new_record)

        events.extend(
            [
                ScheduleCollected(
                    scheduler_id=scheduler_id, entries=len(batch.entries)
                ),
                SchedulePlanned(scheduler_id=scheduler_id),
                RequestsDispatched(
                    scheduler_id=scheduler_id, count=len(requests)
                ),
                SchedulerSnapshotCreated(scheduler_id=scheduler_id),
                SchedulerMetricsUpdated(scheduler_id=scheduler_id),
                SchedulerCompleted(scheduler_id=scheduler_id),
            ]
        )
        self._info(scheduler_id, new_record, "scheduled")
        return SchedulerResult(
            status=SchedulerResultStatus.SUCCESS,
            record=new_record,
            snapshot=snapshot,
            batch=batch,
            requests=requests,
            metrics=metrics,
        )

    async def _fail(self, scheduler_id: str, message: str) -> SchedulerResult:
        self._error(scheduler_id, message)
        await self._bus.publish(
            SchedulerErrorOccurred(scheduler_id=scheduler_id, message=message)
        )
        return SchedulerResult(
            status=SchedulerResultStatus.FAILED, errors=(message,)
        )

    def _info(
        self, scheduler_id: str, record: SchedulerRecord, status: str
    ) -> None:
        if self._log is not None:
            self._log.info(
                "Scheduler update",
                extra={
                    "scheduler_id": scheduler_id,
                    "status": status,
                    "entries": record.entry_count,
                },
            )

    def _error(self, scheduler_id: str, message: str) -> None:
        if self._log is not None:
            self._log.error(
                "Scheduler error",
                extra={"scheduler_id": scheduler_id, "error": message},
            )


def _new_record(scheduler_id: str, now: datetime) -> SchedulerRecord:
    return SchedulerRecord(
        id=scheduler_id,
        state=SchedulerState.COLLECTING,
        created_at=now,
        updated_at=now,
    )
