"""Backtest history.

:class:`DefaultBacktestHistory` appends simulation steps to an append-only
:class:`~backtesting.models.BacktestHistory`. It is stateless — it returns a new
history and never mutates existing records, so the replay timeline is immutable
and can never be rewritten.
"""

from __future__ import annotations

from backtesting.models import BacktestHistory, SimulationStep

__all__ = ["DefaultBacktestHistory"]


class DefaultBacktestHistory:
    """Stateless, append-only simulation-step history service."""

    def append(
        self, history: BacktestHistory, step: SimulationStep
    ) -> BacktestHistory:
        """Return a new history with ``step`` appended."""
        return history.append(step)
