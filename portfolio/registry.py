"""Portfolio registry.

:class:`InMemoryPortfolioRegistry` is a thread-safe store of portfolios keyed by
id. It never creates portfolios (creation is the manager's/DI's job) — it only
registers, updates, looks up, lists, and removes them.
"""

from __future__ import annotations

from threading import Lock

from portfolio.exceptions import PortfolioNotFoundError
from portfolio.models import Portfolio

__all__ = ["InMemoryPortfolioRegistry"]


class InMemoryPortfolioRegistry:
    """A thread-safe registry of portfolios, keyed by id."""

    def __init__(self) -> None:
        self._portfolios: dict[str, Portfolio] = {}
        self._lock = Lock()

    def register(self, portfolio: Portfolio) -> None:
        """Store ``portfolio`` (insert or replace)."""
        with self._lock:
            self._portfolios[portfolio.id] = portfolio

    def update(self, portfolio: Portfolio) -> None:
        """Replace an existing portfolio (same as register)."""
        self.register(portfolio)

    def exists(self, portfolio_id: str) -> bool:
        """Return ``True`` if ``portfolio_id`` is registered."""
        with self._lock:
            return portfolio_id in self._portfolios

    def get(self, portfolio_id: str) -> Portfolio:
        """Return the portfolio for ``portfolio_id``.

        Raises:
            PortfolioNotFoundError: If it is not registered.
        """
        with self._lock:
            portfolio = self._portfolios.get(portfolio_id)
        if portfolio is None:
            raise PortfolioNotFoundError(f"portfolio {portfolio_id!r} not found")
        return portfolio

    def list(self) -> list[Portfolio]:
        """Return all registered portfolios."""
        with self._lock:
            return list(self._portfolios.values())

    def remove(self, portfolio_id: str) -> None:
        """Remove ``portfolio_id`` if present."""
        with self._lock:
            self._portfolios.pop(portfolio_id, None)
