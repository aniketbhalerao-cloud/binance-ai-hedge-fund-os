"""Unit tests for the Trade Lifecycle Framework (stdlib unittest, deterministic)."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal

from core.container import ServiceContainer
from core.logging import LoggerFactory
from events.bus import EventBus
from models import OrderSide
from positions.models import PositionSide
from positions.state import PositionState
from tests.support.fakes import FakeLoggerFactory, FakeSubscriber
from tests.support.trade_fakes import FIXED_TIME, make_position, make_trade_context
from trades import (
    DefaultTradeAnalytics,
    DefaultTradeEngine,
    DefaultTradeHistory,
    DefaultTradeLifecycle,
    DefaultTradeManager,
    DefaultTradeMatcher,
    DefaultTradeTracker,
    InMemoryTradeRegistry,
    TradeClosed,
    TradeEngine,
    TradeError,
    TradeErrorOccurred,
    TradeEvent,
    TradeManager,
    TradeOpened,
    TradePartiallyFilled,
    TradeRegistry,
    TradeResult,
    TradeResultStatus,
    TradeState,
    register_trades,
)
from trades.exceptions import (
    InvalidTradeStateError,
    TradeClosedError,
    TradeNotFoundError,
    TradeTrackerError,
)
from trades.models import Trade, TradeFill, TradeHistory, TradeMatch
from trades.state import VALID_TRANSITIONS, can_transition

_ZERO = Decimal("0")


def _fill(
    side: OrderSide = OrderSide.BUY,
    qty: str = "1",
    price: str = "100",
    pnl: str = "0",
) -> TradeFill:
    """Build a deterministic BTCUSDT fill."""
    return TradeFill(
        "BTCUSDT", side, Decimal(qty), Decimal(price), Decimal(pnl), FIXED_TIME
    )


def _trade(
    state: TradeState = TradeState.OPEN,
    entry: str = "0",
    exit_: str = "0",
    pnl: str = "0",
    fill_count: int = 0,
) -> Trade:
    """Build a deterministic BTCUSDT trade with the given figures."""
    return Trade(
        id="pos-1",
        symbol="BTCUSDT",
        side=PositionSide.LONG,
        state=state,
        entry_quantity=Decimal(entry),
        exit_quantity=Decimal(exit_),
        realized_pnl=Decimal(pnl),
        fill_count=fill_count,
    )


def _manager(bus: EventBus | None = None) -> DefaultTradeManager:
    return DefaultTradeManager(
        bus or EventBus(),
        InMemoryTradeRegistry(),
        DefaultTradeTracker(),
        DefaultTradeMatcher(),
        DefaultTradeLifecycle(),
        DefaultTradeHistory(),
        DefaultTradeAnalytics(),
        logger=FakeLoggerFactory(),  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
class TradeStateTests(unittest.TestCase):
    def test_valid_transition(self) -> None:
        self.assertTrue(can_transition(TradeState.PENDING, TradeState.OPEN))
        self.assertTrue(can_transition(TradeState.OPEN, TradeState.CLOSED))

    def test_reentrant_self_loop(self) -> None:
        self.assertTrue(can_transition(TradeState.OPEN, TradeState.OPEN))
        self.assertFalse(can_transition(TradeState.PENDING, TradeState.PENDING))

    def test_terminal_states_have_no_exits(self) -> None:
        self.assertEqual(VALID_TRANSITIONS[TradeState.CLOSED], frozenset())
        self.assertEqual(VALID_TRANSITIONS[TradeState.CANCELLED], frozenset())
        self.assertFalse(can_transition(TradeState.CLOSED, TradeState.OPEN))


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class TradeModelTests(unittest.TestCase):
    def test_history_append_is_immutable(self) -> None:
        history = TradeHistory("t1")
        new = history.append(_fill())
        self.assertEqual(len(history.fills), 0)  # original untouched
        self.assertEqual(len(new.fills), 1)

    def test_trade_is_frozen(self) -> None:
        trade = _trade()
        with self.assertRaises(FrozenInstanceError):
            trade.state = TradeState.CLOSED  # type: ignore[misc]

    def test_result_succeeded_property(self) -> None:
        ok = TradeResult(status=TradeResultStatus.SUCCESS)
        bad = TradeResult(status=TradeResultStatus.FAILED, errors=("x",))
        self.assertTrue(ok.succeeded)
        self.assertFalse(bad.succeeded)


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------
class TradeTrackerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tracker = DefaultTradeTracker()

    def test_derive_entry_fill_from_new_trade(self) -> None:
        position = make_position(total_bought=Decimal("2"), total_sold=_ZERO)
        fill = self.tracker.derive_fill(None, position, FIXED_TIME)
        self.assertEqual(fill.side, OrderSide.BUY)
        self.assertEqual(fill.quantity, Decimal("2"))
        self.assertEqual(fill.price, position.average_entry)

    def test_derive_exit_fill_from_delta(self) -> None:
        previous = _trade(entry="2")
        position = make_position(
            total_bought=Decimal("2"),
            total_sold=Decimal("1"),
            average_exit=Decimal("110"),
            realized_pnl=Decimal("10"),
        )
        fill = self.tracker.derive_fill(previous, position, FIXED_TIME)
        self.assertEqual(fill.side, OrderSide.SELL)
        self.assertEqual(fill.quantity, Decimal("1"))
        self.assertEqual(fill.price, Decimal("110"))
        self.assertEqual(fill.realized_pnl, Decimal("10"))

    def test_no_delta_raises(self) -> None:
        previous = _trade(entry="1")
        position = make_position(total_bought=Decimal("1"), total_sold=_ZERO)
        with self.assertRaises(TradeTrackerError):
            self.tracker.derive_fill(previous, position, FIXED_TIME)

    def test_build_sets_close_timestamp(self) -> None:
        position = make_position(total_bought=Decimal("1"), total_sold=Decimal("1"))
        trade = self.tracker.build(
            "pos-1", None, position, TradeState.CLOSED, FIXED_TIME, FIXED_TIME
        )
        self.assertEqual(trade.state, TradeState.CLOSED)
        self.assertEqual(trade.closed_at, FIXED_TIME)
        self.assertEqual(trade.fill_count, 1)


# ---------------------------------------------------------------------------
# Matcher
# ---------------------------------------------------------------------------
class TradeMatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.matcher = DefaultTradeMatcher()

    def test_entry_only_not_completed(self) -> None:
        position = make_position(total_bought=Decimal("2"), total_sold=_ZERO)
        match = self.matcher.match(position, _fill(qty="2"))
        self.assertTrue(match.is_entry)
        self.assertFalse(match.is_exit)
        self.assertEqual(match.matched_quantity, _ZERO)
        self.assertFalse(match.completed)

    def test_full_exit_completed(self) -> None:
        position = make_position(total_bought=Decimal("2"), total_sold=Decimal("2"))
        match = self.matcher.match(position, _fill(side=OrderSide.SELL, qty="2"))
        self.assertTrue(match.is_exit)
        self.assertEqual(match.matched_quantity, Decimal("2"))
        self.assertTrue(match.completed)

    def test_partial_exit_matched_min(self) -> None:
        position = make_position(total_bought=Decimal("2"), total_sold=Decimal("1"))
        match = self.matcher.match(position, _fill(side=OrderSide.SELL))
        self.assertEqual(match.matched_quantity, Decimal("1"))
        self.assertFalse(match.completed)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
class TradeLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lifecycle = DefaultTradeLifecycle()

    def _match(self, entry: str, exit_: str, completed: bool) -> TradeMatch:
        return TradeMatch(
            entry_quantity=Decimal(entry),
            exit_quantity=Decimal(exit_),
            matched_quantity=min(Decimal(entry), Decimal(exit_)),
            is_entry=True,
            is_exit=Decimal(exit_) > 0,
            completed=completed,
        )

    def test_open_when_entry_only(self) -> None:
        state = self.lifecycle.derive_state(self._match("1", "0", False), False)
        self.assertEqual(state, TradeState.OPEN)

    def test_partial_when_some_exit(self) -> None:
        state = self.lifecycle.derive_state(self._match("2", "1", False), False)
        self.assertEqual(state, TradeState.PARTIALLY_FILLED)

    def test_filled_when_completed_not_closed(self) -> None:
        state = self.lifecycle.derive_state(self._match("2", "2", True), False)
        self.assertEqual(state, TradeState.FILLED)

    def test_closed_when_position_closed(self) -> None:
        state = self.lifecycle.derive_state(self._match("2", "2", True), True)
        self.assertEqual(state, TradeState.CLOSED)

    def test_validate_rejects_illegal(self) -> None:
        with self.assertRaises(InvalidTradeStateError):
            self.lifecycle.validate(TradeState.CLOSED, TradeState.OPEN)


# ---------------------------------------------------------------------------
# History & Analytics
# ---------------------------------------------------------------------------
class TradeHistoryAnalyticsTests(unittest.TestCase):
    def test_history_service_appends(self) -> None:
        service = DefaultTradeHistory()
        fill = _fill()
        history = service.append(TradeHistory("t1"), fill)
        self.assertEqual(history.fills, (fill,))

    def test_analytics_marks_win_and_profit(self) -> None:
        analytics = DefaultTradeAnalytics()
        trade = _trade(
            state=TradeState.CLOSED, entry="1", exit_="1", pnl="10", fill_count=2
        )
        history = TradeHistory(
            "t1",
            (
                _fill(),
                _fill(side=OrderSide.SELL, price="110", pnl="10"),
            ),
        )
        result = analytics.compute(trade, history)
        self.assertEqual(result.gross_profit, Decimal("10"))
        self.assertEqual(result.net_profit, Decimal("10"))
        self.assertTrue(result.won)
        self.assertEqual(result.fill_count, 2)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
class TradeRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = InMemoryTradeRegistry()
        self.trade = _trade()

    def test_register_and_get(self) -> None:
        self.registry.register(self.trade, TradeHistory("pos-1"))
        self.assertTrue(self.registry.exists("pos-1"))
        self.assertEqual(self.registry.get("pos-1"), self.trade)
        self.assertEqual(self.registry.list(), [self.trade])

    def test_get_missing_raises(self) -> None:
        with self.assertRaises(TradeNotFoundError):
            self.registry.get("nope")

    def test_history_defaults_empty(self) -> None:
        self.assertEqual(self.registry.history("pos-1").fills, ())

    def test_remove(self) -> None:
        self.registry.register(self.trade, TradeHistory("pos-1"))
        self.registry.remove("pos-1")
        self.assertFalse(self.registry.exists("pos-1"))


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------
class TradeManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_open_trade_publishes_opened(self) -> None:
        bus = EventBus()
        sub = FakeSubscriber()
        bus.subscribe(TradeEvent, sub.handle)
        manager = _manager(bus)

        result = await manager.update(make_trade_context())

        self.assertEqual(result.status, TradeResultStatus.SUCCESS)
        assert result.trade is not None
        self.assertEqual(result.trade.state, TradeState.OPEN)
        self.assertTrue(any(isinstance(e, TradeOpened) for e in sub.received))

    async def test_full_lifecycle_closes(self) -> None:
        bus = EventBus()
        sub = FakeSubscriber()
        bus.subscribe(TradeClosed, sub.handle)
        manager = _manager(bus)

        await manager.update(make_trade_context())  # open (buy 1)
        result = await manager.update(
            make_trade_context(
                position=make_position(
                    state=PositionState.CLOSED,
                    quantity=_ZERO,
                    total_bought=Decimal("1"),
                    total_sold=Decimal("1"),
                    average_exit=Decimal("110"),
                    realized_pnl=Decimal("10"),
                    closed_at=FIXED_TIME,
                )
            )
        )
        self.assertEqual(result.status, TradeResultStatus.SUCCESS)
        assert result.trade is not None
        self.assertEqual(result.trade.state, TradeState.CLOSED)
        self.assertEqual(result.trade.realized_pnl, Decimal("10"))
        self.assertEqual(len(sub.received), 1)

    async def test_partial_fill_publishes(self) -> None:
        bus = EventBus()
        sub = FakeSubscriber()
        bus.subscribe(TradePartiallyFilled, sub.handle)
        manager = _manager(bus)

        await manager.update(
            make_trade_context(position=make_position(total_bought=Decimal("2")))
        )
        result = await manager.update(
            make_trade_context(
                position=make_position(
                    state=PositionState.PARTIALLY_CLOSED,
                    quantity=Decimal("1"),
                    total_bought=Decimal("2"),
                    total_sold=Decimal("1"),
                    average_exit=Decimal("110"),
                    realized_pnl=Decimal("5"),
                )
            )
        )
        assert result.trade is not None
        self.assertEqual(result.trade.state, TradeState.PARTIALLY_FILLED)
        self.assertEqual(len(sub.received), 1)

    async def test_no_completed_position_returns_failed(self) -> None:
        bus = EventBus()
        errors = FakeSubscriber()
        bus.subscribe(TradeErrorOccurred, errors.handle)
        manager = _manager(bus)

        result = await manager.update(make_trade_context(succeeded=False))

        self.assertEqual(result.status, TradeResultStatus.FAILED)
        self.assertTrue(result.errors)
        self.assertEqual(len(errors.received), 1)

    async def test_updating_closed_trade_fails(self) -> None:
        manager = _manager()
        await manager.update(make_trade_context())
        await manager.update(
            make_trade_context(
                position=make_position(
                    state=PositionState.CLOSED,
                    quantity=_ZERO,
                    total_bought=Decimal("1"),
                    total_sold=Decimal("1"),
                    average_exit=Decimal("110"),
                    realized_pnl=Decimal("10"),
                )
            )
        )
        # A third update on a closed trade must be rejected.
        result = await manager.update(
            make_trade_context(
                position=make_position(
                    state=PositionState.CLOSED,
                    quantity=_ZERO,
                    total_bought=Decimal("2"),
                    total_sold=Decimal("2"),
                )
            )
        )
        self.assertEqual(result.status, TradeResultStatus.FAILED)

    async def test_no_delta_returns_failed(self) -> None:
        manager = _manager()
        await manager.update(make_trade_context())
        # Same position again → no fill delta → TradeTrackerError → FAILED.
        result = await manager.update(make_trade_context())
        self.assertEqual(result.status, TradeResultStatus.FAILED)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class TradeEngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_engine_delegates_to_manager(self) -> None:
        engine = DefaultTradeEngine(
            _manager(), logger=FakeLoggerFactory()  # type: ignore[arg-type]
        )
        await engine.start()
        result = await engine.process(make_trade_context())
        await engine.stop()
        self.assertEqual(result.status, TradeResultStatus.SUCCESS)


# ---------------------------------------------------------------------------
# Dependency Injection
# ---------------------------------------------------------------------------
class TradeRegistrationTests(unittest.TestCase):
    def test_registers_and_binds_abstractions(self) -> None:
        container = ServiceContainer()
        container.register_instance(LoggerFactory, FakeLoggerFactory())  # type: ignore[arg-type]
        register_trades(container)

        self.assertTrue(container.has(EventBus))
        self.assertIsInstance(container.resolve(TradeEngine), DefaultTradeEngine)
        self.assertIsInstance(container.resolve(TradeManager), DefaultTradeManager)
        self.assertIsInstance(container.resolve(TradeRegistry), InMemoryTradeRegistry)

    def test_engine_and_manager_are_singletons(self) -> None:
        container = ServiceContainer()
        register_trades(container)
        self.assertIs(
            container.resolve(DefaultTradeEngine),
            container.resolve(DefaultTradeEngine),
        )
        self.assertIs(
            container.resolve(TradeManager),
            container.resolve(DefaultTradeManager),
        )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class TradeExceptionTests(unittest.TestCase):
    def test_hierarchy(self) -> None:
        subclasses = (
            TradeClosedError,
            InvalidTradeStateError,
            TradeTrackerError,
            TradeNotFoundError,
        )
        for exc in subclasses:
            self.assertTrue(issubclass(exc, TradeError))


if __name__ == "__main__":
    unittest.main()
