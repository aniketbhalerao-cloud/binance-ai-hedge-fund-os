"""Reporting metrics.

:class:`DefaultReportingMetrics` derives aggregate metrics from a reporting
record: cumulative report and export counts, average report score, highest and
lowest priority report, the export ratio of the current batch, and the pending
/ suppressed report split. It is stateless and pure — metrics are always
derived from the record — and all arithmetic is :class:`~decimal.Decimal`.

``suppressed_reports_count`` reflects the reports that produced no export
request: the framework only exports included reports, it never exports a
suppressed one.
"""

from __future__ import annotations

from decimal import Decimal

from reporting.exceptions import MetricsError
from reporting.models import ReportingMetrics, ReportingRecord

__all__ = ["DefaultReportingMetrics"]

_ZERO = Decimal("0")


class DefaultReportingMetrics:
    """Stateless reporting metrics derived from a record."""

    def calculate(self, record: ReportingRecord) -> ReportingMetrics:
        """Return :class:`ReportingMetrics` for ``record``.

        Raises:
            MetricsError: If an unexpected failure occurs.
        """
        try:
            return self._calculate(record)
        except MetricsError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise MetricsError(str(exc)) from exc

    def _calculate(self, record: ReportingRecord) -> ReportingMetrics:
        sources = record.batch.sources
        reports = record.batch.reports
        pending = len(record.exports)

        if sources:
            highest = max(sources, key=lambda s: s.priority)
            lowest = min(sources, key=lambda s: s.priority)
            avg_priority = sum((s.priority for s in sources), _ZERO) / Decimal(
                len(sources)
            )
            highest_name, lowest_name = highest.name, lowest.name
        else:
            avg_priority, highest_name, lowest_name = _ZERO, "", ""

        if reports:
            included = sum(1 for r in reports if r.include)
            export_ratio = Decimal(included) / Decimal(len(reports))
            suppressed = len(reports) - included
        else:
            export_ratio, suppressed = _ZERO, 0

        return ReportingMetrics(
            total_reports=record.report_count,
            total_exports=record.export_count,
            average_report_score=avg_priority,
            highest_priority_report=highest_name,
            lowest_priority_report=lowest_name,
            export_ratio=export_ratio,
            pending_reports_count=pending,
            suppressed_reports_count=suppressed,
        )
