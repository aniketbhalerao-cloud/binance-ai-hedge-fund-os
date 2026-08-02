"""Binance authentication.

Holds the API credentials (via :class:`BinanceConfig`) and signs requests with
HMAC-SHA256. It never communicates with the REST client and never exposes the
secret key or signature outside its own return values.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from adapters.binance.config import BinanceConfig
from adapters.binance.errors import BinanceAuthenticationError
from adapters.binance.signer import BinanceSigner

__all__ = ["BinanceAuthentication"]


class BinanceAuthentication:
    """Credential holder + request signer for the Binance Spot API.

    Args:
        config: The adapter configuration (holds the credentials).
        signer: The HMAC signer.
    """

    def __init__(self, config: BinanceConfig, signer: BinanceSigner) -> None:
        self._config = config
        self._signer = signer

    @property
    def api_key(self) -> str:
        """Return the API key (safe to place in a request header)."""
        return self._config.api_key

    def validate_credentials(self) -> bool:
        """Return ``True`` when both API key and secret are present."""
        return self._config.has_credentials

    def authenticate(self) -> bool:
        """Validate credentials locally (no network call).

        Raises:
            BinanceAuthenticationError: If credentials are missing.
        """
        if not self.validate_credentials():
            raise BinanceAuthenticationError("missing API key or secret")
        return True

    def sign_request(self, params: Mapping[str, Any]) -> dict[str, Any]:
        """Return ``params`` with a ``timestamp`` and HMAC ``signature`` added.

        Raises:
            BinanceAuthenticationError: If credentials are missing.
        """
        self.authenticate()
        signed = dict(params)
        signed["timestamp"] = int(time.time() * 1000)
        query = self._signer.build_query(signed)
        signed["signature"] = self._signer.sign(query, self._config.secret_key)
        return signed

    def auth_headers(self) -> dict[str, str]:
        """Return the authentication headers (API key only; never the secret)."""
        return {"X-MBX-APIKEY": self._config.api_key}
