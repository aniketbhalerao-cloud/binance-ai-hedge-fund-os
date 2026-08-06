"""Reporting builder.

:class:`DefaultBuilder` builds a raw reporting batch into immutable report
domain objects: it assigns each report a report type, resolves whether it
clears the priority threshold for inclusion, and produces the built batch whose
reports carry their routing. It is deterministic and stateless, and it **never
applies changes** — it only constructs the report objects.
"""

from __future__ import annotations

from reporting.context import ReportingContext
from reporting.exceptions import BuildError
from reporting.models import (
    SUPPORTED_REPORT_TYPES,
    Report,
    ReportingBatch,
    ReportingParameters,
    ReportingSource,
)

__all__ = ["DefaultBuilder"]


class DefaultBuilder:
    """Stateless batch building (report construction only, never applied)."""

    def build(
        self, batch: ReportingBatch, context: ReportingContext
    ) -> ReportingBatch:
        """Return the built batch (reports carry their routing).

        Raises:
            BuildError: If an unexpected failure occurs.
        """
        try:
            reports = tuple(
                _report(s, context.parameters) for s in batch.sources
            )
            return ReportingBatch(sources=batch.sources, reports=reports)
        except BuildError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise BuildError(str(exc)) from exc


def _report(source: ReportingSource, parameters: ReportingParameters) -> Report:
    if source.priority >= parameters.priority_threshold:
        include, detail = True, "eligible for export"
    else:
        include, detail = False, "below priority threshold"
    report_type = (
        source.category if source.category in SUPPORTED_REPORT_TYPES else "daily"
    )
    return Report(
        source=source, include=include, report_type=report_type, detail=detail
    )
