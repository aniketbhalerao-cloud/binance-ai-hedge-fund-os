"""Monitoring manager.

:class:`DefaultMonitoringManager` owns the monitoring workflow. For each input it
loads the running :class:`~monitoring.models.MonitoringRecord` from the Registry,
collects a health report, evaluates it, generates alerts, computes metrics, builds
a **new** immutable record, and writes it back. The whole read-modify-write is
synchronous (the components are pure — no ``await`` inside), so atomicity is
provided by a :class:`threading.Lock`; events are published only after a consistent
update.

Any failure is translated to a framework exception, isolated, published as
:class:`~monitoring.events.MonitoringErrorOccurred`, and returned as a FAILED
result — never a leaked internal exception, and never a partial record write. The
framework only observes: it never sends an alert and never modifies a strategy,
agent, or portfolio.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from threading import Lock

from core.logging import LoggerFactory
from events.base import Event
from events.bus import EventBus
from monitoring.context import MonitoringContext
from monitoring.events import (
    AlertsGenerated,
    HealthEvaluated,
    HealthReportCreated,
    MonitoringCancelled,
    MonitoringCompleted,
    MonitoringErrorOccurred,
    MonitoringMetricsUpdated,
    MonitoringSnapshotCreated,
    MonitoringStarted,
)
from monitoring.exceptions import MonitoringError
from monitoring.interfaces import (
    AlertGenerator,
    Collector,
    Evaluator,
    MonitoringMetricsCalculator,
    MonitoringRegistry,
)
from monitoring.models import (
    MonitoringRecord,
    MonitoringResult,
    MonitoringResultStatus,
    MonitoringSnapshot,
)
from monitoring.state import MonitoringState

__all__ = ["DefaultMonitoringManager"]

_TERMINAL = (
    MonitoringState.COMPLETED,
    MonitoringState.CANCELLED,
    MonitoringState.FAILED,
)


class DefaultMonitoringManager:
    """Coordinates the monitoring pipeline over a registry-owned record."""

    def __init__(
        self,
        bus: EventBus,
        registry: MonitoringRegistry,
        collector: Collector,
        evaluator: Evaluator,
        alerts: AlertGenerator,
        metrics: MonitoringMetricsCalculator,
        logger: LoggerFactory | None = None,
    ) -> None:
        self._bus = bus
        self._registry = registry
        self._collector = collector
        self._evaluator = evaluator
        self._alerts = alerts
        self._metrics = metrics
        self._log = logger.get_logger("monitoring.manager") if logger else None
        self._lock = Lock()

    async def monitor(self, context: MonitoringContext) -> MonitoringResult:
        """Observe one input and return a result."""
        monitoring_id = context.monitoring_id
        events: list[Event] = []
        try:
            result = self._compute(monitoring_id, context, events)
        except MonitoringError as exc:
            return await self._fail(monitoring_id, str(exc))
        except Exception as exc:  # translate; never leak internals
            return await self._fail(monitoring_id, str(exc))

        for event in events:  # publish only after a consistent update
            await self._bus.publish(event)
        return result

    def _compute(
        self,
        monitoring_id: str,
        context: MonitoringContext,
        events: list[Event],
    ) -> MonitoringResult:
        events.append(MonitoringStarted(monitoring_id=monitoring_id))
        now = datetime.now(UTC)
        with self._lock:  # synchronous, atomic read-modify-write
            if self._registry.exists(monitoring_id):
                record = self._registry.get(monitoring_id)
            else:
                record = _new_record(monitoring_id, now)
            if record.state in _TERMINAL:
                raise MonitoringError(
                    f"monitoring record {monitoring_id!r} is {record.state.value}"
                )

            if context.metadata.get("cancel"):
                cancelled = replace(
                    record, state=MonitoringState.CANCELLED, updated_at=now
                )
                self._registry.register(cancelled)
                events.append(MonitoringCancelled(monitoring_id=monitoring_id))
                self._info(monitoring_id, cancelled, "cancelled")
                return MonitoringResult(
                    status=MonitoringResultStatus.CANCELLED, record=cancelled
                )

            report = self._collector.collect(context)
            report = self._evaluator.evaluate(report, context)
            alerts = self._alerts.generate(report, context)

            new_record = replace(
                record,
                state=MonitoringState.EVALUATED,
                history=record.history.append(report),
                report=report,
                alerts=alerts,
                check_count=record.check_count + len(report.checks),
                alert_count=record.alert_count + len(alerts),
                updated_at=now,
            )
            metrics = self._metrics.calculate(new_record)
            snapshot = MonitoringSnapshot(
                record=new_record, metrics=metrics, timestamp=now
            )
            self._registry.register(new_record)

        events.extend(
            [
                HealthReportCreated(
                    monitoring_id=monitoring_id, checks=len(report.checks)
                ),
                HealthEvaluated(monitoring_id=monitoring_id),
                AlertsGenerated(monitoring_id=monitoring_id, count=len(alerts)),
                MonitoringSnapshotCreated(monitoring_id=monitoring_id),
                MonitoringMetricsUpdated(monitoring_id=monitoring_id),
                MonitoringCompleted(monitoring_id=monitoring_id),
            ]
        )
        self._info(monitoring_id, new_record, "observed")
        return MonitoringResult(
            status=MonitoringResultStatus.SUCCESS,
            record=new_record,
            snapshot=snapshot,
            report=report,
            alerts=alerts,
            metrics=metrics,
        )

    async def _fail(self, monitoring_id: str, message: str) -> MonitoringResult:
        self._error(monitoring_id, message)
        await self._bus.publish(
            MonitoringErrorOccurred(monitoring_id=monitoring_id, message=message)
        )
        return MonitoringResult(
            status=MonitoringResultStatus.FAILED, errors=(message,)
        )

    def _info(
        self, monitoring_id: str, record: MonitoringRecord, status: str
    ) -> None:
        if self._log is not None:
            self._log.info(
                "Monitoring update",
                extra={
                    "monitoring_id": monitoring_id,
                    "status": status,
                    "checks": record.check_count,
                },
            )

    def _error(self, monitoring_id: str, message: str) -> None:
        if self._log is not None:
            self._log.error(
                "Monitoring error",
                extra={"monitoring_id": monitoring_id, "error": message},
            )


def _new_record(monitoring_id: str, now: datetime) -> MonitoringRecord:
    return MonitoringRecord(
        id=monitoring_id,
        state=MonitoringState.COLLECTING,
        created_at=now,
        updated_at=now,
    )
