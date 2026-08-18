"""Workflow Orchestration Framework domain models.

Immutable, exchange-independent, credential-free value objects. The rest of
the application consumes only these standardized models. Priorities and
scores use :class:`~decimal.Decimal`; timestamps are timezone-aware UTC.
Every model is frozen — batches, plans, requests, and the running record are
never mutated; each composed input produces a **new** record.

The framework only *validates, orders, and plans* declarative domain
objects: ``WorkflowPlan`` and ``WorkflowRequest`` describe an intended step
order and handoff as immutable domain objects and are never executed, run,
or dispatched to a target framework anywhere. No model defined here may
carry a callable reference to another framework's manager or engine, a
network client, a database client, or credentials, API keys, or secrets.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Any

from workflows.state import WorkflowState

__all__ = [
    "WorkflowResultStatus",
    "WorkflowParameters",
    "WorkflowStep",
    "WorkflowDependency",
    "WorkflowDefinition",
    "WorkflowBatch",
    "WorkflowPlanEntry",
    "WorkflowPlan",
    "WorkflowRequest",
    "WorkflowHistory",
    "WorkflowRecord",
    "WorkflowMetrics",
    "WorkflowSnapshot",
    "WorkflowResult",
]

_ZERO = Decimal("0")

#: The four supported handoff-target domain values (see
#: ``docs/prompts/task-37.md`` "Handoff Target Validation").
SUPPORTED_HANDOFF_TARGETS: frozenset[str] = frozenset(
    {"agents", "model_gateway", "scheduler", "workers"}
)


# (str, Enum) matches the project-wide convention used by every sibling
# framework and 50+ other enums in this codebase; StrEnum has zero
# precedent here, and adopting it only in this one file would be the
# inconsistency, not the fix.
class WorkflowResultStatus(str, Enum):  # noqa: UP042
    """Coarse outcome of composing one input."""

    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class WorkflowParameters:
    """Deterministic workflow orchestration configuration.

    Attributes:
        max_items: Maximum number of ``WorkflowDefinition`` objects to
            collect per input.
    """

    max_items: int = 25


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    """An immutable workflow graph node, scoped to one ``WorkflowDefinition``.

    Attributes:
        step_id: Stable identifier, unique within its ``WorkflowDefinition``.
        handoff_target: Immutable handoff-target identifier — must be one of
            :data:`SUPPORTED_HANDOFF_TARGETS`; validated by the Planner.
        priority: Deterministic step priority (higher preferred).
        detail: Free-form descriptive detail.
        metadata: Optional read-only extra detail.
    """

    step_id: str
    handoff_target: str
    priority: Decimal = _ZERO
    detail: str = ""
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class WorkflowDependency:
    """An immutable directed edge, scoped to one ``WorkflowDefinition``.

    Attributes:
        step_id: The dependent step identifier.
        depends_on: The step identifier it depends on.
    """

    step_id: str
    depends_on: str


@dataclass(frozen=True, slots=True)
class WorkflowDefinition:
    """A declarative, immutable workflow — an independent dependency graph.

    Attributes:
        workflow_id: Stable identifier, unique within a ``WorkflowBatch``.
        workflow_priority: Deterministic workflow priority (higher
            preferred) — workflow-level metadata only, never used to order
            steps inside this definition.
        steps: The workflow's own graph nodes.
        dependencies: The workflow's own graph edges — every edge must
            reference only ``steps`` on this same definition.
        detail: Free-form descriptive detail.
    """

    workflow_id: str
    workflow_priority: Decimal = _ZERO
    steps: tuple[WorkflowStep, ...] = ()
    dependencies: tuple[WorkflowDependency, ...] = ()
    detail: str = ""


@dataclass(frozen=True, slots=True)
class WorkflowBatch:
    """An immutable batch: the collected, unresolved workflow definitions."""

    definitions: tuple[WorkflowDefinition, ...] = ()


@dataclass(frozen=True, slots=True)
class WorkflowPlanEntry:
    """One resolved position in a ``WorkflowPlan`` (a documented structural
    addition, mirroring the two structural models Task 36 added — the named
    models alone cannot express one ordered step's provenance).

    Attributes:
        position: The deterministic, zero-based resolved ordering position
            across the whole ``WorkflowPlan``.
        workflow_id: The owning ``WorkflowDefinition``'s identifier.
        workflow_priority: The owning ``WorkflowDefinition``'s priority —
            explains the workflow-level ordering outcome.
        step: The resolved ``WorkflowStep``.
        dependencies: The step's own ``depends_on`` identifiers, within its
            own ``WorkflowDefinition``.
    """

    position: int
    workflow_id: str
    workflow_priority: Decimal
    step: WorkflowStep
    dependencies: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class WorkflowPlan:
    """A deterministic, declarative plan — never executes anything.

    ``entries`` is the fully resolved order: workflows ordered first (by
    workflow priority, then workflow identifier), each contributing its own
    independently topologically-ordered steps (by step priority, then step
    identifier) in sequence.
    """

    entries: tuple[WorkflowPlanEntry, ...] = ()
    detail: str = ""


@dataclass(frozen=True, slots=True)
class WorkflowRequest:
    """A deterministic handoff-intent request — describes intent; it never
    performs it.

    Never contains a callable reference to another framework's manager or
    engine, credentials, API keys, secrets, or a network connection.
    """

    subject: str
    source: str
    handoff_target: str
    priority: Decimal = _ZERO
    position: int = 0
    detail: str = ""


@dataclass(frozen=True, slots=True)
class WorkflowHistory:
    """Append-only record of produced batches."""

    batches: tuple[WorkflowBatch, ...] = ()

    def append(self, batch: WorkflowBatch) -> WorkflowHistory:
        """Return a new history with ``batch`` appended (never mutates)."""
        return WorkflowHistory(self.batches + (batch,))


@dataclass(frozen=True, slots=True)
class WorkflowRecord:
    """The durable, immutable running state of one workflow orchestration
    session.

    The Registry owns the current ``WorkflowRecord``; the Manager loads it,
    processes one input, and writes back a **new** ``WorkflowRecord``.
    """

    id: str
    state: WorkflowState
    history: WorkflowHistory = field(default_factory=WorkflowHistory)
    batch: WorkflowBatch = field(default_factory=WorkflowBatch)
    plan: WorkflowPlan = field(default_factory=WorkflowPlan)
    requests: tuple[WorkflowRequest, ...] = ()
    definition_count: int = 0
    step_count: int = 0
    request_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WorkflowMetrics:
    """Derived metrics over a workflow record."""

    total_steps: int = 0
    total_requests: int = 0
    average_step_score: Decimal = _ZERO
    highest_priority_step: str = ""
    lowest_priority_step: str = ""
    dispatch_ratio: Decimal = _ZERO
    pending_requests_count: int = 0
    suppressed_requests_count: int = 0


@dataclass(frozen=True, slots=True)
class WorkflowSnapshot:
    """A complete, immutable record of one workflow orchestration update."""

    record: WorkflowRecord
    metrics: WorkflowMetrics
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    """The immutable outcome of composing one input."""

    status: WorkflowResultStatus
    record: WorkflowRecord | None = None
    snapshot: WorkflowSnapshot | None = None
    batch: WorkflowBatch | None = None
    plan: WorkflowPlan | None = None
    requests: tuple[WorkflowRequest, ...] = ()
    metrics: WorkflowMetrics | None = None
    errors: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        """Return ``True`` when the input was composed successfully."""
        return self.status is WorkflowResultStatus.SUCCESS
