"""Strategy manager.

:class:`StrategyExecutionManager` coordinates strategy execution. It receives a
:class:`~strategies.context.StrategyContext`, retrieves the enabled strategies
from the registry, executes each, collects their signals, publishes
``SignalGenerated`` events, and returns the signals. It **coordinates only** —
it never calculates indicators, decides BUY/SELL, manages risk, or executes
orders; that logic lives inside individual strategies.

It also provides a thin registration façade (register/enable/disable/start/stop)
that delegates state to the registry and publishes the corresponding framework
events (the registry itself never publishes).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.bus import EventBus
from strategies.context import StrategyContext
from strategies.events import (
    SignalGenerated,
    StrategyDisabled,
    StrategyEnabled,
    StrategyErrorOccurred,
    StrategyRegistered,
    StrategyStarted,
    StrategyStopped,
)
from strategies.factory import DefaultStrategyFactory
from strategies.interfaces import Strategy, StrategyRegistry
from strategies.signals import TradingSignal

if TYPE_CHECKING:
    from market_data.interfaces import MarketDataService
    from trading.engine import TradingEngine

__all__ = ["StrategyExecutionManager"]


class StrategyExecutionManager:
    """Coordinates execution of the registered, enabled strategies.

    Args:
        bus: The event bus used to publish framework/signal events.
        registry: The strategy registry (abstraction).
        factory: The strategy factory (abstraction).
        logger: Optional logger factory for framework logs.
        engine: Optional Trading Engine reference (held, not driven directly).
        market_data: Optional Market Data Service reference (held; strategies
            receive data via the injected context, never by reading it here).
    """

    def __init__(
        self,
        bus: EventBus,
        registry: StrategyRegistry,
        factory: DefaultStrategyFactory,
        logger: LoggerFactory | None = None,
        engine: TradingEngine | None = None,
        market_data: MarketDataService | None = None,
    ) -> None:
        self._bus = bus
        self._registry = registry
        self._factory = factory
        self._engine = engine
        self._market_data = market_data
        self._log = logger.get_logger("strategies.manager") if logger else None

    # -- registration façade (delegates to registry, publishes events) ------

    async def register(self, strategy: Strategy) -> None:
        """Register ``strategy`` and publish ``StrategyRegistered``."""
        self._registry.register(strategy)
        self._info("Strategy registered", strategy.name)
        await self._bus.publish(StrategyRegistered(name=strategy.name))

    async def create_and_register(self, strategy_cls: type[Strategy]) -> Strategy:
        """Build ``strategy_cls`` via the factory, register it, and return it."""
        strategy = self._factory.create(strategy_cls)
        await self.register(strategy)
        return strategy

    async def enable(self, name: str) -> None:
        """Enable a strategy and publish ``StrategyEnabled``."""
        self._registry.enable(name)
        self._info("Strategy enabled", name)
        await self._bus.publish(StrategyEnabled(name=name))

    async def disable(self, name: str) -> None:
        """Disable a strategy and publish ``StrategyDisabled``."""
        self._registry.disable(name)
        self._info("Strategy disabled", name)
        await self._bus.publish(StrategyDisabled(name=name))

    async def start(self) -> None:
        """Start all enabled strategies, publishing ``StrategyStarted`` each."""
        for strategy in self._registry.list_enabled():
            await strategy.on_start()
            self._info("Strategy started", strategy.name)
            await self._bus.publish(StrategyStarted(name=strategy.name))

    async def stop(self) -> None:
        """Stop all enabled strategies, publishing ``StrategyStopped`` each."""
        for strategy in self._registry.list_enabled():
            await strategy.on_stop()
            self._info("Strategy stopped", strategy.name)
            await self._bus.publish(StrategyStopped(name=strategy.name))

    # -- execution ----------------------------------------------------------

    async def execute(self, context: StrategyContext) -> list[TradingSignal]:
        """Run every enabled strategy over ``context`` and return their signals.

        Each strategy is isolated: a failing one is logged, published as a
        ``StrategyErrorOccurred`` event, and skipped — it never stops the others.
        """
        signals: list[TradingSignal] = []
        for strategy in self._registry.list_enabled():
            try:
                produced = await strategy.evaluate(context)
            except Exception as exc:  # isolate per-strategy failures
                self._error(strategy.name, str(exc))
                await self._bus.publish(
                    StrategyErrorOccurred(name=strategy.name, message=str(exc))
                )
                continue
            for signal in produced:
                signals.append(signal)
                await self._bus.publish(SignalGenerated(signal=signal))
                self._info("Signal generated", signal.strategy_name)
        return signals

    # -- logging ------------------------------------------------------------

    def _info(self, message: str, name: str) -> None:
        if self._log is not None:
            self._log.info(message, extra={"strategy": name})

    def _error(self, name: str, message: str) -> None:
        if self._log is not None:
            self._log.error("Strategy failure", extra={"strategy": name, "error": message})
