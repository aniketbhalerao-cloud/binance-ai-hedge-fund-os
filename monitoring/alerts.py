"""Alert generator.

:class:`DefaultAlerts` turns the unhealthy checks in an evaluated report into
deterministic :class:`~monitoring.models.Alert` proposals — a subject, its source,
a severity, and the observed detail. It is stateless and deterministic, and it
**never sends** a real notification and never modifies strategies, agents, or
portfolios; it only proposes.
"""

from __future__ import annotations

from monitoring.context import MonitoringContext
from monitoring.exceptions import AlertError
from monitoring.models import Alert, HealthReport

__all__ = ["DefaultAlerts"]


class DefaultAlerts:
    """Stateless, deterministic alert generation (proposals only)."""

    def generate(
        self, report: HealthReport, context: MonitoringContext
    ) -> tuple[Alert, ...]:
        """Return one alert per unhealthy check in ``report``.

        Raises:
            AlertError: If an unexpected failure occurs.
        """
        try:
            return tuple(
                Alert(
                    subject=check.component.name,
                    source=check.component.source,
                    severity=check.severity,
                    status=check.component.status,
                    score=check.component.score,
                    detail=check.detail,
                )
                for check in report.checks
                if not check.healthy
            )
        except AlertError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise AlertError(str(exc)) from exc
