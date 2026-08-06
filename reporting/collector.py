"""Reporting collector.

:class:`DefaultCollector` gathers the standardized source readings in a
context, normalizes them into :class:`~reporting.models.ReportingSource`
entries (highest-priority-first, capped by ``max_reports``), and builds a raw
:class:`~reporting.models.ReportingBatch` with one unbuilt report per source.
Report typing and export routing are the Builder and Exporter stages' job. It
is deterministic and stateless, and it only *collects* — it never modifies any
subject.
"""

from __future__ import annotations

from reporting.context import ReportingContext
from reporting.exceptions import CollectionError
from reporting.models import Report, ReportingBatch, ReportingSource

__all__ = ["DefaultCollector"]


class DefaultCollector:
    """Stateless source collection and batch construction."""

    def collect(self, context: ReportingContext) -> ReportingBatch:
        """Return the raw :class:`ReportingBatch` for ``context``.

        Raises:
            CollectionError: If an unexpected failure occurs.
        """
        try:
            sources = self._sources(context)
            reports = tuple(Report(source=s) for s in sources)
            return ReportingBatch(sources=sources, reports=reports)
        except CollectionError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise CollectionError(str(exc)) from exc

    @staticmethod
    def _sources(
        context: ReportingContext,
    ) -> tuple[ReportingSource, ...]:
        candidates = [
            *context.dashboard_sources,
            *context.notification_sources,
            *context.monitoring_sources,
            *context.performance_sources,
            *context.learning_sources,
        ]
        # Highest-priority-first, with a stable tiebreak by name for determinism.
        candidates.sort(key=lambda s: (-s.priority, s.source, s.name))
        return tuple(candidates[: context.parameters.max_reports])
