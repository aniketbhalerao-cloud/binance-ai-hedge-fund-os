"""Portfolio performance.

:class:`DefaultPortfolioPerformance` derives return metrics from valuation
outputs (not holdings directly). Stateless — it takes the current value and the
previous value and returns a :class:`PortfolioPerformance`.
"""

from __future__ import annotations

from decimal import Decimal

from portfolio.models import PortfolioPerformance, PortfolioValue

__all__ = ["DefaultPortfolioPerformance"]

_ZERO = Decimal("0")


class DefaultPortfolioPerformance:
    """Stateless performance derived from valuation outputs."""

    def measure(
        self, value: PortfolioValue, previous: PortfolioValue | None
    ) -> PortfolioPerformance:
        """Return performance metrics from current and previous valuations."""
        # ROI and total return are relative to invested cost basis.
        roi = (
            (value.unrealized_pnl + value.realized_pnl) / value.cost_basis
            if value.cost_basis > 0
            else _ZERO
        )
        total_return = roi

        # Daily/cumulative return compare against the previous total value.
        if previous is not None and previous.total_value > 0:
            daily = (value.total_value - previous.total_value) / previous.total_value
        else:
            daily = _ZERO

        return PortfolioPerformance(
            daily_return=daily,
            total_return=total_return,
            roi=roi,
            cumulative_return=roi,
        )
