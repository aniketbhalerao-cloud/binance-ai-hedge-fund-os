"""Fakes and helpers for Execution Framework tests.

A new, standalone support module (existing support files are unchanged). Fakes
only — no exchange adapters, broker SDKs, or network calls.
"""

from __future__ import annotations

from decimal import Decimal

from execution.context import ExecutionContext
from execution.models import (
    ExecutionRequest,
    ExecutionResult,
    ExecutionRoute,
    ExecutionStatus,
    ExecutionValidationResult,
)
from execution.state import ExecutionState
from models import OrderSide, OrderType
from order_management.models import (
    OrderIdentifier,
    OrderRequest,
    OrderResult,
    OrderRoute,
)
from order_management.state import OrderState

__all__ = [
    "FakeExecutionExecutor",
    "FakeExecutionValidator",
    "FakeExecutionRouter",
    "make_execution_context",
]


class FakeExecutionExecutor:
    """Returns a ready result, or raises if configured with an error."""

    def __init__(self, *, error: Exception | None = None) -> None:
        self._error = error

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        if self._error is not None:
            raise self._error
        return ExecutionResult(
            status=ExecutionStatus.READY,
            state=ExecutionState.READY,
            request=request,
        )


class FakeExecutionValidator:
    """Returns a configurable validation result."""

    def __init__(self, *, valid: bool = True, errors: tuple[str, ...] = ()) -> None:
        self._result = ExecutionValidationResult(valid=valid, errors=errors)

    def validate(self, request: ExecutionRequest) -> ExecutionValidationResult:
        return self._result


class FakeExecutionRouter:
    """Returns a fixed route, or raises if configured with an error."""

    def __init__(
        self, destination: str = "fake", *, error: Exception | None = None
    ) -> None:
        self._destination = destination
        self._error = error

    def route(self, request: ExecutionRequest) -> ExecutionRoute:
        if self._error is not None:
            raise self._error
        return ExecutionRoute(destination=self._destination)


def make_execution_context(
    *,
    exchange: str = "sim",
    symbol: str = "BTCUSDT",
    ready: bool = True,
) -> ExecutionContext:
    """Build a deterministic ExecutionContext from a ready OrderResult."""
    order_request = OrderRequest(
        identifier=OrderIdentifier(),
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("1"),
        state=(OrderState.READY_FOR_EXECUTION if ready else OrderState.REJECTED),
    )
    order_result = OrderResult(
        state=(OrderState.READY_FOR_EXECUTION if ready else OrderState.REJECTED),
        request=order_request if ready else None,
        route=OrderRoute(destination="default") if ready else None,
    )
    return ExecutionContext(order_result=order_result, exchange=exchange, symbol=symbol)
