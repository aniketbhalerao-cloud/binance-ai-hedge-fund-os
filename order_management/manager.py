"""Order manager.

:class:`DefaultOrderManager` coordinates the order pipeline: it invokes the
factory, validator, and router, advances the lifecycle state, publishes order
events, and **always** returns an :class:`OrderResult`. Failures in any stage are
isolated — they produce a rejected/errored result rather than crashing the
framework. It never communicates with exchanges.
"""

from __future__ import annotations

from core.logging import LoggerFactory
from events.bus import EventBus
from order_management.context import OrderContext
from order_management.events import (
    OrderCreated,
    OrderErrorOccurred,
    OrderReadyForExecution,
    OrderRejected,
    OrderRouted,
    OrderValidated,
    OrderValidationFailed,
)
from order_management.exceptions import OrderError
from order_management.interfaces import (
    OrderFactory,
    OrderRouter,
    OrderValidator,
)
from order_management.models import OrderRequest, OrderResult
from order_management.state import OrderState

__all__ = ["DefaultOrderManager"]


class DefaultOrderManager:
    """Coordinates factory → validator → router and publishes order events.

    Args:
        bus: The event bus used to publish order events.
        factory: The order factory (abstraction).
        validator: The order validator (abstraction).
        router: The order router (abstraction).
        logger: Optional logger factory for framework logs.
    """

    def __init__(
        self,
        bus: EventBus,
        factory: OrderFactory,
        validator: OrderValidator,
        router: OrderRouter,
        logger: LoggerFactory | None = None,
    ) -> None:
        self._bus = bus
        self._factory = factory
        self._validator = validator
        self._router = router
        self._log = logger.get_logger("order.manager") if logger else None

    async def process(self, context: OrderContext) -> OrderResult:
        """Process ``context`` end-to-end and return an :class:`OrderResult`."""
        # -- create ---------------------------------------------------------
        try:
            request = self._factory.create(context)
        except OrderError as exc:
            await self._bus.publish(OrderErrorOccurred(order_id=None, message=str(exc)))
            await self._bus.publish(OrderRejected(order_id=None, reason=str(exc)))
            self._error(None, f"factory: {exc}")
            return OrderResult(state=OrderState.REJECTED, errors=(str(exc),))

        order_id = request.identifier.id
        await self._bus.publish(OrderCreated(order_id=order_id, symbol=request.symbol))
        self._info("Order created", order_id)

        # -- validate -------------------------------------------------------
        validation = self._validator.validate(request)
        if not validation.valid:
            await self._bus.publish(
                OrderValidationFailed(order_id=order_id, errors=validation.errors)
            )
            await self._bus.publish(
                OrderRejected(order_id=order_id, reason="validation failed")
            )
            self._info("Order validation failed", order_id)
            return OrderResult(
                state=OrderState.REJECTED,
                request=self._with_state(request, OrderState.REJECTED),
                validation=validation,
                errors=validation.errors,
            )
        await self._bus.publish(OrderValidated(order_id=order_id))
        request = self._with_state(request, OrderState.VALIDATED)
        self._info("Order validated", order_id)

        # -- route ----------------------------------------------------------
        try:
            route = self._router.route(request)
        except OrderError as exc:
            await self._bus.publish(
                OrderErrorOccurred(order_id=order_id, message=str(exc))
            )
            await self._bus.publish(OrderRejected(order_id=order_id, reason=str(exc)))
            self._error(order_id, f"router: {exc}")
            return OrderResult(
                state=OrderState.REJECTED,
                request=self._with_state(request, OrderState.REJECTED),
                validation=validation,
                errors=(str(exc),),
            )
        await self._bus.publish(
            OrderRouted(order_id=order_id, destination=route.destination)
        )
        request = self._with_state(request, OrderState.ROUTED)
        self._info("Order routed", order_id)

        # -- ready ----------------------------------------------------------
        request = self._with_state(request, OrderState.READY_FOR_EXECUTION)
        await self._bus.publish(OrderReadyForExecution(order_id=order_id))
        self._info("Order ready for execution", order_id)
        return OrderResult(
            state=OrderState.READY_FOR_EXECUTION,
            request=request,
            validation=validation,
            route=route,
        )

    @staticmethod
    def _with_state(request: OrderRequest, state: OrderState) -> OrderRequest:
        import dataclasses

        return dataclasses.replace(request, state=state)

    def _info(self, message: str, order_id: str | None) -> None:
        if self._log is not None:
            self._log.info(message, extra={"order_id": order_id})

    def _error(self, order_id: str | None, message: str) -> None:
        if self._log is not None:
            self._log.error(
                "Order error", extra={"order_id": order_id, "error": message}
            )
