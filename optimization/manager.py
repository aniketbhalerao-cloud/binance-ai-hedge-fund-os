"""Optimization manager.

:class:`DefaultOptimizationManager` owns the optimization workflow. For each input
it loads the running :class:`~optimization.models.OptimizationRecord` from the
Registry, builds a plan, resolves it, generates recommendations, computes metrics,
builds a **new** immutable record, and writes it back. The whole read-modify-write
is synchronous (the components are pure — no ``await`` inside), so atomicity is
provided by a :class:`threading.Lock`; events are published only after a consistent
update.

Any failure is translated to a framework exception, isolated, published as
:class:`~optimization.events.OptimizationErrorOccurred`, and returned as a FAILED
result — never a leaked internal exception, and never a partial record write. The
framework only proposes: it never applies a recommendation and never modifies a
strategy, agent, or portfolio.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from threading import Lock

from core.logging import LoggerFactory
from events.base import Event
from events.bus import EventBus
from optimization.context import OptimizationContext
from optimization.events import (
    OptimizationCancelled,
    OptimizationCompleted,
    OptimizationErrorOccurred,
    OptimizationEvaluated,
    OptimizationMetricsUpdated,
    OptimizationSnapshotCreated,
    OptimizationStarted,
    PlanCreated,
    RecommendationsGenerated,
)
from optimization.exceptions import OptimizationError
from optimization.interfaces import (
    OptimizationMetricsCalculator,
    OptimizationRegistry,
    Optimizer,
    Planner,
    RecommendationGenerator,
)
from optimization.models import (
    OptimizationRecord,
    OptimizationResult,
    OptimizationResultStatus,
    OptimizationSnapshot,
)
from optimization.state import OptimizationState

__all__ = ["DefaultOptimizationManager"]

_TERMINAL = (
    OptimizationState.COMPLETED,
    OptimizationState.CANCELLED,
    OptimizationState.FAILED,
)


class DefaultOptimizationManager:
    """Coordinates the optimization pipeline over a registry-owned record."""

    def __init__(
        self,
        bus: EventBus,
        registry: OptimizationRegistry,
        planner: Planner,
        optimizer: Optimizer,
        recommendations: RecommendationGenerator,
        metrics: OptimizationMetricsCalculator,
        logger: LoggerFactory | None = None,
    ) -> None:
        self._bus = bus
        self._registry = registry
        self._planner = planner
        self._optimizer = optimizer
        self._recommendations = recommendations
        self._metrics = metrics
        self._log = logger.get_logger("optimization.manager") if logger else None
        self._lock = Lock()

    async def optimize(self, context: OptimizationContext) -> OptimizationResult:
        """Optimize over one input and return a result."""
        optimization_id = context.optimization_id
        events: list[Event] = []
        try:
            result = self._compute(optimization_id, context, events)
        except OptimizationError as exc:
            return await self._fail(optimization_id, str(exc))
        except Exception as exc:  # translate; never leak internals
            return await self._fail(optimization_id, str(exc))

        for event in events:  # publish only after a consistent update
            await self._bus.publish(event)
        return result

    def _compute(
        self,
        optimization_id: str,
        context: OptimizationContext,
        events: list[Event],
    ) -> OptimizationResult:
        events.append(OptimizationStarted(optimization_id=optimization_id))
        now = datetime.now(UTC)
        with self._lock:  # synchronous, atomic read-modify-write
            if self._registry.exists(optimization_id):
                record = self._registry.get(optimization_id)
            else:
                record = _new_record(optimization_id, now)
            if record.state in _TERMINAL:
                raise OptimizationError(
                    f"optimization record {optimization_id!r} is {record.state.value}"
                )

            if context.metadata.get("cancel"):
                cancelled = replace(
                    record, state=OptimizationState.CANCELLED, updated_at=now
                )
                self._registry.register(cancelled)
                events.append(
                    OptimizationCancelled(optimization_id=optimization_id)
                )
                self._info(optimization_id, cancelled, "cancelled")
                return OptimizationResult(
                    status=OptimizationResultStatus.CANCELLED, record=cancelled
                )

            plan = self._planner.plan(context)
            plan = self._optimizer.optimize(plan, context)
            recommendations = self._recommendations.generate(plan, context)

            new_record = replace(
                record,
                state=OptimizationState.OPTIMIZED,
                history=record.history.append(plan),
                plan=plan,
                recommendations=recommendations,
                plan_count=record.plan_count + 1,
                recommendation_count=record.recommendation_count
                + len(recommendations),
                updated_at=now,
            )
            metrics = self._metrics.calculate(new_record)
            snapshot = OptimizationSnapshot(
                record=new_record, metrics=metrics, timestamp=now
            )
            self._registry.register(new_record)

        events.extend(
            [
                PlanCreated(
                    optimization_id=optimization_id, targets=len(plan.targets)
                ),
                OptimizationEvaluated(optimization_id=optimization_id),
                RecommendationsGenerated(
                    optimization_id=optimization_id, count=len(recommendations)
                ),
                OptimizationSnapshotCreated(optimization_id=optimization_id),
                OptimizationMetricsUpdated(optimization_id=optimization_id),
                OptimizationCompleted(optimization_id=optimization_id),
            ]
        )
        self._info(optimization_id, new_record, "optimized")
        return OptimizationResult(
            status=OptimizationResultStatus.SUCCESS,
            record=new_record,
            snapshot=snapshot,
            plan=plan,
            recommendations=recommendations,
            metrics=metrics,
        )

    async def _fail(self, optimization_id: str, message: str) -> OptimizationResult:
        self._error(optimization_id, message)
        await self._bus.publish(
            OptimizationErrorOccurred(
                optimization_id=optimization_id, message=message
            )
        )
        return OptimizationResult(
            status=OptimizationResultStatus.FAILED, errors=(message,)
        )

    def _info(
        self, optimization_id: str, record: OptimizationRecord, status: str
    ) -> None:
        if self._log is not None:
            self._log.info(
                "Optimization update",
                extra={
                    "optimization_id": optimization_id,
                    "status": status,
                    "plans": record.plan_count,
                },
            )

    def _error(self, optimization_id: str, message: str) -> None:
        if self._log is not None:
            self._log.error(
                "Optimization error",
                extra={"optimization_id": optimization_id, "error": message},
            )


def _new_record(optimization_id: str, now: datetime) -> OptimizationRecord:
    return OptimizationRecord(
        id=optimization_id,
        state=OptimizationState.PLANNING,
        created_at=now,
        updated_at=now,
    )
