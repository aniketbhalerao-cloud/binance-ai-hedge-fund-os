"""Binance Spot adapter.

:class:`BinanceSpotAdapter` is the first concrete implementation of
:class:`~exchange_adapters.adapter.BaseExchangeAdapter`. It coordinates the
Binance sub-components — authentication, connection, REST client, request
translator, validator, and response parser — to submit an order and return a
standardized :class:`~exchange_adapters.models.ExchangeResponse`. All Binance
errors are translated to framework exceptions; no raw Binance error or secret
escapes. It performs no strategy, risk, order-creation, or execution logic.
"""

from __future__ import annotations

from decimal import Decimal

from adapters.binance.authentication import BinanceAuthentication
from adapters.binance.config import BinanceConfig
from adapters.binance.connection import BinanceConnection
from adapters.binance.converters import BinanceRequestTranslator
from adapters.binance.errors import (
    BinanceError,
    BinanceRequestError,
    BinanceResponseError,
)
from adapters.binance.events import (
    BinanceAuthenticated,
    BinanceAuthenticationFailed,
    BinanceErrorOccurred,
    BinanceOrderCancelled,
    BinanceOrderSubmitted,
)
from adapters.binance.models import BinanceAccount, BinanceBalance
from adapters.binance.parser import BinanceResponseParser
from adapters.binance.requests import BinanceRequestValidator
from adapters.binance.rest import BinanceRESTClient
from adapters.binance.routes import ACCOUNT, ORDER
from core.logging import LoggerFactory
from events.bus import EventBus
from exchange_adapters.adapter import BaseExchangeAdapter
from exchange_adapters.models import ExchangeRequest, ExchangeResponse

__all__ = ["BinanceSpotAdapter", "BINANCE_ADAPTER_NAME"]

BINANCE_ADAPTER_NAME = "binance"


class BinanceSpotAdapter(BaseExchangeAdapter):
    """Concrete Binance Spot adapter (submits orders via the REST client)."""

    def __init__(
        self,
        authentication: BinanceAuthentication,
        connection: BinanceConnection,
        rest: BinanceRESTClient,
        translator: BinanceRequestTranslator,
        validator: BinanceRequestValidator,
        parser: BinanceResponseParser,
        bus: EventBus,
        config: BinanceConfig,
        logger: LoggerFactory | None = None,
    ) -> None:
        super().__init__(BINANCE_ADAPTER_NAME)
        self._auth = authentication
        self._connection = connection
        self._rest = rest
        self._translator = translator
        self._validator = validator
        self._parser = parser
        self._bus = bus
        self._config = config
        self._log = logger.get_logger("binance.adapter") if logger else None

    async def submit(self, request: ExchangeRequest) -> ExchangeResponse:
        """Submit an order to Binance and return a standardized response.

        Raises:
            BinanceError: On any authentication, request, or response failure
                (already a framework ``ExchangeError``; no raw Binance error
                escapes).
        """
        try:
            self._auth.authenticate()
            await self._bus.publish(BinanceAuthenticated())

            binance_order = self._translator.translate(request)
            errors = self._validator.validate(binance_order)
            if errors:
                raise BinanceRequestError("; ".join(errors))

            payload = await self._rest.post(ORDER, binance_order.to_params())
            order = self._parser.parse_order(payload)
            response = self._parser.to_exchange_response(order)

            await self._bus.publish(
                BinanceOrderSubmitted(symbol=order.symbol, order_id=order.order_id)
            )
            if self._log is not None:
                self._log.info("Order submitted", extra={"order_id": order.order_id})
            return response
        except BinanceError as exc:
            await self._on_error(exc)
            raise
        except Exception as exc:  # never leak a raw exception/secret
            wrapped = BinanceResponseError("unexpected adapter failure")
            await self._on_error(wrapped)
            raise wrapped from exc

    async def cancel_order(self, symbol: str, order_id: str) -> ExchangeResponse:
        """Cancel an order and return a standardized response."""
        try:
            payload = await self._rest.delete(
                ORDER, {"symbol": symbol, "orderId": order_id}
            )
            order = self._parser.parse_order(payload)
            response = self._parser.to_exchange_response(order)
            await self._bus.publish(
                BinanceOrderCancelled(symbol=symbol, order_id=order_id)
            )
            return response
        except BinanceError as exc:
            await self._on_error(exc)
            raise

    async def get_account(self) -> BinanceAccount:
        """Fetch and parse the account snapshot."""
        payload = await self._rest.get(ACCOUNT)
        balances = tuple(
            BinanceBalance(
                asset=str(b["asset"]),
                free=Decimal(str(b.get("free", "0"))),
                locked=Decimal(str(b.get("locked", "0"))),
            )
            for b in (payload.get("balances", []) if isinstance(payload, dict) else [])
        )
        return BinanceAccount(
            can_trade=(
                bool(payload.get("canTrade", False))
                if isinstance(payload, dict)
                else False
            ),
            balances=balances,
        )

    async def _on_error(self, exc: BinanceError) -> None:
        # Publish a masked, secret-free error message.
        if self._log is not None:
            self._log.error("Binance adapter error", extra={"error": str(exc)})
        if isinstance(exc, (BinanceRequestError, BinanceResponseError)):
            pass
        await self._bus.publish(BinanceErrorOccurred(message=str(exc)))
        # Authentication-specific signal.
        from adapters.binance.errors import BinanceAuthenticationError

        if isinstance(exc, BinanceAuthenticationError):
            await self._bus.publish(BinanceAuthenticationFailed(reason=str(exc)))
