"""Storage manager.

:class:`DefaultStorageManager` owns the storage workflow. For each input it
loads the running :class:`~storage.models.StorageRecord` from the Registry,
collects a batch, serializes it, generates storage requests, computes metrics,
builds a **new** immutable record, and writes it back. The whole
read-modify-write is synchronous (the components are pure — no ``await``
inside), so atomicity is provided by a :class:`threading.Lock`; events are
published only after a consistent update.

Any failure is translated to a framework exception, isolated, published as
:class:`~storage.events.StorageErrorOccurred`, and returned as a FAILED
result — never a leaked internal exception, and never a partial record write.
The framework only serializes and plans domain objects: it never connects to a
database, writes a file, uploads an object, or persists a request, and never
modifies a strategy, agent, or portfolio.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from threading import Lock

from core.logging import LoggerFactory
from events.base import Event
from events.bus import EventBus
from storage.context import StorageContext
from storage.events import (
    RequestsPlanned,
    StorageCancelled,
    StorageCollected,
    StorageCompleted,
    StorageErrorOccurred,
    StorageMetricsUpdated,
    StorageSerialized,
    StorageSnapshotCreated,
    StorageStarted,
)
from storage.exceptions import StorageError
from storage.interfaces import (
    Collector,
    PersistencePlanner,
    Serializer,
    StorageMetricsCalculator,
    StorageRegistry,
)
from storage.models import (
    StorageRecord,
    StorageResult,
    StorageResultStatus,
    StorageSnapshot,
)
from storage.state import StorageState

__all__ = ["DefaultStorageManager"]

_TERMINAL = (
    StorageState.COMPLETED,
    StorageState.CANCELLED,
    StorageState.FAILED,
)


class DefaultStorageManager:
    """Coordinates the storage pipeline over a registry-owned record."""

    def __init__(
        self,
        bus: EventBus,
        registry: StorageRegistry,
        collector: Collector,
        serializer: Serializer,
        planner: PersistencePlanner,
        metrics: StorageMetricsCalculator,
        logger: LoggerFactory | None = None,
    ) -> None:
        self._bus = bus
        self._registry = registry
        self._collector = collector
        self._serializer = serializer
        self._planner = planner
        self._metrics = metrics
        self._log = logger.get_logger("storage.manager") if logger else None
        self._lock = Lock()

    async def store(self, context: StorageContext) -> StorageResult:
        """Store one input and return a result."""
        storage_id = context.storage_id
        events: list[Event] = []
        try:
            result = self._compute(storage_id, context, events)
        except StorageError as exc:
            return await self._fail(storage_id, str(exc))
        except Exception as exc:  # translate; never leak internals
            return await self._fail(storage_id, str(exc))

        for event in events:  # publish only after a consistent update
            await self._bus.publish(event)
        return result

    def _compute(
        self,
        storage_id: str,
        context: StorageContext,
        events: list[Event],
    ) -> StorageResult:
        events.append(StorageStarted(storage_id=storage_id))
        now = datetime.now(UTC)
        with self._lock:  # synchronous, atomic read-modify-write
            if self._registry.exists(storage_id):
                record = self._registry.get(storage_id)
            else:
                record = _new_record(storage_id, now)
            if record.state in _TERMINAL:
                raise StorageError(
                    f"storage record {storage_id!r} is {record.state.value}"
                )

            if context.metadata.get("cancel"):
                cancelled = replace(
                    record, state=StorageState.CANCELLED, updated_at=now
                )
                self._registry.register(cancelled)
                events.append(StorageCancelled(storage_id=storage_id))
                self._info(storage_id, cancelled, "cancelled")
                return StorageResult(
                    status=StorageResultStatus.CANCELLED, record=cancelled
                )

            batch = self._collector.collect(context)
            batch = self._serializer.serialize(batch, context)
            requests = self._planner.plan(batch, context)

            new_record = replace(
                record,
                state=StorageState.SERIALIZED,
                history=record.history.append(batch),
                batch=batch,
                requests=requests,
                item_count=record.item_count + len(batch.items),
                request_count=record.request_count + len(requests),
                updated_at=now,
            )
            metrics = self._metrics.calculate(new_record)
            snapshot = StorageSnapshot(
                record=new_record, metrics=metrics, timestamp=now
            )
            self._registry.register(new_record)

        events.extend(
            [
                StorageCollected(storage_id=storage_id, items=len(batch.items)),
                StorageSerialized(storage_id=storage_id),
                RequestsPlanned(storage_id=storage_id, count=len(requests)),
                StorageSnapshotCreated(storage_id=storage_id),
                StorageMetricsUpdated(storage_id=storage_id),
                StorageCompleted(storage_id=storage_id),
            ]
        )
        self._info(storage_id, new_record, "stored")
        return StorageResult(
            status=StorageResultStatus.SUCCESS,
            record=new_record,
            snapshot=snapshot,
            batch=batch,
            requests=requests,
            metrics=metrics,
        )

    async def _fail(self, storage_id: str, message: str) -> StorageResult:
        self._error(storage_id, message)
        await self._bus.publish(
            StorageErrorOccurred(storage_id=storage_id, message=message)
        )
        return StorageResult(
            status=StorageResultStatus.FAILED, errors=(message,)
        )

    def _info(
        self, storage_id: str, record: StorageRecord, status: str
    ) -> None:
        if self._log is not None:
            self._log.info(
                "Storage update",
                extra={
                    "storage_id": storage_id,
                    "status": status,
                    "items": record.item_count,
                },
            )

    def _error(self, storage_id: str, message: str) -> None:
        if self._log is not None:
            self._log.error(
                "Storage error",
                extra={"storage_id": storage_id, "error": message},
            )


def _new_record(storage_id: str, now: datetime) -> StorageRecord:
    return StorageRecord(
        id=storage_id,
        state=StorageState.COLLECTING,
        created_at=now,
        updated_at=now,
    )
