"""Performance manager.

:class:`DefaultPerformanceManager` owns the analysis workflow: returns → risk →
statistics → benchmarking → snapshot → registry. It runs the stateless
calculators, assembles the immutable snapshot atomically under a lock, registers
it, then publishes the ordered event set and returns a
:class:`~performance.models.PerformanceResult`. Any stage failure is translated
to a framework exception, isolated, published as
:class:`~performance.events.PerformanceErrorOccurred`, and returned as a FAILED
result — never a partial or leaked internal exception. The components stay
independent and never call one another.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from threading import Lock

from core.logging import LoggerFactory
from events.base import Event
from events.bus import EventBus
from performance.context import PerformanceContext
from performance.events import (
    BenchmarkCalculated,
    PerformanceAnalysisCompleted,
    PerformanceAnalysisStarted,
    PerformanceErrorOccurred,
    PerformanceSnapshotCreated,
    ReturnsCalculated,
    RiskCalculated,
    StatisticsCalculated,
)
from performance.exceptions import PerformanceError
from performance.interfaces import (
    BenchmarkingService,
    PerformanceRegistry,
    ReturnsCalculator,
    RiskCalculator,
    StatisticsCalculator,
)
from performance.models import (
    PerformanceIdentifier,
    PerformanceMetadata,
    PerformanceMetrics,
    PerformanceResult,
    PerformanceSnapshot,
    PerformanceSummary,
    StatisticsMetrics,
)
from performance.state import PerformanceStatus

__all__ = ["DefaultPerformanceManager"]

_ZERO = Decimal("0")


class DefaultPerformanceManager:
    """Coordinates the performance analysis pipeline."""

    def __init__(
        self,
        bus: EventBus,
        registry: PerformanceRegistry,
        returns: ReturnsCalculator,
        risk: RiskCalculator,
        statistics: StatisticsCalculator,
        benchmarking: BenchmarkingService,
        logger: LoggerFactory | None = None,
    ) -> None:
        self._bus = bus
        self._registry = registry
        self._returns = returns
        self._risk = risk
        self._statistics = statistics
        self._benchmarking = benchmarking
        self._log = logger.get_logger("performance.manager") if logger else None
        self._lock = Lock()

    async def analyze(self, context: PerformanceContext) -> PerformanceResult:
        """Run the analysis in ``context`` and return a result."""
        analysis_id = uuid.uuid4().hex
        events: list[Event] = []
        try:
            result = self._compute(analysis_id, context, events)
        except PerformanceError as exc:
            self._error(analysis_id, str(exc))
            await self._bus.publish(
                PerformanceErrorOccurred(analysis_id=analysis_id, message=str(exc))
            )
            return PerformanceResult(
                status=PerformanceStatus.FAILED, errors=(str(exc),)
            )

        for event in events:  # publish only after a fully consistent analysis
            await self._bus.publish(event)
        return result

    def _compute(
        self, analysis_id: str, context: PerformanceContext, events: list[Event]
    ) -> PerformanceResult:
        now = datetime.now(UTC)
        with self._lock:
            returns = self._returns.calculate(context)
            risk = self._risk.calculate(context)
            statistics = self._statistics.calculate(context)
            benchmark = self._benchmarking.compare(context)

            metrics = PerformanceMetrics(
                returns=returns,
                risk=risk,
                statistics=statistics,
                benchmark=benchmark,
            )
            identifier = PerformanceIdentifier(
                id=analysis_id,
                correlation_id=context.correlation_id,
                timestamp=now,
            )
            snapshot = PerformanceSnapshot(
                identifier=identifier,
                timestamp=now,
                returns=returns,
                risk=risk,
                statistics=statistics,
                benchmark=benchmark,
                summary=_build_summary(context, statistics),
                metadata=PerformanceMetadata(
                    correlation_id=context.correlation_id, extra=context.metadata
                ),
            )
            self._registry.register(snapshot)

        events.extend(
            [
                PerformanceAnalysisStarted(analysis_id=analysis_id),
                ReturnsCalculated(analysis_id=analysis_id),
                RiskCalculated(analysis_id=analysis_id),
                StatisticsCalculated(analysis_id=analysis_id),
                BenchmarkCalculated(analysis_id=analysis_id),
                PerformanceSnapshotCreated(analysis_id=analysis_id),
                PerformanceAnalysisCompleted(analysis_id=analysis_id),
            ]
        )
        self._info(analysis_id, context.correlation_id)
        return PerformanceResult(
            status=PerformanceStatus.COMPLETED, snapshot=snapshot, metrics=metrics
        )

    def _info(self, analysis_id: str, correlation_id: str | None) -> None:
        if self._log is not None:
            self._log.info(
                "Performance analysis completed",
                extra={"analysis_id": analysis_id, "correlation_id": correlation_id},
            )

    def _error(self, analysis_id: str, message: str) -> None:
        if self._log is not None:
            self._log.error(
                "Performance analysis error",
                extra={"analysis_id": analysis_id, "error": message},
            )


def _build_summary(
    context: PerformanceContext, statistics: StatisticsMetrics
) -> PerformanceSummary:
    """Assemble the compact cross-cutting summary (never logs raw datasets)."""
    total_value = cost_basis = realized = unrealized = _ZERO
    open_positions = 0
    pr = context.portfolio_result
    if pr is not None and pr.snapshot is not None:
        value = pr.snapshot.value
        total_value = value.total_value
        cost_basis = value.cost_basis
        realized = value.realized_pnl
        unrealized = value.unrealized_pnl
        if pr.snapshot.portfolio is not None:
            open_positions = len(pr.snapshot.portfolio.positions)

    gross_profit = sum(
        (t.realized_pnl for t in context.completed_trades() if t.realized_pnl > _ZERO),
        _ZERO,
    )
    return PerformanceSummary(
        total_value=total_value,
        cost_basis=cost_basis,
        realized_pnl=realized,
        unrealized_pnl=unrealized,
        open_positions=open_positions,
        total_trades=statistics.total_trades,
        win_rate=statistics.win_rate,
        gross_profit=gross_profit,
    )
