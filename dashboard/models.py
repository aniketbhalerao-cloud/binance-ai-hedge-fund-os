"""Dashboard Framework domain models.

Immutable, exchange-independent value objects. The rest of the application
consumes only these standardized models. Scores use :class:`~decimal.Decimal`;
timestamps are timezone-aware UTC. Every model is frozen — views, widgets, and the
running record are never mutated; each rendered input produces a **new** record.

The framework only *presents*: widgets carry view-model detail and are never
rendered to a real display, and the framework never modifies a strategy, agent, or
portfolio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from dashboard.state import DashboardState

__all__ = [
    "DashboardResultStatus",
    "DashboardParameters",
    "DashboardSource",
    "Panel",
    "DashboardView",
    "Widget",
    "DashboardHistory",
    "DashboardRecord",
    "DashboardMetrics",
    "DashboardSnapshot",
    "DashboardResult",
]

_ZERO = Decimal("0")


class DashboardResultStatus(str, Enum):
    """Coarse outcome of rendering one input."""

    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class DashboardParameters:
    """Deterministic dashboard configuration.

    Attributes:
        visible_threshold: Score at or above which a panel's widget is visible.
        max_panels: Maximum number of panels to render per input.
    """

    visible_threshold: Decimal = _ZERO
    max_panels: int = 5


@dataclass(frozen=True, slots=True)
class DashboardSource:
    """A normalized display datum feeding one panel."""

    name: str
    source: str
    label: str = "unknown"
    score: Decimal = _ZERO
    samples: int = 0


@dataclass(frozen=True, slots=True)
class Panel:
    """A composed panel within a view (a presentation unit, never acted upon)."""

    source: DashboardSource
    visible: bool = True
    section: str = "general"
    detail: str = ""


@dataclass(frozen=True, slots=True)
class DashboardView:
    """An immutable view: the aggregated sources and their composed panels."""

    sources: tuple[DashboardSource, ...] = ()
    panels: tuple[Panel, ...] = ()


@dataclass(frozen=True, slots=True)
class Widget:
    """A deterministic widget (a view model, never rendered to a real display)."""

    subject: str
    source: str
    section: str
    label: str = "unknown"
    score: Decimal = _ZERO
    detail: str = ""


@dataclass(frozen=True, slots=True)
class DashboardHistory:
    """Append-only record of produced views."""

    views: tuple[DashboardView, ...] = ()

    def append(self, view: DashboardView) -> DashboardHistory:
        """Return a new history with ``view`` appended (never mutates)."""
        return DashboardHistory(self.views + (view,))


@dataclass(frozen=True, slots=True)
class DashboardRecord:
    """The durable, immutable running state of one dashboard session.

    The Registry owns the current ``DashboardRecord``; the Manager loads it,
    processes one input, and writes back a **new** ``DashboardRecord``.
    """

    id: str
    state: DashboardState
    history: DashboardHistory = field(default_factory=DashboardHistory)
    view: DashboardView = field(default_factory=DashboardView)
    widgets: tuple[Widget, ...] = ()
    panel_count: int = 0
    widget_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class DashboardMetrics:
    """Derived metrics over a dashboard record."""

    total_panels: int = 0
    total_widgets: int = 0
    average_panel_score: Decimal = _ZERO
    best_panel: str = ""
    worst_panel: str = ""
    coverage_ratio: Decimal = _ZERO
    visible_widgets_count: int = 0
    hidden_widgets_count: int = 0


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    """A complete, immutable record of one dashboard update."""

    record: DashboardRecord
    metrics: DashboardMetrics
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class DashboardResult:
    """The immutable outcome of rendering one input."""

    status: DashboardResultStatus
    record: DashboardRecord | None = None
    snapshot: DashboardSnapshot | None = None
    view: DashboardView | None = None
    widgets: tuple[Widget, ...] = ()
    metrics: DashboardMetrics | None = None
    errors: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        """Return ``True`` when the input was rendered successfully."""
        return self.status is DashboardResultStatus.SUCCESS
