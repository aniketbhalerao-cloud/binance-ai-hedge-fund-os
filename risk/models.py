"""Risk Framework domain models.

Immutable value objects describing risk evaluation inputs/outputs. They carry no
exchange-specific fields and never execute anything — a decision is a *record*,
not an action.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Any

__all__ = [
    "RiskDecisionType",
    "RiskMetadata",
    "RiskViolation",
    "RiskResult",
    "RiskDecision",
    "PositionSizing",
]


class RiskDecisionType(str, Enum):
    """The approval status a risk decision expresses."""

    APPROVED = "approved"
    REJECTED = "rejected"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class RiskMetadata:
    """Immutable, free-form metadata attached to risk models."""

    data: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", MappingProxyType(dict(self.data)))

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


@dataclass(frozen=True, slots=True)
class RiskViolation:
    """A single failed-rule record."""

    rule_name: str
    message: str
    metadata: RiskMetadata = field(default_factory=RiskMetadata)


@dataclass(frozen=True, slots=True)
class RiskResult:
    """The aggregated outcome of running the rules (the validator's product).

    Attributes:
        passed: ``True`` when no rule produced a violation.
        violations: Violations produced by failed rules.
        passed_rules: Names of rules that passed.
        errors: ``(rule_name, message)`` for rules that raised during evaluation.
    """

    passed: bool
    violations: tuple[RiskViolation, ...] = ()
    passed_rules: tuple[str, ...] = ()
    errors: tuple[tuple[str, str], ...] = ()

    @property
    def evaluated_rules(self) -> tuple[str, ...]:
        """Names of every rule that was evaluated (passed, failed, or errored)."""
        failed = tuple(v.rule_name for v in self.violations)
        errored = tuple(name for name, _ in self.errors)
        return self.passed_rules + failed + errored


@dataclass(frozen=True, slots=True)
class RiskDecision:
    """An immutable approval decision (never executes anything).

    Attributes:
        id: Unique decision identifier.
        decision_type: Approved, rejected, or warning.
        timestamp: When the decision was produced (UTC).
        triggered_rules: Names of the rules that drove the decision.
        violations: The violations behind a rejection/warning.
        metadata: Optional decision metadata.
    """

    id: str
    decision_type: RiskDecisionType
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    triggered_rules: tuple[str, ...] = ()
    violations: tuple[RiskViolation, ...] = ()
    metadata: RiskMetadata = field(default_factory=RiskMetadata)

    @property
    def approved(self) -> bool:
        """Return ``True`` when the decision approves the signal."""
        return self.decision_type is RiskDecisionType.APPROVED


@dataclass(frozen=True, slots=True)
class PositionSizing:
    """A sizing recommendation model for future sizing rules to populate.

    Data only — this task computes nothing.
    """

    symbol: str
    max_quantity: Decimal | None = None
    target_notional: Decimal | None = None
    leverage: Decimal | None = None
