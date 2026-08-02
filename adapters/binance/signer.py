"""Binance request signing (HMAC SHA256).

Pure, stateless signing helpers as required by the Binance Spot API. The secret
is only used to compute the signature and is never stored, logged, or returned.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlencode

__all__ = ["BinanceSigner"]


class BinanceSigner:
    """Builds query strings and HMAC-SHA256 signatures for Binance requests."""

    @staticmethod
    def build_query(params: Mapping[str, Any]) -> str:
        """Return a URL-encoded query string from ``params`` (insertion order)."""
        return urlencode({k: v for k, v in params.items() if v is not None})

    @staticmethod
    def sign(query: str, secret_key: str) -> str:
        """Return the hex HMAC-SHA256 signature of ``query`` using ``secret_key``."""
        return hmac.new(
            secret_key.encode("utf-8"), query.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def signed_query(self, params: Mapping[str, Any], secret_key: str) -> str:
        """Return ``params`` as a query string with an appended ``signature``."""
        query = self.build_query(params)
        signature = self.sign(query, secret_key)
        return f"{query}&signature={signature}"
