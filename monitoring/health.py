"""Health collector.

:class:`DefaultHealth` gathers the standardized health signals in a context,
normalizes them into :class:`~monitoring.models.MonitoredComponent` readings
(worst-first, capped by ``max_components``), and builds a raw
:class:`~monitoring.models.HealthReport` with one unevaluated check per component.
Scoring and breach detection are the Diagnostics stage's job. It is deterministic
and stateless, and it only *observes* — it never modifies any subject.
"""

from __future__ import annotations

from monitoring.context import MonitoringContext
from monitoring.exceptions import CollectionError
from monitoring.models import HealthCheck, HealthReport, MonitoredComponent

__all__ = ["DefaultHealth"]


class DefaultHealth:
    """Stateless health-signal collection and report construction."""

    def collect(self, context: MonitoringContext) -> HealthReport:
        """Return the raw :class:`HealthReport` for ``context``.

        Raises:
            CollectionError: If an unexpected failure occurs.
        """
        try:
            components = self._components(context)
            checks = tuple(HealthCheck(component=c) for c in components)
            return HealthReport(components=components, checks=checks)
        except CollectionError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise CollectionError(str(exc)) from exc

    @staticmethod
    def _components(
        context: MonitoringContext,
    ) -> tuple[MonitoredComponent, ...]:
        candidates = [
            *context.strategy_signals,
            *context.agent_signals,
            *context.performance_metrics,
            *context.optimization_signals,
        ]
        # Worst-first, with a stable tiebreak by name for determinism.
        candidates.sort(key=lambda c: (c.score, c.source, c.name))
        return tuple(candidates[: context.parameters.max_components])
