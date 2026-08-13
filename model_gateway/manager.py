"""Model Gateway manager.

:class:`DefaultModelGatewayManager` owns the model gateway workflow. For
each input it loads the running
:class:`~model_gateway.models.ModelInvocationRecord` from the Registry,
collects a batch, plans it, routes providers and generates model invocation
requests, computes metrics, builds a **new** immutable record, and writes it
back. The whole read-modify-write is synchronous (the components are pure —
no ``await`` inside), so atomicity is provided by a :class:`threading.Lock`;
events are published only after a consistent update.

Any failure (collection, planning, dispatch/routing, or metrics) is
translated to a framework exception, isolated, published as
:class:`~model_gateway.events.ModelGatewayErrorOccurred`, and returned as a
FAILED result — never a leaked internal exception, and never a partial
registry write: the registry is only ever updated with a fully-built new
record, after every stage (including metrics) has already succeeded. The
framework only plans and routes domain objects: it never calls an AI
provider, imports a provider SDK, performs model inference, computes an
embedding, accesses a vector database, makes a network request, handles or
stores an API key, writes to a database, or writes a file, and never
modifies a strategy, agent, learning, optimization, or portfolio state.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from threading import Lock

from core.logging import LoggerFactory
from events.base import Event
from events.bus import EventBus
from model_gateway.context import ModelGatewayContext
from model_gateway.events import (
    InvocationsCollected,
    InvocationsPlanned,
    ModelGatewayCancelled,
    ModelGatewayCompleted,
    ModelGatewayErrorOccurred,
    ModelGatewayMetricsUpdated,
    ModelGatewaySnapshotCreated,
    ModelGatewayStarted,
    RequestsDispatched,
)
from model_gateway.exceptions import ModelGatewayError
from model_gateway.interfaces import (
    Collector,
    Dispatcher,
    ModelGatewayMetricsCalculator,
    ModelGatewayRegistry,
    Planner,
)
from model_gateway.models import (
    ModelGatewayResult,
    ModelGatewayResultStatus,
    ModelGatewaySnapshot,
    ModelInvocationRecord,
)
from model_gateway.state import ModelGatewayState

__all__ = ["DefaultModelGatewayManager"]

_TERMINAL = (
    ModelGatewayState.COMPLETED,
    ModelGatewayState.CANCELLED,
    ModelGatewayState.FAILED,
)


class DefaultModelGatewayManager:
    """Coordinates the model gateway pipeline over a registry-owned record."""

    def __init__(
        self,
        bus: EventBus,
        registry: ModelGatewayRegistry,
        collector: Collector,
        planner: Planner,
        dispatcher: Dispatcher,
        metrics: ModelGatewayMetricsCalculator,
        logger: LoggerFactory | None = None,
    ) -> None:
        self._bus = bus
        self._registry = registry
        self._collector = collector
        self._planner = planner
        self._dispatcher = dispatcher
        self._metrics = metrics
        self._log = logger.get_logger("model_gateway.manager") if logger else None
        self._lock = Lock()

    async def invoke(self, context: ModelGatewayContext) -> ModelGatewayResult:
        """Invoke one input and return a result."""
        model_gateway_id = context.model_gateway_id
        events: list[Event] = []
        try:
            result = self._compute(model_gateway_id, context, events)
        except ModelGatewayError as exc:
            return await self._fail(model_gateway_id, str(exc))
        except Exception as exc:  # translate; never leak internals
            return await self._fail(model_gateway_id, str(exc))

        for event in events:  # publish only after a consistent update
            await self._bus.publish(event)
        return result

    def _compute(
        self,
        model_gateway_id: str,
        context: ModelGatewayContext,
        events: list[Event],
    ) -> ModelGatewayResult:
        events.append(ModelGatewayStarted(model_gateway_id=model_gateway_id))
        now = datetime.now(UTC)
        with self._lock:  # synchronous, atomic read-modify-write
            if self._registry.exists(model_gateway_id):
                record = self._registry.get(model_gateway_id)
            else:
                record = _new_record(model_gateway_id, now)
            if record.state in _TERMINAL:
                raise ModelGatewayError(
                    f"model gateway record {model_gateway_id!r} is "
                    f"{record.state.value}"
                )

            if context.metadata.get("cancel"):
                cancelled = replace(
                    record, state=ModelGatewayState.CANCELLED, updated_at=now
                )
                self._registry.register(cancelled)
                events.append(
                    ModelGatewayCancelled(model_gateway_id=model_gateway_id)
                )
                self._info(model_gateway_id, cancelled, "cancelled")
                return ModelGatewayResult(
                    status=ModelGatewayResultStatus.CANCELLED, record=cancelled
                )

            batch = self._collector.collect(context)
            batch = self._planner.plan(batch, context)
            requests = self._dispatcher.dispatch(batch, context)

            new_record = replace(
                record,
                state=ModelGatewayState.PLANNED,
                history=record.history.append(batch),
                batch=batch,
                requests=requests,
                entry_count=record.entry_count + len(batch.entries),
                request_count=record.request_count + len(requests),
                updated_at=now,
            )
            metrics = self._metrics.calculate(new_record)
            snapshot = ModelGatewaySnapshot(
                record=new_record, metrics=metrics, timestamp=now
            )
            self._registry.register(new_record)

        events.extend(
            [
                InvocationsCollected(
                    model_gateway_id=model_gateway_id, entries=len(batch.entries)
                ),
                InvocationsPlanned(model_gateway_id=model_gateway_id),
                RequestsDispatched(
                    model_gateway_id=model_gateway_id, count=len(requests)
                ),
                ModelGatewaySnapshotCreated(model_gateway_id=model_gateway_id),
                ModelGatewayMetricsUpdated(model_gateway_id=model_gateway_id),
                ModelGatewayCompleted(model_gateway_id=model_gateway_id),
            ]
        )
        self._info(model_gateway_id, new_record, "invoked")
        return ModelGatewayResult(
            status=ModelGatewayResultStatus.SUCCESS,
            record=new_record,
            snapshot=snapshot,
            batch=batch,
            requests=requests,
            metrics=metrics,
        )

    async def _fail(self, model_gateway_id: str, message: str) -> ModelGatewayResult:
        self._error(model_gateway_id, message)
        await self._bus.publish(
            ModelGatewayErrorOccurred(
                model_gateway_id=model_gateway_id, message=message
            )
        )
        return ModelGatewayResult(
            status=ModelGatewayResultStatus.FAILED, errors=(message,)
        )

    def _info(
        self, model_gateway_id: str, record: ModelInvocationRecord, status: str
    ) -> None:
        if self._log is not None:
            self._log.info(
                "Model gateway update",
                extra={
                    "model_gateway_id": model_gateway_id,
                    "status": status,
                    "entries": record.entry_count,
                },
            )

    def _error(self, model_gateway_id: str, message: str) -> None:
        if self._log is not None:
            self._log.error(
                "Model gateway error",
                extra={"model_gateway_id": model_gateway_id, "error": message},
            )


def _new_record(model_gateway_id: str, now: datetime) -> ModelInvocationRecord:
    return ModelInvocationRecord(
        id=model_gateway_id,
        state=ModelGatewayState.COLLECTING,
        created_at=now,
        updated_at=now,
    )
