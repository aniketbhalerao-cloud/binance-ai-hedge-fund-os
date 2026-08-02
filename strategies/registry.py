"""Strategy registry.

:class:`InMemoryStrategyRegistry` maintains the set of available strategies and
their enabled/disabled state. It is thread-safe and its **only** responsibility
is registration and lookup — it never executes strategies, generates signals,
publishes events, or performs calculations.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

from strategies.exceptions import (
    DuplicateStrategyError,
    InvalidStrategyError,
    StrategyRegistrationError,
)
from strategies.interfaces import Strategy

__all__ = ["InMemoryStrategyRegistry"]


@dataclass(slots=True)
class _Entry:
    strategy: Strategy
    enabled: bool = False


class InMemoryStrategyRegistry:
    """A thread-safe, in-memory registry implementing ``StrategyRegistry``."""

    def __init__(self) -> None:
        self._entries: dict[str, _Entry] = {}
        self._lock = Lock()

    def register(self, strategy: Strategy) -> None:
        """Register ``strategy`` (disabled by default).

        Raises:
            DuplicateStrategyError: If a strategy with the same name exists.
        """
        name = strategy.name
        with self._lock:
            if name in self._entries:
                raise DuplicateStrategyError(f"Strategy {name!r} already registered.")
            self._entries[name] = _Entry(strategy=strategy)

    def unregister(self, name: str) -> None:
        """Remove the strategy named ``name``.

        Raises:
            StrategyRegistrationError: If ``name`` is not registered.
        """
        with self._lock:
            if name not in self._entries:
                raise StrategyRegistrationError(f"Strategy {name!r} is not registered.")
            del self._entries[name]

    def enable(self, name: str) -> None:
        """Enable the strategy named ``name``."""
        self._set_enabled(name, True)

    def disable(self, name: str) -> None:
        """Disable the strategy named ``name``."""
        self._set_enabled(name, False)

    def exists(self, name: str) -> bool:
        """Return ``True`` if a strategy named ``name`` is registered."""
        with self._lock:
            return name in self._entries

    def get(self, name: str) -> Strategy:
        """Return the strategy named ``name``.

        Raises:
            InvalidStrategyError: If ``name`` is not registered.
        """
        with self._lock:
            entry = self._entries.get(name)
        if entry is None:
            raise InvalidStrategyError(f"Strategy {name!r} is not registered.")
        return entry.strategy

    def list(self) -> list[Strategy]:
        """Return all registered strategies."""
        with self._lock:
            return [entry.strategy for entry in self._entries.values()]

    def list_enabled(self) -> list[Strategy]:
        """Return a snapshot of the currently enabled strategies."""
        with self._lock:
            return [e.strategy for e in self._entries.values() if e.enabled]

    def _set_enabled(self, name: str, enabled: bool) -> None:
        with self._lock:
            entry = self._entries.get(name)
            if entry is None:
                raise InvalidStrategyError(f"Strategy {name!r} is not registered.")
            entry.enabled = enabled
