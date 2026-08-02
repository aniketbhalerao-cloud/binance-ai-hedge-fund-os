"""Exchange manager.

:class:`DefaultExchangeManager` coordinates the framework pipeline:
authentication → connection → translation → validation → routing → adapter, then
produces an :class:`ExchangeResult` and publishes events. Translation (building a
broker-neutral :class:`ExchangeRequest` from the context) runs just before
validation, since validation verifies the *translated* request. The manager owns
the framework's logging narrative and **always** returns an ExchangeResult;
failures in any stage are isolated. It never communicates with brokers.
"""

from __future__ import annotations

import dataclasses

from core.logging import LoggerFactory
from events.bus import EventBus
from exchange_adapters.context import ExchangeContext
from exchange_adapters.events import (
    ExchangeAuthenticationFailed,
    ExchangeAuthenticationStarted,
    ExchangeAuthenticationSucceeded,
    ExchangeConnectionClosed,
    ExchangeConnectionOpened,
    ExchangeErrorOccurred,
    ExchangeRoutingCompleted,
    ExchangeValidationFailed,
    ExchangeValidationSucceeded,
)
from exchange_adapters.exceptions import ExchangeError
from exchange_adapters.interfaces import (
    ExchangeAuthentication,
    ExchangeConnection,
    ExchangeRegistry,
    ExchangeRouter,
    ExchangeValidator,
)
from exchange_adapters.models import (
    ExchangeIdentifier,
    ExchangeMetadata,
    ExchangeRequest,
    ExchangeResult,
    ExchangeStatus,
)
from exchange_adapters.state import AuthenticationState, ConnectionState

__all__ = ["DefaultExchangeManager"]


class DefaultExchangeManager:
    """Coordinates the exchange-adapter framework pipeline.

    Args:
        bus: The event bus used to publish exchange events.
        authentication: Authentication abstraction.
        connection: Connection abstraction.
        validator: Exchange request validator.
        router: Exchange router.
        registry: Adapter registry.
        logger: Optional logger factory for framework logs.
    """

    def __init__(
        self,
        bus: EventBus,
        authentication: ExchangeAuthentication,
        connection: ExchangeConnection,
        validator: ExchangeValidator,
        router: ExchangeRouter,
        registry: ExchangeRegistry,
        logger: LoggerFactory | None = None,
    ) -> None:
        self._bus = bus
        self._auth = authentication
        self._connection = connection
        self._validator = validator
        self._router = router
        self._registry = registry
        self._log = logger.get_logger("exchange.manager") if logger else None

    async def process(self, context: ExchangeContext) -> ExchangeResult:
        """Coordinate ``context`` end-to-end and return an :class:`ExchangeResult`."""
        exchange = context.exchange
        exec_result = context.execution_result
        if exec_result.request is None or not exec_result.ready:
            reason = "execution result is not ready"
            await self._bus.publish(ExchangeErrorOccurred(message=reason))
            self._error(reason)
            return ExchangeResult(status=ExchangeStatus.FAILED, errors=(reason,))

        # -- authentication -------------------------------------------------
        await self._bus.publish(ExchangeAuthenticationStarted(exchange=exchange))
        auth_state = await self._auth.authenticate(context)
        if auth_state is not AuthenticationState.AUTHENTICATED:
            await self._bus.publish(
                ExchangeAuthenticationFailed(
                    exchange=exchange, reason="not authenticated"
                )
            )
            self._info("Authentication failed")
            return ExchangeResult(
                status=ExchangeStatus.FAILED,
                authentication_state=auth_state,
                errors=("authentication failed",),
            )
        await self._bus.publish(ExchangeAuthenticationSucceeded(exchange=exchange))
        self._info("Authenticated")

        # -- connection -----------------------------------------------------
        connection_state = await self._connection.open(context)
        if connection_state is not ConnectionState.CONNECTED:
            await self._bus.publish(ExchangeConnectionClosed(exchange=exchange))
            self._info("Connection failed")
            return ExchangeResult(
                status=ExchangeStatus.FAILED,
                authentication_state=auth_state,
                connection_state=connection_state,
                errors=("connection failed",),
            )
        await self._bus.publish(ExchangeConnectionOpened(exchange=exchange))
        self._info("Connection opened")

        # -- translation ----------------------------------------------------
        request = ExchangeRequest(
            identifier=ExchangeIdentifier(),
            execution_request=exec_result.request,
            execution_route=exec_result.route,
            exchange=exchange,
            symbol=context.symbol,
            metadata=ExchangeMetadata(dict(context.metadata)),
        )

        # -- validation -----------------------------------------------------
        validation = self._validator.validate(request)
        if not validation.valid:
            await self._bus.publish(
                ExchangeValidationFailed(exchange=exchange, errors=validation.errors)
            )
            await self._close(exchange)
            self._info("Validation failed")
            return ExchangeResult(
                status=ExchangeStatus.FAILED,
                request=request,
                authentication_state=auth_state,
                connection_state=ConnectionState.CLOSED,
                errors=validation.errors,
            )
        await self._bus.publish(ExchangeValidationSucceeded(exchange=exchange))
        self._info("Validated")

        # -- routing --------------------------------------------------------
        try:
            route = self._router.route(context)
        except ExchangeError as exc:
            await self._bus.publish(ExchangeErrorOccurred(message=str(exc)))
            await self._close(exchange)
            self._error(f"routing: {exc}")
            return ExchangeResult(
                status=ExchangeStatus.FAILED,
                request=request,
                authentication_state=auth_state,
                connection_state=ConnectionState.CLOSED,
                errors=(str(exc),),
            )
        request = dataclasses.replace(request, adapter_name=route.adapter_name)
        await self._bus.publish(
            ExchangeRoutingCompleted(adapter_name=route.adapter_name)
        )
        self._info("Routed")

        # -- adapter (hand off; no broker unless a real adapter registered) -
        response = None
        status = ExchangeStatus.READY
        if self._registry.exists(route.adapter_name):
            adapter = self._registry.get(route.adapter_name)
            try:
                response = await adapter.submit(request)
            except ExchangeError as exc:
                await self._bus.publish(ExchangeErrorOccurred(message=str(exc)))
                await self._close(exchange)
                self._error(f"adapter: {exc}")
                return ExchangeResult(
                    status=ExchangeStatus.FAILED,
                    request=request,
                    authentication_state=auth_state,
                    connection_state=ConnectionState.CLOSED,
                    errors=(str(exc),),
                )
            status = (
                ExchangeStatus.READY if response.accepted else ExchangeStatus.REJECTED
            )

        await self._close(exchange)
        self._info("Exchange request ready for broker adapter")
        return ExchangeResult(
            status=status,
            request=request,
            response=response,
            authentication_state=auth_state,
            connection_state=ConnectionState.CLOSED,
            route=route,
        )

    async def _close(self, exchange: str) -> None:
        await self._connection.close()
        await self._bus.publish(ExchangeConnectionClosed(exchange=exchange))

    def _info(self, message: str) -> None:
        if self._log is not None:
            self._log.info(message)

    def _error(self, message: str) -> None:
        if self._log is not None:
            self._log.error("Exchange error", extra={"error": message})
