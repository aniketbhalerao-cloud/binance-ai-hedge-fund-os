"""Model Provider Gateway Framework events.

Each inherits the existing :class:`events.base.Event` and is immutable. The
framework publishes **only** these — never agents, memory, learning,
optimization, or any other framework's events. Events are published only
after a consistent record update (or an isolated failure), and never carry
a credential, API key, access token, provider SDK object, network client,
or other mutable state.
"""

from __future__ import annotations

from dataclasses import dataclass

from events.base import Event

__all__ = [
    "ModelGatewayEvent",
    "ModelGatewayStarted",
    "InvocationsCollected",
    "InvocationsPlanned",
    "RequestsDispatched",
    "ModelGatewaySnapshotCreated",
    "ModelGatewayMetricsUpdated",
    "ModelGatewayCompleted",
    "ModelGatewayCancelled",
    "ModelGatewayErrorOccurred",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelGatewayEvent(Event):
    """Base class for all model gateway events."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelGatewayStarted(ModelGatewayEvent):
    """A model gateway update was requested for a record."""

    model_gateway_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class InvocationsCollected(ModelGatewayEvent):
    """A model invocation batch was collected."""

    model_gateway_id: str
    entries: int


@dataclass(frozen=True, slots=True, kw_only=True)
class InvocationsPlanned(ModelGatewayEvent):
    """The model invocation batch's entries were planned."""

    model_gateway_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RequestsDispatched(ModelGatewayEvent):
    """Model invocation requests were generated (domain objects, never executed)."""

    model_gateway_id: str
    count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelGatewaySnapshotCreated(ModelGatewayEvent):
    """A model gateway snapshot was created."""

    model_gateway_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelGatewayMetricsUpdated(ModelGatewayEvent):
    """Model gateway metrics were recomputed."""

    model_gateway_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelGatewayCompleted(ModelGatewayEvent):
    """A model gateway update completed successfully."""

    model_gateway_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelGatewayCancelled(ModelGatewayEvent):
    """A model gateway session was cancelled."""

    model_gateway_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelGatewayErrorOccurred(ModelGatewayEvent):
    """A model gateway update failed and was isolated by the manager."""

    model_gateway_id: str
    message: str
