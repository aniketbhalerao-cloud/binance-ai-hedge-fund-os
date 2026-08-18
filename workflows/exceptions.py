"""Workflow Orchestration Framework exceptions.

Definitions only. Internal failures are translated into these so no
implementation detail (and no credential or secret material) escapes; the
manager always returns a :class:`~workflows.models.WorkflowResult`.
"""

from __future__ import annotations

__all__ = [
    "WorkflowError",
    "CollectionError",
    "PlanningError",
    "DispatchError",
    "MetricsError",
    "RegistryError",
    "WorkflowCancelledError",
]


class WorkflowError(Exception):
    """Base class for all Workflow Orchestration Framework errors."""


class CollectionError(WorkflowError):
    """Raised when building a workflow batch fails."""


class PlanningError(WorkflowError):
    """Raised when dependency validation or ordering fails.

    Covers duplicate step identifiers, missing dependencies, cross-workflow
    dependency references, self-dependencies, cyclic dependency graphs, and
    invalid handoff targets — none of these ever produce a partial
    ``WorkflowPlan``.
    """


class DispatchError(WorkflowError):
    """Raised when workflow request generation fails."""


class MetricsError(WorkflowError):
    """Raised when a metrics calculation fails."""


class RegistryError(WorkflowError):
    """Raised when a registry operation fails."""


class WorkflowCancelledError(WorkflowError):
    """Raised internally to unwind a workflow session that was cancelled."""
