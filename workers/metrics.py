"""Worker metrics.

:class:`DefaultWorkerMetrics` derives aggregate metrics from a worker record:
cumulative job and request counts, average job score, highest and lowest
priority job, the dispatch ratio of the current batch, and the pending /
suppressed request split. It is stateless and pure — metrics are always
derived from the record — and all arithmetic is :class:`~decimal.Decimal`.

``suppressed_requests_count`` reflects the jobs that produced no worker
request: the framework only plans dispatchable jobs, it never dispatches a
suppressed one.
"""

from __future__ import annotations

from decimal import Decimal

from workers.exceptions import MetricsError
from workers.models import WorkerMetrics, WorkerRecord

__all__ = ["DefaultWorkerMetrics"]

_ZERO = Decimal("0")


class DefaultWorkerMetrics:
    """Stateless worker metrics derived from a record."""

    def calculate(self, record: WorkerRecord) -> WorkerMetrics:
        """Return :class:`WorkerMetrics` for ``record``.

        Raises:
            MetricsError: If an unexpected failure occurs.
        """
        try:
            return self._calculate(record)
        except MetricsError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise MetricsError(str(exc)) from exc

    def _calculate(self, record: WorkerRecord) -> WorkerMetrics:
        sources = record.batch.sources
        entries = record.batch.entries
        pending = len(record.requests)

        if sources:
            highest = max(sources, key=lambda s: s.priority)
            lowest = min(sources, key=lambda s: s.priority)
            avg_priority = sum((s.priority for s in sources), _ZERO) / Decimal(
                len(sources)
            )
            highest_name, lowest_name = highest.name, lowest.name
        else:
            avg_priority, highest_name, lowest_name = _ZERO, "", ""

        if entries:
            dispatched = sum(1 for e in entries if e.dispatch)
            dispatch_ratio = Decimal(dispatched) / Decimal(len(entries))
            suppressed = len(entries) - dispatched
        else:
            dispatch_ratio, suppressed = _ZERO, 0

        return WorkerMetrics(
            total_jobs=record.job_count,
            total_requests=record.request_count,
            average_job_score=avg_priority,
            highest_priority_job=highest_name,
            lowest_priority_job=lowest_name,
            dispatch_ratio=dispatch_ratio,
            pending_requests_count=pending,
            suppressed_requests_count=suppressed,
        )
