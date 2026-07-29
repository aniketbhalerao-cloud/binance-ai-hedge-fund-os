"""Signal domain model.

A :class:`Signal` is an immutable trading intent emitted by a strategy or AI
agent — a suggestion to act on an instrument, independent of any exchange. The
Trading Engine and Risk Manager consume signals without knowing which strategy
or model produced them.

Only structural validation lives here; turning a signal into an order is the
job of higher layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum

__all__ = ["SignalAction", "Signal"]


class SignalAction(str, Enum):
    """The action a signal recommends."""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    CLOSE = "close"


@dataclass(frozen=True, slots=True)
class Signal:
    """An immutable trading suggestion.

    Attributes:
        id: Application-level unique identifier for the signal.
        symbol: The instrument/pair the signal refers to.
        action: The recommended action.
        confidence: Strength of the signal in the range ``[0.0, 1.0]``.
        source: Name of the strategy or agent that produced the signal.
        target_price: Optional suggested entry price (positive if set).
        stop_loss: Optional suggested stop-loss price (positive if set).
        take_profit: Optional suggested take-profit price (positive if set).
        created_at: Emission timestamp (timezone-aware, UTC).

    Raises:
        ValueError: If ``confidence`` is out of range or any price is not
            positive when provided.
    """

    id: str
    symbol: str
    action: SignalAction
    confidence: float = 0.0
    source: str = ""
    target_price: Decimal | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Validate structural invariants (no business rules)."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Signal.confidence must be within [0.0, 1.0].")
        for name in ("target_price", "stop_loss", "take_profit"):
            value: Decimal | None = getattr(self, name)
            if value is not None and value <= 0:
                raise ValueError(f"Signal.{name} must be positive when set.")
