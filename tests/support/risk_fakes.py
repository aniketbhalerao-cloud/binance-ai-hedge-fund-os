"""Fake risk rules and helpers for Risk Framework tests.

A new, standalone support module (existing support files are unchanged). These
are test doubles only — no real risk thresholds or trading rules.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from risk.context import RiskContext
from risk.models import RiskViolation
from risk.rules import BaseRiskRule
from strategies.signals import SignalDirection, TradingSignal

__all__ = [
    "PassRule",
    "RejectRule",
    "ErrorRule",
    "make_risk_context",
]

_FIXED = datetime(2026, 1, 1, tzinfo=UTC)


class PassRule(BaseRiskRule):
    """A rule that always passes."""

    def __init__(self, name: str = "pass") -> None:
        super().__init__(name)

    async def check(self, context: RiskContext) -> RiskViolation | None:
        return None


class RejectRule(BaseRiskRule):
    """A rule that always produces a violation."""

    def __init__(self, name: str = "reject") -> None:
        super().__init__(name)

    async def check(self, context: RiskContext) -> RiskViolation | None:
        return self.make_violation("blocked by test rule")


class ErrorRule(BaseRiskRule):
    """A rule that always raises, to test error isolation."""

    def __init__(self, name: str = "error") -> None:
        super().__init__(name)

    async def check(self, context: RiskContext) -> RiskViolation | None:
        raise RuntimeError("rule exploded")


def make_risk_context(
    *,
    exchange: str = "sim",
    symbol: str = "BTCUSDT",
    direction: SignalDirection = SignalDirection.BUY,
) -> RiskContext:
    """Build a deterministic RiskContext wrapping a trading signal."""
    signal = TradingSignal(
        id=uuid.uuid4().hex,
        strategy_name="test",
        symbol=symbol,
        direction=direction,
        confidence=0.5,
        timestamp=_FIXED,
    )
    return RiskContext(
        signal=signal, exchange=exchange, symbol=symbol, timestamp=_FIXED
    )
