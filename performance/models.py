"""Performance Analytics domain models.

Immutable, exchange-independent value objects. The rest of the application
consumes only these standardized models. Every monetary value is
:class:`~decimal.Decimal`; timestamps are timezone-aware UTC. Analysis produces
**new** objects — nothing here is ever mutated.

The metric containers (``ReturnsMetrics`` / ``RiskMetrics`` / ``StatisticsMetrics``
/ ``BenchmarkMetrics``) are the outputs of the four stateless calculators;
``PerformanceMetrics`` aggregates them; ``PerformanceSnapshot`` is the complete,
cacheable record of one analysis; ``PerformanceResult`` is the returned outcome.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from performance.state import PerformanceStatus

__all__ = [
    "PerformanceIdentifier",
    "PerformanceValue",
    "ReturnsMetrics",
    "RiskMetrics",
    "StatisticsMetrics",
    "BenchmarkMetrics",
    "PerformanceMetrics",
    "PerformanceSummary",
    "PerformanceMetadata",
    "PerformanceSnapshot",
    "PerformanceResult",
]

_ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class PerformanceIdentifier:
    """Identity of a single analysis run."""

    id: str
    correlation_id: str | None
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class PerformanceValue:
    """A single labelled metric value (for generic reporting/summaries)."""

    label: str
    value: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class ReturnsMetrics:
    """Return analytics (output of the returns calculator)."""

    daily_return: Decimal = _ZERO
    weekly_return: Decimal = _ZERO
    monthly_return: Decimal = _ZERO
    quarterly_return: Decimal = _ZERO
    yearly_return: Decimal = _ZERO
    total_return: Decimal = _ZERO
    compound_return: Decimal = _ZERO
    cagr: Decimal = _ZERO
    absolute_return: Decimal = _ZERO
    percentage_return: Decimal = _ZERO
    realized_return: Decimal = _ZERO
    unrealized_return: Decimal = _ZERO
    roi: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class RiskMetrics:
    """Risk analytics (output of the risk calculator)."""

    volatility: Decimal = _ZERO
    sharpe_ratio: Decimal = _ZERO
    sortino_ratio: Decimal = _ZERO
    calmar_ratio: Decimal = _ZERO
    max_drawdown: Decimal = _ZERO
    average_drawdown: Decimal = _ZERO
    downside_deviation: Decimal = _ZERO
    upside_capture: Decimal = _ZERO
    risk_reward_ratio: Decimal = _ZERO
    recovery_factor: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class StatisticsMetrics:
    """Trading statistics (output of the statistics calculator)."""

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    open_trades: int = 0
    closed_trades: int = 0
    win_rate: Decimal = _ZERO
    loss_rate: Decimal = _ZERO
    average_win: Decimal = _ZERO
    average_loss: Decimal = _ZERO
    largest_winner: Decimal = _ZERO
    largest_loser: Decimal = _ZERO
    average_holding_time: Decimal = _ZERO
    profit_factor: Decimal = _ZERO
    expectancy: Decimal = _ZERO
    average_position_size: Decimal = _ZERO
    average_trade_duration: Decimal = _ZERO
    best_day: Decimal = _ZERO
    worst_day: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class BenchmarkMetrics:
    """Benchmark-comparison analytics (output of the benchmarking service)."""

    benchmark_return: Decimal = _ZERO
    relative_return: Decimal = _ZERO
    alpha: Decimal = _ZERO
    beta: Decimal = _ZERO
    tracking_error: Decimal = _ZERO
    information_ratio: Decimal = _ZERO
    benchmark_drawdown: Decimal = _ZERO
    excess_return: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class PerformanceMetrics:
    """Aggregate of the four metric families for one analysis."""

    returns: ReturnsMetrics
    risk: RiskMetrics
    statistics: StatisticsMetrics
    benchmark: BenchmarkMetrics


@dataclass(frozen=True, slots=True)
class PerformanceSummary:
    """Compact cross-cutting summary (portfolio + position + trade highlights)."""

    total_value: Decimal = _ZERO
    cost_basis: Decimal = _ZERO
    realized_pnl: Decimal = _ZERO
    unrealized_pnl: Decimal = _ZERO
    open_positions: int = 0
    total_trades: int = 0
    win_rate: Decimal = _ZERO
    gross_profit: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class PerformanceMetadata:
    """Read-only provenance for an analysis (correlation + free-form extras)."""

    source: str = "performance"
    correlation_id: str | None = None
    extra: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "extra", MappingProxyType(dict(self.extra)))


@dataclass(frozen=True, slots=True)
class PerformanceSnapshot:
    """A complete, immutable record of one analysis run."""

    identifier: PerformanceIdentifier
    timestamp: datetime
    returns: ReturnsMetrics
    risk: RiskMetrics
    statistics: StatisticsMetrics
    benchmark: BenchmarkMetrics
    summary: PerformanceSummary
    metadata: PerformanceMetadata


@dataclass(frozen=True, slots=True)
class PerformanceResult:
    """The immutable outcome of a performance analysis."""

    status: PerformanceStatus
    snapshot: PerformanceSnapshot | None = None
    metrics: PerformanceMetrics | None = None
    errors: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        """Return ``True`` when the analysis completed successfully."""
        return self.status is PerformanceStatus.COMPLETED
