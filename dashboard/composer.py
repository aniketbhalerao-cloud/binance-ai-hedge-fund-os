"""Dashboard composer.

:class:`DefaultComposer` composes a raw dashboard view: it assigns each panel to a
section, resolves its visibility against the visible threshold, and produces the
arranged view whose panels carry their placement. It is deterministic and
stateless, and it **never acts** — it only arranges the presentation.
"""

from __future__ import annotations

from dashboard.context import DashboardContext
from dashboard.exceptions import CompositionError
from dashboard.models import (
    DashboardParameters,
    DashboardSource,
    DashboardView,
    Panel,
)

__all__ = ["DefaultComposer"]


class DefaultComposer:
    """Stateless view composition (arrangement only, never acted upon)."""

    def compose(
        self, view: DashboardView, context: DashboardContext
    ) -> DashboardView:
        """Return the arranged view (panels carry their placement).

        Raises:
            CompositionError: If an unexpected failure occurs.
        """
        try:
            panels = tuple(
                _panel(s, context.parameters) for s in view.sources
            )
            return DashboardView(sources=view.sources, panels=panels)
        except CompositionError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise CompositionError(str(exc)) from exc


def _panel(source: DashboardSource, parameters: DashboardParameters) -> Panel:
    if source.score >= parameters.visible_threshold:
        visible, detail = True, "visible"
    else:
        visible, detail = False, "below visible threshold"
    return Panel(
        source=source, visible=visible, section=source.source, detail=detail
    )
