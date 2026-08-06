"""Dashboard metrics.

:class:`DefaultDashboardMetrics` derives aggregate metrics from a dashboard record:
cumulative panel and widget counts, average panel score, best and worst panel, the
coverage ratio of the current view, and the visible / hidden widget split. It is
stateless and pure — metrics are always derived from the record — and all
arithmetic is :class:`~decimal.Decimal`.

``hidden_widgets_count`` reflects the panels that produced no widget: the framework
only presents visible panels, it never renders a hidden one.
"""

from __future__ import annotations

from decimal import Decimal

from dashboard.exceptions import MetricsError
from dashboard.models import DashboardMetrics, DashboardRecord

__all__ = ["DefaultDashboardMetrics"]

_ZERO = Decimal("0")


class DefaultDashboardMetrics:
    """Stateless dashboard metrics derived from a record."""

    def calculate(self, record: DashboardRecord) -> DashboardMetrics:
        """Return :class:`DashboardMetrics` for ``record``.

        Raises:
            MetricsError: If an unexpected failure occurs.
        """
        try:
            return self._calculate(record)
        except MetricsError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise MetricsError(str(exc)) from exc

    def _calculate(self, record: DashboardRecord) -> DashboardMetrics:
        sources = record.view.sources
        panels = record.view.panels
        visible = len(record.widgets)

        if sources:
            best = max(sources, key=lambda s: s.score)
            worst = min(sources, key=lambda s: s.score)
            avg_score = sum((s.score for s in sources), _ZERO) / Decimal(len(sources))
            best_name, worst_name = best.name, worst.name
        else:
            avg_score, best_name, worst_name = _ZERO, "", ""

        if panels:
            shown = sum(1 for p in panels if p.visible)
            coverage = Decimal(shown) / Decimal(len(panels))
            hidden = len(panels) - shown
        else:
            coverage, hidden = _ZERO, 0

        return DashboardMetrics(
            total_panels=record.panel_count,
            total_widgets=record.widget_count,
            average_panel_score=avg_score,
            best_panel=best_name,
            worst_panel=worst_name,
            coverage_ratio=coverage,
            visible_widgets_count=visible,
            hidden_widgets_count=hidden,
        )
