"""Optimization Framework exceptions.

Definitions only. Internal failures are translated into these so no
implementation detail escapes; the manager always returns an
:class:`~optimization.models.OptimizationResult`.
"""

from __future__ import annotations

__all__ = [
    "OptimizationError",
    "PlanningError",
    "OptimizerError",
    "RecommendationError",
    "MetricsError",
    "RegistryError",
    "OptimizationCancelledError",
]


class OptimizationError(Exception):
    """Base class for all Optimization Framework errors."""


class PlanningError(OptimizationError):
    """Raised when building an optimization plan fails."""


class OptimizerError(OptimizationError):
    """Raised when optimizing a plan fails."""


class RecommendationError(OptimizationError):
    """Raised when recommendation generation fails."""


class MetricsError(OptimizationError):
    """Raised when a metrics calculation fails."""


class RegistryError(OptimizationError):
    """Raised when a registry operation fails."""


class OptimizationCancelledError(OptimizationError):
    """Raised internally to unwind an optimization session that was cancelled."""
