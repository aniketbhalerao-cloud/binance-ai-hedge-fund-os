"""Monitoring metrics.

:class:`DefaultMonitoringMetrics` derives aggregate metrics from a monitoring
record: cumulative check and alert counts, average component health score, best and
worst component, the uptime ratio of the current report, and the active / resolved
alert split. It is stateless and pure — metrics are always derived from the record
— and all arithmetic is :class:`~decimal.Decimal`.

``resolved_alerts_count`` is always zero by design: the framework only observes, it
never resolves an alert.
"""

from __future__ import annotations

from decimal import Decimal

from monitoring.exceptions import MetricsError
from monitoring.models import MonitoringMetrics, MonitoringRecord

__all__ = ["DefaultMonitoringMetrics"]

_ZERO = Decimal("0")


class DefaultMonitoringMetrics:
    """Stateless monitoring metrics derived from a record."""

    def calculate(self, record: MonitoringRecord) -> MonitoringMetrics:
        """Return :class:`MonitoringMetrics` for ``record``.

        Raises:
            MetricsError: If an unexpected failure occurs.
        """
        try:
            return self._calculate(record)
        except MetricsError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise MetricsError(str(exc)) from exc

    def _calculate(self, record: MonitoringRecord) -> MonitoringMetrics:
        components = record.report.components
        checks = record.report.checks
        active = len(record.alerts)

        if components:
            best = max(components, key=lambda c: c.score)
            worst = min(components, key=lambda c: c.score)
            avg_score = sum((c.score for c in components), _ZERO) / Decimal(
                len(components)
            )
            best_name, worst_name = best.name, worst.name
        else:
            avg_score, best_name, worst_name = _ZERO, "", ""

        if checks:
            healthy = sum(1 for c in checks if c.healthy)
            uptime = Decimal(healthy) / Decimal(len(checks))
        else:
            uptime = _ZERO

        return MonitoringMetrics(
            total_checks=record.check_count,
            total_alerts=record.alert_count,
            average_health_score=avg_score,
            best_component=best_name,
            worst_component=worst_name,
            uptime_ratio=uptime,
            active_alerts_count=active,
            resolved_alerts_count=0,  # alerts are never resolved by the framework
        )
