"""Market-data normalization.

:class:`DefaultNormalizer` converts a raw payload into a normalized domain model.
It understands a small, exchange-neutral *canonical* payload shape — a mapping
with a ``kind`` discriminator (``tick`` / ``trade`` / ``ohlcv`` / ``order_book``)
and standard fields. Exchange-specific parsing (Binance JSON, a CSV row, a
database row, …) belongs in adapters/providers that emit this canonical shape,
or in a subclass that registers additional converters via :meth:`register`.

This keeps the normalizer open for extension (future exchanges) but closed for
modification. It touches neither the event bus nor persistence.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from models import OrderSide

from market_data.exceptions import NormalizationError
from market_data.interfaces import NormalizedData, RawPayload
from market_data.models import (
    OHLCV,
    OrderBookSnapshot,
    PriceTick,
    TradeTick,
)

__all__ = ["DefaultNormalizer"]

Converter = Callable[[Mapping[str, Any]], NormalizedData]


def _dec(value: Any, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise NormalizationError(f"Invalid decimal for {field!r}: {value!r}.") from exc


def _dt(value: Any, field: str) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise NormalizationError(f"Invalid datetime for {field!r}: {value!r}.") from exc
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    raise NormalizationError(f"Unsupported datetime for {field!r}: {value!r}.")


def _require(raw: Mapping[str, Any], *fields: str) -> None:
    missing = [f for f in fields if f not in raw]
    if missing:
        raise NormalizationError(f"Missing field(s): {', '.join(missing)}.")


class DefaultNormalizer:
    """Normalizes canonical mapping payloads into domain models.

    Additional payload ``kind`` s can be supported without modifying this class
    by calling :meth:`register`.
    """

    def __init__(self) -> None:
        self._converters: dict[str, Converter] = {
            "tick": self._to_tick,
            "trade": self._to_trade,
            "ohlcv": self._to_ohlcv,
            "order_book": self._to_order_book,
        }

    def register(self, kind: str, converter: Converter) -> None:
        """Register a converter for a custom payload ``kind`` (extension point)."""
        self._converters[kind] = converter

    def normalize(self, raw: RawPayload) -> NormalizedData:
        """Convert ``raw`` into a normalized domain model.

        Raises:
            NormalizationError: If ``raw`` is not a supported canonical payload.
        """
        if not isinstance(raw, Mapping):
            raise NormalizationError("Raw payload must be a mapping.")
        kind = raw.get("kind")
        if not isinstance(kind, str):
            raise NormalizationError("Raw payload is missing a string 'kind'.")
        converter = self._converters.get(kind)
        if converter is None:
            raise NormalizationError(f"Unsupported payload kind: {kind!r}.")
        return converter(raw)

    # -- converters ---------------------------------------------------------

    @staticmethod
    def _to_tick(raw: Mapping[str, Any]) -> PriceTick:
        _require(raw, "exchange", "symbol", "price", "timestamp")
        return PriceTick(
            exchange=str(raw["exchange"]),
            symbol=str(raw["symbol"]),
            price=_dec(raw["price"], "price"),
            timestamp=_dt(raw["timestamp"], "timestamp"),
        )

    @staticmethod
    def _to_trade(raw: Mapping[str, Any]) -> TradeTick:
        _require(raw, "exchange", "symbol", "price", "quantity", "side", "timestamp")
        try:
            side = OrderSide(str(raw["side"]).lower())
        except ValueError as exc:
            raise NormalizationError(f"Invalid side: {raw['side']!r}.") from exc
        return TradeTick(
            exchange=str(raw["exchange"]),
            symbol=str(raw["symbol"]),
            price=_dec(raw["price"], "price"),
            quantity=_dec(raw["quantity"], "quantity"),
            side=side,
            timestamp=_dt(raw["timestamp"], "timestamp"),
        )

    @staticmethod
    def _to_ohlcv(raw: Mapping[str, Any]) -> OHLCV:
        _require(
            raw,
            "exchange",
            "symbol",
            "timeframe",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "open_time",
            "close_time",
        )
        return OHLCV(
            exchange=str(raw["exchange"]),
            symbol=str(raw["symbol"]),
            timeframe=str(raw["timeframe"]),
            open=_dec(raw["open"], "open"),
            high=_dec(raw["high"], "high"),
            low=_dec(raw["low"], "low"),
            close=_dec(raw["close"], "close"),
            volume=_dec(raw["volume"], "volume"),
            open_time=_dt(raw["open_time"], "open_time"),
            close_time=_dt(raw["close_time"], "close_time"),
            is_closed=bool(raw.get("is_closed", False)),
        )

    @staticmethod
    def _to_order_book(raw: Mapping[str, Any]) -> OrderBookSnapshot:
        _require(raw, "exchange", "symbol", "bids", "asks", "timestamp")

        def _levels(rows: Any, side: str) -> tuple[tuple[Decimal, Decimal], ...]:
            try:
                return tuple(
                    (_dec(p, f"{side}.price"), _dec(q, f"{side}.qty")) for p, q in rows
                )
            except (TypeError, ValueError) as exc:
                raise NormalizationError(f"Invalid {side} levels: {rows!r}.") from exc

        return OrderBookSnapshot(
            exchange=str(raw["exchange"]),
            symbol=str(raw["symbol"]),
            bids=_levels(raw["bids"], "bids"),
            asks=_levels(raw["asks"], "asks"),
            timestamp=_dt(raw["timestamp"], "timestamp"),
        )
