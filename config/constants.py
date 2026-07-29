"""Configuration constants, enumerations, and safe default values.

This module holds *only* declarative data used by the configuration layer:
enumerations, allowed value sets, numeric bounds, and default literals.

It contains no business, trading, database, or API logic — it is imported by
:mod:`config.settings`, :mod:`config.validators`, and
:mod:`config.environment` to keep magic values in a single place.
"""

from __future__ import annotations

from enum import Enum
from typing import Final

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class TradingMode(str, Enum):
    """How orders are (or are not) sent to a real venue.

    ``LIVE`` is intentionally the only mode that reaches a real exchange and is
    permitted exclusively in the production environment (enforced in
    :mod:`config.settings`).
    """

    PAPER = "paper"
    SIMULATION = "simulation"
    BACKTEST = "backtest"
    LIVE = "live"


class LogLevel(str, Enum):
    """Standard Python logging levels, expressed as strings."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(str, Enum):
    """Serialization format for emitted log records."""

    JSON = "json"
    TEXT = "text"


class AIProvider(str, Enum):
    """Supported large language model providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    LOCAL = "local"


class OrderType(str, Enum):
    """Order types the trading layer may default to (config only)."""

    MARKET = "market"
    LIMIT = "limit"


# ---------------------------------------------------------------------------
# Allowed URL schemes (used by validators)
# ---------------------------------------------------------------------------

HTTP_SCHEMES: Final[frozenset[str]] = frozenset({"http", "https"})
WS_SCHEMES: Final[frozenset[str]] = frozenset({"ws", "wss"})
DATABASE_SCHEMES: Final[frozenset[str]] = frozenset(
    {
        "postgresql",
        "postgresql+asyncpg",
        "postgresql+psycopg",
        "sqlite",
    }
)
REDIS_SCHEMES: Final[frozenset[str]] = frozenset({"redis", "rediss"})

# ---------------------------------------------------------------------------
# Numeric bounds
# ---------------------------------------------------------------------------

MIN_PORT: Final[int] = 1
MAX_PORT: Final[int] = 65_535

#: Minimum length for secrets that must be strong (e.g. in production).
MIN_SECRET_LENGTH: Final[int] = 32

#: Minimum plausible length of a real exchange/provider API credential.
MIN_API_KEY_LENGTH: Final[int] = 16

# ---------------------------------------------------------------------------
# Safe defaults
# ---------------------------------------------------------------------------

DEFAULT_APP_NAME: Final[str] = "binance-ai-hedge-fund-os"
DEFAULT_TIMEZONE: Final[str] = "UTC"
DEFAULT_BASE_CURRENCY: Final[str] = "USDT"

DEFAULT_BINANCE_TESTNET_REST: Final[str] = "https://testnet.binance.vision"
DEFAULT_BINANCE_TESTNET_WS: Final[str] = "wss://testnet.binance.vision/ws"

DEFAULT_DATABASE_URL: Final[str] = (
    "postgresql://postgres:postgres@localhost:5432/hedge_fund_os"
)
DEFAULT_REDIS_URL: Final[str] = "redis://localhost:6379/0"

#: Placeholder security key. Any environment that keeps this value is rejected
#: when running in production (see :mod:`config.settings`).
INSECURE_SECRET_KEY: Final[str] = "CHANGE_ME_INSECURE_DEFAULT_SECRET_KEY"
