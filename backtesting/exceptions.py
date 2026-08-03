"""Backtesting Framework exceptions.

Definitions only. Internal failures are translated into these so no
implementation detail escapes; the manager always returns a
:class:`~backtesting.models.BacktestResult`.
"""

from __future__ import annotations

__all__ = [
    "BacktestError",
    "SimulationError",
    "SchedulerError",
    "MetricsError",
    "HistoryError",
    "RegistryError",
    "BacktestCancelledError",
]


class BacktestError(Exception):
    """Base class for all Backtesting Framework errors."""


class SimulationError(BacktestError):
    """Raised when the simulator fails to produce a fill."""


class SchedulerError(BacktestError):
    """Raised when timeline scheduling fails."""


class MetricsError(BacktestError):
    """Raised when a metrics calculation fails."""


class HistoryError(BacktestError):
    """Raised when a history update fails."""


class RegistryError(BacktestError):
    """Raised when a registry operation fails."""


class BacktestCancelledError(BacktestError):
    """Raised internally to unwind a run that was cancelled."""
