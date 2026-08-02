"""Execution coordination context.

An :class:`ExecutionContext` is the single, immutable input the framework uses to
coordinate an execution. It bundles the upstream :class:`OrderResult` (which
carries the order request and route) plus supporting references, so execution
components never access infrastructure directly.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from order_management.context import OrderContext
from order_management.models import OrderResult
from risk.models import RiskDecision
from strategies.signals import TradingSignal

__all__ = ["ExecutionContext"]


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Immutable input for execution coordination.

    Attributes:
        order_result: The order-management result (holds request + route).
        exchange: Neutral exchange label.
        symbol: Instrument to execute.
        order_context: Optional originating order context.
        risk_decision: Optional originating approved risk decision.
        signal: Optional originating trading signal.
        timestamp: When the context was assembled (UTC).
        metadata: Optional read-only extra context.
    """

    order_result: OrderResult
    exchange: str
    symbol: str
    order_context: OrderContext | None = None
    risk_decision: RiskDecision | None = None
    signal: TradingSignal | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
