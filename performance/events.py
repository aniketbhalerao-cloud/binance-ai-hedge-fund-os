"""Performance Analytics Framework events.

Each inherits the existing :class:`events.base.Event` and is immutable. The
framework publishes **only** these — never strategy, risk, order, execution,
exchange, portfolio, position, or trade events. Events are published only after
a fully successful analysis (never partial or failed calculations).
"""

from __future__ import annotations

from dataclasses import dataclass

from events.base import Event

__all__ = [
    "PerformanceEvent",
    "PerformanceAnalysisStarted",
    "ReturnsCalculated",
    "RiskCalculated",
    "StatisticsCalculated",
    "BenchmarkCalculated",
    "PerformanceSnapshotCreated",
    "PerformanceAnalysisCompleted",
    "PerformanceEngineStarted",
    "PerformanceEngineStopped",
    "PerformanceErrorOccurred",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class PerformanceEvent(Event):
    """Base class for all performance events."""


@dataclass(frozen=True, slots=True, kw_only=True)
class PerformanceAnalysisStarted(PerformanceEvent):
    """A performance analysis run has started."""

    analysis_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ReturnsCalculated(PerformanceEvent):
    """Return metrics were computed for an analysis."""

    analysis_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class RiskCalculated(PerformanceEvent):
    """Risk metrics were computed for an analysis."""

    analysis_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class StatisticsCalculated(PerformanceEvent):
    """Trading statistics were computed for an analysis."""

    analysis_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class BenchmarkCalculated(PerformanceEvent):
    """Benchmark comparison was computed for an analysis."""

    analysis_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PerformanceSnapshotCreated(PerformanceEvent):
    """A performance snapshot was created and registered."""

    analysis_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PerformanceAnalysisCompleted(PerformanceEvent):
    """A performance analysis run completed successfully."""

    analysis_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PerformanceEngineStarted(PerformanceEvent):
    """The performance engine was started."""


@dataclass(frozen=True, slots=True, kw_only=True)
class PerformanceEngineStopped(PerformanceEvent):
    """The performance engine was stopped."""


@dataclass(frozen=True, slots=True, kw_only=True)
class PerformanceErrorOccurred(PerformanceEvent):
    """A performance analysis failed and was isolated by the manager."""

    analysis_id: str
    message: str
