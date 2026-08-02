"""Execution manager.

:class:`DefaultExecutionManager` coordinates the execution pipeline: it builds an
:class:`ExecutionRequest` from the context, then runs validator → executor →
router, advancing the lifecycle and publishing events. It **always** returns an
:class:`ExecutionResult`; failures in any stage are isolated (they yield a failed
result rather than crashing the framework). It never communicates with brokers.
"""

from __future__ import annotations

import dataclasses

from core.logging import LoggerFactory
from events.bus import EventBus
from execution.context import ExecutionContext
from execution.events import (
    ExecutionCompleted,
    ExecutionErrorOccurred,
    ExecutionFailed,
    ExecutionQueued,
    ExecutionStarted,
    ExecutionValidated,
)
from execution.exceptions import ExecutionError
from execution.interfaces import (
    ExecutionExecutor,
    ExecutionRouter,
    ExecutionValidator,
)
from execution.lifecycle import ExecutionLifecycle
from execution.models import (
    ExecutionIdentifier,
    ExecutionMetadata,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
)
from execution.state import ExecutionState

__all__ = ["DefaultExecutionManager"]


class DefaultExecutionManager:
    """Coordinates validator → executor → router and publishes execution events.

    Args:
        bus: The event bus used to publish execution events.
        executor: The execution executor (abstraction).
        validator: The execution validator (abstraction).
        router: The execution router (abstraction).
        logger: Optional logger factory for framework logs.
    """

    def __init__(
        self,
        bus: EventBus,
        executor: ExecutionExecutor,
        validator: ExecutionValidator,
        router: ExecutionRouter,
        logger: LoggerFactory | None = None,
    ) -> None:
        self._bus = bus
        self._executor = executor
        self._validator = validator
        self._router = router
        self._log = logger.get_logger("execution.manager") if logger else None

    async def process(self, context: ExecutionContext) -> ExecutionResult:
        """Coordinate ``context`` end-to-end and return an :class:`ExecutionResult`."""
        lifecycle = ExecutionLifecycle()
        order_result = context.order_result

        # Only orders prepared and ready for execution may proceed.
        if order_result.request is None or not order_result.ready:
            reason = "order is not ready for execution"
            await self._bus.publish(ExecutionFailed(execution_id=None, reason=reason))
            self._error(None, reason)
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                state=ExecutionState.FAILED,
                errors=(reason,),
            )

        request = ExecutionRequest(
            identifier=ExecutionIdentifier(order_id=order_result.order_id),
            order_request=order_result.request,
            order_route=order_result.route,
            exchange=context.exchange,
            symbol=context.symbol,
            metadata=ExecutionMetadata(dict(context.metadata)),
        )
        execution_id = request.identifier.id
        await self._bus.publish(
            ExecutionStarted(execution_id=execution_id, symbol=request.symbol)
        )
        self._info("Execution started", execution_id)

        # -- validate -------------------------------------------------------
        validation = self._validator.validate(request)
        if not validation.valid:
            lifecycle.transition(ExecutionState.FAILED)
            await self._bus.publish(
                ExecutionFailed(execution_id=execution_id, reason="validation failed")
            )
            self._info("Execution validation failed", execution_id)
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                state=ExecutionState.FAILED,
                request=request,
                validation=validation,
                errors=validation.errors,
            )
        lifecycle.transition(ExecutionState.QUEUED)
        await self._bus.publish(ExecutionQueued(execution_id=execution_id))
        await self._bus.publish(ExecutionValidated(execution_id=execution_id))
        self._info("Execution validated", execution_id)

        # -- execute (coordinate) ------------------------------------------
        try:
            result = await self._executor.execute(request)
        except ExecutionError as exc:
            lifecycle.transition(ExecutionState.FAILED)
            await self._bus.publish(
                ExecutionErrorOccurred(execution_id=execution_id, message=str(exc))
            )
            await self._bus.publish(
                ExecutionFailed(execution_id=execution_id, reason=str(exc))
            )
            self._error(execution_id, f"executor: {exc}")
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                state=ExecutionState.FAILED,
                request=request,
                validation=validation,
                errors=(str(exc),),
            )
        lifecycle.transition(ExecutionState.READY)

        # -- route ----------------------------------------------------------
        try:
            route = self._router.route(request)
        except ExecutionError as exc:
            lifecycle.transition(ExecutionState.FAILED)
            await self._bus.publish(
                ExecutionErrorOccurred(execution_id=execution_id, message=str(exc))
            )
            await self._bus.publish(
                ExecutionFailed(execution_id=execution_id, reason=str(exc))
            )
            self._error(execution_id, f"router: {exc}")
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                state=ExecutionState.FAILED,
                request=request,
                validation=validation,
                errors=(str(exc),),
            )

        # -- ready for adapter ---------------------------------------------
        final = dataclasses.replace(
            result,
            state=lifecycle.current_state(),
            validation=validation,
            route=route,
            request=dataclasses.replace(request, state=ExecutionState.READY),
        )
        await self._bus.publish(ExecutionCompleted(execution_id=execution_id))
        self._info("Execution ready for adapter", execution_id)
        return final

    def _info(self, message: str, execution_id: str | None) -> None:
        if self._log is not None:
            self._log.info(message, extra={"execution_id": execution_id})

    def _error(self, execution_id: str | None, message: str) -> None:
        if self._log is not None:
            self._log.error(
                "Execution error",
                extra={"execution_id": execution_id, "error": message},
            )
