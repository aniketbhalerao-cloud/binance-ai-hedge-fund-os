"""Trade lifecycle states.

Pure data: the finite trade states plus the legal transition table. No tracking,
matching, or analytics logic here — those live in the dedicated components. A
trade advances through these states as fills arrive and entries are matched
against exits.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["TradeState", "can_transition", "VALID_TRANSITIONS"]


class TradeState(str, Enum):
    """Lifecycle state of a trade."""

    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CLOSED = "closed"
    CANCELLED = "cancelled"


#: Allowed transitions. ``OPEN`` / ``PARTIALLY_FILLED`` / ``FILLED`` may re-enter
#: themselves as more fills arrive for the same trade.
VALID_TRANSITIONS: dict[TradeState, frozenset[TradeState]] = {
    TradeState.PENDING: frozenset({TradeState.OPEN, TradeState.CANCELLED}),
    TradeState.OPEN: frozenset(
        {
            TradeState.OPEN,
            TradeState.PARTIALLY_FILLED,
            TradeState.FILLED,
            TradeState.CLOSED,
            TradeState.CANCELLED,
        }
    ),
    TradeState.PARTIALLY_FILLED: frozenset(
        {
            TradeState.PARTIALLY_FILLED,
            TradeState.FILLED,
            TradeState.CLOSED,
        }
    ),
    TradeState.FILLED: frozenset({TradeState.FILLED, TradeState.CLOSED}),
    TradeState.CLOSED: frozenset(),
    TradeState.CANCELLED: frozenset(),
}

#: The states in which a trade re-entering itself (another fill) is legal.
_REENTRANT: frozenset[TradeState] = frozenset(
    {TradeState.OPEN, TradeState.PARTIALLY_FILLED, TradeState.FILLED}
)


def can_transition(source: TradeState, target: TradeState) -> bool:
    """Return ``True`` if moving from ``source`` to ``target`` is permitted."""
    if source == target and target in _REENTRANT:
        return True
    return target in VALID_TRANSITIONS.get(source, frozenset())
