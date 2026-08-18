"""Workflow planner — dependency validation and deterministic ordering.

:class:`DefaultPlanner` turns a raw :class:`~workflows.models.WorkflowBatch`
into a deterministic, immutable :class:`~workflows.models.WorkflowPlan`.
Every :class:`~workflows.models.WorkflowDefinition` owns an independent
dependency graph; each is validated and topologically resolved on its own,
using a genuine Kahn's-algorithm topological sort with a deterministic
ready queue — never ``sorted(steps)``. It is stateless and never applies
changes: it never calls another framework, executes a step, or triggers an
Agent — it only validates and orders.

Ordering (see ``docs/prompts/task-37.md`` "Deterministic Workflow Ordering"):

Workflow level — across the ``WorkflowDefinition`` objects in one batch:
    0. reject duplicate ``workflow_id`` values before any sorting or plan
       entry is constructed
    1. workflow priority (higher first)
    2. stable workflow identifier (lexical ascending)

Each ``WorkflowPlanEntry.dependencies`` is canonicalized to lexical
ascending order, so equivalent graphs with differently ordered dependency
declarations always produce identical plan entries.

Step level — within one ``WorkflowDefinition``, independently of every
other:
    1. validate step identifiers are unique
    2. validate every dependency references an existing step in the *same*
       definition (a reference to another definition's step is rejected the
       same way as a missing one — the graphs are independent by design)
    3. reject self-dependencies
    4. reject cyclic dependency graphs
    5. resolve via deterministic topological ordering (Kahn's algorithm)
    6. among simultaneously-ready steps: step priority (higher first), then
       stable step identifier (lexical ascending)

A step's handoff target must be one of the four supported domain values;
any other value invalidates the definition before a ``WorkflowRequest`` is
ever produced.

Any validation failure raises :class:`~workflows.exceptions.PlanningError`
and never produces a partially ordered plan.
"""

from __future__ import annotations

import heapq
from decimal import Decimal

from workflows.context import WorkflowContext
from workflows.exceptions import PlanningError
from workflows.models import (
    SUPPORTED_HANDOFF_TARGETS,
    WorkflowBatch,
    WorkflowDefinition,
    WorkflowPlan,
    WorkflowPlanEntry,
    WorkflowStep,
)

__all__ = ["DefaultPlanner"]


class DefaultPlanner:
    """Stateless dependency validation and deterministic ordering."""

    def plan(self, batch: WorkflowBatch, context: WorkflowContext) -> WorkflowPlan:
        """Return the deterministic :class:`WorkflowPlan` for ``batch``.

        Raises:
            PlanningError: If validation or ordering fails for any
                definition — no partial plan is ever returned.
        """
        try:
            return self._plan(batch)
        except PlanningError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise PlanningError(str(exc)) from exc

    def _plan(self, batch: WorkflowBatch) -> WorkflowPlan:
        workflow_ids = [d.workflow_id for d in batch.definitions]
        if len(set(workflow_ids)) != len(workflow_ids):
            raise PlanningError(
                f"workflow batch has duplicate workflow identifiers: {workflow_ids!r}"
            )

        # Workflow-level ordering: priority desc, workflow_id asc.
        ordered_definitions = sorted(
            batch.definitions, key=lambda d: (-d.workflow_priority, d.workflow_id)
        )
        entries: list[WorkflowPlanEntry] = []
        position = 0
        for definition in ordered_definitions:
            for step in _topological_order(definition):
                entries.append(
                    WorkflowPlanEntry(
                        position=position,
                        workflow_id=definition.workflow_id,
                        workflow_priority=definition.workflow_priority,
                        step=step,
                        # Canonicalized lexical-ascending: equivalent graphs
                        # with differently ordered dependency declarations
                        # must produce identical plan entries.
                        dependencies=tuple(
                            sorted(
                                dep.depends_on
                                for dep in definition.dependencies
                                if dep.step_id == step.step_id
                            )
                        ),
                    )
                )
                position += 1
        return WorkflowPlan(entries=tuple(entries))


def _topological_order(definition: WorkflowDefinition) -> tuple[WorkflowStep, ...]:
    """Validate ``definition``'s own graph and return its steps in
    deterministic topological order (Kahn's algorithm)."""
    steps_by_id = {step.step_id: step for step in definition.steps}
    if len(steps_by_id) != len(definition.steps):
        raise PlanningError(
            f"workflow {definition.workflow_id!r} has duplicate step identifiers"
        )
    for step in definition.steps:
        if step.handoff_target not in SUPPORTED_HANDOFF_TARGETS:
            raise PlanningError(
                f"workflow {definition.workflow_id!r} step {step.step_id!r} has "
                f"invalid handoff target {step.handoff_target!r}"
            )

    dependents: dict[str, list[str]] = {step_id: [] for step_id in steps_by_id}
    in_degree: dict[str, int] = dict.fromkeys(steps_by_id, 0)
    for dep in definition.dependencies:
        if dep.step_id not in steps_by_id or dep.depends_on not in steps_by_id:
            raise PlanningError(
                f"workflow {definition.workflow_id!r} step {dep.step_id!r} "
                f"depends on unknown step {dep.depends_on!r} "
                "(dependencies must reference a step within the same workflow)"
            )
        if dep.step_id == dep.depends_on:
            raise PlanningError(
                f"workflow {definition.workflow_id!r} step {dep.step_id!r} "
                "has a self-dependency"
            )
        dependents[dep.depends_on].append(dep.step_id)
        in_degree[dep.step_id] += 1

    # Deterministic ready queue: (-step_priority, step_id) — a genuine
    # dependency-aware Kahn's algorithm, not sorted(steps).
    ready: list[tuple[Decimal, str]] = [
        (-steps_by_id[step_id].priority, step_id)
        for step_id, degree in in_degree.items()
        if degree == 0
    ]
    heapq.heapify(ready)

    order: list[WorkflowStep] = []
    while ready:
        _, step_id = heapq.heappop(ready)
        order.append(steps_by_id[step_id])
        for dependent in dependents[step_id]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                heapq.heappush(
                    ready, (-steps_by_id[dependent].priority, dependent)
                )

    if len(order) != len(steps_by_id):
        raise PlanningError(
            f"workflow {definition.workflow_id!r} has a cyclic dependency graph"
        )
    return tuple(order)
