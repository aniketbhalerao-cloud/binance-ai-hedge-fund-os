"""Performance analysis status.

Performance analysis is a single-shot, read-only computation (not a long-lived
lifecycle FSM like positions or trades), so this module carries only the coarse
outcome status. No transition table is needed.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["PerformanceStatus"]


class PerformanceStatus(str, Enum):
    """Coarse outcome of a performance analysis run."""

    COMPLETED = "completed"
    FAILED = "failed"
