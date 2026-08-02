"""Risk Framework interfaces.

Protocols only — no implementations. The framework depends on these abstractions
so future rules and policies plug in without modification (Open/Closed).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from risk.context import RiskContext
from risk.models import RiskDecision, RiskResult, RiskViolation

__all__ = [
    "RiskRule",
    "RiskValidator",
    "RiskPolicy",
    "RiskManager",
    "RiskEngine",
]


@runtime_checkable
class RiskRule(Protocol):
    """One independent, stateless risk validation."""

    @property
    def name(self) -> str:
        """Unique rule name."""
        ...

    async def evaluate(self, context: RiskContext) -> RiskViolation | None:
        """Return a violation if the rule fails, else ``None``."""
        ...


@runtime_checkable
class RiskValidator(Protocol):
    """Coordinates execution of the enabled rules and produces a result."""

    def add_rule(self, rule: RiskRule) -> None: ...
    def enable(self, name: str) -> None: ...
    def disable(self, name: str) -> None: ...
    def rules(self) -> list[RiskRule]: ...
    async def validate(self, context: RiskContext) -> RiskResult: ...


@runtime_checkable
class RiskPolicy(Protocol):
    """Maps a :class:`RiskResult` to an approval :class:`RiskDecision`."""

    def decide(self, result: RiskResult, context: RiskContext) -> RiskDecision: ...


@runtime_checkable
class RiskManager(Protocol):
    """Coordinates a full evaluation and publishes risk events."""

    async def evaluate(self, context: RiskContext) -> RiskDecision: ...


@runtime_checkable
class RiskEngine(Protocol):
    """Public entry point coordinating the risk evaluation process."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def evaluate(self, context: RiskContext) -> RiskDecision: ...
