"""Memory metrics.

:class:`DefaultMemoryMetrics` derives aggregate metrics from a memory
record: cumulative entry and request counts, average memory score, highest
and lowest priority entry, the commit ratio of the current batch, and the
pending / suppressed request split. It is stateless and pure — metrics are
always derived from the record — and all arithmetic is
:class:`~decimal.Decimal`.

``suppressed_requests_count`` reflects the entries that produced no memory
request: the framework only plans commit-eligible entries, it never commits
a suppressed one.
"""

from __future__ import annotations

from decimal import Decimal

from memory.exceptions import MetricsError
from memory.models import MemoryMetrics, MemoryRecord

__all__ = ["DefaultMemoryMetrics"]

_ZERO = Decimal("0")


class DefaultMemoryMetrics:
    """Stateless memory metrics derived from a record."""

    def calculate(self, record: MemoryRecord) -> MemoryMetrics:
        """Return :class:`MemoryMetrics` for ``record``.

        Raises:
            MetricsError: If an unexpected failure occurs.
        """
        try:
            return self._calculate(record)
        except MetricsError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise MetricsError(str(exc)) from exc

    def _calculate(self, record: MemoryRecord) -> MemoryMetrics:
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
            committed = sum(1 for e in entries if e.commit)
            commit_ratio = Decimal(committed) / Decimal(len(entries))
            suppressed = len(entries) - committed
        else:
            commit_ratio, suppressed = _ZERO, 0

        return MemoryMetrics(
            total_entries=record.entry_count,
            total_requests=record.request_count,
            average_memory_score=avg_priority,
            highest_priority_entry=highest_name,
            lowest_priority_entry=lowest_name,
            commit_ratio=commit_ratio,
            pending_requests_count=pending,
            suppressed_requests_count=suppressed,
        )
