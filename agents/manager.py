"""AI decision manager.

:class:`DefaultDecisionManager` owns the decision workflow. It gathers opinions
from the registered analyst agents, hands them to the CEO agent for arbitration
(via an enriched context), resolves consensus, builds an immutable
:class:`~agents.models.Decision`, appends it to the decision history, and computes
metrics. The whole read-modify-write of the durable decision history spans
``await`` points (agents are async), so atomicity is provided by an
:class:`asyncio.Lock` that serializes decision runs; events are published only
after a consistent decision.

Any failure is translated to a framework exception, isolated, published as
:class:`~agents.events.DecisionErrorOccurred` (and
:class:`~agents.events.AgentErrorOccurred` for an agent failure), and returned as
a FAILED result. A *rejection* is a first-class non-failure outcome (a resolved
decision with ``approved=False``). The framework never calls a model, provider, or
network client.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from agents.context import DecisionContext
from agents.events import (
    AgentErrorOccurred,
    AgentEvaluated,
    ConsensusReached,
    DecisionErrorOccurred,
    DecisionMade,
    DecisionMetricsUpdated,
    DecisionRejected,
    DecisionRequested,
    DecisionSnapshotCreated,
)
from agents.exceptions import AgentError, DecisionError
from agents.interfaces import (
    AgentRegistry,
    ConsensusResolver,
    DecisionHistoryService,
    DecisionMetricsCalculator,
)
from agents.models import (
    AgentOpinion,
    AgentRole,
    Decision,
    DecisionHistory,
    DecisionResult,
    DecisionResultStatus,
    DecisionSnapshot,
    DecisionSummary,
)
from core.logging import LoggerFactory
from events.base import Event
from events.bus import EventBus
from strategies.signals import SignalDirection

__all__ = ["DefaultDecisionManager"]

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


class DefaultDecisionManager:
    """Coordinates the decision pipeline over the registered agents."""

    def __init__(
        self,
        bus: EventBus,
        registry: AgentRegistry,
        consensus: ConsensusResolver,
        metrics: DecisionMetricsCalculator,
        history: DecisionHistoryService,
        logger: LoggerFactory | None = None,
    ) -> None:
        self._bus = bus
        self._registry = registry
        self._consensus = consensus
        self._metrics = metrics
        self._history = history
        self._decisions = DecisionHistory()
        self._log = logger.get_logger("agents.manager") if logger else None
        self._lock = asyncio.Lock()

    async def decide(self, context: DecisionContext) -> DecisionResult:
        """Run one decision and return a result."""
        decision_id = uuid.uuid4().hex
        events: list[Event] = []
        try:
            result = await self._decide(decision_id, context, events)
        except AgentError as exc:
            role = exc.role.value if isinstance(exc.role, AgentRole) else None
            return await self._fail(decision_id, str(exc), role=role)
        except DecisionError as exc:
            return await self._fail(decision_id, str(exc))
        except Exception as exc:  # translate; never leak internals
            return await self._fail(decision_id, str(exc))

        for event in events:  # publish only after a consistent decision
            await self._bus.publish(event)
        return result

    async def _decide(
        self, decision_id: str, context: DecisionContext, events: list[Event]
    ) -> DecisionResult:
        events.append(
            DecisionRequested(decision_id=decision_id, symbol=context.symbol)
        )
        async with self._lock:  # atomic decision + history update
            now = datetime.now(UTC)
            agents = self._registry.list()
            analysts = [a for a in agents if a.role is not AgentRole.CEO]
            ceos = [a for a in agents if a.role is AgentRole.CEO]

            opinions: list[AgentOpinion] = []
            for agent in analysts:
                opinions.append(await self._evaluate(agent, context))
                events.append(
                    AgentEvaluated(decision_id=decision_id, role=agent.role.value)
                )
            if ceos:
                enriched = context.with_opinions(opinions)
                opinions.append(await self._evaluate(ceos[0], enriched))
                events.append(
                    AgentEvaluated(decision_id=decision_id, role=AgentRole.CEO.value)
                )

            consensus = self._consensus.resolve(opinions, context.parameters)
            events.append(ConsensusReached(decision_id=decision_id))

            decision = Decision(
                id=decision_id,
                symbol=context.symbol,
                direction=consensus.direction,
                confidence=consensus.confidence,
                approved=consensus.approved,
                opinions=tuple(opinions),
                timestamp=now,
            )
            self._decisions = self._history.append(self._decisions, decision)
            metrics = self._metrics.calculate(self._decisions.decisions)
            snapshot = DecisionSnapshot(
                decision=decision,
                summary=_summary(
                    opinions, consensus.agreement_rate, consensus.approved
                ),
                timestamp=now,
            )

        if decision.approved:
            events.append(DecisionMade(decision_id=decision_id))
        else:
            events.append(DecisionRejected(decision_id=decision_id))
        events.append(DecisionSnapshotCreated(decision_id=decision_id))
        events.append(DecisionMetricsUpdated(decision_id=decision_id))
        self._info(decision_id, decision)
        return DecisionResult(
            status=DecisionResultStatus.SUCCESS,
            decision=decision,
            snapshot=snapshot,
            metrics=metrics,
        )

    async def _evaluate(self, agent: object, context: DecisionContext) -> AgentOpinion:
        try:
            return await agent.evaluate(context)  # type: ignore[attr-defined]
        except Exception as exc:
            role = getattr(agent, "role", None)
            raise AgentError(f"agent {role} failed: {exc}", role=role) from exc

    async def _fail(
        self, decision_id: str, message: str, role: str | None = None
    ) -> DecisionResult:
        self._error(decision_id, message)
        if role is not None:
            await self._bus.publish(
                AgentErrorOccurred(
                    decision_id=decision_id, role=role, message=message
                )
            )
        await self._bus.publish(
            DecisionErrorOccurred(decision_id=decision_id, message=message)
        )
        return DecisionResult(
            status=DecisionResultStatus.FAILED, errors=(message,)
        )

    def _info(self, decision_id: str, decision: Decision) -> None:
        if self._log is not None:
            self._log.info(
                "Decision resolved",
                extra={
                    "decision_id": decision_id,
                    "direction": decision.direction.value,
                    "approved": decision.approved,
                },
            )

    def _error(self, decision_id: str, message: str) -> None:
        if self._log is not None:
            self._log.error(
                "Decision error",
                extra={"decision_id": decision_id, "error": message},
            )


def _summary(
    opinions: list[AgentOpinion], agreement_rate: Decimal, approved: bool
) -> DecisionSummary:
    buy = sum(1 for op in opinions if _bucket(op.direction) is SignalDirection.BUY)
    sell = sum(1 for op in opinions if _bucket(op.direction) is SignalDirection.SELL)
    hold = len(opinions) - buy - sell
    avg_confidence = (
        sum((op.confidence for op in opinions), _ZERO) / Decimal(len(opinions))
        if opinions
        else _ZERO
    )
    return DecisionSummary(
        agent_count=len(opinions),
        buy_votes=buy,
        sell_votes=sell,
        hold_votes=hold,
        approved=approved,
        average_confidence=avg_confidence,
        agreement_rate=agreement_rate,
    )
