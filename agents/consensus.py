"""Consensus resolution.

:class:`DefaultConsensus` aggregates agent opinions into a single
:class:`~agents.models.ConsensusResult`: a confidence- and role-weighted
directional vote, a risk veto, and an agreement rate. It is stateless and pure —
it holds no agent logic of its own beyond aggregation — and all arithmetic is
:class:`~decimal.Decimal`.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from agents.exceptions import ConsensusError
from agents.models import AgentOpinion, ConsensusResult, DecisionParameters
from strategies.signals import SignalDirection

__all__ = ["DefaultConsensus"]

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


class DefaultConsensus:
    """Stateless weighted-vote consensus with a risk veto."""

    def resolve(
        self,
        opinions: Sequence[AgentOpinion],
        parameters: DecisionParameters,
    ) -> ConsensusResult:
        """Return the :class:`ConsensusResult` for ``opinions``.

        Raises:
            ConsensusError: If an unexpected failure occurs.
        """
        try:
            return self._resolve(opinions, parameters)
        except ConsensusError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise ConsensusError(str(exc)) from exc

    def _resolve(
        self,
        opinions: Sequence[AgentOpinion],
        parameters: DecisionParameters,
    ) -> ConsensusResult:
        buy = sell = hold = _ZERO
        for op in opinions:
            weight = parameters.weight_for(op.role) * op.confidence
            bucket = _bucket(op.direction)
            if bucket is SignalDirection.BUY:
                buy += weight
            elif bucket is SignalDirection.SELL:
                sell += weight
            else:
                hold += weight

        total = buy + sell + hold
        if buy > sell and buy >= hold:
            direction, winning = SignalDirection.BUY, buy
        elif sell > buy and sell >= hold:
            direction, winning = SignalDirection.SELL, sell
        else:
            direction, winning = SignalDirection.HOLD, hold

        confidence = winning / total if total > _ZERO else _ZERO
        vetoed = parameters.risk_veto and any(not op.approve for op in opinions)
        approved = (
            not vetoed
            and direction is not SignalDirection.HOLD
            and confidence >= parameters.min_confidence
        )

        agree = sum(1 for op in opinions if _bucket(op.direction) is direction)
        agreement_rate = (
            Decimal(agree) / Decimal(len(opinions)) if opinions else _ZERO
        )

        return ConsensusResult(
            direction=direction,
            confidence=confidence,
            approved=approved,
            agreement_rate=agreement_rate,
            buy_weight=buy,
            sell_weight=sell,
            hold_weight=hold,
        )
