"""Portfolio valuation.

:class:`DefaultPortfolioValuation` computes the portfolio value from holdings,
standardized market prices, and cash. Stateless — it reads a portfolio and a
price map and returns a :class:`PortfolioValue`. It contains no exchange-specific
pricing logic; prices are supplied as standardized values.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from portfolio.exceptions import ValuationError
from portfolio.models import Portfolio, PortfolioValue

__all__ = ["DefaultPortfolioValuation"]

_ZERO = Decimal("0")


class DefaultPortfolioValuation:
    """Stateless valuation from holdings + prices + cash."""

    def value(
        self, portfolio: Portfolio, prices: Mapping[str, Decimal]
    ) -> PortfolioValue:
        """Return the :class:`PortfolioValue` for ``portfolio`` at ``prices``.

        Raises:
            ValuationError: If a held symbol has no price.
        """
        holdings_value = _ZERO
        cost_basis = _ZERO
        unrealized = _ZERO
        # Realized P&L is tracked at the portfolio level so it survives a
        # position being fully closed and removed from ``positions``.
        realized = portfolio.realized_pnl
        for pos in portfolio.positions:
            price = prices.get(pos.symbol)
            if price is None:
                raise ValuationError(f"missing price for {pos.symbol}")
            market_value = pos.quantity * price
            holdings_value += market_value
            cost_basis += pos.cost_basis
            unrealized += market_value - pos.cost_basis

        cash_value = portfolio.cash.total
        return PortfolioValue(
            cash_value=cash_value,
            holdings_value=holdings_value,
            cost_basis=cost_basis,
            unrealized_pnl=unrealized,
            realized_pnl=realized,
            total_value=cash_value + holdings_value,
        )
