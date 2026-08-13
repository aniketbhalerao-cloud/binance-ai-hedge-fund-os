"""Model Provider Gateway Framework domain models.

Immutable, exchange-independent, credential-free value objects. The rest of
the application consumes only these standardized models. Scores use
:class:`~decimal.Decimal`; timestamps are timezone-aware UTC. Every model is
frozen — batches, model invocation requests, and the running record are
never mutated; each invoked input produces a **new** record.

The framework only *plans and routes domain objects*: ``ModelInvocationRequest``
describes desired inference as an immutable domain object and is never
executed, run, or sent to a provider anywhere, and the framework never
modifies a strategy, agent, or portfolio.

No model defined here may carry an API key, access token, password,
credential, secret, private key, connection object, SDK client, network
client, authorization header, or provider session — routing candidates
(:class:`ModelProviderProfile`) are metadata only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from model_gateway.state import ModelGatewayState

__all__ = [
    "ModelGatewayResultStatus",
    "ModelGatewayParameters",
    "ModelInvocationSource",
    "ModelProviderProfile",
    "ModelInvocationEntry",
    "ModelInvocationBatch",
    "ModelInvocationRequest",
    "ModelGatewayHistory",
    "ModelInvocationRecord",
    "ModelGatewayMetrics",
    "ModelGatewaySnapshot",
    "ModelGatewayResult",
]

_ZERO = Decimal("0")


# (str, Enum) matches the project-wide convention used by every sibling
# framework and 50+ other enums in this codebase; StrEnum has zero
# precedent here, and adopting it only in this one file would be the
# inconsistency, not the fix.
class ModelGatewayResultStatus(str, Enum):  # noqa: UP042
    """Coarse outcome of invoking one input."""

    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class ModelProviderProfile:
    """An immutable, credential-free routing candidate.

    Represents provider/model routing metadata only — never a live
    connection, SDK client, or credential. ``available`` and ``routing_id``
    are supplied as declared domain input, never queried from a live
    provider. Field order mirrors the Task 36 deterministic routing
    precedence (dimensions 4-9): ``routing_policy_priority`` (4),
    ``priority`` (5), ``cost`` (6), ``available`` (7), ``provider_id`` /
    ``model_id`` (8/9, always present), ``routing_id`` (final tie-break).

    Attributes:
        provider_id: Stable provider identifier (e.g. ``"anthropic"``) —
            precedence dimension 8.
        model_id: Stable model identifier (e.g. ``"claude"``) — precedence
            dimension 9.
        capabilities: Capabilities this candidate supports — a candidate
            failing a required capability is suppressed (precedence
            dimension 2).
        context_support: Context requirements this candidate supports — a
            candidate failing a required context is suppressed (precedence
            dimension 3).
        routing_policy_priority: Deterministic routing-policy priority,
            distinct from ``priority`` (higher is preferred) — precedence
            dimension 4.
        priority: Deterministic provider/model priority (higher is
            preferred) — precedence dimension 5.
        cost: Deterministic cost/routing-policy value (lower is preferred)
            — precedence dimension 6.
        available: Declared availability (domain input, never live state;
            available candidates are preferred) — precedence dimension 7.
        routing_id: Stable identifier used as the final tie-break, after
            provider_id/model_id (dimensions 8/9) both tie.
    """

    provider_id: str
    model_id: str
    capabilities: tuple[str, ...] = ()
    context_support: tuple[str, ...] = ()
    routing_policy_priority: Decimal = _ZERO
    priority: Decimal = _ZERO
    cost: Decimal = _ZERO
    available: bool = True
    routing_id: str = ""


@dataclass(frozen=True, slots=True)
class ModelGatewayParameters:
    """Deterministic model gateway configuration.

    Attributes:
        priority_threshold: Priority at or above which an entry is planned
            for dispatch.
        max_items: Maximum number of entries to plan per input.
        provider_profiles: The immutable routing candidates available for
            deterministic provider routing.
    """

    priority_threshold: Decimal = _ZERO
    max_items: int = 5
    provider_profiles: tuple[ModelProviderProfile, ...] = ()


@dataclass(frozen=True, slots=True)
class ModelInvocationSource:
    """A normalized model invocation datum feeding one entry.

    Attributes:
        name: The subject of the desired invocation.
        source: The upstream framework this reading came from.
        category: Free-form classification (domain only).
        priority: Deterministic priority.
        samples: Sample count backing this reading.
        required_capabilities: Capabilities a candidate must support.
        required_context: Context requirements a candidate must support.
        preferred_provider_id: Explicit provider preference, if any.
        preferred_model_id: Explicit model preference, if any.
    """

    name: str
    source: str
    category: str = "unknown"
    priority: Decimal = _ZERO
    samples: int = 0
    required_capabilities: tuple[str, ...] = ()
    required_context: tuple[str, ...] = ()
    preferred_provider_id: str = ""
    preferred_model_id: str = ""


@dataclass(frozen=True, slots=True)
class ModelInvocationEntry:
    """A planned entry within a batch (an immutable domain object, never run)."""

    source: ModelInvocationSource
    dispatch: bool = True
    detail: str = ""


@dataclass(frozen=True, slots=True)
class ModelInvocationBatch:
    """An immutable batch: the collected sources and their planned entries."""

    sources: tuple[ModelInvocationSource, ...] = ()
    entries: tuple[ModelInvocationEntry, ...] = ()


@dataclass(frozen=True, slots=True)
class ModelInvocationRequest:
    """A deterministic model invocation request — describes desired
    inference; it never performs it.

    Carries only the information a downstream adapter needs to fulfill the
    request, plus enough routing metadata to explain the deterministic
    selection outcome (selected provider/model, required capabilities and
    context, priority, routing policy, and the availability metadata used
    — see the Task 36 "Routing Result" requirements). Never contains an API
    key, access token, password, credential, provider SDK object, or
    network connection.
    """

    subject: str
    source: str
    provider_id: str
    model_id: str
    capabilities: tuple[str, ...] = ()
    context_requirements: tuple[str, ...] = ()
    routing_policy_priority: Decimal = _ZERO
    priority: Decimal = _ZERO
    cost: Decimal = _ZERO
    available: bool = True
    detail: str = ""


@dataclass(frozen=True, slots=True)
class ModelGatewayHistory:
    """Append-only record of produced batches."""

    batches: tuple[ModelInvocationBatch, ...] = ()

    def append(self, batch: ModelInvocationBatch) -> ModelGatewayHistory:
        """Return a new history with ``batch`` appended (never mutates)."""
        return ModelGatewayHistory(self.batches + (batch,))


@dataclass(frozen=True, slots=True)
class ModelInvocationRecord:
    """The durable, immutable running state of one model gateway session.

    The Registry owns the current ``ModelInvocationRecord``; the Manager
    loads it, processes one input, and writes back a **new**
    ``ModelInvocationRecord``.
    """

    id: str
    state: ModelGatewayState
    history: ModelGatewayHistory = field(default_factory=ModelGatewayHistory)
    batch: ModelInvocationBatch = field(default_factory=ModelInvocationBatch)
    requests: tuple[ModelInvocationRequest, ...] = ()
    entry_count: int = 0
    request_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ModelGatewayMetrics:
    """Derived metrics over a model gateway record."""

    total_entries: int = 0
    total_requests: int = 0
    average_invocation_score: Decimal = _ZERO
    highest_priority_entry: str = ""
    lowest_priority_entry: str = ""
    dispatch_ratio: Decimal = _ZERO
    pending_requests_count: int = 0
    suppressed_requests_count: int = 0


@dataclass(frozen=True, slots=True)
class ModelGatewaySnapshot:
    """A complete, immutable record of one model gateway update."""

    record: ModelInvocationRecord
    metrics: ModelGatewayMetrics
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class ModelGatewayResult:
    """The immutable outcome of invoking one input."""

    status: ModelGatewayResultStatus
    record: ModelInvocationRecord | None = None
    snapshot: ModelGatewaySnapshot | None = None
    batch: ModelInvocationBatch | None = None
    requests: tuple[ModelInvocationRequest, ...] = ()
    metrics: ModelGatewayMetrics | None = None
    errors: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        """Return ``True`` when the input was invoked successfully."""
        return self.status is ModelGatewayResultStatus.SUCCESS
