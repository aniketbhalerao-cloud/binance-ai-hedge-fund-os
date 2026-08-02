"""Execution executor.

:class:`DefaultExecutionExecutor` coordinates an execution request into a result.
Because this framework contains no broker connectivity, "coordination" means
preparing the request and marking it ready for a future Exchange Adapter — it
produces an :class:`ExecutionResult` with status ``READY``. It is stateless and
never calls REST APIs, opens WebSockets, or talks to any exchange.
"""

from __future__ import annotations

from execution.models import ExecutionRequest, ExecutionResult, ExecutionStatus
from execution.state import ExecutionState

__all__ = ["DefaultExecutionExecutor"]


class DefaultExecutionExecutor:
    """Coordinates execution without contacting any broker."""

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Coordinate ``request`` and return a result ready for the adapter."""
        return ExecutionResult(
            status=ExecutionStatus.READY,
            state=ExecutionState.READY,
            request=request,
        )
