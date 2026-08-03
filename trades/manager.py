"""Trade manager.

:class:`DefaultTradeManager` owns the trade update workflow: tracker (derive
fill) → history (append) → matcher (correlate) → lifecycle (derive + validate
state) → tracker (build durable trade) → analytics → snapshot. It computes the
complete new trade state atomically under a lock (so partial updates never leave
a trade inconsistent), then publishes events and returns a
:class:`~trades.models.TradeResult`. Internal failures are translated to
framework exceptions and never escape; the components stay independent and never
call one another.
"""

from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock

from core.logging import LoggerFactory
from events.base import Event
from events.bus import EventBus
from positions.models import Position
from positions.state import PositionState
from trades.context import TradeContext
from trades.events import (
    TradeAnalyticsUpdated,
    TradeClosed,
    TradeErrorOccurred,
    TradeFilled,
    TradeHistoryUpdated,
    TradeMatched,
    TradeOpened,
    TradePartiallyFilled,
    TradeStateChanged,
    TradeUpdated,
)
from trades.exceptions import TradeClosedError, TradeError
from trades.interfaces import (
    TradeAnalyticsService,
    TradeHistoryService,
    TradeLifecycle,
    TradeMatcher,
    TradeRegistry,
    TradeTracker,
)
from trades.models import TradeResult, TradeResultStatus, TradeSnapshot
from trades.state import TradeState

__all__ = ["DefaultTradeManager"]

_CLOSED_POSITION_STATES = (PositionState.CLOSED, PositionState.CANCELLED)
_TERMINAL_TRADE_STATES = (TradeState.CLOSED, TradeState.CANCELLED)


class DefaultTradeManager:
    """Coordinates the trade update pipeline."""

    def __init__(
        self,
        bus: EventBus,
        registry: TradeRegistry,
        tracker: TradeTracker,
        matcher: TradeMatcher,
        lifecycle: TradeLifecycle,
        history: TradeHistoryService,
        analytics: TradeAnalyticsService,
        logger: LoggerFactory | None = None,
    ) -> None:
        self._bus = bus
        self._registry = registry
        self._tracker = tracker
        self._matcher = matcher
        self._lifecycle = lifecycle
        self._history = history
        self._analytics = analytics
        self._log = logger.get_logger("trades.manager") if logger else None
        self._lock = Lock()

    async def update(self, context: TradeContext) -> TradeResult:
        """Apply the completed position update in ``context``; return a result."""
        events: list[Event] = []
        try:
            position = self._extract(context)
            result = self._compute(position, context, events)
        except TradeError as exc:
            tid = _safe_id(context)
            self._error(tid, str(exc))
            await self._bus.publish(TradeErrorOccurred(trade_id=tid, message=str(exc)))
            existing = self._registry.get(tid) if self._registry.exists(tid) else None
            return TradeResult(
                status=TradeResultStatus.FAILED,
                trade=existing,
                errors=(str(exc),),
            )

        for event in events:  # publish only after a fully consistent update
            await self._bus.publish(event)
        return result

    def _compute(
        self, position: Position, context: TradeContext, events: list[Event]
    ) -> TradeResult:
        tid = position.id
        now = datetime.now(UTC)
        with self._lock:
            existing = self._registry.get(tid) if self._registry.exists(tid) else None
            if existing is not None and existing.state in _TERMINAL_TRADE_STATES:
                raise TradeClosedError(f"trade {tid!r} is {existing.state.value}")

            fill = self._tracker.derive_fill(existing, position, now)
            history = self._history.append(self._registry.history(tid), fill)
            match = self._matcher.match(position, fill)

            source = existing.state if existing else TradeState.PENDING
            position_closed = position.state in _CLOSED_POSITION_STATES
            target = self._lifecycle.derive_state(match, position_closed)
            self._lifecycle.validate(source, target)

            opened_at = existing.opened_at if existing and existing.opened_at else now
            trade = self._tracker.build(tid, existing, position, target, opened_at, now)
            analytics = self._analytics.compute(trade, history)
            snapshot = TradeSnapshot(
                trade=trade,
                analytics=analytics,
                fill_count=len(history.fills),
                timestamp=now,
            )
            self._registry.register(trade, history)

        if existing is None:
            events.append(TradeOpened(trade_id=tid, symbol=position.symbol))
        else:
            events.append(TradeUpdated(trade_id=tid))
        if source != target:
            events.append(
                TradeStateChanged(trade_id=tid, previous=source, current=target)
            )
        events.append(
            TradeMatched(trade_id=tid, matched_quantity=match.matched_quantity)
        )
        if target is TradeState.PARTIALLY_FILLED:
            events.append(TradePartiallyFilled(trade_id=tid))
        if target is TradeState.FILLED:
            events.append(TradeFilled(trade_id=tid))
        if target is TradeState.CLOSED:
            events.append(TradeClosed(trade_id=tid))
        events.append(TradeHistoryUpdated(trade_id=tid))
        events.append(TradeAnalyticsUpdated(trade_id=tid))

        self._log_lifecycle(existing is None, target, tid)
        return TradeResult(
            status=TradeResultStatus.SUCCESS,
            trade=trade,
            snapshot=snapshot,
            fill=fill,
        )

    @staticmethod
    def _extract(context: TradeContext) -> Position:
        """Return the completed position from the update.

        Raises:
            TradeError: If the position update did not complete successfully.
        """
        pr = context.position_result
        if pr.position is None or not pr.succeeded:
            raise TradeError("no completed position update")
        return pr.position

    def _log_lifecycle(self, opened: bool, target: TradeState, tid: str) -> None:
        if self._log is None:
            return
        if opened:
            message = "Trade opened"
        elif target is TradeState.CLOSED:
            message = "Trade closed"
        else:
            message = "Trade updated"
        self._log.info(message, extra={"trade_id": tid, "state": target.value})

    def _error(self, tid: str, message: str) -> None:
        if self._log is not None:
            self._log.error(
                "Trade error", extra={"trade_id": tid, "error": message}
            )


def _safe_id(context: TradeContext) -> str:
    """Best-effort trade id for error reporting."""
    pr = context.position_result
    if pr.position is not None:
        return pr.position.id
    return "unknown"
