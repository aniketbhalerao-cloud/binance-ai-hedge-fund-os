"""Learning manager.

:class:`DefaultLearningManager` owns the learning workflow. For each completed
outcome it loads the running :class:`~learning.models.LearningRecord` from the
Registry, records the outcome in the journal, re-derives strategy and agent
evaluations, generates deterministic feedback, computes metrics, builds a **new**
immutable record, and writes it back. The whole read-modify-write is synchronous
(the calculators are pure — no ``await`` inside), so atomicity is provided by a
:class:`threading.Lock`; events are published only after a consistent update.

Any failure is translated to a framework exception, isolated, published as
:class:`~learning.events.LearningErrorOccurred`, and returned as a FAILED result —
never a leaked internal exception, and never a partial record write. The framework
never trains a model, makes a network call, or uses an external ML library.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from threading import Lock

from core.logging import LoggerFactory
from events.base import Event
from events.bus import EventBus
from learning.context import LearningContext
from learning.events import (
    AgentEvaluated,
    FeedbackGenerated,
    LearningCancelled,
    LearningCompleted,
    LearningErrorOccurred,
    LearningMetricsUpdated,
    LearningSnapshotCreated,
    LearningStarted,
    OutcomeRecorded,
    StrategyEvaluated,
)
from learning.exceptions import LearningError
from learning.interfaces import (
    Evaluator,
    FeedbackGenerator,
    Journal,
    LearningMetricsCalculator,
    LearningRegistry,
)
from learning.models import (
    LearningRecord,
    LearningResult,
    LearningResultStatus,
    LearningSnapshot,
)
from learning.state import LearningState

__all__ = ["DefaultLearningManager"]

_TERMINAL = (
    LearningState.COMPLETED,
    LearningState.CANCELLED,
    LearningState.FAILED,
)


class DefaultLearningManager:
    """Coordinates the learning pipeline over a registry-owned record."""

    def __init__(
        self,
        bus: EventBus,
        registry: LearningRegistry,
        journal: Journal,
        evaluator: Evaluator,
        feedback: FeedbackGenerator,
        metrics: LearningMetricsCalculator,
        logger: LoggerFactory | None = None,
    ) -> None:
        self._bus = bus
        self._registry = registry
        self._journal = journal
        self._evaluator = evaluator
        self._feedback = feedback
        self._metrics = metrics
        self._log = logger.get_logger("learning.manager") if logger else None
        self._lock = Lock()

    async def learn(self, context: LearningContext) -> LearningResult:
        """Learn from one outcome and return a result."""
        learning_id = context.learning_id
        events: list[Event] = []
        try:
            result = self._compute(learning_id, context, events)
        except LearningError as exc:
            return await self._fail(learning_id, str(exc))
        except Exception as exc:  # translate; never leak internals
            return await self._fail(learning_id, str(exc))

        for event in events:  # publish only after a consistent update
            await self._bus.publish(event)
        return result

    def _compute(
        self, learning_id: str, context: LearningContext, events: list[Event]
    ) -> LearningResult:
        events.append(LearningStarted(learning_id=learning_id))
        now = datetime.now(UTC)
        with self._lock:  # synchronous, atomic read-modify-write
            if self._registry.exists(learning_id):
                record = self._registry.get(learning_id)
            else:
                record = _new_record(learning_id, now)
            if record.state in _TERMINAL:
                raise LearningError(
                    f"learning record {learning_id!r} is {record.state.value}"
                )

            if context.metadata.get("cancel"):
                cancelled = replace(
                    record, state=LearningState.CANCELLED, updated_at=now
                )
                self._registry.register(cancelled)
                events.append(LearningCancelled(learning_id=learning_id))
                self._info(learning_id, cancelled, "cancelled")
                return LearningResult(
                    status=LearningResultStatus.CANCELLED, record=cancelled
                )

            outcome = context.to_outcome(now)
            history = self._journal.record(record.history, outcome)
            strategies = self._evaluator.evaluate_strategies(history.entries)
            agents = self._evaluator.evaluate_agents(history.entries)
            feedback = self._feedback.generate(strategies, agents, context.parameters)

            new_record = replace(
                record,
                state=LearningState.EVALUATED,
                history=history,
                strategy_evaluations=strategies,
                agent_evaluations=agents,
                feedback=feedback,
                outcome_count=record.outcome_count + 1,
                updated_at=now,
            )
            metrics = self._metrics.calculate(new_record)
            snapshot = LearningSnapshot(
                record=new_record, metrics=metrics, timestamp=now
            )
            self._registry.register(new_record)

        events.extend(
            [
                OutcomeRecorded(learning_id=learning_id),
                StrategyEvaluated(learning_id=learning_id),
                AgentEvaluated(learning_id=learning_id),
                FeedbackGenerated(learning_id=learning_id, count=len(feedback)),
                LearningSnapshotCreated(learning_id=learning_id),
                LearningMetricsUpdated(learning_id=learning_id),
                LearningCompleted(learning_id=learning_id),
            ]
        )
        self._info(learning_id, new_record, "learned")
        return LearningResult(
            status=LearningResultStatus.SUCCESS,
            record=new_record,
            snapshot=snapshot,
            feedback=feedback,
            metrics=metrics,
        )

    async def _fail(self, learning_id: str, message: str) -> LearningResult:
        self._error(learning_id, message)
        await self._bus.publish(
            LearningErrorOccurred(learning_id=learning_id, message=message)
        )
        return LearningResult(
            status=LearningResultStatus.FAILED, errors=(message,)
        )

    def _info(self, learning_id: str, record: LearningRecord, status: str) -> None:
        if self._log is not None:
            self._log.info(
                "Learning update",
                extra={
                    "learning_id": learning_id,
                    "status": status,
                    "outcomes": record.outcome_count,
                },
            )

    def _error(self, learning_id: str, message: str) -> None:
        if self._log is not None:
            self._log.error(
                "Learning error",
                extra={"learning_id": learning_id, "error": message},
            )


def _new_record(learning_id: str, now: datetime) -> LearningRecord:
    return LearningRecord(
        id=learning_id,
        state=LearningState.RECORDING,
        created_at=now,
        updated_at=now,
    )
