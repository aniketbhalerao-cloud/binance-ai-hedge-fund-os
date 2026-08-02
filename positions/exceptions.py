"""Position Framework exceptions.

Definitions only. Internal failures are translated into these so no
implementation detail escapes; the framework always returns a
:class:`~positions.models.PositionResult`.
"""

from __future__ import annotations

__all__ = [
    "PositionError",
    "PositionNotFoundError",
    "PositionClosedError",
    "InvalidPositionStateError",
    "PositionTrackerError",
    "PositionCalculationError",
    "PositionHistoryError",
    "PositionMetricsError",
]


class PositionError(Exception):
    """Base class for all Position Framework errors."""


class PositionNotFoundError(PositionError):
    """Raised when a position id is not registered."""


class PositionClosedError(PositionError):
    """Raised when updating a closed position."""


class InvalidPositionStateError(PositionError):
    """Raised on an illegal position state transition."""


class PositionTrackerError(PositionError):
    """Raised when position tracking fails."""


class PositionCalculationError(PositionError):
    """Raised when a position calculation fails."""


class PositionHistoryError(PositionError):
    """Raised when a history update fails."""


class PositionMetricsError(PositionError):
    """Raised when a metrics calculation fails."""
