"""Portfolio Framework events.

Each inherits the existing :class:`events.base.Event` and is immutable. The
framework publishes **only** these — never strategy, risk, order, execution, or
exchange events.
"""

from __future__ import annotations

from dataclasses import dataclass

from events.base import Event

__all__ = [
    "PortfolioEvent",
    "PortfolioCreated",
    "PortfolioUpdated",
    "HoldingsUpdated",
    "CashUpdated",
    "PortfolioValuationCompleted",
    "AllocationUpdated",
    "PerformanceUpdated",
    "PortfolioSnapshotCreated",
    "PortfolioClosed",
    "PortfolioErrorOccurred",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class PortfolioEvent(Event):
    """Base class for all portfolio events."""


@dataclass(frozen=True, slots=True, kw_only=True)
class PortfolioCreated(PortfolioEvent):
    """A portfolio was created."""

    portfolio_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PortfolioUpdated(PortfolioEvent):
    """A portfolio was updated after an execution."""

    portfolio_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class HoldingsUpdated(PortfolioEvent):
    """Holdings changed."""

    portfolio_id: str
    symbol: str


@dataclass(frozen=True, slots=True, kw_only=True)
class CashUpdated(PortfolioEvent):
    """Cash balance changed."""

    portfolio_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PortfolioValuationCompleted(PortfolioEvent):
    """Valuation completed."""

    portfolio_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class AllocationUpdated(PortfolioEvent):
    """Allocation recalculated."""

    portfolio_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PerformanceUpdated(PortfolioEvent):
    """Performance recalculated."""

    portfolio_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PortfolioSnapshotCreated(PortfolioEvent):
    """A portfolio snapshot was produced."""

    portfolio_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PortfolioClosed(PortfolioEvent):
    """A portfolio was closed."""

    portfolio_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PortfolioErrorOccurred(PortfolioEvent):
    """An error occurred during a portfolio update."""

    portfolio_id: str
    message: str
