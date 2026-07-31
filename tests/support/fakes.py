"""Standard-library fakes (test doubles) for the project's collaborators.

These are deliberately lightweight and independent of the production
implementations:

* the fake repositories store entities in a dict *and* record every call, so a
  test can assert both resulting state and interaction (spy behaviour);
* :class:`FakeSubscriber` records the events it receives;
* :class:`FakeLoggerFactory` / :class:`FakeLogger` capture log calls in memory,
  so logging can be asserted without configuring real handlers.

None of them perform I/O, so tests stay deterministic and never touch real
exchanges, APIs, or databases.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Generic, TypeVar

from database.interfaces import (
    OrderRepository,
    PositionRepository,
    Repository,
    TradeRepository,
)
from events.base import Event
from events.subscriber import Subscriber
from models import Order, Position, Trade

T = TypeVar("T")

__all__ = [
    "FakeOrderRepository",
    "FakeTradeRepository",
    "FakePositionRepository",
    "FakeSubscriber",
    "FakeLogger",
    "FakeLoggerFactory",
]


# ---------------------------------------------------------------------------
# Fake repositories
# ---------------------------------------------------------------------------


class _RecordingRepository(Repository[T], Generic[T]):
    """Dict-backed repository that records every operation for assertions."""

    def __init__(self, identity: Callable[[T], str]) -> None:
        self._items: dict[str, T] = {}
        self._identity = identity
        #: Ordered log of ``(operation, argument)`` pairs.
        self.calls: list[tuple[str, Any]] = []

    def add(self, entity: T) -> None:
        self.calls.append(("add", entity))
        self._items[self._identity(entity)] = entity

    def get(self, key: str) -> T | None:
        self.calls.append(("get", key))
        return self._items.get(key)

    def list(self) -> list[T]:
        self.calls.append(("list", None))
        return list(self._items.values())

    def remove(self, key: str) -> bool:
        self.calls.append(("remove", key))
        return self._items.pop(key, None) is not None

    def clear(self) -> None:
        self.calls.append(("clear", None))
        self._items.clear()

    def operations(self) -> list[str]:
        """Return just the operation names that were invoked, in order."""
        return [name for name, _ in self.calls]


class FakeOrderRepository(_RecordingRepository[Order], OrderRepository):
    """In-memory, call-recording :class:`OrderRepository` (keyed by order id)."""

    def __init__(self) -> None:
        super().__init__(lambda order: order.id)

    def list_by_symbol(self, symbol: str) -> list[Order]:
        self.calls.append(("list_by_symbol", symbol))
        return [order for order in self._items.values() if order.symbol == symbol]


class FakeTradeRepository(_RecordingRepository[Trade], TradeRepository):
    """In-memory, call-recording :class:`TradeRepository` (keyed by trade id)."""

    def __init__(self) -> None:
        super().__init__(lambda trade: trade.id)

    def list_by_symbol(self, symbol: str) -> list[Trade]:
        self.calls.append(("list_by_symbol", symbol))
        return [trade for trade in self._items.values() if trade.symbol == symbol]


class FakePositionRepository(_RecordingRepository[Position], PositionRepository):
    """In-memory, call-recording :class:`PositionRepository` (keyed by symbol)."""

    def __init__(self) -> None:
        super().__init__(lambda position: position.symbol)


# ---------------------------------------------------------------------------
# Fake event subscriber
# ---------------------------------------------------------------------------


class FakeSubscriber(Subscriber):
    """An event subscriber that records every event it receives."""

    def __init__(self) -> None:
        self.received: list[Event] = []

    async def handle(self, event: Event) -> None:
        self.received.append(event)


# ---------------------------------------------------------------------------
# Fake logger
# ---------------------------------------------------------------------------


class FakeLogger:
    """Captures log calls as ``(level, message, extra)`` tuples in memory."""

    def __init__(self) -> None:
        self.records: list[tuple[str, str, dict[str, Any]]] = []

    def _record(self, level: str, message: str, extra: dict[str, Any] | None) -> None:
        self.records.append((level, message, dict(extra or {})))

    def debug(self, message: str, *args: Any, extra: dict[str, Any] | None = None,
              **kwargs: Any) -> None:
        self._record("DEBUG", message, extra)

    def info(self, message: str, *args: Any, extra: dict[str, Any] | None = None,
             **kwargs: Any) -> None:
        self._record("INFO", message, extra)

    def warning(self, message: str, *args: Any, extra: dict[str, Any] | None = None,
                **kwargs: Any) -> None:
        self._record("WARNING", message, extra)

    def error(self, message: str, *args: Any, extra: dict[str, Any] | None = None,
              **kwargs: Any) -> None:
        self._record("ERROR", message, extra)

    def critical(self, message: str, *args: Any, extra: dict[str, Any] | None = None,
                 **kwargs: Any) -> None:
        self._record("CRITICAL", message, extra)

    def messages(self) -> list[str]:
        """Return just the logged messages, in order."""
        return [message for _, message, _ in self.records]


class FakeLoggerFactory:
    """Duck-typed stand-in for :class:`core.logging.LoggerFactory`.

    Hands out a single shared :class:`FakeLogger` and records the names it was
    asked for, so components that depend on a ``LoggerFactory`` can be tested
    without configuring real logging handlers.
    """

    def __init__(self) -> None:
        self.logger = FakeLogger()
        self.requested_names: list[str | None] = []

    def get_logger(self, name: str | None = None):
        self.requested_names.append(name)
        return self.logger

    @property
    def records(self) -> list[tuple[str, str, dict[str, Any]]]:
        """Convenience accessor for the shared logger's captured records."""
        return self.logger.records
