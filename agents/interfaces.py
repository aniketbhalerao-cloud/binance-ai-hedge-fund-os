"""AI Decision Engine interfaces.

Protocols only — no implementations. Components depend on these abstractions so
new agents and resolvers plug in without modification (Open/Closed). The ``Agent``
protocol is the key extension point: concrete agents (rule-based defaults today,
model-backed agents in future) are injected, and the framework core never calls a
model, provider, or network client.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from agents.context import DecisionContext
from agents.models import (
    AgentOpinion,
    AgentRole,
    ConsensusResult,
    Decision,
    DecisionMetrics,
    DecisionParameters,
    DecisionResult,
)

__all__ = [
    "Agent",
    "ConsensusResolver",
    "DecisionMetricsCalculator",
    "DecisionHistoryService",
    "AgentRegistry",
    "DecisionManager",
    "DecisionEngine",
]


@runtime_checkable
class Agent(Protocol):
    """An autonomous agent that reasons over a context and produces an opinion."""

    @property
    def role(self) -> AgentRole: ...

    async def evaluate(self, context: DecisionContext) -> AgentOpinion: ...


@runtime_checkable
class ConsensusResolver(Protocol):
    """Aggregates agent opinions into a consensus result (stateless)."""

    def resolve(
        self,
        opinions: Sequence[AgentOpinion],
        parameters: DecisionParameters,
    ) -> ConsensusResult: ...


@runtime_checkable
class DecisionMetricsCalculator(Protocol):
    """Derives metrics from a set of decisions (stateless)."""

    def calculate(self, decisions: Sequence[Decision]) -> DecisionMetrics: ...


@runtime_checkable
class DecisionHistoryService(Protocol):
    """Appends decisions to an append-only history (stateless)."""

    def append(self, history: object, decision: Decision) -> object: ...


@runtime_checkable
class AgentRegistry(Protocol):
    """Thread-safe store of agents keyed by role (never creates them)."""

    def register(self, agent: Agent) -> None: ...
    def unregister(self, role: AgentRole) -> None: ...
    def get(self, role: AgentRole) -> Agent: ...
    def exists(self, role: AgentRole) -> bool: ...
    def list(self) -> list[Agent]: ...
    def clear(self) -> None: ...


@runtime_checkable
class DecisionManager(Protocol):
    """Coordinates the decision pipeline and publishes events."""

    async def decide(self, context: DecisionContext) -> DecisionResult: ...


@runtime_checkable
class DecisionEngine(Protocol):
    """Public entry point coordinating decisions."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def decide(self, context: DecisionContext) -> DecisionResult: ...
