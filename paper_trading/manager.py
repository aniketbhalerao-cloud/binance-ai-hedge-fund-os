"""Paper trading manager.

:class:`DefaultPaperTradingManager` owns the live paper-trading workflow. For each
live market update it loads the running :class:`~paper_trading.models.PaperSession`
from the Registry, processes exactly one update **atomically**, builds a new
immutable session, and writes it back. The read-modify-write spans ``await``
points (the pipeline drives async framework engines), so atomicity is provided by
an :class:`asyncio.Lock` that serializes per-update processing; the Registry's own
:class:`threading.Lock` guards its store.

Per update the manager runs the existing frameworks in order — Feed → Strategy →
Risk → Order → Execution → Paper Broker(fill) → Portfolio → Position → Trade →
Performance → Metrics. Every upstream framework is an optional injected engine, so
the manager reuses the real frameworks without duplicating any of them. The Paper
Broker is invoked strictly *after* Execution and only computes fill economics.

Any failure is translated to a framework exception, isolated, published as
:class:`~paper_trading.events.PaperTradingErrorOccurred`, and returned as a FAILED
result — never a leaked internal exception, and never a partial session write.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.base import Event
from events.bus import EventBus
from execution.context import ExecutionContext
from execution.models import ExecutionResult
from order_management.context import OrderContext
from paper_trading.context import PaperTradingContext
from paper_trading.events import (
    MarketDataProcessed,
    PaperMetricsUpdated,
    PaperOrderFilled,
    PaperSessionCancelled,
    PaperSessionCompleted,
    PaperSnapshotCreated,
    PaperTradeExecuted,
    PaperTradingErrorOccurred,
)
from paper_trading.exceptions import PaperTradingError
from paper_trading.interfaces import (
    Broker,
    Feed,
    PaperTradingHistoryService,
    PaperTradingMetricsCalculator,
    PaperTradingRegistry,
)
from paper_trading.models import (
    PaperFill,
    PaperSession,
    PaperTradingHistory,
    PaperTradingResult,
    PaperTradingResultStatus,
    PaperTradingSnapshot,
    PaperTradingSummary,
    SessionParameters,
)
from paper_trading.state import SessionState
from performance.context import PerformanceContext
from performance.models import PerformanceResult
from portfolio.context import PortfolioContext
from portfolio.models import PortfolioResult
from positions.context import PositionContext
from positions.models import PositionResult
from risk.context import RiskContext
from strategies.signals import SignalDirection
from trades.context import TradeContext
from trades.models import Trade, TradeResult

if TYPE_CHECKING:
    from execution.interfaces import ExecutionEngine
    from order_management.interfaces import OrderEngine
    from performance.interfaces import PerformanceEngine
    from portfolio.interfaces import PortfolioEngine
    from positions.interfaces import PositionEngine
    from risk.interfaces import RiskEngine
    from trades.interfaces import TradeEngine

__all__ = ["DefaultPaperTradingManager"]

_ZERO = Decimal("0")
_TERMINAL = (SessionState.COMPLETED, SessionState.CANCELLED, SessionState.FAILED)


class DefaultPaperTradingManager:
    """Coordinates live paper trading over the existing frameworks."""

    def __init__(
        self,
        bus: EventBus,
        registry: PaperTradingRegistry,
        feed: Feed,
        broker: Broker,
        metrics: PaperTradingMetricsCalculator,
        history: PaperTradingHistoryService,
        logger: LoggerFactory | None = None,
        risk_engine: RiskEngine | None = None,
        order_engine: OrderEngine | None = None,
        execution_engine: ExecutionEngine | None = None,
        portfolio_engine: PortfolioEngine | None = None,
        position_engine: PositionEngine | None = None,
        trade_engine: TradeEngine | None = None,
        performance_engine: PerformanceEngine | None = None,
    ) -> None:
        self._bus = bus
        self._registry = registry
        self._feed = feed
        self._broker = broker
        self._metrics = metrics
        self._history = history
        self._risk_engine = risk_engine
        self._order_engine = order_engine
        self._execution_engine = execution_engine
        self._portfolio_engine = portfolio_engine
        self._position_engine = position_engine
        self._trade_engine = trade_engine
        self._performance_engine = performance_engine
        self._log = logger.get_logger("paper_trading.manager") if logger else None
        self._lock = asyncio.Lock()

    async def process(self, context: PaperTradingContext) -> PaperTradingResult:
        """Process one live update and return a result."""
        session_id = context.session_id
        events: list[Event] = []
        try:
            result = await self._process(session_id, context, events)
        except PaperTradingError as exc:
            return await self._fail(session_id, str(exc))
        except Exception as exc:  # translate; never leak internals
            return await self._fail(session_id, str(exc))

        for event in events:  # publish only after a consistent update
            await self._bus.publish(event)
        return result

    async def _process(
        self, session_id: str, context: PaperTradingContext, events: list[Event]
    ) -> PaperTradingResult:
        params = context.parameters
        async with self._lock:  # atomic per-update read-modify-write
            now = datetime.now(UTC)
            if self._registry.exists(session_id):
                session = self._registry.get(session_id)
            else:
                session = self._new_session(session_id, context, now)
            if session.state in _TERMINAL:
                raise PaperTradingError(
                    f"session {session_id!r} is {session.state.value}"
                )

            if (
                params.cancel_after_updates is not None
                and session.update_count >= params.cancel_after_updates
            ):
                cancelled = replace(
                    session, state=SessionState.CANCELLED, updated_at=now
                )
                self._registry.register(cancelled)
                events.append(PaperSessionCancelled(session_id=session_id))
                self._info(session_id, "cancelled")
                return PaperTradingResult(
                    status=PaperTradingResultStatus.CANCELLED, session=cancelled
                )

            recent = (session.recent_candles + (context.candle,))[-params.window :]
            filled = await self._step(context, recent)

            fill: PaperFill | None = None
            portfolio_result = session.portfolio_result
            position_result = session.position_result
            trade_result = session.trade_result
            trades = list(session.trades)
            history = session.history
            total_commission = session.total_commission
            fill_count = session.fill_count

            if filled is not None:
                execution_result, fill = filled
                fill_count += 1
                total_commission += fill.commission
                portfolio_result = await self._book(
                    context, execution_result, fill, portfolio_result
                )
                position_result = await self._position(
                    context, portfolio_result, position_result
                )
                trade_result = await self._trade(position_result, trade_result)
                trades = _upsert_trade(trades, trade_result)
                history = self._history.append(history, fill)

            equity = _equity(portfolio_result, params.initial_cash)
            prev = (
                session.equity_curve[-1]
                if session.equity_curve
                else params.initial_cash
            )
            equity_curve = session.equity_curve + (equity,)
            returns = session.returns + (
                (equity - prev) / prev if prev > _ZERO else _ZERO,
            )

            performance_result = await self._analyze(
                context, portfolio_result, position_result, trade_result, trades,
                equity_curve, returns,
            )
            metrics = self._metrics.calculate(
                performance_result, trades, equity_curve, total_commission
            )

            state = SessionState.COMPLETED if context.final else SessionState.RUNNING
            new_session = replace(
                session,
                state=state,
                portfolio_result=portfolio_result,
                position_result=position_result,
                trade_result=trade_result,
                recent_candles=recent,
                equity_curve=equity_curve,
                returns=returns,
                trades=tuple(trades),
                history=history,
                total_commission=total_commission,
                update_count=session.update_count + 1,
                fill_count=fill_count,
                updated_at=now,
            )
            summary = _summary(new_session, params)
            snapshot = PaperTradingSnapshot(
                session=new_session, metrics=metrics, summary=summary, timestamp=now
            )
            self._registry.register(new_session)

        events.append(
            MarketDataProcessed(session_id=session_id, symbol=context.symbol)
        )
        if fill is not None:
            events.append(
                PaperOrderFilled(
                    session_id=session_id,
                    symbol=fill.symbol,
                    quantity=fill.quantity,
                    price=fill.price,
                )
            )
            events.append(PaperTradeExecuted(session_id=session_id))
        events.append(PaperMetricsUpdated(session_id=session_id))
        events.append(PaperSnapshotCreated(session_id=session_id))
        if context.final:
            events.append(PaperSessionCompleted(session_id=session_id))
            status = PaperTradingResultStatus.COMPLETED
        else:
            status = PaperTradingResultStatus.PROCESSED
        self._info(session_id, status.value)
        return PaperTradingResult(
            status=status,
            session=new_session,
            snapshot=snapshot,
            fill=fill,
            metrics=metrics,
        )

    async def _step(
        self, context: PaperTradingContext, recent: tuple[object, ...]
    ) -> tuple[ExecutionResult, PaperFill] | None:
        """Run Feed → Strategy → Risk → Order → Execution → Broker for one update."""
        strategy = context.strategy
        if strategy is None:
            return None
        strategy_ctx = self._feed.normalize(context, recent)  # type: ignore[arg-type]
        signals = await strategy.evaluate(strategy_ctx)

        for signal in signals:
            if signal.direction is SignalDirection.HOLD:
                continue
            if self._risk_engine is None:
                continue
            decision = await self._risk_engine.evaluate(
                RiskContext(
                    signal=signal,
                    exchange=context.exchange,
                    symbol=context.symbol,
                )
            )
            if not decision.approved:
                continue
            if self._order_engine is None:
                continue
            order_result = await self._order_engine.process(
                OrderContext(
                    risk_decision=decision,
                    signal=signal,
                    exchange=context.exchange,
                    symbol=context.symbol,
                )
            )
            if not order_result.ready:
                continue
            if self._execution_engine is None:
                continue
            execution_result = await self._execution_engine.process(
                ExecutionContext(
                    order_result=order_result,
                    exchange=context.exchange,
                    symbol=context.symbol,
                    risk_decision=decision,
                    signal=signal,
                )
            )
            if not execution_result.ready:
                continue
            fill = self._broker.fill(
                execution_result, context.candle, context.parameters
            )
            return execution_result, fill
        return None

    async def _book(
        self,
        context: PaperTradingContext,
        execution_result: ExecutionResult,
        fill: PaperFill,
        previous: PortfolioResult | None,
    ) -> PortfolioResult | None:
        if self._portfolio_engine is None:
            return previous
        result = await self._portfolio_engine.process(
            PortfolioContext(
                portfolio_id=context.session_id,
                execution_result=execution_result,
                prices={fill.symbol: fill.price},
                initial_cash=context.parameters.initial_cash,
            )
        )
        return result if result.succeeded else previous

    async def _position(
        self,
        context: PaperTradingContext,
        portfolio_result: PortfolioResult | None,
        previous: PositionResult | None,
    ) -> PositionResult | None:
        if self._position_engine is None or portfolio_result is None:
            return previous
        result = await self._position_engine.process(
            PositionContext(
                portfolio_result=portfolio_result,
                prices={context.symbol: context.candle.close},
            )
        )
        return result if result.succeeded else previous

    async def _trade(
        self, position_result: PositionResult | None, previous: TradeResult | None
    ) -> TradeResult | None:
        if self._trade_engine is None or position_result is None:
            return previous
        result = await self._trade_engine.process(
            TradeContext(position_result=position_result)
        )
        return result if result.succeeded else previous

    async def _analyze(
        self,
        context: PaperTradingContext,
        portfolio_result: PortfolioResult | None,
        position_result: PositionResult | None,
        trade_result: TradeResult | None,
        trades: list[Trade],
        equity_curve: tuple[Decimal, ...],
        returns: tuple[Decimal, ...],
    ) -> PerformanceResult | None:
        if self._performance_engine is None:
            return context.performance_result
        return await self._performance_engine.analyze(
            PerformanceContext(
                portfolio_result=portfolio_result,
                position_result=position_result,
                trade_result=trade_result,
                trades=tuple(trades),
                equity_curve=equity_curve,
                returns=returns,
                correlation_id=context.correlation_id,
            )
        )

    def _new_session(
        self, session_id: str, context: PaperTradingContext, now: datetime
    ) -> PaperSession:
        return PaperSession(
            id=session_id,
            exchange=context.exchange,
            symbol=context.symbol,
            state=SessionState.RUNNING,
            equity_curve=(context.parameters.initial_cash,),
            history=PaperTradingHistory(session_id),
            started_at=now,
            updated_at=now,
        )

    async def _fail(self, session_id: str, message: str) -> PaperTradingResult:
        self._error(session_id, message)
        await self._bus.publish(
            PaperTradingErrorOccurred(session_id=session_id, message=message)
        )
        return PaperTradingResult(
            status=PaperTradingResultStatus.FAILED, errors=(message,)
        )

    def _info(self, session_id: str, status: str) -> None:
        if self._log is not None:
            self._log.info(
                "Paper update processed",
                extra={"session_id": session_id, "status": status},
            )

    def _error(self, session_id: str, message: str) -> None:
        if self._log is not None:
            self._log.error(
                "Paper trading error",
                extra={"session_id": session_id, "error": message},
            )


def _equity(portfolio_result: PortfolioResult | None, fallback: Decimal) -> Decimal:
    if portfolio_result is None or portfolio_result.snapshot is None:
        return fallback
    return portfolio_result.snapshot.value.total_value


def _summary(
    session: PaperSession, params: SessionParameters
) -> PaperTradingSummary:
    final_equity = (
        session.equity_curve[-1] if session.equity_curve else params.initial_cash
    )
    return PaperTradingSummary(
        total_updates=session.update_count,
        total_fills=session.fill_count,
        total_trades=len(session.trades),
        total_commission=session.total_commission,
        initial_equity=params.initial_cash,
        final_equity=final_equity,
        net_profit=final_equity - params.initial_cash,
    )


def _upsert_trade(trades: list[Trade], result: TradeResult | None) -> list[Trade]:
    """Replace the trade with the same id (or append), keeping latest state."""
    if result is None or result.trade is None:
        return trades
    trade = result.trade
    updated = [t for t in trades if t.id != trade.id]
    updated.append(trade)
    return updated
