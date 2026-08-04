"""Decision metrics.

:class:`DefaultDecisionMetrics` derives aggregate metrics from a set of resolved
decisions: counts, approval / rejection / agreement rates, average confidence,
directional breakdown, and average agent participation. It is stateless and pure
— metrics are always derived from the decisions passed in, never stored — and all
arithmetic is :class:`~decimal.Decimal`.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from agents.exceptions import MetricsError
from agents.models import Decision, DecisionMetrics
from strategies.signals import SignalDirection

__all__ = ["DefaultDecisionMetrics"]

_ZERO = Decimal("0")


def _bucket(direction: SignalDirection) -> SignalDirection:
    if direction in (SignalDirection.BUY, SignalDirection.INCREASE):
        return SignalDirection.BUY
    if direction in (
        SignalDirection.SELL,
        SignalDirection.CLOSE,
        SignalDirection.REDUCE,
    ):
        return SignalDirection.SELL
    return SignalDirection.HOLD


class DefaultDecisionMetrics:
    """Stateless metrics derived from a set of decisions."""

    def calculate(self, decisions: Sequence[Decision]) -> DecisionMetrics:
        """Return :class:`DecisionMetrics` for ``decisions``.

        Raises:
            MetricsError: If an unexpected failure occurs.
        """
        try:
            return self._calculate(decisions)
        except MetricsError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise MetricsError(str(exc)) from exc

    def _calculate(self, decisions: Sequence[Decision]) -> DecisionMetrics:
        total = len(decisions)
        if total == 0:
            return DecisionMetrics()

        approved = sum(1 for d in decisions if d.approved)
        buy = sum(1 for d in decisions if _bucket(d.direction) is SignalDirection.BUY)
        sell = sum(1 for d in decisions if _bucket(d.direction) is SignalDirection.SELL)
        hold = total - buy - sell
        total_dec = Decimal(total)

        avg_confidence = sum((d.confidence for d in decisions), _ZERO) / total_dec
        avg_agents = (
            Decimal(sum(len(d.opinions) for d in decisions)) / total_dec
        )
        agreement = sum((_decision_agreement(d) for d in decisions), _ZERO) / total_dec

        return DecisionMetrics(
            total_decisions=total,
            approval_rate=Decimal(approved) / total_dec,
            rejection_rate=Decimal(total - approved) / total_dec,
            agreement_rate=agreement,
            average_confidence=avg_confidence,
            buy_decisions=buy,
            sell_decisions=sell,
            hold_decisions=hold,
            average_agent_count=avg_agents,
        )


def _decision_agreement(decision: Decision) -> Decimal:
    """Fraction of a decision's opinions that agree with its final direction."""
    if not decision.opinions:
        return _ZERO
    agree = sum(
        1 for op in decision.opinions if _bucket(op.direction) is decision.direction
    )
    return Decimal(agree) / Decimal(len(decision.opinions))
