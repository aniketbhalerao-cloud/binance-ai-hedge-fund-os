"""Binance Spot REST client.

A reusable REST client over an injected :class:`~adapters.binance.client.HttpTransport`.
It centralizes request construction (no per-endpoint duplication), timeout and
retry policy, signing for signed routes, error translation, and response
handling. It is safe for concurrent use — it holds no per-request mutable state
and the transport is reused (connection reuse / keep-alive live in the transport).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlencode

from adapters.binance.authentication import BinanceAuthentication
from adapters.binance.client import HttpResponse, HttpTransport
from adapters.binance.config import BinanceConfig
from adapters.binance.errors import (
    BinanceConnectionError,
    BinanceError,
    translate_http_error,
)
from adapters.binance.events import (
    BinanceRateLimitReached,
    BinanceRequestSent,
    BinanceResponseReceived,
)
from adapters.binance.routes import SIGNED_ROUTES
from core.logging import LoggerFactory
from events.bus import EventBus

__all__ = ["BinanceRESTClient"]


class BinanceRESTClient:
    """REST client coordinating transport, signing, retries, and parsing.

    Args:
        transport: The HTTP transport (abstraction; injected).
        config: Adapter configuration (base URL, timeout, retries).
        authentication: Signer/credentials for signed routes.
        bus: Event bus for request/response events.
        logger: Optional logger factory.
    """

    def __init__(
        self,
        transport: HttpTransport,
        config: BinanceConfig,
        authentication: BinanceAuthentication,
        bus: EventBus,
        logger: LoggerFactory | None = None,
    ) -> None:
        self._transport = transport
        self._config = config
        self._auth = authentication
        self._bus = bus
        self._log = logger.get_logger("binance.rest") if logger else None

    async def get(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        return await self._request("GET", path, params)

    async def post(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        return await self._request("POST", path, params)

    async def put(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        return await self._request("PUT", path, params)

    async def delete(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        return await self._request("DELETE", path, params)

    async def _request(
        self, method: str, path: str, params: Mapping[str, Any] | None
    ) -> Any:
        query_params: dict[str, Any] = dict(params or {})
        headers: dict[str, str] = {}
        if path in SIGNED_ROUTES:
            query_params = self._auth.sign_request(query_params)
            headers.update(self._auth.auth_headers())

        query = urlencode({k: v for k, v in query_params.items() if v is not None})
        url = f"{self._config.base_url}{path}"
        if query:
            url = f"{url}?{query}"

        # Never log the query string (it may contain the signature).
        if self._log is not None:
            self._log.info("REST request", extra={"method": method, "path": path})
        await self._bus.publish(BinanceRequestSent(method=method, path=path))

        response = await self._send_with_retry(method, url, headers)

        await self._bus.publish(
            BinanceResponseReceived(path=path, status=response.status)
        )
        if response.status == 200:
            return response.payload
        if response.status in (418, 429):
            await self._bus.publish(BinanceRateLimitReached())
        message = ""
        if isinstance(response.payload, Mapping):
            message = str(response.payload.get("msg", ""))
        raise translate_http_error(response.status, message)

    async def _send_with_retry(
        self, method: str, url: str, headers: Mapping[str, str]
    ) -> HttpResponse:
        attempts = max(1, self._config.retry_count)
        last_error: BinanceError | None = None
        for _ in range(attempts):
            try:
                return await self._transport.request(
                    method, url, headers=headers, timeout=self._config.timeout
                )
            except BinanceError as exc:  # connection/timeout — retry
                last_error = exc
        raise last_error or BinanceConnectionError("request failed")
