"""Strategy Framework events.

Each inherits the existing :class:`events.base.Event` and is immutable. The
framework publishes **only** these — never orders, trades, portfolio updates,
risk decisions, or execution events.
"""

from __future__ import annotations

from dataclasses import dataclass

from events.base import Event
from strategies.signals import TradingSignal

__all__ = [
    "StrategyEvent",
    "StrategyRegistered",
    "StrategyEnabled",
    "StrategyDisabled",
    "StrategyStarted",
    "StrategyStopped",
    "SignalGenerated",
    "StrategyErrorOccurred",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class StrategyEvent(Event):
    """Base class for all strategy events."""


@dataclass(frozen=True, slots=True, kw_only=True)
class StrategyRegistered(StrategyEvent):
    """A strategy was registered."""

    name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class StrategyEnabled(StrategyEvent):
    """A strategy was enabled."""

    name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class StrategyDisabled(StrategyEvent):
    """A strategy was disabled."""

    name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class StrategyStarted(StrategyEvent):
    """A strategy was started."""

    name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class StrategyStopped(StrategyEvent):
    """A strategy was stopped."""

    name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SignalGenerated(StrategyEvent):
    """A strategy generated a trading signal."""

    signal: TradingSignal


@dataclass(frozen=True, slots=True, kw_only=True)
class StrategyErrorOccurred(StrategyEvent):
    """A strategy raised an error during execution.

    Named ``StrategyErrorOccurred`` to avoid clashing with the
    :class:`~strategies.exceptions.StrategyError` exception.
    """

    name: str
    message: str
