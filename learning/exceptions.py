"""Learning Framework exceptions.

Definitions only. Internal failures are translated into these so no
implementation detail escapes; the manager always returns a
:class:`~learning.models.LearningResult`.
"""

from __future__ import annotations

__all__ = [
    "LearningError",
    "JournalError",
    "EvaluationError",
    "FeedbackError",
    "MetricsError",
    "RegistryError",
    "LearningCancelledError",
]


class LearningError(Exception):
    """Base class for all Learning Framework errors."""


class JournalError(LearningError):
    """Raised when recording an outcome fails."""


class EvaluationError(LearningError):
    """Raised when an evaluation fails."""


class FeedbackError(LearningError):
    """Raised when feedback generation fails."""


class MetricsError(LearningError):
    """Raised when a metrics calculation fails."""


class RegistryError(LearningError):
    """Raised when a registry operation fails."""


class LearningCancelledError(LearningError):
    """Raised internally to unwind a learning session that was cancelled."""
