"""Production-grade configuration for Binance AI Hedge Fund OS.

Each configuration *section* is an independent Pydantic ``BaseSettings`` class
with its own environment-variable prefix. A single :class:`Settings` object
composes every section and performs cross-section validation (for example,
ensuring live trading is only possible in production with real credentials).

Load order and precedence are handled by :func:`config.environment.load_environment`
before the settings object is constructed. Access the singleton via
:func:`get_settings`, which is cached.

This module contains configuration only — no trading, database, or API logic.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from config.constants import (
    DATABASE_SCHEMES,
    DEFAULT_APP_NAME,
    DEFAULT_BASE_CURRENCY,
    DEFAULT_BINANCE_TESTNET_REST,
    DEFAULT_BINANCE_TESTNET_WS,
    DEFAULT_DATABASE_URL,
    DEFAULT_REDIS_URL,
    DEFAULT_TIMEZONE,
    HTTP_SCHEMES,
    INSECURE_SECRET_KEY,
    REDIS_SCHEMES,
    WS_SCHEMES,
    AIProvider,
    LogFormat,
    LogLevel,
    OrderType,
    TradingMode,
)
from config.environment import Environment, load_environment
from config.validators import (
    split_csv,
    validate_api_key,
    validate_fraction,
    validate_non_negative,
    validate_port,
    validate_positive,
    validate_secret,
    validate_url,
)

# ---------------------------------------------------------------------------
# Shared config for every section
# ---------------------------------------------------------------------------

#: Base ``model_config`` shared by all section classes. Individual sections add
#: their own ``env_prefix``.
_BASE_CONFIG = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    case_sensitive=False,
    extra="ignore",
)


# ---------------------------------------------------------------------------
# Section: Application
# ---------------------------------------------------------------------------


class ApplicationSettings(BaseSettings):
    """General application metadata and runtime flags."""

    model_config = SettingsConfigDict(**_BASE_CONFIG, env_prefix="APP_")

    name: str = DEFAULT_APP_NAME
    version: str = "0.1.0"
    debug: bool = True
    timezone: str = DEFAULT_TIMEZONE


# ---------------------------------------------------------------------------
# Section: Binance
# ---------------------------------------------------------------------------


class BinanceSettings(BaseSettings):
    """Binance exchange connectivity settings."""

    model_config = SettingsConfigDict(**_BASE_CONFIG, env_prefix="BINANCE_")

    api_key: str = ""
    api_secret: str = ""
    testnet: bool = True
    base_url: str = DEFAULT_BINANCE_TESTNET_REST
    ws_url: str = DEFAULT_BINANCE_TESTNET_WS
    recv_window_ms: int = Field(default=5_000, ge=100, le=60_000)

    @field_validator("api_key", "api_secret")
    @classmethod
    def _check_credentials(cls, value: str) -> str:
        # Optional here; live trading requirements are enforced on the master
        # Settings object where the environment/mode are known.
        return validate_api_key(value, field="binance credential", required=False)

    @field_validator("base_url")
    @classmethod
    def _check_base_url(cls, value: str) -> str:
        return validate_url(value, schemes=HTTP_SCHEMES, field="BINANCE_BASE_URL")

    @field_validator("ws_url")
    @classmethod
    def _check_ws_url(cls, value: str) -> str:
        return validate_url(value, schemes=WS_SCHEMES, field="BINANCE_WS_URL")


# ---------------------------------------------------------------------------
# Section: Database
# ---------------------------------------------------------------------------


class DatabaseSettings(BaseSettings):
    """Database connection configuration (no ORM/engine logic here)."""

    model_config = SettingsConfigDict(**_BASE_CONFIG, env_prefix="DATABASE_")

    url: str = DEFAULT_DATABASE_URL
    pool_size: int = Field(default=5, ge=1, le=100)
    max_overflow: int = Field(default=10, ge=0, le=100)
    echo: bool = False

    @field_validator("url")
    @classmethod
    def _check_url(cls, value: str) -> str:
        return validate_url(
            value, schemes=DATABASE_SCHEMES, field="DATABASE_URL"
        )


# ---------------------------------------------------------------------------
# Section: Redis
# ---------------------------------------------------------------------------


class RedisSettings(BaseSettings):
    """Redis connection configuration."""

    model_config = SettingsConfigDict(**_BASE_CONFIG, env_prefix="REDIS_")

    url: str = DEFAULT_REDIS_URL
    max_connections: int = Field(default=10, ge=1, le=1_000)

    @field_validator("url")
    @classmethod
    def _check_url(cls, value: str) -> str:
        return validate_url(value, schemes=REDIS_SCHEMES, field="REDIS_URL")


# ---------------------------------------------------------------------------
# Section: Logging
# ---------------------------------------------------------------------------


class LoggingSettings(BaseSettings):
    """Structured logging configuration."""

    model_config = SettingsConfigDict(**_BASE_CONFIG, env_prefix="LOG_")

    level: LogLevel = LogLevel.INFO
    format: LogFormat = LogFormat.JSON
    file_path: str | None = None


# ---------------------------------------------------------------------------
# Section: Dashboard
# ---------------------------------------------------------------------------


class DashboardSettings(BaseSettings):
    """Web dashboard configuration."""

    model_config = SettingsConfigDict(**_BASE_CONFIG, env_prefix="DASHBOARD_")

    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8501

    @field_validator("port")
    @classmethod
    def _check_port(cls, value: int) -> int:
        return validate_port(value, field="DASHBOARD_PORT")


# ---------------------------------------------------------------------------
# Section: AI Providers
# ---------------------------------------------------------------------------


class AIProviderSettings(BaseSettings):
    """Large language model provider configuration."""

    model_config = SettingsConfigDict(**_BASE_CONFIG, env_prefix="AI_")

    provider: AIProvider = AIProvider.ANTHROPIC
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    model: str = "claude-opus-4-8"
    request_timeout_s: int = Field(default=60, ge=1, le=600)
    max_retries: int = Field(default=3, ge=0, le=10)

    @field_validator("anthropic_api_key", "openai_api_key")
    @classmethod
    def _check_keys(cls, value: str) -> str:
        return validate_api_key(value, field="AI provider key", required=False)


# ---------------------------------------------------------------------------
# Section: Risk
# ---------------------------------------------------------------------------


class RiskSettings(BaseSettings):
    """Risk-management limits (fractions expressed in the range ``(0, 1]``)."""

    model_config = SettingsConfigDict(**_BASE_CONFIG, env_prefix="RISK_")

    max_position_size_pct: float = 0.10
    risk_per_trade_pct: float = 0.01
    max_daily_drawdown_pct: float = 0.05
    max_total_drawdown_pct: float = 0.20
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.04
    max_leverage: float = 1.0
    max_open_positions: int = Field(default=5, ge=1, le=1_000)

    @field_validator(
        "max_position_size_pct",
        "risk_per_trade_pct",
        "max_daily_drawdown_pct",
        "max_total_drawdown_pct",
        "stop_loss_pct",
        "take_profit_pct",
    )
    @classmethod
    def _check_fractions(cls, value: float) -> float:
        return validate_fraction(value, field="risk fraction", allow_zero=False)

    @field_validator("max_leverage")
    @classmethod
    def _check_leverage(cls, value: float) -> float:
        if value < 1.0:
            raise ValueError(f"RISK_MAX_LEVERAGE must be >= 1.0, got {value}.")
        return value

    @model_validator(mode="after")
    def _check_drawdown_ordering(self) -> "RiskSettings":
        if self.max_daily_drawdown_pct > self.max_total_drawdown_pct:
            raise ValueError(
                "RISK_MAX_DAILY_DRAWDOWN_PCT cannot exceed "
                "RISK_MAX_TOTAL_DRAWDOWN_PCT."
            )
        return self


# ---------------------------------------------------------------------------
# Section: Trading
# ---------------------------------------------------------------------------


class TradingSettings(BaseSettings):
    """High-level trading configuration (no execution logic)."""

    model_config = SettingsConfigDict(**_BASE_CONFIG, env_prefix="TRADING_")

    mode: TradingMode = TradingMode.PAPER
    base_currency: str = DEFAULT_BASE_CURRENCY
    symbols: Annotated[list[str], Field(default_factory=lambda: ["BTCUSDT"])]
    default_order_type: OrderType = OrderType.MARKET
    max_order_notional: float = Field(default=1_000.0, gt=0)

    @field_validator("symbols", mode="before")
    @classmethod
    def _split_symbols(cls, value: object) -> object:
        return split_csv(value)

    @field_validator("base_currency")
    @classmethod
    def _upper_currency(cls, value: str) -> str:
        return value.strip().upper()


# ---------------------------------------------------------------------------
# Section: Backtesting
# ---------------------------------------------------------------------------


class BacktestingSettings(BaseSettings):
    """Backtesting engine configuration."""

    model_config = SettingsConfigDict(**_BASE_CONFIG, env_prefix="BACKTEST_")

    initial_balance: float = Field(default=100_000.0, gt=0)
    commission_pct: float = 0.001
    slippage_pct: float = 0.0005
    data_dir: str = "data/backtests"

    @field_validator("commission_pct", "slippage_pct")
    @classmethod
    def _check_non_negative(cls, value: float) -> float:
        return validate_non_negative(value, field="backtest cost")


# ---------------------------------------------------------------------------
# Section: Simulation
# ---------------------------------------------------------------------------


class SimulationSettings(BaseSettings):
    """Live-like paper/simulation environment configuration."""

    model_config = SettingsConfigDict(**_BASE_CONFIG, env_prefix="SIMULATION_")

    initial_balance: float = Field(default=100_000.0, gt=0)
    latency_ms: int = Field(default=50, ge=0, le=60_000)
    fill_ratio: float = 1.0
    commission_pct: float = 0.001
    slippage_pct: float = 0.0005
    random_seed: int | None = None

    @field_validator("fill_ratio")
    @classmethod
    def _check_fill_ratio(cls, value: float) -> float:
        return validate_fraction(value, field="SIMULATION_FILL_RATIO", allow_zero=False)

    @field_validator("commission_pct", "slippage_pct")
    @classmethod
    def _check_non_negative(cls, value: float) -> float:
        return validate_non_negative(value, field="simulation cost")


# ---------------------------------------------------------------------------
# Section: Monitoring
# ---------------------------------------------------------------------------


class MonitoringSettings(BaseSettings):
    """Metrics, alerting, and observability configuration."""

    model_config = SettingsConfigDict(**_BASE_CONFIG, env_prefix="MONITORING_")

    enabled: bool = True
    metrics_port: int = 9090
    sentry_dsn: str | None = None
    healthcheck_interval_s: int = Field(default=30, ge=1, le=3_600)

    @field_validator("metrics_port")
    @classmethod
    def _check_port(cls, value: int) -> int:
        return validate_port(value, field="MONITORING_METRICS_PORT")


# ---------------------------------------------------------------------------
# Section: Security
# ---------------------------------------------------------------------------


class SecuritySettings(BaseSettings):
    """Application security configuration."""

    model_config = SettingsConfigDict(**_BASE_CONFIG, env_prefix="SECURITY_")

    secret_key: str = INSECURE_SECRET_KEY
    api_token: str | None = None
    allowed_hosts: Annotated[
        list[str], Field(default_factory=lambda: ["localhost", "127.0.0.1"])
    ]

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def _split_hosts(cls, value: object) -> object:
        return split_csv(value)


# ---------------------------------------------------------------------------
# Master settings object
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    """Master settings object composing every configuration section.

    The active :class:`~config.environment.Environment` is read from ``APP_ENV``
    and drives cross-section validation performed in :meth:`_validate_environment`.
    """

    model_config = SettingsConfigDict(**_BASE_CONFIG, env_prefix="APP_")

    environment: Environment = Environment.DEVELOPMENT

    application: Annotated[ApplicationSettings, Field(default_factory=ApplicationSettings)]
    binance: Annotated[BinanceSettings, Field(default_factory=BinanceSettings)]
    database: Annotated[DatabaseSettings, Field(default_factory=DatabaseSettings)]
    redis: Annotated[RedisSettings, Field(default_factory=RedisSettings)]
    logging: Annotated[LoggingSettings, Field(default_factory=LoggingSettings)]
    dashboard: Annotated[DashboardSettings, Field(default_factory=DashboardSettings)]
    ai: Annotated[AIProviderSettings, Field(default_factory=AIProviderSettings)]
    risk: Annotated[RiskSettings, Field(default_factory=RiskSettings)]
    trading: Annotated[TradingSettings, Field(default_factory=TradingSettings)]
    backtesting: Annotated[
        BacktestingSettings, Field(default_factory=BacktestingSettings)
    ]
    simulation: Annotated[SimulationSettings, Field(default_factory=SimulationSettings)]
    monitoring: Annotated[MonitoringSettings, Field(default_factory=MonitoringSettings)]
    security: Annotated[SecuritySettings, Field(default_factory=SecuritySettings)]

    # -- cross-section validation -------------------------------------------

    @model_validator(mode="after")
    def _validate_environment(self) -> "Settings":
        """Enforce consistency between environment, trading mode, and secrets."""
        env = self.environment
        mode = self.trading.mode

        # Live trading is only ever allowed in production.
        if mode is TradingMode.LIVE and not env.is_live_capable:
            raise ValueError(
                f"Trading mode 'live' is not permitted in the '{env.value}' "
                "environment; live trading requires APP_ENV=production."
            )

        # The paper environment must never run anything but paper trading.
        if env is Environment.PAPER and mode is not TradingMode.PAPER:
            raise ValueError(
                "The 'paper' environment only supports TRADING_MODE=paper, "
                f"got '{mode.value}'."
            )

        # Live trading needs real credentials against the real (non-testnet) API.
        if mode is TradingMode.LIVE:
            validate_api_key(
                self.binance.api_key, field="BINANCE_API_KEY", required=True
            )
            validate_api_key(
                self.binance.api_secret, field="BINANCE_API_SECRET", required=True
            )
            if self.binance.testnet:
                raise ValueError(
                    "Live trading requires BINANCE_TESTNET=false with real "
                    "production credentials."
                )

        # Production must not ship with the insecure placeholder secret.
        if env.is_production:
            validate_secret(self.security.secret_key, field="SECURITY_SECRET_KEY")
            if self.security.secret_key == INSECURE_SECRET_KEY:
                raise ValueError(
                    "SECURITY_SECRET_KEY must be overridden in production."
                )
            if self.application.debug:
                raise ValueError("APP_DEBUG must be false in production.")

        return self


# ---------------------------------------------------------------------------
# Accessor
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached, validated master :class:`Settings` instance.

    Dotenv files are loaded for the active environment (via
    :func:`config.environment.load_environment`) before the settings object is
    constructed. The result is cached so subsequent calls are cheap.

    Returns:
        The singleton :class:`Settings`.

    Raises:
        pydantic.ValidationError: If any value fails validation.
    """
    load_environment()
    return Settings()


def reload_settings() -> Settings:
    """Clear the :func:`get_settings` cache and rebuild the settings.

    Useful in tests or after mutating the process environment.

    Returns:
        A freshly built :class:`Settings`.
    """
    get_settings.cache_clear()
    return get_settings()
