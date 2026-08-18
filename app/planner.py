"""Composition-root planner — dependency validation and deterministic
component registration ordering.

:func:`plan` turns a raw :class:`~app.models.ComponentManifest` into a
deterministic, immutable :class:`~app.models.BootstrapPlan`, using a genuine
Kahn's-algorithm topological sort with a deterministic ready queue — never
``sorted(components)``. It is stateless and never touches a container: it
only validates and orders the declared graph.

Sequence (see ``docs/prompts/task-38.md`` "Deterministic Component
Registration Ordering"):

1. every ``component_id`` must be a member of ``wiring.KNOWN_COMPONENT_IDS``
   — an unknown component id is rejected before any other validation
2. all component identifiers must be unique within the manifest
3. every dependency must reference an existing component in the same
   manifest
4. self-dependencies are rejected
5. cyclic dependency graphs are rejected
6. components are resolved via deterministic topological ordering
7. among simultaneously-ready components: priority (higher first), then
   stable component identifier (lexical ascending)

``BootstrapPlanEntry.dependencies`` is canonicalized to lexical-ascending
order, so equivalent graphs with differently ordered dependency
declarations always produce identical plan entries.

No timestamp, random value, dictionary/set iteration order, or process/
external state may influence ordering.
"""

from __future__ import annotations

import heapq
from decimal import Decimal

from app import wiring
from app.exceptions import PlanningError
from app.models import BootstrapPlan, BootstrapPlanEntry, ComponentManifest

__all__ = ["plan"]


def plan(manifest: ComponentManifest) -> BootstrapPlan:
    """Return the deterministic :class:`~app.models.BootstrapPlan` for
    ``manifest``.

    Raises:
        PlanningError: If validation or ordering fails — no partial plan is
            ever returned, and no container is ever created.
    """
    try:
        return _plan(manifest)
    except PlanningError:
        raise
    except Exception as exc:  # translate; never echo internals or input values
        raise PlanningError("component manifest failed validation") from exc


def _plan(manifest: ComponentManifest) -> BootstrapPlan:
    components = manifest.components

    # 1. Unknown component ids — rejected before any other validation. The
    # message never echoes the offending id: a manifest is caller-supplied
    # input, and ids are not trusted to be safe to surface verbatim.
    for component in components:
        if component.component_id not in wiring.KNOWN_COMPONENT_IDS:
            raise PlanningError(
                "component manifest references an unknown component id"
            )

    # 2. Uniqueness.
    component_ids = [component.component_id for component in components]
    if len(set(component_ids)) != len(component_ids):
        raise PlanningError(
            "component manifest has duplicate component identifiers"
        )
    components_by_id = {component.component_id: component for component in components}

    # 3. Every dependency references an existing component.
    for dependency in manifest.dependencies:
        if (
            dependency.component_id not in components_by_id
            or dependency.depends_on not in components_by_id
        ):
            raise PlanningError(
                "component manifest has a dependency referencing an "
                "unknown component"
            )

    # 4. Self-dependencies.
    for dependency in manifest.dependencies:
        if dependency.component_id == dependency.depends_on:
            raise PlanningError("component manifest has a self-dependency")

    # 5-7. Deterministic topological ordering (Kahn's algorithm).
    dependents: dict[str, list[str]] = {cid: [] for cid in components_by_id}
    in_degree: dict[str, int] = dict.fromkeys(components_by_id, 0)
    deps_by_component: dict[str, list[str]] = {cid: [] for cid in components_by_id}
    for dependency in manifest.dependencies:
        dependents[dependency.depends_on].append(dependency.component_id)
        in_degree[dependency.component_id] += 1
        deps_by_component[dependency.component_id].append(dependency.depends_on)

    # Deterministic ready queue: (-priority, component_id).
    ready: list[tuple[Decimal, str]] = [
        (-components_by_id[cid].priority, cid)
        for cid, degree in in_degree.items()
        if degree == 0
    ]
    heapq.heapify(ready)

    order: list[str] = []
    while ready:
        _, component_id = heapq.heappop(ready)
        order.append(component_id)
        for dependent in dependents[component_id]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                heapq.heappush(
                    ready, (-components_by_id[dependent].priority, dependent)
                )

    if len(order) != len(components_by_id):
        raise PlanningError("component manifest has a cyclic dependency graph")

    entries = tuple(
        BootstrapPlanEntry(
            position=position,
            component_id=component_id,
            priority=components_by_id[component_id].priority,
            required_service_keys=components_by_id[component_id].required_service_keys,
            dependencies=tuple(sorted(deps_by_component[component_id])),
        )
        for position, component_id in enumerate(order)
    )
    return BootstrapPlan(entries=entries)
