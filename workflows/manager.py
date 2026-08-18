"""Workflow manager.

:class:`DefaultWorkflowManager` owns the workflow orchestration pipeline.
For each input it loads the running
:class:`~workflows.models.WorkflowRecord` from the Registry, collects a
batch, validates and deterministically orders it into a
:class:`~workflows.models.WorkflowPlan`, generates workflow requests,
computes metrics, builds a **new** immutable record, and writes it back. The
whole read-modify-write is synchronous (the components are pure — no
``await`` inside), so atomicity is provided by a :class:`threading.Lock`;
events are published only after a consistent update.

Any failure (collection, planning — including cycle/self-dependency/
missing-dependency/duplicate-identifier/invalid-handoff-target rejection —
or dispatch/metrics) is translated to a framework exception, isolated,
published as :class:`~workflows.events.WorkflowErrorOccurred`, and returned
as a FAILED result — never a leaked internal exception, and never a partial
registry write: the registry is only ever updated with a fully-built new
record, after every stage (including metrics) has already succeeded. The
manager never executes a step, triggers an Agent, or calls another
framework's manager method.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from threading import Lock

from core.logging import LoggerFactory
from events.base import Event
from events.bus import EventBus
from workflows.context import WorkflowContext
from workflows.events import (
    RequestsDispatched,
    StepsCollected,
    WorkflowCancelled,
    WorkflowCompleted,
    WorkflowErrorOccurred,
    WorkflowMetricsUpdated,
    WorkflowPlanned,
    WorkflowSnapshotCreated,
    WorkflowStarted,
)
from workflows.exceptions import WorkflowError
from workflows.interfaces import (
    Collector,
    Dispatcher,
    Planner,
    WorkflowMetricsCalculator,
    WorkflowRegistry,
)
from workflows.models import (
    WorkflowRecord,
    WorkflowResult,
    WorkflowResultStatus,
    WorkflowSnapshot,
)
from workflows.state import WorkflowState

__all__ = ["DefaultWorkflowManager"]

_TERMINAL = (WorkflowState.COMPLETED, WorkflowState.CANCELLED, WorkflowState.FAILED)


class DefaultWorkflowManager:
    """Coordinates the workflow pipeline over a registry-owned record."""

    def __init__(
        self,
        bus: EventBus,
        registry: WorkflowRegistry,
        collector: Collector,
        planner: Planner,
        dispatcher: Dispatcher,
        metrics: WorkflowMetricsCalculator,
        logger: LoggerFactory | None = None,
    ) -> None:
        self._bus = bus
        self._registry = registry
        self._collector = collector
        self._planner = planner
        self._dispatcher = dispatcher
        self._metrics = metrics
        self._log = logger.get_logger("workflows.manager") if logger else None
        self._lock = Lock()

    async def compose(self, context: WorkflowContext) -> WorkflowResult:
        """Compose one input and return a result."""
        workflow_id = context.workflow_id
        events: list[Event] = []
        try:
            result = self._compute(workflow_id, context, events)
        except WorkflowError as exc:
            return await self._fail(workflow_id, str(exc))
        except Exception as exc:  # translate; never leak internals
            return await self._fail(workflow_id, str(exc))

        for event in events:  # publish only after a consistent update
            await self._bus.publish(event)
        return result

    def _compute(
        self, workflow_id: str, context: WorkflowContext, events: list[Event]
    ) -> WorkflowResult:
        events.append(WorkflowStarted(workflow_id=workflow_id))
        now = datetime.now(UTC)
        with self._lock:  # synchronous, atomic read-modify-write
            if self._registry.exists(workflow_id):
                record = self._registry.get(workflow_id)
            else:
                record = _new_record(workflow_id, now)
            if record.state in _TERMINAL:
                raise WorkflowError(
                    f"workflow record {workflow_id!r} is {record.state.value}"
                )

            if context.metadata.get("cancel"):
                cancelled = replace(
                    record, state=WorkflowState.CANCELLED, updated_at=now
                )
                self._registry.register(cancelled)
                events.append(WorkflowCancelled(workflow_id=workflow_id))
                self._info(workflow_id, cancelled, "cancelled")
                return WorkflowResult(
                    status=WorkflowResultStatus.CANCELLED, record=cancelled
                )

            batch = self._collector.collect(context)
            plan = self._planner.plan(batch, context)
            requests = self._dispatcher.dispatch(plan, context)

            step_count = sum(len(d.steps) for d in batch.definitions)
            new_record = replace(
                record,
                state=WorkflowState.PLANNED,
                history=record.history.append(batch),
                batch=batch,
                plan=plan,
                requests=requests,
                definition_count=record.definition_count + len(batch.definitions),
                step_count=record.step_count + step_count,
                request_count=record.request_count + len(requests),
                updated_at=now,
            )
            metrics = self._metrics.calculate(new_record)
            snapshot = WorkflowSnapshot(
                record=new_record, metrics=metrics, timestamp=now
            )
            self._registry.register(new_record)

        events.extend(
            [
                StepsCollected(workflow_id=workflow_id, steps=step_count),
                WorkflowPlanned(workflow_id=workflow_id),
                RequestsDispatched(workflow_id=workflow_id, count=len(requests)),
                WorkflowSnapshotCreated(workflow_id=workflow_id),
                WorkflowMetricsUpdated(workflow_id=workflow_id),
                WorkflowCompleted(workflow_id=workflow_id),
            ]
        )
        self._info(workflow_id, new_record, "composed")
        return WorkflowResult(
            status=WorkflowResultStatus.SUCCESS,
            record=new_record,
            snapshot=snapshot,
            batch=batch,
            plan=plan,
            requests=requests,
            metrics=metrics,
        )

    async def _fail(self, workflow_id: str, message: str) -> WorkflowResult:
        self._error(workflow_id, message)
        await self._bus.publish(
            WorkflowErrorOccurred(workflow_id=workflow_id, message=message)
        )
        return WorkflowResult(status=WorkflowResultStatus.FAILED, errors=(message,))

    def _info(self, workflow_id: str, record: WorkflowRecord, status: str) -> None:
        if self._log is not None:
            self._log.info(
                "Workflow update",
                extra={
                    "workflow_id": workflow_id,
                    "status": status,
                    "steps": record.step_count,
                },
            )

    def _error(self, workflow_id: str, message: str) -> None:
        if self._log is not None:
            self._log.error(
                "Workflow error", extra={"workflow_id": workflow_id, "error": message}
            )


def _new_record(workflow_id: str, now: datetime) -> WorkflowRecord:
    return WorkflowRecord(
        id=workflow_id,
        state=WorkflowState.COLLECTING,
        created_at=now,
        updated_at=now,
    )
