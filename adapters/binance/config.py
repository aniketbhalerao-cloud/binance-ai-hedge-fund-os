"""Binance Spot adapter configuration.

Immutable configuration for the adapter. The secret key is stored but never
rendered — ``repr`` masks it — so credentials cannot leak through logs, events,
or exceptions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["BinanceConfig"]

_TESTNET_REST = "https://testnet.binance.vision"
_TESTNET_WS = "wss://testnet.binance.vision/ws"


@dataclass(frozen=True, slots=True)
class BinanceConfig:
    """Immutable Binance Spot connection configuration.

    Attributes:
        api_key: Binance API key.
        secret_key: Binance secret key (never logged or rendered).
        base_url: REST base URL (defaults to the Spot testnet).
        ws_url: WebSocket base URL (defaults to the Spot testnet).
        timeout: Per-request timeout in seconds.
        retry_count: Number of REST retry attempts.
        rate_limit_per_minute: Client-side rate-limit awareness value.
    """

    api_key: str = ""
    secret_key: str = field(default="", repr=False)
    base_url: str = _TESTNET_REST
    ws_url: str = _TESTNET_WS
    timeout: float = 10.0
    retry_count: int = 3
    rate_limit_per_minute: int = 1200

    @property
    def has_credentials(self) -> bool:
        """Return ``True`` when both API key and secret are present."""
        return bool(self.api_key) and bool(self.secret_key)

    def masked_secret(self) -> str:
        """Return a masked form of the secret, safe for display."""
        if not self.secret_key:
            return ""
        return f"***{self.secret_key[-2:]}" if len(self.secret_key) > 2 else "***"
