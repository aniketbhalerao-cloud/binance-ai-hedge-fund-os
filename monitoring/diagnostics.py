"""Diagnostics.

:class:`DefaultDiagnostics` evaluates a raw health report: it scores each component
against the monitoring thresholds, flags threshold breaches, classifies their
severity (``critical`` / ``warning`` / ``ok``), and resolves the report so the
checks flowing downstream carry their verdicts. It is deterministic and stateless,
and it **never acts** on a breach — it only diagnoses.
"""

from __future__ import annotations

from monitoring.context import MonitoringContext
from monitoring.exceptions import EvaluationError
from monitoring.models import (
    HealthCheck,
    HealthReport,
    MonitoredComponent,
    MonitoringParameters,
)

__all__ = ["DefaultDiagnostics"]


class DefaultDiagnostics:
    """Stateless health evaluation (diagnosis only, never acted upon)."""

    def evaluate(
        self, report: HealthReport, context: MonitoringContext
    ) -> HealthReport:
        """Return the evaluated report (checks carry their verdicts).

        Raises:
            EvaluationError: If an unexpected failure occurs.
        """
        try:
            checks = tuple(
                _check(c, context.parameters) for c in report.components
            )
            return HealthReport(components=report.components, checks=checks)
        except EvaluationError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise EvaluationError(str(exc)) from exc


def _check(
    component: MonitoredComponent, parameters: MonitoringParameters
) -> HealthCheck:
    score = component.score
    if score < parameters.critical_threshold:
        healthy, severity, detail = False, "critical", "below critical threshold"
    elif score < parameters.health_threshold:
        healthy, severity, detail = False, "warning", "below health threshold"
    else:
        healthy, severity, detail = True, "ok", "healthy"
    return HealthCheck(
        component=component, healthy=healthy, severity=severity, detail=detail
    )
