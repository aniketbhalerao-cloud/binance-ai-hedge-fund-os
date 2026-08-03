"""Backtest manager.

:class:`DefaultBacktestManager` owns the backtest run workflow. Driven by the
Scheduler, it replays the historical candles and, per step, runs the existing
frameworks in order — Strategy → Risk → Order → Execution → Simulator(fill) →
Portfolio → Position → Trade — then, at the end of the run, Performance and
Metrics. Every upstream framework is an **optional injected engine**: a stage is
run only when its engine is present and the previous stage produced an actionable
result, so the manager reuses the real frameworks without duplicating any of
them.

The Simulator is invoked strictly *after* Execution has coordinated the order; it
only computes the historical fill economics and never validates, routes, or
contacts an exchange.

The snapshot is registered atomically under a lock and the terminal event is
published only after a consistent run. Any failure is translated to a framework
exception, isolated, published as
:class:`~backtesting.events.BacktestErrorOccurred`, and returned as a FAILED
result — never a leaked internal exception.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from threading import Lock
from typing import TYPE_CHECKING

from backtesting.context import BacktestingContext
from backtesting.events import (
    BacktestCancelled,
    BacktestCompleted,
    BacktestErrorOccurred,
    BacktestMetricsUpdated,
    BacktestPaused,
    BacktestProgress,
    BacktestResumed,
    BacktestSnapshotCreated,
    BacktestStarted,
    SimulationStepCompleted,
)
from backtesting.exceptions import BacktestError
from backtesting.interfaces import (
    BacktestHistoryService,
    BacktestMetricsCalculator,
    BacktestRegistry,
    Scheduler,
    Simulator,
)
from backtesting.models import (
    Backtest,
    BacktestHistory,
    BacktestResult,
    BacktestResultStatus,
    BacktestSnapshot,
    BacktestSummary,
    SimulatedFill,
    SimulationStep,
)
from backtesting.state import SimulationState
from core.logging import LoggerFactory
from events.bus import EventBus
from execution.context import ExecutionContext
from execution.models import ExecutionResult
from market_data.models import OHLCV
from order_management.context import OrderContext
from performance.context import PerformanceContext
from performance.models import PerformanceResult
from portfolio.context import PortfolioContext
from portfolio.models import PortfolioResult
from positions.context import PositionContext
from positions.models import PositionResult
from risk.context import RiskContext
from strategies.context import StrategyContext
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

__all__ = ["DefaultBacktestManager"]

_ZERO = Decimal("0")
_WINDOW = 128


class DefaultBacktestManager:
    """Coordinates the backtest run pipeline over the existing frameworks."""

    def __init__(
        self,
        bus: EventBus,
        registry: BacktestRegistry,
        scheduler: Scheduler,
        simulator: Simulator,
        metrics: BacktestMetricsCalculator,
        history: BacktestHistoryService,
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
        self._scheduler = scheduler
        self._simulator = simulator
        self._metrics = metrics
        self._history = history
        self._risk_engine = risk_engine
        self._order_engine = order_engine
        self._execution_engine = execution_engine
        self._portfolio_engine = portfolio_engine
        self._position_engine = position_engine
        self._trade_engine = trade_engine
        self._performance_engine = performance_engine
        self._log = logger.get_logger("backtesting.manager") if logger else None
        self._lock = Lock()

    async def run(self, context: BacktestingContext) -> BacktestResult:
        """Run the backtest in ``context`` and return a result."""
        backtest_id = uuid.uuid4().hex
        try:
            return await self._run(backtest_id, context)
        except BacktestError as exc:
            return await self._fail(backtest_id, str(exc))
        except Exception as exc:  # translate; never leak internals
            return await self._fail(backtest_id, str(exc))

    async def _run(
        self, backtest_id: str, context: BacktestingContext
    ) -> BacktestResult:
        params = context.parameters
        started = datetime.now(UTC)
        await self._bus.publish(
            BacktestStarted(backtest_id=backtest_id, symbol=context.symbol)
        )

        schedule = self._scheduler.iterate(context.candles, params.replay_speed)
        total = len(schedule)

        equity_curve: list[Decimal] = [params.initial_cash]
        returns: list[Decimal] = []
        trades: list[Trade] = []
        history = BacktestHistory(backtest_id)
        portfolio_result = context.portfolio_result
        position_result = context.position_result
        trade_result = context.trade_result
        total_commission = _ZERO
        fills = 0
        cancelled = False
        step_no = 0

        for step_no, (idx, candle) in enumerate(schedule, start=1):
            if (
                params.cancel_after_steps is not None
                and step_no > params.cancel_after_steps
            ):
                cancelled = True
                step_no -= 1
                break
            if params.pause_at_step == step_no:
                await self._bus.publish(
                    BacktestPaused(backtest_id=backtest_id, step=step_no)
                )
                await self._bus.publish(
                    BacktestResumed(backtest_id=backtest_id, step=step_no)
                )

            filled = await self._step(context, idx, candle)
            fill: SimulatedFill | None = None
            if filled is not None:
                execution_result, fill = filled
                fills += 1
                total_commission += fill.commission
                portfolio_result = await self._book(
                    context, execution_result, fill, portfolio_result
                )
                position_result = await self._position(
                    context, portfolio_result, candle, position_result
                )
                trade_result = await self._trade(position_result, trade_result)
                trades = _upsert_trade(trades, trade_result)

            equity = _equity(portfolio_result, params.initial_cash)
            prev = equity_curve[-1]
            equity_curve.append(equity)
            returns.append((equity - prev) / prev if prev > _ZERO else _ZERO)
            history = self._history.append(
                history,
                SimulationStep(
                    index=idx,
                    timestamp=candle.close_time,
                    close=candle.close,
                    equity=equity,
                    fill=fill,
                ),
            )
            await self._bus.publish(
                SimulationStepCompleted(backtest_id=backtest_id, step=step_no)
            )
            await self._bus.publish(
                BacktestProgress(backtest_id=backtest_id, step=step_no, total=total)
            )

        performance_result = await self._analyze(
            context, portfolio_result, position_result, trade_result, trades,
            equity_curve, returns,
        )
        metrics = self._metrics.calculate(
            performance_result, trades, equity_curve, total_commission
        )

        state = SimulationState.CANCELLED if cancelled else SimulationState.COMPLETED
        backtest = Backtest(
            id=backtest_id,
            exchange=context.exchange,
            symbol=context.symbol,
            state=state,
            step_count=step_no,
            started_at=started,
            completed_at=datetime.now(UTC),
        )
        summary = BacktestSummary(
            total_steps=step_no,
            total_fills=fills,
            total_trades=len(trades),
            total_commission=total_commission,
            initial_equity=params.initial_cash,
            final_equity=equity_curve[-1],
            net_profit=equity_curve[-1] - params.initial_cash,
        )
        snapshot = BacktestSnapshot(
            backtest=backtest,
            metrics=metrics,
            summary=summary,
            timestamp=datetime.now(UTC),
        )
        with self._lock:
            self._registry.register(snapshot)

        await self._bus.publish(BacktestMetricsUpdated(backtest_id=backtest_id))
        await self._bus.publish(BacktestSnapshotCreated(backtest_id=backtest_id))
        if cancelled:
            await self._bus.publish(
                BacktestCancelled(backtest_id=backtest_id, step=step_no)
            )
            status = BacktestResultStatus.CANCELLED
        else:
            await self._bus.publish(BacktestCompleted(backtest_id=backtest_id))
            status = BacktestResultStatus.COMPLETED
        self._info(backtest_id, status.value)
        return BacktestResult(
            status=status,
            backtest=backtest,
            snapshot=snapshot,
            history=history,
            metrics=metrics,
        )

    async def _step(
        self, context: BacktestingContext, idx: int, candle: OHLCV
    ) -> tuple[ExecutionResult, SimulatedFill] | None:
        """Run Strategy → Risk → Order → Execution → Simulator for one candle."""
        strategy = context.strategy
        if strategy is None:
            return None
        recent = tuple(context.candles[max(0, idx - _WINDOW + 1) : idx + 1])
        strategy_ctx = StrategyContext(
            exchange=context.exchange,
            symbol=context.symbol,
            timeframe=context.timeframe,
            latest_candle=candle,
            recent_candles=recent,
        )
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
            fill = self._simulator.simulate(
                execution_result, candle, context.parameters
            )
            return execution_result, fill
        return None

    async def _book(
        self,
        context: BacktestingContext,
        execution_result: ExecutionResult,
        fill: SimulatedFill,
        previous: PortfolioResult | None,
    ) -> PortfolioResult | None:
        if self._portfolio_engine is None:
            return previous
        result = await self._portfolio_engine.process(
            PortfolioContext(
                portfolio_id=context.portfolio_id,
                execution_result=execution_result,
                prices={fill.symbol: fill.price},
                initial_cash=context.parameters.initial_cash,
            )
        )
        return result if result.succeeded else previous

    async def _position(
        self,
        context: BacktestingContext,
        portfolio_result: PortfolioResult | None,
        candle: OHLCV,
        previous: PositionResult | None,
    ) -> PositionResult | None:
        if self._position_engine is None or portfolio_result is None:
            return previous
        result = await self._position_engine.process(
            PositionContext(
                portfolio_result=portfolio_result,
                prices={context.symbol: candle.close},
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
        context: BacktestingContext,
        portfolio_result: PortfolioResult | None,
        position_result: PositionResult | None,
        trade_result: TradeResult | None,
        trades: list[Trade],
        equity_curve: list[Decimal],
        returns: list[Decimal],
    ) -> PerformanceResult | None:
        if self._performance_engine is None:
            return context.performance_result
        return await self._performance_engine.analyze(
            PerformanceContext(
                portfolio_result=portfolio_result,
                position_result=position_result,
                trade_result=trade_result,
                trades=tuple(trades),
                equity_curve=tuple(equity_curve),
                returns=tuple(returns),
                correlation_id=context.correlation_id,
            )
        )

    async def _fail(self, backtest_id: str, message: str) -> BacktestResult:
        self._error(backtest_id, message)
        await self._bus.publish(
            BacktestErrorOccurred(backtest_id=backtest_id, message=message)
        )
        return BacktestResult(
            status=BacktestResultStatus.FAILED, errors=(message,)
        )

    def _info(self, backtest_id: str, status: str) -> None:
        if self._log is not None:
            self._log.info(
                "Backtest finished",
                extra={"backtest_id": backtest_id, "status": status},
            )

    def _error(self, backtest_id: str, message: str) -> None:
        if self._log is not None:
            self._log.error(
                "Backtest error",
                extra={"backtest_id": backtest_id, "error": message},
            )


def _equity(portfolio_result: PortfolioResult | None, fallback: Decimal) -> Decimal:
    if portfolio_result is None or portfolio_result.snapshot is None:
        return fallback
    return portfolio_result.snapshot.value.total_value


def _upsert_trade(trades: list[Trade], result: TradeResult | None) -> list[Trade]:
    """Replace the trade with the same id (or append), keeping latest state."""
    if result is None or result.trade is None:
        return trades
    trade = result.trade
    updated = [t for t in trades if t.id != trade.id]
    updated.append(trade)
    return updated
