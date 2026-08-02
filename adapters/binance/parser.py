"""Response parsing: Binance payload → standardized ExchangeResponse.

Stateless translation that hides Binance-specific payloads. Only standardized,
non-sensitive fields (order id, status) are surfaced to the rest of the system.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from adapters.binance.models import BinanceOrderStatus
from adapters.binance.responses import BinanceOrderResponse
from exchange_adapters.models import ExchangeMetadata, ExchangeResponse

__all__ = ["BinanceResponseParser"]

_ACCEPTED = {
    BinanceOrderStatus.NEW,
    BinanceOrderStatus.PARTIALLY_FILLED,
    BinanceOrderStatus.FILLED,
}


class BinanceResponseParser:
    """Translates Binance responses into standardized exchange responses."""

    def parse_order(self, payload: Mapping[str, Any]) -> BinanceOrderResponse:
        """Parse a raw order payload into a Binance response model."""
        return BinanceOrderResponse.from_payload(payload)

    def to_exchange_response(self, order: BinanceOrderResponse) -> ExchangeResponse:
        """Convert a Binance order response into a standardized response."""
        return ExchangeResponse(
            accepted=order.status in _ACCEPTED,
            message=order.status.value,
            metadata=ExchangeMetadata(
                {
                    "order_id": order.order_id,
                    "symbol": order.symbol,
                    "status": order.status.value,
                }
            ),
        )
