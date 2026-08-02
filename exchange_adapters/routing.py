"""Exchange router.

:class:`DefaultExchangeRouter` determines which adapter should receive a request
and produces an :class:`~exchange_adapters.models.ExchangeRoute` (metadata only).
It is stateless, exchange-independent, and never communicates with brokers.
"""

from __future__ import annotations

from exchange_adapters.context import ExchangeContext
from exchange_adapters.models import ExchangeMetadata, ExchangeRoute

__all__ = ["DefaultExchangeRouter", "DEFAULT_ADAPTER"]

#: The neutral, placeholder adapter name used until real adapters are registered.
DEFAULT_ADAPTER = "default"


class DefaultExchangeRouter:
    """Selects a target adapter name without contacting any broker."""

    def route(self, context: ExchangeContext) -> ExchangeRoute:
        """Return an :class:`ExchangeRoute` naming the target adapter."""
        adapter_name = context.metadata.get("adapter", DEFAULT_ADAPTER)
        return ExchangeRoute(
            adapter_name=adapter_name,
            metadata=ExchangeMetadata(
                {"exchange": context.exchange, "symbol": context.symbol}
            ),
        )
