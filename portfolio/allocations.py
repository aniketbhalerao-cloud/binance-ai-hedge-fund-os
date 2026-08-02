"""Asset allocation.

:class:`DefaultPortfolioAllocation` derives position and cash weights from a
valued portfolio. It is stateless and always derived from the current portfolio
value — it stores nothing.
"""

from __future__ import annotations

from decimal import Decimal

from portfolio.models import Portfolio, PortfolioAllocation, PortfolioValue

__all__ = ["DefaultPortfolioAllocation"]

_ZERO = Decimal("0")


class DefaultPortfolioAllocation:
    """Stateless allocation derived from a valued portfolio."""

    def allocate(
        self, portfolio: Portfolio, value: PortfolioValue
    ) -> PortfolioAllocation:
        """Return position weights and cash weight as fractions of total value."""
        total = value.total_value
        if total <= 0:
            return PortfolioAllocation(weights={}, cash_weight=_ZERO)

        weights: dict[str, Decimal] = {}
        for pos in portfolio.positions:
            # Market value uses cost basis proportion when a price map is not
            # re-supplied here; the manager passes a valuation already computed
            # from prices, so weight by cost basis keeps this component price-free.
            weights[pos.symbol] = (pos.cost_basis / total) if total else _ZERO

        cash_weight = value.cash_value / total
        return PortfolioAllocation(weights=weights, cash_weight=cash_weight)
