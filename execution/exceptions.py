"""Execution Framework exceptions.

Definitions only — no handling logic. These isolate execution failures so the
framework always produces an :class:`~execution.models.ExecutionResult`.
"""

from __future__ import annotations

__all__ = [
    "ExecutionError",
    "ExecutionValidationError",
    "ExecutionRoutingError",
    "ExecutionLifecycleError",
    "ExecutionEngineError",
    "InvalidExecutionRequest",
]


class ExecutionError(Exception):
    """Base class for all Execution Framework errors."""


class ExecutionValidationError(ExecutionError):
    """Raised when validation cannot be performed."""


class ExecutionRoutingError(ExecutionError):
    """Raised when execution routing cannot be prepared."""


class ExecutionLifecycleError(ExecutionError):
    """Raised when an illegal execution lifecycle transition is attempted."""


class ExecutionEngineError(ExecutionError):
    """Raised when the engine fails to coordinate an execution."""


class InvalidExecutionRequest(ExecutionError):
    """Raised when an execution request is missing or structurally invalid."""
