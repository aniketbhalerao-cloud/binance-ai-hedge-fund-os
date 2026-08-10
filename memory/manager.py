"""Memory manager.

:class:`DefaultMemoryManager` owns the memory workflow. For each input it
loads the running :class:`~memory.models.MemoryRecord` from the Registry,
collects a batch, plans it, generates memory requests, computes metrics,
builds a **new** immutable record, and writes it back. The whole
read-modify-write is synchronous (the components are pure — no ``await``
inside), so atomicity is provided by a :class:`threading.Lock`; events are
published only after a consistent update.

Any failure is translated to a framework exception, isolated, published as
:class:`~memory.events.MemoryErrorOccurred`, and returned as a FAILED
result — never a leaked internal exception, and never a partial record write.
The framework only plans and dispatches domain objects: it never calls an AI
provider, computes an embedding, accesses a vector database, writes to a
database, or writes a file, and never modifies a strategy, agent, or
portfolio.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from threading import Lock

from core.logging import LoggerFactory
from events.base import Event
from events.bus import EventBus
from memory.context import MemoryContext
from memory.events import (
    EntriesCollected,
    EntriesPlanned,
    MemoryCancelled,
    MemoryCompleted,
    MemoryErrorOccurred,
    MemoryMetricsUpdated,
    MemorySnapshotCreated,
    MemoryStarted,
    RequestsDispatched,
)
from memory.exceptions import MemoryError
from memory.interfaces import (
    Collector,
    Dispatcher,
    MemoryMetricsCalculator,
    MemoryRegistry,
    Planner,
)
from memory.models import (
    MemoryRecord,
    MemoryResult,
    MemoryResultStatus,
    MemorySnapshot,
)
from memory.state import MemoryState

__all__ = ["DefaultMemoryManager"]

_TERMINAL = (
    MemoryState.COMPLETED,
    MemoryState.CANCELLED,
    MemoryState.FAILED,
)


class DefaultMemoryManager:
    """Coordinates the memory pipeline over a registry-owned record."""

    def __init__(
        self,
        bus: EventBus,
        registry: MemoryRegistry,
        collector: Collector,
        planner: Planner,
        dispatcher: Dispatcher,
        metrics: MemoryMetricsCalculator,
        logger: LoggerFactory | None = None,
    ) -> None:
        self._bus = bus
        self._registry = registry
        self._collector = collector
        self._planner = planner
        self._dispatcher = dispatcher
        self._metrics = metrics
        self._log = logger.get_logger("memory.manager") if logger else None
        self._lock = Lock()

    async def remember(self, context: MemoryContext) -> MemoryResult:
        """Remember one input and return a result."""
        memory_id = context.memory_id
        events: list[Event] = []
        try:
            result = self._compute(memory_id, context, events)
        except MemoryError as exc:
            return await self._fail(memory_id, str(exc))
        except Exception as exc:  # translate; never leak internals
            return await self._fail(memory_id, str(exc))

        for event in events:  # publish only after a consistent update
            await self._bus.publish(event)
        return result

    def _compute(
        self,
        memory_id: str,
        context: MemoryContext,
        events: list[Event],
    ) -> MemoryResult:
        events.append(MemoryStarted(memory_id=memory_id))
        now = datetime.now(UTC)
        with self._lock:  # synchronous, atomic read-modify-write
            if self._registry.exists(memory_id):
                record = self._registry.get(memory_id)
            else:
                record = _new_record(memory_id, now)
            if record.state in _TERMINAL:
                raise MemoryError(
                    f"memory record {memory_id!r} is {record.state.value}"
                )

            if context.metadata.get("cancel"):
                cancelled = replace(
                    record, state=MemoryState.CANCELLED, updated_at=now
                )
                self._registry.register(cancelled)
                events.append(MemoryCancelled(memory_id=memory_id))
                self._info(memory_id, cancelled, "cancelled")
                return MemoryResult(
                    status=MemoryResultStatus.CANCELLED, record=cancelled
                )

            batch = self._collector.collect(context)
            batch = self._planner.plan(batch, context)
            requests = self._dispatcher.dispatch(batch, context)

            new_record = replace(
                record,
                state=MemoryState.PLANNED,
                history=record.history.append(batch),
                batch=batch,
                requests=requests,
                entry_count=record.entry_count + len(batch.entries),
                request_count=record.request_count + len(requests),
                updated_at=now,
            )
            metrics = self._metrics.calculate(new_record)
            snapshot = MemorySnapshot(
                record=new_record, metrics=metrics, timestamp=now
            )
            self._registry.register(new_record)

        events.extend(
            [
                EntriesCollected(memory_id=memory_id, entries=len(batch.entries)),
                EntriesPlanned(memory_id=memory_id),
                RequestsDispatched(memory_id=memory_id, count=len(requests)),
                MemorySnapshotCreated(memory_id=memory_id),
                MemoryMetricsUpdated(memory_id=memory_id),
                MemoryCompleted(memory_id=memory_id),
            ]
        )
        self._info(memory_id, new_record, "remembered")
        return MemoryResult(
            status=MemoryResultStatus.SUCCESS,
            record=new_record,
            snapshot=snapshot,
            batch=batch,
            requests=requests,
            metrics=metrics,
        )

    async def _fail(self, memory_id: str, message: str) -> MemoryResult:
        self._error(memory_id, message)
        await self._bus.publish(
            MemoryErrorOccurred(memory_id=memory_id, message=message)
        )
        return MemoryResult(
            status=MemoryResultStatus.FAILED, errors=(message,)
        )

    def _info(
        self, memory_id: str, record: MemoryRecord, status: str
    ) -> None:
        if self._log is not None:
            self._log.info(
                "Memory update",
                extra={
                    "memory_id": memory_id,
                    "status": status,
                    "entries": record.entry_count,
                },
            )

    def _error(self, memory_id: str, message: str) -> None:
        if self._log is not None:
            self._log.error(
                "Memory error",
                extra={"memory_id": memory_id, "error": message},
            )


def _new_record(memory_id: str, now: datetime) -> MemoryRecord:
    return MemoryRecord(
        id=memory_id,
        state=MemoryState.COLLECTING,
        created_at=now,
        updated_at=now,
    )
