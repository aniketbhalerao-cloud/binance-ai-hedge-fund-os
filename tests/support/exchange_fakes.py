"""Fakes and helpers for Exchange Adapter Framework tests.

A new, standalone support module (existing support files are unchanged). Fakes
only — no broker SDKs, REST, WebSockets, or credentials.
"""

from __future__ import annotations

from decimal import Decimal

from exchange_adapters.adapter import BaseExchangeAdapter
from exchange_adapters.context import ExchangeContext
from exchange_adapters.models import (
    ExchangeRequest,
    ExchangeResponse,
)
from exchange_adapters.state import AuthenticationState, ConnectionState
from execution.models import (
    ExecutionIdentifier,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
)
from execution.state import ExecutionState
from models import OrderSide, OrderType
from order_management.models import OrderIdentifier, OrderRequest

__all__ = [
    "FakeExchangeAdapter",
    "FakeAuthentication",
    "FakeConnection",
    "make_exchange_context",
]


class FakeExchangeAdapter(BaseExchangeAdapter):
    """An adapter that accepts requests (or raises if configured)."""

    def __init__(
        self, name: str = "default", *, error: Exception | None = None
    ) -> None:
        super().__init__(name)
        self._error = error
        self.submitted: list[ExchangeRequest] = []

    async def submit(self, request: ExchangeRequest) -> ExchangeResponse:
        if self._error is not None:
            raise self._error
        self.submitted.append(request)
        return ExchangeResponse(accepted=True, message="ok")


class FakeAuthentication:
    """Authentication stub returning a configurable state."""

    def __init__(
        self, state: AuthenticationState = AuthenticationState.AUTHENTICATED
    ) -> None:
        self._state = state

    async def authenticate(self, context: ExchangeContext) -> AuthenticationState:
        return self._state


class FakeConnection:
    """Connection stub returning a configurable open state."""

    def __init__(self, open_state: ConnectionState = ConnectionState.CONNECTED) -> None:
        self._open_state = open_state

    async def open(self, context: ExchangeContext) -> ConnectionState:
        return self._open_state

    async def close(self) -> ConnectionState:
        return ConnectionState.CLOSED


def make_exchange_context(
    *,
    exchange: str = "sim",
    symbol: str = "BTCUSDT",
    ready: bool = True,
    adapter: str | None = None,
) -> ExchangeContext:
    """Build a deterministic ExchangeContext from a ready ExecutionResult."""
    order_request = OrderRequest(
        identifier=OrderIdentifier(),
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("1"),
    )
    exec_request = ExecutionRequest(
        identifier=ExecutionIdentifier(),
        order_request=order_request,
        exchange=exchange,
        symbol=symbol,
        state=ExecutionState.READY,
    )
    exec_result = ExecutionResult(
        status=ExecutionStatus.READY if ready else ExecutionStatus.FAILED,
        state=ExecutionState.READY if ready else ExecutionState.FAILED,
        request=exec_request if ready else None,
    )
    metadata = {"adapter": adapter} if adapter else {}
    return ExchangeContext(
        execution_result=exec_result,
        exchange=exchange,
        symbol=symbol,
        metadata=metadata,
    )
