"""Workflow context.

An immutable input carrying declarative workflow definitions supplied by the
running system, plus the workflow parameters. Workflow components never
access infrastructure directly; they read only from this context and the
models it carries, and they never modify any subject. Scheduler, Workers,
Agents, and Model Provider Gateway are handoff *targets* referenced inside
step data, never upstream data sources read from here. The context must
never carry a callable reference to another framework's manager or engine, a
network client, or a credential.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from workflows.models import WorkflowDefinition, WorkflowParameters

__all__ = ["WorkflowContext"]


@dataclass(frozen=True, slots=True)
class WorkflowContext:
    """Immutable input for producing a deterministic ``WorkflowPlan``.

    Attributes:
        workflow_id: Identifier of the workflow orchestration record to
            update.
        workflow_definitions: The declarative workflow definitions to
            collect and resolve.
        parameters: Deterministic workflow orchestration parameters.
        correlation_id: Optional correlation id propagated to events.
        timestamp: When the context was assembled (UTC).
        metadata: Optional read-only extra context.
    """

    workflow_id: str = "workflow"
    workflow_definitions: tuple[WorkflowDefinition, ...] = ()
    parameters: WorkflowParameters = field(default_factory=WorkflowParameters)
    correlation_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "workflow_definitions", tuple(self.workflow_definitions)
        )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
