"""Risk Framework exceptions.

Definitions only — no handling logic. These isolate risk failures so a single
misbehaving rule never crashes the framework.
"""

from __future__ import annotations

__all__ = [
    "RiskError",
    "RiskValidationError",
    "RiskRuleError",
    "RiskEngineError",
    "InvalidRiskContext",
    "DuplicateRiskRule",
]


class RiskError(Exception):
    """Base class for all Risk Framework errors."""


class RiskValidationError(RiskError):
    """Raised when validation cannot be performed."""


class RiskRuleError(RiskError):
    """Raised when a rule fails in a way that must surface to the caller."""


class RiskEngineError(RiskError):
    """Raised when the risk engine fails to coordinate an evaluation."""


class InvalidRiskContext(RiskError):
    """Raised when a :class:`~risk.context.RiskContext` is missing/invalid."""


class DuplicateRiskRule(RiskError):
    """Raised when registering a rule whose name already exists."""
