"""Reporting exporter.

:class:`DefaultExporter` turns the included reports in a built batch into
deterministic :class:`~reporting.models.ExportRequest` domain objects — a
subject, its source, its report type, and the export detail. It is stateless
and deterministic, and it **never saves, writes, or sends** anything through
any channel and never modifies strategies, agents, or portfolios; it only
produces immutable export request objects.
"""

from __future__ import annotations

from reporting.context import ReportingContext
from reporting.exceptions import ExportError
from reporting.models import ExportRequest, ReportingBatch

__all__ = ["DefaultExporter"]


class DefaultExporter:
    """Stateless, deterministic export request generation (domain objects only)."""

    def export(
        self, batch: ReportingBatch, context: ReportingContext
    ) -> tuple[ExportRequest, ...]:
        """Return one export request per included report in ``batch``.

        Raises:
            ExportError: If an unexpected failure occurs.
        """
        try:
            return tuple(
                ExportRequest(
                    subject=report.source.name,
                    source=report.source.source,
                    report_type=report.report_type,
                    category=report.source.category,
                    priority=report.source.priority,
                    detail=report.detail,
                )
                for report in batch.reports
                if report.include
            )
        except ExportError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise ExportError(str(exc)) from exc
