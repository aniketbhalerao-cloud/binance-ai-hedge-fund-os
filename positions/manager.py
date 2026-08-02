"""Position manager.

:class:`DefaultPositionManager` owns the position update workflow: history →
calculator → lifecycle → tracker → metrics → snapshot. It computes the complete
new position state atomically under a lock (so partial updates never leave a
position inconsistent), then publishes events and returns a
:class:`PositionResult`. Internal failures are translated to framework
exceptions and never escape. The components stay independent.
"""

from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock

from core.logging import LoggerFactory
from events.base import Event
from events.bus import EventBus
from positions.context import PositionContext
from positions.events import (
    PositionClosed,
    PositionErrorOccurred,
    PositionHistoryUpdated,
    PositionMetricsUpdated,
    PositionOpened,
    PositionPartiallyClosed,
    PositionSnapshotCreated,
    PositionStateChanged,
    PositionUpdated,
)
from positions.exceptions import PositionClosedError, PositionError
from positions.interfaces import (
    PositionCalculator,
    PositionHistoryService,
    PositionLifecycle,
    PositionMetricsService,
    PositionRegistry,
    PositionTracker,
)
from positions.models import (
    PositionResult,
    PositionResultStatus,
    PositionSnapshot,
    PositionTrade,
)
from positions.state import PositionState

__all__ = ["DefaultPositionManager"]


class DefaultPositionManager:
    """Coordinates the position update pipeline."""

    def __init__(
        self,
        bus: EventBus,
        registry: PositionRegistry,
        tracker: PositionTracker,
        lifecycle: PositionLifecycle,
        calculator: PositionCalculator,
        history: PositionHistoryService,
        metrics: PositionMetricsService,
        logger: LoggerFactory | None = None,
    ) -> None:
        self._bus = bus
        self._registry = registry
        self._tracker = tracker
        self._lifecycle = lifecycle
        self._calculator = calculator
        self._history = history
        self._metrics = metrics
        self._log = logger.get_logger("positions.manager") if logger else None
        self._lock = Lock()

    async def update(self, context: PositionContext) -> PositionResult:
        """Apply the trade in ``context`` and return a :class:`PositionResult`."""
        events: list[Event] = []
        try:
            trade = self._extract(context)
            result = self._compute(trade, context, events)
        except PositionError as exc:
            pid = _safe_symbol(context)
            self._error(pid, str(exc))
            await self._bus.publish(
                PositionErrorOccurred(position_id=pid, message=str(exc))
            )
            existing = self._registry.get(pid) if self._registry.exists(pid) else None
            return PositionResult(
                status=PositionResultStatus.FAILED,
                position=existing,
                errors=(str(exc),),
            )

        for event in events:  # publish only after a fully consistent update
            await self._bus.publish(event)
        return result

    def _compute(
        self, trade: PositionTrade, context: PositionContext, events: list[Event]
    ) -> PositionResult:
        pid = trade.symbol
        now = datetime.now(UTC)
        with self._lock:
            existing = self._registry.get(pid) if self._registry.exists(pid) else None
            if existing is not None and existing.state in (
                PositionState.CLOSED,
                PositionState.CANCELLED,
            ):
                raise PositionClosedError(f"position {pid!r} is {existing.state.value}")

            history = self._history.append(self._registry.history(pid), trade)
            calc = self._calculator.calculate(history.trades, context.prices, now)

            source = existing.state if existing else PositionState.PENDING
            target = self._lifecycle.derive_state(calc)
            self._lifecycle.validate(source, target)

            opened_at = existing.opened_at if existing and existing.opened_at else now
            position = self._tracker.build(
                pid, trade.symbol, calc, target, opened_at, now
            )
            metrics = self._metrics.compute(history, calc)
            snapshot = PositionSnapshot(
                position=position,
                metrics=metrics,
                unrealized_pnl=calc.unrealized_pnl,
                duration_seconds=calc.duration_seconds,
                timestamp=now,
            )
            self._registry.register(position, history)

        if existing is None:
            events.append(PositionOpened(position_id=pid, symbol=trade.symbol))
        else:
            events.append(PositionUpdated(position_id=pid))
        if source != target:
            events.append(
                PositionStateChanged(position_id=pid, previous=source, current=target)
            )
        if target is PositionState.PARTIALLY_CLOSED:
            events.append(PositionPartiallyClosed(position_id=pid))
        if target is PositionState.CLOSED:
            events.append(PositionClosed(position_id=pid))
        events.extend(
            [
                PositionHistoryUpdated(position_id=pid),
                PositionMetricsUpdated(position_id=pid),
                PositionSnapshotCreated(position_id=pid),
            ]
        )
        self._info("Position updated", pid)
        return PositionResult(
            status=PositionResultStatus.SUCCESS, position=position, snapshot=snapshot
        )

    @staticmethod
    def _extract(context: PositionContext) -> PositionTrade:
        """Extract the latest booked trade from the portfolio update."""
        pr = context.portfolio_result
        if pr.portfolio is None or not pr.succeeded or not pr.portfolio.ledger:
            raise PositionError("no completed trade in portfolio update")
        entry = pr.portfolio.ledger[-1]
        return PositionTrade(
            symbol=entry.symbol,
            side=entry.side,
            quantity=entry.quantity,
            price=entry.price,
            timestamp=entry.timestamp,
        )

    def _info(self, message: str, pid: str) -> None:
        if self._log is not None:
            self._log.info(message, extra={"position_id": pid})

    def _error(self, pid: str, message: str) -> None:
        if self._log is not None:
            self._log.error(
                "Position error", extra={"position_id": pid, "error": message}
            )


def _safe_symbol(context: PositionContext) -> str:
    """Best-effort position id for error reporting."""
    pr = context.portfolio_result
    if pr.portfolio is not None and pr.portfolio.ledger:
        return pr.portfolio.ledger[-1].symbol
    return "unknown"
