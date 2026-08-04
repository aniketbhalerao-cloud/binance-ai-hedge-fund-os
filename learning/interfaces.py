"""Learning Framework interfaces.

Protocols only — no implementations. Components depend on these abstractions so
new evaluators, feedback policies, and metric families plug in without
modification (Open/Closed). DI binds the ``Default*`` / ``InMemory*`` concretes to
these keys (Dependency Inversion).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from learning.context import LearningContext
from learning.models import (
    AgentEvaluation,
    FeedbackRecommendation,
    JournalEntry,
    LearningHistory,
    LearningMetrics,
    LearningOutcome,
    LearningRecord,
    LearningResult,
    StrategyEvaluation,
)

__all__ = [
    "Journal",
    "Evaluator",
    "FeedbackGenerator",
    "LearningMetricsCalculator",
    "LearningRegistry",
    "LearningManager",
    "LearningEngine",
]


@runtime_checkable
class Journal(Protocol):
    """Appends outcomes to an append-only history (stateless)."""

    def record(
        self, history: LearningHistory, outcome: LearningOutcome
    ) -> LearningHistory: ...


@runtime_checkable
class Evaluator(Protocol):
    """Derives strategy and agent evaluations from the journal (stateless)."""

    def evaluate_strategies(
        self, entries: Sequence[JournalEntry]
    ) -> tuple[StrategyEvaluation, ...]: ...

    def evaluate_agents(
        self, entries: Sequence[JournalEntry]
    ) -> tuple[AgentEvaluation, ...]: ...


@runtime_checkable
class FeedbackGenerator(Protocol):
    """Generates deterministic recommendations from evaluations (stateless)."""

    def generate(
        self,
        strategies: Sequence[StrategyEvaluation],
        agents: Sequence[AgentEvaluation],
        parameters: object,
    ) -> tuple[FeedbackRecommendation, ...]: ...


@runtime_checkable
class LearningMetricsCalculator(Protocol):
    """Derives learning metrics from a record (stateless)."""

    def calculate(self, record: LearningRecord) -> LearningMetrics: ...


@runtime_checkable
class LearningRegistry(Protocol):
    """Thread-safe store that owns the running records (never creates them)."""

    def register(self, record: LearningRecord) -> None: ...
    def unregister(self, record_id: str) -> None: ...
    def get(self, record_id: str) -> LearningRecord: ...
    def exists(self, record_id: str) -> bool: ...
    def list(self) -> list[LearningRecord]: ...
    def clear(self) -> None: ...


@runtime_checkable
class LearningManager(Protocol):
    """Processes one outcome atomically and publishes events."""

    async def learn(self, context: LearningContext) -> LearningResult: ...


@runtime_checkable
class LearningEngine(Protocol):
    """Public entry point coordinating learning."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def learn(self, context: LearningContext) -> LearningResult: ...
