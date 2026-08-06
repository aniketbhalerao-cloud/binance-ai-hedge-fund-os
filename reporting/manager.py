"""Reporting manager.

:class:`DefaultReportingManager` owns the reporting workflow. For each input it
loads the running :class:`~reporting.models.ReportingRecord` from the Registry,
collects a batch, builds it, generates export requests, computes metrics,
builds a **new** immutable record, and writes it back. The whole
read-modify-write is synchronous (the components are pure — no ``await``
inside), so atomicity is provided by a :class:`threading.Lock`; events are
published only after a consistent update.

Any failure is translated to a framework exception, isolated, published as
:class:`~reporting.events.ReportingErrorOccurred`, and returned as a FAILED
result — never a leaked internal exception, and never a partial record write.
The framework only builds and exports domain objects: it never saves, writes,
or sends a report and never modifies a strategy, agent, or portfolio.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from threading import Lock

from core.logging import LoggerFactory
from events.base import Event
from events.bus import EventBus
from reporting.context import ReportingContext
from reporting.events import (
    ReportBuilt,
    ReportingCancelled,
    ReportingCollected,
    ReportingCompleted,
    ReportingErrorOccurred,
    ReportingMetricsUpdated,
    ReportingSnapshotCreated,
    ReportingStarted,
    ReportsExported,
)
from reporting.exceptions import ReportingError
from reporting.interfaces import (
    Builder,
    Collector,
    Exporter,
    ReportingMetricsCalculator,
    ReportingRegistry,
)
from reporting.models import (
    ReportingRecord,
    ReportingResult,
    ReportingResultStatus,
    ReportingSnapshot,
)
from reporting.state import ReportingState

__all__ = ["DefaultReportingManager"]

_TERMINAL = (
    ReportingState.COMPLETED,
    ReportingState.CANCELLED,
    ReportingState.FAILED,
)


class DefaultReportingManager:
    """Coordinates the reporting pipeline over a registry-owned record."""

    def __init__(
        self,
        bus: EventBus,
        registry: ReportingRegistry,
        collector: Collector,
        builder: Builder,
        exporter: Exporter,
        metrics: ReportingMetricsCalculator,
        logger: LoggerFactory | None = None,
    ) -> None:
        self._bus = bus
        self._registry = registry
        self._collector = collector
        self._builder = builder
        self._exporter = exporter
        self._metrics = metrics
        self._log = logger.get_logger("reporting.manager") if logger else None
        self._lock = Lock()

    async def report(self, context: ReportingContext) -> ReportingResult:
        """Report over one input and return a result."""
        reporting_id = context.reporting_id
        events: list[Event] = []
        try:
            result = self._compute(reporting_id, context, events)
        except ReportingError as exc:
            return await self._fail(reporting_id, str(exc))
        except Exception as exc:  # translate; never leak internals
            return await self._fail(reporting_id, str(exc))

        for event in events:  # publish only after a consistent update
            await self._bus.publish(event)
        return result

    def _compute(
        self,
        reporting_id: str,
        context: ReportingContext,
        events: list[Event],
    ) -> ReportingResult:
        events.append(ReportingStarted(reporting_id=reporting_id))
        now = datetime.now(UTC)
        with self._lock:  # synchronous, atomic read-modify-write
            if self._registry.exists(reporting_id):
                record = self._registry.get(reporting_id)
            else:
                record = _new_record(reporting_id, now)
            if record.state in _TERMINAL:
                raise ReportingError(
                    f"reporting record {reporting_id!r} is {record.state.value}"
                )

            if context.metadata.get("cancel"):
                cancelled = replace(
                    record, state=ReportingState.CANCELLED, updated_at=now
                )
                self._registry.register(cancelled)
                events.append(ReportingCancelled(reporting_id=reporting_id))
                self._info(reporting_id, cancelled, "cancelled")
                return ReportingResult(
                    status=ReportingResultStatus.CANCELLED, record=cancelled
                )

            batch = self._collector.collect(context)
            batch = self._builder.build(batch, context)
            exports = self._exporter.export(batch, context)

            new_record = replace(
                record,
                state=ReportingState.BUILT,
                history=record.history.append(batch),
                batch=batch,
                exports=exports,
                report_count=record.report_count + len(batch.reports),
                export_count=record.export_count + len(exports),
                updated_at=now,
            )
            metrics = self._metrics.calculate(new_record)
            snapshot = ReportingSnapshot(
                record=new_record, metrics=metrics, timestamp=now
            )
            self._registry.register(new_record)

        events.extend(
            [
                ReportingCollected(
                    reporting_id=reporting_id, reports=len(batch.reports)
                ),
                ReportBuilt(reporting_id=reporting_id),
                ReportsExported(reporting_id=reporting_id, count=len(exports)),
                ReportingSnapshotCreated(reporting_id=reporting_id),
                ReportingMetricsUpdated(reporting_id=reporting_id),
                ReportingCompleted(reporting_id=reporting_id),
            ]
        )
        self._info(reporting_id, new_record, "reported")
        return ReportingResult(
            status=ReportingResultStatus.SUCCESS,
            record=new_record,
            snapshot=snapshot,
            batch=batch,
            exports=exports,
            metrics=metrics,
        )

    async def _fail(self, reporting_id: str, message: str) -> ReportingResult:
        self._error(reporting_id, message)
        await self._bus.publish(
            ReportingErrorOccurred(reporting_id=reporting_id, message=message)
        )
        return ReportingResult(
            status=ReportingResultStatus.FAILED, errors=(message,)
        )

    def _info(
        self, reporting_id: str, record: ReportingRecord, status: str
    ) -> None:
        if self._log is not None:
            self._log.info(
                "Reporting update",
                extra={
                    "reporting_id": reporting_id,
                    "status": status,
                    "reports": record.report_count,
                },
            )

    def _error(self, reporting_id: str, message: str) -> None:
        if self._log is not None:
            self._log.error(
                "Reporting error",
                extra={"reporting_id": reporting_id, "error": message},
            )


def _new_record(reporting_id: str, now: datetime) -> ReportingRecord:
    return ReportingRecord(
        id=reporting_id,
        state=ReportingState.COLLECTING,
        created_at=now,
        updated_at=now,
    )
