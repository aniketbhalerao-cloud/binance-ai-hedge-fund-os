"""Portfolio Framework exceptions.

Definitions only. Internal failures are translated into these so no
implementation detail escapes; the framework always returns a
:class:`~portfolio.models.PortfolioResult`.
"""

from __future__ import annotations

__all__ = [
    "PortfolioError",
    "PortfolioNotFoundError",
    "PortfolioClosedError",
    "InvalidPortfolioStateError",
    "HoldingsError",
    "CashError",
    "ValuationError",
    "AccountingError",
    "AllocationError",
    "PerformanceError",
]


class PortfolioError(Exception):
    """Base class for all Portfolio Framework errors."""


class PortfolioNotFoundError(PortfolioError):
    """Raised when a portfolio id is not registered."""


class PortfolioClosedError(PortfolioError):
    """Raised when updating a closed portfolio."""


class InvalidPortfolioStateError(PortfolioError):
    """Raised on an illegal portfolio state transition."""


class HoldingsError(PortfolioError):
    """Raised when a holdings update fails."""


class CashError(PortfolioError):
    """Raised when a cash update fails."""


class ValuationError(PortfolioError):
    """Raised when valuation fails."""


class AccountingError(PortfolioError):
    """Raised when accounting fails."""


class AllocationError(PortfolioError):
    """Raised when allocation calculation fails."""


class PerformanceError(PortfolioError):
    """Raised when performance calculation fails."""
