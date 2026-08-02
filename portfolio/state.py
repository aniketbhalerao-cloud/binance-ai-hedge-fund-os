"""Portfolio lifecycle states.

Pure data: the finite portfolio states plus the legal transition table. No
accounting or valuation logic here.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["PortfolioState", "can_transition", "VALID_TRANSITIONS"]


class PortfolioState(str, Enum):
    """Lifecycle state of a portfolio."""

    EMPTY = "empty"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


#: Allowed transitions (``ACTIVE`` may stay active on each update).
VALID_TRANSITIONS: dict[PortfolioState, frozenset[PortfolioState]] = {
    PortfolioState.EMPTY: frozenset(
        {PortfolioState.ACTIVE, PortfolioState.SUSPENDED, PortfolioState.CLOSED}
    ),
    PortfolioState.ACTIVE: frozenset(
        {PortfolioState.ACTIVE, PortfolioState.SUSPENDED, PortfolioState.CLOSED}
    ),
    PortfolioState.SUSPENDED: frozenset(
        {PortfolioState.ACTIVE, PortfolioState.CLOSED}
    ),
    PortfolioState.CLOSED: frozenset(),
}


def can_transition(source: PortfolioState, target: PortfolioState) -> bool:
    """Return ``True`` if moving from ``source`` to ``target`` is permitted."""
    return target in VALID_TRANSITIONS.get(source, frozenset())
