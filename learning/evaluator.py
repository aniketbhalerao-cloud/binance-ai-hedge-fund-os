"""Learning evaluator.

:class:`DefaultEvaluator` derives per-strategy and per-agent evaluations from the
journal: sample counts, win/loss counts, win rate, total and average P&L, and a
deterministic score (expectancy — average realized P&L per outcome). This is how
"model benchmarking" is realized — scoring agents by their realized outcomes, with
no machine-learning model, training, or network involved.

Stateless and pure: it reads only the journal, and all arithmetic is
:class:`~decimal.Decimal`.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from learning.exceptions import EvaluationError
from learning.models import (
    AgentEvaluation,
    JournalEntry,
    StrategyEvaluation,
)

__all__ = ["DefaultEvaluator"]

_ZERO = Decimal("0")


class _Tally:
    __slots__ = ("samples", "wins", "total_pnl")

    def __init__(self) -> None:
        self.samples = 0
        self.wins = 0
        self.total_pnl = _ZERO


class DefaultEvaluator:
    """Stateless strategy and agent evaluation from the journal."""

    def evaluate_strategies(
        self, entries: Sequence[JournalEntry]
    ) -> tuple[StrategyEvaluation, ...]:
        """Return one :class:`StrategyEvaluation` per strategy in the journal."""
        try:
            tallies = self._group(entries, key=lambda o: o.strategy_name)
            return tuple(
                StrategyEvaluation(strategy_name=name, **_figures(tally))
                for name, tally in sorted(tallies.items())
            )
        except EvaluationError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise EvaluationError(str(exc)) from exc

    def evaluate_agents(
        self, entries: Sequence[JournalEntry]
    ) -> tuple[AgentEvaluation, ...]:
        """Return one :class:`AgentEvaluation` per agent role in the journal."""
        try:
            tallies = self._group(entries, key=lambda o: o.agent_role)
            return tuple(
                AgentEvaluation(role=role, **_figures(tally))
                for role, tally in sorted(tallies.items(), key=lambda kv: kv[0].value)
            )
        except EvaluationError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise EvaluationError(str(exc)) from exc

    @staticmethod
    def _group(
        entries: Sequence[JournalEntry], key: object
    ) -> dict:
        tallies: dict = {}
        for entry in entries:
            outcome = entry.outcome
            k = key(outcome)  # type: ignore[operator]
            tally = tallies.get(k)
            if tally is None:
                tally = _Tally()
                tallies[k] = tally
            tally.samples += 1
            if outcome.won:
                tally.wins += 1
            tally.total_pnl += outcome.realized_pnl
        return tallies


def _figures(tally: _Tally) -> dict:
    samples = tally.samples
    if samples == 0:
        return {
            "samples": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": _ZERO,
            "total_pnl": _ZERO,
            "average_pnl": _ZERO,
            "score": _ZERO,
        }
    n = Decimal(samples)
    average_pnl = tally.total_pnl / n
    return {
        "samples": samples,
        "wins": tally.wins,
        "losses": samples - tally.wins,
        "win_rate": Decimal(tally.wins) / n,
        "total_pnl": tally.total_pnl,
        "average_pnl": average_pnl,
        "score": average_pnl,
    }
