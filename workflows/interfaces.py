"""Workflow Orchestration Framework interfaces.

Protocols only — no implementations. Components depend on these
abstractions so new collectors, planners, and ordering policies plug in
without modification (Open/Closed). DI binds the ``Default*`` /
``InMemory*`` concretes to these keys (Dependency Inversion).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from workflows.context import WorkflowContext
from workflows.models import (
    WorkflowBatch,
    WorkflowMetrics,
    WorkflowPlan,
    WorkflowRecord,
    WorkflowRequest,
    WorkflowResult,
)

__all__ = [
    "Collector",
    "Planner",
    "Dispatcher",
    "WorkflowMetricsCalculator",
    "WorkflowRegistry",
    "WorkflowManager",
    "WorkflowEngine",
]


@runtime_checkable
class Collector(Protocol):
    """Builds a workflow batch from a context (stateless)."""

    def collect(self, context: WorkflowContext) -> WorkflowBatch: ...


@runtime_checkable
class Planner(Protocol):
    """Validates and deterministically orders a batch into a plan (stateless)."""

    def plan(self, batch: WorkflowBatch, context: WorkflowContext) -> WorkflowPlan: ...


@runtime_checkable
class Dispatcher(Protocol):
    """Produces deterministic, immutable workflow requests (stateless)."""

    def dispatch(
        self, plan: WorkflowPlan, context: WorkflowContext
    ) -> tuple[WorkflowRequest, ...]: ...


@runtime_checkable
class WorkflowMetricsCalculator(Protocol):
    """Derives workflow metrics from a record (stateless)."""

    def calculate(self, record: WorkflowRecord) -> WorkflowMetrics: ...


@runtime_checkable
class WorkflowRegistry(Protocol):
    """Thread-safe store that owns the running records (never creates them)."""

    def register(self, record: WorkflowRecord) -> None: ...
    def unregister(self, record_id: str) -> None: ...
    def get(self, record_id: str) -> WorkflowRecord: ...
    def exists(self, record_id: str) -> bool: ...
    def list(self) -> list[WorkflowRecord]: ...
    def clear(self) -> None: ...


@runtime_checkable
class WorkflowManager(Protocol):
    """Processes one input atomically and publishes events."""

    async def compose(self, context: WorkflowContext) -> WorkflowResult: ...


@runtime_checkable
class WorkflowEngine(Protocol):
    """Public entry point coordinating workflow composition."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def compose(self, context: WorkflowContext) -> WorkflowResult: ...
