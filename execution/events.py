"""Execution Framework events.

Each inherits the existing :class:`events.base.Event` and is immutable. The
framework publishes **only** these — never strategy, risk, order, portfolio, or
exchange events.
"""

from __future__ import annotations

from dataclasses import dataclass

from events.base import Event

__all__ = [
    "ExecutionEvent",
    "ExecutionStarted",
    "ExecutionQueued",
    "ExecutionValidated",
    "ExecutionCompleted",
    "ExecutionFailed",
    "ExecutionCancelled",
    "ExecutionRetried",
    "ExecutionEngineStarted",
    "ExecutionEngineStopped",
    "ExecutionErrorOccurred",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionEvent(Event):
    """Base class for all execution events."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionStarted(ExecutionEvent):
    """Execution coordination began."""

    execution_id: str
    symbol: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionQueued(ExecutionEvent):
    """The execution was queued after validation."""

    execution_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionValidated(ExecutionEvent):
    """The execution request passed validation."""

    execution_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionCompleted(ExecutionEvent):
    """Framework coordination completed; the execution is ready for the adapter."""

    execution_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionFailed(ExecutionEvent):
    """The execution failed during coordination."""

    execution_id: str | None
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionCancelled(ExecutionEvent):
    """The execution was cancelled."""

    execution_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionRetried(ExecutionEvent):
    """A retry of the execution was attempted."""

    execution_id: str
    attempt: int = 1


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionEngineStarted(ExecutionEvent):
    """The execution engine started."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionEngineStopped(ExecutionEvent):
    """The execution engine stopped."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionErrorOccurred(ExecutionEvent):
    """An error occurred during execution coordination."""

    execution_id: str | None
    message: str
