"""Execution validator.

:class:`DefaultExecutionValidator` checks an :class:`ExecutionRequest` for
integrity, lifecycle state, and routing metadata, producing an
:class:`ExecutionValidationResult`. It is stateless. It performs no risk
evaluation, portfolio checks, or broker calls.
"""

from __future__ import annotations

from execution.models import ExecutionRequest, ExecutionValidationResult
from execution.state import ExecutionState

__all__ = ["DefaultExecutionValidator"]


class DefaultExecutionValidator:
    """Validates the consistency of an :class:`ExecutionRequest`."""

    def validate(self, request: ExecutionRequest) -> ExecutionValidationResult:
        """Return a validation result listing any structural problems."""
        errors: list[str] = []

        if not request.symbol:
            errors.append("symbol must not be empty")
        if request.order_request is None:
            errors.append("order_request is required")
        elif request.order_request.quantity <= 0:
            errors.append("order quantity must be greater than 0")
        if request.state is not ExecutionState.CREATED:
            errors.append(
                f"execution must start in CREATED state, got {request.state.value}"
            )

        return ExecutionValidationResult(valid=not errors, errors=tuple(errors))
