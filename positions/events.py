"""Position Framework events.

Each inherits the existing :class:`events.base.Event` and is immutable. The
framework publishes **only** these — never strategy, risk, order, execution,
exchange, or portfolio events.
"""

from __future__ import annotations

from dataclasses import dataclass

from events.base import Event

from positions.state import PositionState

__all__ = [
    "PositionEvent",
    "PositionOpened",
    "PositionUpdated",
    "PositionPartiallyClosed",
    "PositionClosed",
    "PositionHistoryUpdated",
    "PositionMetricsUpdated",
    "PositionSnapshotCreated",
    "PositionStateChanged",
    "PositionErrorOccurred",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class PositionEvent(Event):
    """Base class for all position events."""


@dataclass(frozen=True, slots=True, kw_only=True)
class PositionOpened(PositionEvent):
    """A position was opened."""

    position_id: str
    symbol: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PositionUpdated(PositionEvent):
    """A position was updated."""

    position_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PositionPartiallyClosed(PositionEvent):
    """A position was partially reduced."""

    position_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PositionClosed(PositionEvent):
    """A position was fully closed."""

    position_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PositionHistoryUpdated(PositionEvent):
    """A position's history was appended to."""

    position_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PositionMetricsUpdated(PositionEvent):
    """A position's metrics were recalculated."""

    position_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PositionSnapshotCreated(PositionEvent):
    """A position snapshot was produced."""

    position_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PositionStateChanged(PositionEvent):
    """A position's lifecycle state changed."""

    position_id: str
    previous: PositionState
    current: PositionState


@dataclass(frozen=True, slots=True, kw_only=True)
class PositionErrorOccurred(PositionEvent):
    """An error occurred during a position update."""

    position_id: str
    message: str
