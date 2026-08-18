"""Helpers for Workflow Orchestration Framework tests.

Standalone support module (existing support files unchanged). Builds
deterministic workflow contexts, steps, dependencies, and definitions. No
network, no sleeps, no randomness, no model training, and no calls into
another framework's manager or engine anywhere.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from workflows.context import WorkflowContext
from workflows.models import (
    WorkflowDefinition,
    WorkflowDependency,
    WorkflowParameters,
    WorkflowStep,
)

__all__ = [
    "make_step",
    "make_dependency",
    "make_definition",
    "make_context",
]


def make_step(
    step_id: str,
    priority: str = "0",
    *,
    handoff_target: str = "agents",
    detail: str = "",
) -> WorkflowStep:
    """Build a workflow step with a given priority."""
    return WorkflowStep(
        step_id=step_id,
        handoff_target=handoff_target,
        priority=Decimal(priority),
        detail=detail,
    )


def make_dependency(step_id: str, depends_on: str) -> WorkflowDependency:
    """Build a dependency edge: ``step_id`` depends on ``depends_on``."""
    return WorkflowDependency(step_id=step_id, depends_on=depends_on)


def make_definition(
    workflow_id: str,
    *,
    workflow_priority: str = "0",
    steps: Sequence[WorkflowStep] | None = None,
    dependencies: Sequence[WorkflowDependency] | None = None,
    detail: str = "",
) -> WorkflowDefinition:
    """Build a declarative workflow definition.

    Defaults to two independent steps (``a``/``b``, matching every sibling
    framework's fixture convention) with no dependencies, unless overridden.
    """
    return WorkflowDefinition(
        workflow_id=workflow_id,
        workflow_priority=Decimal(workflow_priority),
        steps=tuple(steps) if steps is not None else (make_step("a"), make_step("b")),
        dependencies=tuple(dependencies) if dependencies is not None else (),
        detail=detail,
    )


def make_context(
    *,
    workflow_id: str = "workflow-1",
    definitions: Sequence[WorkflowDefinition] | None = None,
    parameters: WorkflowParameters | None = None,
    cancel: bool = False,
) -> WorkflowContext:
    """Build a deterministic workflow context.

    Defaults to a single ``make_definition("w1")`` unless overridden.
    """
    metadata = {"cancel": True} if cancel else {}
    return WorkflowContext(
        workflow_id=workflow_id,
        workflow_definitions=tuple(definitions)
        if definitions is not None
        else (make_definition("w1"),),
        parameters=parameters if parameters is not None else WorkflowParameters(),
        correlation_id="workflow-corr",
        metadata=metadata,
    )
