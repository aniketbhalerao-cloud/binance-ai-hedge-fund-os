"""Dashboard manager.

:class:`DefaultDashboardManager` owns the dashboard workflow. For each input it
loads the running :class:`~dashboard.models.DashboardRecord` from the Registry,
aggregates a view, composes it, generates widgets, computes metrics, builds a
**new** immutable record, and writes it back. The whole read-modify-write is
synchronous (the components are pure — no ``await`` inside), so atomicity is
provided by a :class:`threading.Lock`; events are published only after a consistent
update.

Any failure is translated to a framework exception, isolated, published as
:class:`~dashboard.events.DashboardErrorOccurred`, and returned as a FAILED result —
never a leaked internal exception, and never a partial record write. The framework
only presents: it never renders to a real display and never modifies a strategy,
agent, or portfolio.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from threading import Lock

from core.logging import LoggerFactory
from dashboard.context import DashboardContext
from dashboard.events import (
    DashboardCancelled,
    DashboardCompleted,
    DashboardComposed,
    DashboardErrorOccurred,
    DashboardMetricsUpdated,
    DashboardSnapshotCreated,
    DashboardStarted,
    DashboardViewCreated,
    WidgetsGenerated,
)
from dashboard.exceptions import DashboardError
from dashboard.interfaces import (
    Aggregator,
    Composer,
    DashboardMetricsCalculator,
    DashboardRegistry,
    WidgetGenerator,
)
from dashboard.models import (
    DashboardRecord,
    DashboardResult,
    DashboardResultStatus,
    DashboardSnapshot,
)
from dashboard.state import DashboardState
from events.base import Event
from events.bus import EventBus

__all__ = ["DefaultDashboardManager"]

_TERMINAL = (
    DashboardState.COMPLETED,
    DashboardState.CANCELLED,
    DashboardState.FAILED,
)


class DefaultDashboardManager:
    """Coordinates the dashboard pipeline over a registry-owned record."""

    def __init__(
        self,
        bus: EventBus,
        registry: DashboardRegistry,
        aggregator: Aggregator,
        composer: Composer,
        widgets: WidgetGenerator,
        metrics: DashboardMetricsCalculator,
        logger: LoggerFactory | None = None,
    ) -> None:
        self._bus = bus
        self._registry = registry
        self._aggregator = aggregator
        self._composer = composer
        self._widgets = widgets
        self._metrics = metrics
        self._log = logger.get_logger("dashboard.manager") if logger else None
        self._lock = Lock()

    async def render(self, context: DashboardContext) -> DashboardResult:
        """Render one input and return a result."""
        dashboard_id = context.dashboard_id
        events: list[Event] = []
        try:
            result = self._compute(dashboard_id, context, events)
        except DashboardError as exc:
            return await self._fail(dashboard_id, str(exc))
        except Exception as exc:  # translate; never leak internals
            return await self._fail(dashboard_id, str(exc))

        for event in events:  # publish only after a consistent update
            await self._bus.publish(event)
        return result

    def _compute(
        self,
        dashboard_id: str,
        context: DashboardContext,
        events: list[Event],
    ) -> DashboardResult:
        events.append(DashboardStarted(dashboard_id=dashboard_id))
        now = datetime.now(UTC)
        with self._lock:  # synchronous, atomic read-modify-write
            if self._registry.exists(dashboard_id):
                record = self._registry.get(dashboard_id)
            else:
                record = _new_record(dashboard_id, now)
            if record.state in _TERMINAL:
                raise DashboardError(
                    f"dashboard record {dashboard_id!r} is {record.state.value}"
                )

            if context.metadata.get("cancel"):
                cancelled = replace(
                    record, state=DashboardState.CANCELLED, updated_at=now
                )
                self._registry.register(cancelled)
                events.append(DashboardCancelled(dashboard_id=dashboard_id))
                self._info(dashboard_id, cancelled, "cancelled")
                return DashboardResult(
                    status=DashboardResultStatus.CANCELLED, record=cancelled
                )

            view = self._aggregator.aggregate(context)
            view = self._composer.compose(view, context)
            widgets = self._widgets.generate(view, context)

            new_record = replace(
                record,
                state=DashboardState.COMPOSED,
                history=record.history.append(view),
                view=view,
                widgets=widgets,
                panel_count=record.panel_count + len(view.panels),
                widget_count=record.widget_count + len(widgets),
                updated_at=now,
            )
            metrics = self._metrics.calculate(new_record)
            snapshot = DashboardSnapshot(
                record=new_record, metrics=metrics, timestamp=now
            )
            self._registry.register(new_record)

        events.extend(
            [
                DashboardViewCreated(
                    dashboard_id=dashboard_id, panels=len(view.panels)
                ),
                DashboardComposed(dashboard_id=dashboard_id),
                WidgetsGenerated(dashboard_id=dashboard_id, count=len(widgets)),
                DashboardSnapshotCreated(dashboard_id=dashboard_id),
                DashboardMetricsUpdated(dashboard_id=dashboard_id),
                DashboardCompleted(dashboard_id=dashboard_id),
            ]
        )
        self._info(dashboard_id, new_record, "rendered")
        return DashboardResult(
            status=DashboardResultStatus.SUCCESS,
            record=new_record,
            snapshot=snapshot,
            view=view,
            widgets=widgets,
            metrics=metrics,
        )

    async def _fail(self, dashboard_id: str, message: str) -> DashboardResult:
        self._error(dashboard_id, message)
        await self._bus.publish(
            DashboardErrorOccurred(dashboard_id=dashboard_id, message=message)
        )
        return DashboardResult(
            status=DashboardResultStatus.FAILED, errors=(message,)
        )

    def _info(
        self, dashboard_id: str, record: DashboardRecord, status: str
    ) -> None:
        if self._log is not None:
            self._log.info(
                "Dashboard update",
                extra={
                    "dashboard_id": dashboard_id,
                    "status": status,
                    "panels": record.panel_count,
                },
            )

    def _error(self, dashboard_id: str, message: str) -> None:
        if self._log is not None:
            self._log.error(
                "Dashboard error",
                extra={"dashboard_id": dashboard_id, "error": message},
            )


def _new_record(dashboard_id: str, now: datetime) -> DashboardRecord:
    return DashboardRecord(
        id=dashboard_id,
        state=DashboardState.AGGREGATING,
        created_at=now,
        updated_at=now,
    )
