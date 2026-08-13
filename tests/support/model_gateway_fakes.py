"""Helpers for Model Provider Gateway Framework tests.

Standalone support module (existing support files unchanged). Builds
deterministic model gateway contexts, sources, and provider profiles. No
network, no sleeps, no randomness, no model training, and no credential
material anywhere.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from model_gateway.context import ModelGatewayContext
from model_gateway.models import (
    ModelGatewayParameters,
    ModelInvocationSource,
    ModelProviderProfile,
)

__all__ = [
    "make_source",
    "make_profile",
    "make_context",
]


def make_source(
    name: str,
    priority: str,
    *,
    source: str = "learning",
    category: str = "unknown",
    samples: int = 5,
    required_capabilities: Sequence[str] = (),
    required_context: Sequence[str] = (),
    preferred_provider_id: str = "",
    preferred_model_id: str = "",
) -> ModelInvocationSource:
    """Build a normalized source reading with a given priority."""
    return ModelInvocationSource(
        name=name,
        source=source,
        category=category,
        priority=Decimal(priority),
        samples=samples,
        required_capabilities=tuple(required_capabilities),
        required_context=tuple(required_context),
        preferred_provider_id=preferred_provider_id,
        preferred_model_id=preferred_model_id,
    )


def make_profile(
    provider_id: str,
    model_id: str,
    *,
    capabilities: Sequence[str] = (),
    context_support: Sequence[str] = (),
    routing_policy_priority: str = "0",
    priority: str = "0",
    cost: str = "0",
    available: bool = True,
    routing_id: str = "",
) -> ModelProviderProfile:
    """Build an immutable, credential-free routing candidate."""
    return ModelProviderProfile(
        provider_id=provider_id,
        model_id=model_id,
        capabilities=tuple(capabilities),
        context_support=tuple(context_support),
        routing_policy_priority=Decimal(routing_policy_priority),
        priority=Decimal(priority),
        cost=Decimal(cost),
        available=available,
        routing_id=routing_id,
    )


def make_context(
    *,
    model_gateway_id: str = "gateway-1",
    agent: Sequence[ModelInvocationSource] | None = None,
    memory: Sequence[ModelInvocationSource] | None = None,
    learning: Sequence[ModelInvocationSource] | None = None,
    optimization: Sequence[ModelInvocationSource] | None = None,
    provider_profiles: Sequence[ModelProviderProfile] | None = None,
    parameters: ModelGatewayParameters | None = None,
    cancel: bool = False,
) -> ModelGatewayContext:
    """Build a deterministic model gateway context.

    Defaults to two ``learning`` sources (``cpu``/``mem``, matching every
    sibling framework's fixture convention) and one always-eligible
    provider profile, unless overridden.
    """
    metadata = {"cancel": True} if cancel else {}
    if parameters is None:
        profiles = (
            tuple(provider_profiles)
            if provider_profiles is not None
            else (make_profile("anthropic", "claude"),)
        )
        parameters = ModelGatewayParameters(provider_profiles=profiles)
    return ModelGatewayContext(
        model_gateway_id=model_gateway_id,
        agent_sources=tuple(agent) if agent is not None else (),
        memory_sources=tuple(memory) if memory is not None else (),
        learning_sources=tuple(learning) if learning is not None
        else (make_source("cpu", "5"), make_source("mem", "-3")),
        optimization_sources=tuple(optimization) if optimization is not None else (),
        parameters=parameters,
        correlation_id="gateway-corr",
        metadata=metadata,
    )
