"""Dashboard widget generator.

:class:`DefaultWidgets` turns the visible panels in a composed view into
deterministic :class:`~dashboard.models.Widget` view models — a subject, its
source, its section, and the display detail. It is stateless and deterministic, and
it **never renders** to a real display and never modifies strategies, agents, or
portfolios; it only presents.
"""

from __future__ import annotations

from dashboard.context import DashboardContext
from dashboard.exceptions import WidgetError
from dashboard.models import DashboardView, Widget

__all__ = ["DefaultWidgets"]


class DefaultWidgets:
    """Stateless, deterministic widget generation (view models only)."""

    def generate(
        self, view: DashboardView, context: DashboardContext
    ) -> tuple[Widget, ...]:
        """Return one widget per visible panel in ``view``.

        Raises:
            WidgetError: If an unexpected failure occurs.
        """
        try:
            return tuple(
                Widget(
                    subject=panel.source.name,
                    source=panel.source.source,
                    section=panel.section,
                    label=panel.source.label,
                    score=panel.source.score,
                    detail=panel.detail,
                )
                for panel in view.panels
                if panel.visible
            )
        except WidgetError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise WidgetError(str(exc)) from exc
