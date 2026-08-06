"""Dashboard aggregator.

:class:`DefaultAggregator` gathers the standardized source readings in a context,
normalizes them into :class:`~dashboard.models.DashboardSource` entries (worst-first,
capped by ``max_panels``), and builds a raw :class:`~dashboard.models.DashboardView`
with one unarranged panel per source. Ordering and visibility are the Composer
stage's job. It is deterministic and stateless, and it only *presents* — it never
modifies any subject.
"""

from __future__ import annotations

from dashboard.context import DashboardContext
from dashboard.exceptions import AggregationError
from dashboard.models import DashboardSource, DashboardView, Panel

__all__ = ["DefaultAggregator"]


class DefaultAggregator:
    """Stateless source aggregation and view construction."""

    def aggregate(self, context: DashboardContext) -> DashboardView:
        """Return the raw :class:`DashboardView` for ``context``.

        Raises:
            AggregationError: If an unexpected failure occurs.
        """
        try:
            sources = self._sources(context)
            panels = tuple(Panel(source=s) for s in sources)
            return DashboardView(sources=sources, panels=panels)
        except AggregationError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise AggregationError(str(exc)) from exc

    @staticmethod
    def _sources(
        context: DashboardContext,
    ) -> tuple[DashboardSource, ...]:
        candidates = [
            *context.strategy_sources,
            *context.performance_sources,
            *context.optimization_sources,
            *context.monitoring_sources,
        ]
        # Worst-first, with a stable tiebreak by name for determinism.
        candidates.sort(key=lambda s: (s.score, s.source, s.name))
        return tuple(candidates[: context.parameters.max_panels])
