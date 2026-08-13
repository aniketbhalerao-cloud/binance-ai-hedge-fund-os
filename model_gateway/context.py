"""Model Gateway context.

An immutable input carrying standardized outputs from across the running
system — agent decisions, memory records, learning records, and
optimization plans — plus the model gateway parameters (including the
declared, credential-free :class:`~model_gateway.models.ModelProviderProfile`
routing candidates). Model gateway components never access infrastructure
directly; they read only from this context and the models it carries, and
they never modify any subject. Upstream frameworks are responsible for
normalizing their outputs into
:class:`~model_gateway.models.ModelInvocationSource` readings; this
framework only plans and routes immutable model invocation requests from
them. The context must never carry a provider SDK client, network client,
API key, access token, password, or credential.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from model_gateway.models import ModelGatewayParameters, ModelInvocationSource

__all__ = ["ModelGatewayContext"]


@dataclass(frozen=True, slots=True)
class ModelGatewayContext:
    """Immutable input for producing model invocation requests.

    Attributes:
        model_gateway_id: Identifier of the model gateway record to update.
        agent_sources: Agent invocation readings to plan.
        memory_sources: Memory invocation readings to plan.
        learning_sources: Learning invocation readings to plan.
        optimization_sources: Optimization invocation readings to plan.
        parameters: Deterministic model gateway parameters, including the
            declared provider-routing candidates.
        correlation_id: Optional correlation id propagated to events.
        timestamp: When the context was assembled (UTC).
        metadata: Optional read-only extra context.
    """

    model_gateway_id: str = "model_gateway"
    agent_sources: tuple[ModelInvocationSource, ...] = ()
    memory_sources: tuple[ModelInvocationSource, ...] = ()
    learning_sources: tuple[ModelInvocationSource, ...] = ()
    optimization_sources: tuple[ModelInvocationSource, ...] = ()
    parameters: ModelGatewayParameters = field(
        default_factory=ModelGatewayParameters
    )
    correlation_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "agent_sources", tuple(self.agent_sources))
        object.__setattr__(self, "memory_sources", tuple(self.memory_sources))
        object.__setattr__(self, "learning_sources", tuple(self.learning_sources))
        object.__setattr__(
            self, "optimization_sources", tuple(self.optimization_sources)
        )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
