"""Performance Analytics Framework exceptions.

Definitions only. Internal failures are translated into these so no
implementation detail escapes; the manager always returns a
:class:`~performance.models.PerformanceResult`.
"""

from __future__ import annotations

__all__ = [
    "PerformanceError",
    "ReturnsCalculationError",
    "RiskCalculationError",
    "StatisticsCalculationError",
    "BenchmarkCalculationError",
    "PerformanceRegistryError",
    "DuplicatePerformanceError",
    "PerformanceNotFoundError",
]


class PerformanceError(Exception):
    """Base class for all Performance Framework errors."""


class ReturnsCalculationError(PerformanceError):
    """Raised when the returns calculation fails."""


class RiskCalculationError(PerformanceError):
    """Raised when the risk calculation fails."""


class StatisticsCalculationError(PerformanceError):
    """Raised when the statistics calculation fails."""


class BenchmarkCalculationError(PerformanceError):
    """Raised when the benchmark comparison fails."""


class PerformanceRegistryError(PerformanceError):
    """Raised when a registry operation fails."""


class DuplicatePerformanceError(PerformanceRegistryError):
    """Raised when registering a snapshot id that already exists."""


class PerformanceNotFoundError(PerformanceRegistryError):
    """Raised when a snapshot id is not registered."""
