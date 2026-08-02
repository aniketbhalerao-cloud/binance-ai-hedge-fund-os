"""Binance Spot response models.

Binance-shaped response objects parsed from raw payloads. These stay inside the
adapter; callers receive standardized
:class:`~exchange_adapters.models.ExchangeResponse` objects from the parser.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from adapters.binance.errors import BinanceResponseError
from adapters.binance.models import BinanceOrderStatus

__all__ = ["BinanceOrderResponse"]


@dataclass(frozen=True, slots=True)
class BinanceOrderResponse:
    """A parsed Binance order response."""

    order_id: str
    client_order_id: str | None
    symbol: str
    status: BinanceOrderStatus
    executed_qty: Decimal

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> BinanceOrderResponse:
        """Build a response from a raw Binance payload.

        Raises:
            BinanceResponseError: If the payload is missing required fields.
        """
        try:
            return cls(
                order_id=str(payload["orderId"]),
                client_order_id=(
                    str(payload["clientOrderId"])
                    if payload.get("clientOrderId") is not None
                    else None
                ),
                symbol=str(payload["symbol"]),
                status=BinanceOrderStatus(str(payload["status"])),
                executed_qty=Decimal(str(payload.get("executedQty", "0"))),
            )
        except (KeyError, ValueError) as exc:
            raise BinanceResponseError("malformed order response") from exc
