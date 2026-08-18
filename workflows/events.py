"""Workflow Orchestration Framework events.

Each inherits the existing :class:`events.base.Event` and is immutable. The
framework publishes **only** these — never Scheduler, Workers, Agents,
Model Provider Gateway, or any other framework's events. Events are
published only after a consistent record update (or an isolated failure),
and never carry a callable reference to another framework's manager or
engine, a credential, a network client, or other mutable state.
"""

from __future__ import annotations

from dataclasses import dataclass

from events.base import Event

__all__ = [
    "WorkflowEvent",
    "WorkflowStarted",
    "StepsCollected",
    "WorkflowPlanned",
    "RequestsDispatched",
    "WorkflowSnapshotCreated",
    "WorkflowMetricsUpdated",
    "WorkflowCompleted",
    "WorkflowCancelled",
    "WorkflowErrorOccurred",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkflowEvent(Event):
    """Base class for all workflow orchestration events."""


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkflowStarted(WorkflowEvent):
    """A workflow orchestration update was requested for a record."""

    workflow_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class StepsCollected(WorkflowEvent):
    """A workflow batch was collected."""

    workflow_id: str
    steps: int


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkflowPlanned(WorkflowEvent):
    """The workflow batch was validated and deterministically ordered."""

    workflow_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RequestsDispatched(WorkflowEvent):
    """Workflow requests were generated (domain objects, never executed)."""

    workflow_id: str
    count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkflowSnapshotCreated(WorkflowEvent):
    """A workflow snapshot was created."""

    workflow_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkflowMetricsUpdated(WorkflowEvent):
    """Workflow metrics were recomputed."""

    workflow_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkflowCompleted(WorkflowEvent):
    """A workflow orchestration update completed successfully."""

    workflow_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkflowCancelled(WorkflowEvent):
    """A workflow orchestration session was cancelled."""

    workflow_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkflowErrorOccurred(WorkflowEvent):
    """A workflow orchestration update failed and was isolated by the manager."""

    workflow_id: str
    message: str
