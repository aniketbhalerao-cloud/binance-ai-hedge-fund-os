"""Notification manager.

:class:`DefaultNotificationManager` owns the notification workflow. For each input
it loads the running :class:`~notification.models.NotificationRecord` from the
Registry, collects a batch, formats it, generates requests, computes metrics, builds
a **new** immutable record, and writes it back. The whole read-modify-write is
synchronous (the components are pure — no ``await`` inside), so atomicity is
provided by a :class:`threading.Lock`; events are published only after a consistent
update.

Any failure is translated to a framework exception, isolated, published as
:class:`~notification.events.NotificationErrorOccurred`, and returned as a FAILED
result — never a leaked internal exception, and never a partial record write. The
framework only requests: it never sends a real notification and never modifies a
strategy, agent, or portfolio.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from threading import Lock

from core.logging import LoggerFactory
from events.base import Event
from events.bus import EventBus
from notification.context import NotificationContext
from notification.events import (
    NotificationCancelled,
    NotificationCollected,
    NotificationCompleted,
    NotificationErrorOccurred,
    NotificationFormatted,
    NotificationMetricsUpdated,
    NotificationSnapshotCreated,
    NotificationStarted,
    RequestsGenerated,
)
from notification.exceptions import NotificationError
from notification.interfaces import (
    Collector,
    Dispatcher,
    Formatter,
    NotificationMetricsCalculator,
    NotificationRegistry,
)
from notification.models import (
    NotificationRecord,
    NotificationResult,
    NotificationResultStatus,
    NotificationSnapshot,
)
from notification.state import NotificationState

__all__ = ["DefaultNotificationManager"]

_TERMINAL = (
    NotificationState.COMPLETED,
    NotificationState.CANCELLED,
    NotificationState.FAILED,
)


class DefaultNotificationManager:
    """Coordinates the notification pipeline over a registry-owned record."""

    def __init__(
        self,
        bus: EventBus,
        registry: NotificationRegistry,
        collector: Collector,
        formatter: Formatter,
        dispatcher: Dispatcher,
        metrics: NotificationMetricsCalculator,
        logger: LoggerFactory | None = None,
    ) -> None:
        self._bus = bus
        self._registry = registry
        self._collector = collector
        self._formatter = formatter
        self._dispatcher = dispatcher
        self._metrics = metrics
        self._log = logger.get_logger("notification.manager") if logger else None
        self._lock = Lock()

    async def notify(self, context: NotificationContext) -> NotificationResult:
        """Notify over one input and return a result."""
        notification_id = context.notification_id
        events: list[Event] = []
        try:
            result = self._compute(notification_id, context, events)
        except NotificationError as exc:
            return await self._fail(notification_id, str(exc))
        except Exception as exc:  # translate; never leak internals
            return await self._fail(notification_id, str(exc))

        for event in events:  # publish only after a consistent update
            await self._bus.publish(event)
        return result

    def _compute(
        self,
        notification_id: str,
        context: NotificationContext,
        events: list[Event],
    ) -> NotificationResult:
        events.append(NotificationStarted(notification_id=notification_id))
        now = datetime.now(UTC)
        with self._lock:  # synchronous, atomic read-modify-write
            if self._registry.exists(notification_id):
                record = self._registry.get(notification_id)
            else:
                record = _new_record(notification_id, now)
            if record.state in _TERMINAL:
                raise NotificationError(
                    f"notification record {notification_id!r} is {record.state.value}"
                )

            if context.metadata.get("cancel"):
                cancelled = replace(
                    record, state=NotificationState.CANCELLED, updated_at=now
                )
                self._registry.register(cancelled)
                events.append(
                    NotificationCancelled(notification_id=notification_id)
                )
                self._info(notification_id, cancelled, "cancelled")
                return NotificationResult(
                    status=NotificationResultStatus.CANCELLED, record=cancelled
                )

            batch = self._collector.collect(context)
            batch = self._formatter.format(batch, context)
            requests = self._dispatcher.dispatch(batch, context)

            new_record = replace(
                record,
                state=NotificationState.FORMATTED,
                history=record.history.append(batch),
                batch=batch,
                requests=requests,
                notification_count=record.notification_count
                + len(batch.notifications),
                request_count=record.request_count + len(requests),
                updated_at=now,
            )
            metrics = self._metrics.calculate(new_record)
            snapshot = NotificationSnapshot(
                record=new_record, metrics=metrics, timestamp=now
            )
            self._registry.register(new_record)

        events.extend(
            [
                NotificationCollected(
                    notification_id=notification_id,
                    notifications=len(batch.notifications),
                ),
                NotificationFormatted(notification_id=notification_id),
                RequestsGenerated(
                    notification_id=notification_id, count=len(requests)
                ),
                NotificationSnapshotCreated(notification_id=notification_id),
                NotificationMetricsUpdated(notification_id=notification_id),
                NotificationCompleted(notification_id=notification_id),
            ]
        )
        self._info(notification_id, new_record, "notified")
        return NotificationResult(
            status=NotificationResultStatus.SUCCESS,
            record=new_record,
            snapshot=snapshot,
            batch=batch,
            requests=requests,
            metrics=metrics,
        )

    async def _fail(
        self, notification_id: str, message: str
    ) -> NotificationResult:
        self._error(notification_id, message)
        await self._bus.publish(
            NotificationErrorOccurred(
                notification_id=notification_id, message=message
            )
        )
        return NotificationResult(
            status=NotificationResultStatus.FAILED, errors=(message,)
        )

    def _info(
        self, notification_id: str, record: NotificationRecord, status: str
    ) -> None:
        if self._log is not None:
            self._log.info(
                "Notification update",
                extra={
                    "notification_id": notification_id,
                    "status": status,
                    "notifications": record.notification_count,
                },
            )

    def _error(self, notification_id: str, message: str) -> None:
        if self._log is not None:
            self._log.error(
                "Notification error",
                extra={"notification_id": notification_id, "error": message},
            )


def _new_record(notification_id: str, now: datetime) -> NotificationRecord:
    return NotificationRecord(
        id=notification_id,
        state=NotificationState.COLLECTING,
        created_at=now,
        updated_at=now,
    )
