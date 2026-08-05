"""Optimization Framework interfaces.

Protocols only — no implementations. Components depend on these abstractions so
new planners, optimizers, and recommendation policies plug in without modification
(Open/Closed). DI binds the ``Default*`` / ``InMemory*`` concretes to these keys
(Dependency Inversion).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from optimization.context import OptimizationContext
from optimization.models import (
    OptimizationMetrics,
    OptimizationPlan,
    OptimizationRecord,
    OptimizationResult,
    Recommendation,
)

__all__ = [
    "Planner",
    "Optimizer",
    "RecommendationGenerator",
    "OptimizationMetricsCalculator",
    "OptimizationRegistry",
    "OptimizationManager",
    "OptimizationEngine",
]


@runtime_checkable
class Planner(Protocol):
    """Builds an optimization plan from a context (stateless)."""

    def plan(self, context: OptimizationContext) -> OptimizationPlan: ...


@runtime_checkable
class Optimizer(Protocol):
    """Scores and resolves a plan; never applies changes (stateless)."""

    def optimize(
        self, plan: OptimizationPlan, context: OptimizationContext
    ) -> OptimizationPlan: ...


@runtime_checkable
class RecommendationGenerator(Protocol):
    """Generates deterministic recommendations from a plan (stateless)."""

    def generate(
        self, plan: OptimizationPlan, context: OptimizationContext
    ) -> tuple[Recommendation, ...]: ...


@runtime_checkable
class OptimizationMetricsCalculator(Protocol):
    """Derives optimization metrics from a record (stateless)."""

    def calculate(self, record: OptimizationRecord) -> OptimizationMetrics: ...


@runtime_checkable
class OptimizationRegistry(Protocol):
    """Thread-safe store that owns the running records (never creates them)."""

    def register(self, record: OptimizationRecord) -> None: ...
    def unregister(self, record_id: str) -> None: ...
    def get(self, record_id: str) -> OptimizationRecord: ...
    def exists(self, record_id: str) -> bool: ...
    def list(self) -> list[OptimizationRecord]: ...
    def clear(self) -> None: ...


@runtime_checkable
class OptimizationManager(Protocol):
    """Processes one input atomically and publishes events."""

    async def optimize(self, context: OptimizationContext) -> OptimizationResult: ...


@runtime_checkable
class OptimizationEngine(Protocol):
    """Public entry point coordinating optimization."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def optimize(
        self, context: OptimizationContext
    ) -> OptimizationResult: ...
