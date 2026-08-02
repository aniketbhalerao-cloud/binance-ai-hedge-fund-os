"""Cash management.

:class:`DefaultCashManager` adjusts cash from a fill and supports deposits and
withdrawals. It is stateless and independent of holdings — it only knows amounts.
"""

from __future__ import annotations

from decimal import Decimal

from models import OrderSide
from portfolio.exceptions import CashError
from portfolio.models import PortfolioCash

__all__ = ["DefaultCashManager"]


class DefaultCashManager:
    """Stateless cash math (independent of holdings)."""

    def apply(
        self, cash: PortfolioCash, side: OrderSide, quantity: Decimal, price: Decimal
    ) -> PortfolioCash:
        """Return cash after a fill: buys debit, sells credit ``available``."""
        notional = quantity * price
        if side is OrderSide.BUY:
            return PortfolioCash(cash.available - notional, cash.reserved)
        return PortfolioCash(cash.available + notional, cash.reserved)

    def deposit(self, cash: PortfolioCash, amount: Decimal) -> PortfolioCash:
        """Add ``amount`` to available cash."""
        if amount < 0:
            raise CashError("deposit must be non-negative")
        return PortfolioCash(cash.available + amount, cash.reserved)

    def withdraw(self, cash: PortfolioCash, amount: Decimal) -> PortfolioCash:
        """Remove ``amount`` from available cash.

        Raises:
            CashError: If the amount is negative or exceeds available cash.
        """
        if amount < 0:
            raise CashError("withdrawal must be non-negative")
        if amount > cash.available:
            raise CashError("insufficient available cash")
        return PortfolioCash(cash.available - amount, cash.reserved)

    def reserve(self, cash: PortfolioCash, amount: Decimal) -> PortfolioCash:
        """Move ``amount`` from available to reserved."""
        if amount < 0 or amount > cash.available:
            raise CashError("invalid reserve amount")
        return PortfolioCash(cash.available - amount, cash.reserved + amount)
