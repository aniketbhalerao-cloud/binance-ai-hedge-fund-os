"""Account domain model.

An :class:`Account` is a venue-independent snapshot of the trading account:
the per-asset balances and, optionally, the associated portfolio snapshot. It
carries no exchange-specific identifiers or fields.

Only structural validation lives here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from models.portfolio import Portfolio

__all__ = ["AssetBalance", "Account"]


@dataclass(frozen=True, slots=True)
class AssetBalance:
    """An immutable balance for a single asset.

    Attributes:
        asset: Asset symbol (e.g. ``"USDT"``, ``"BTC"``).
        free: Amount available to trade (non-negative).
        locked: Amount reserved by open orders (non-negative).

    Raises:
        ValueError: If any amount is negative.
    """

    asset: str
    free: Decimal = Decimal("0")
    locked: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        """Validate structural invariants (no business rules)."""
        if self.free < 0:
            raise ValueError("AssetBalance.free must not be negative.")
        if self.locked < 0:
            raise ValueError("AssetBalance.locked must not be negative.")


@dataclass(frozen=True, slots=True)
class Account:
    """An immutable snapshot of a trading account.

    Attributes:
        id: Application-level unique identifier for the account.
        balances: Per-asset balances (immutable tuple).
        portfolio: Optional associated portfolio snapshot.
        as_of: Snapshot timestamp (timezone-aware, UTC).
    """

    id: str
    balances: tuple[AssetBalance, ...] = ()
    portfolio: Portfolio | None = None
    as_of: datetime = field(default_factory=lambda: datetime.now(UTC))
