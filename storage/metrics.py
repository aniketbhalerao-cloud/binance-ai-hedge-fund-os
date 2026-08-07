"""Storage metrics.

:class:`DefaultStorageMetrics` derives aggregate metrics from a storage record:
cumulative item and request counts, average storage score, highest and lowest
priority item, the persistence ratio of the current batch, and the pending /
suppressed request split. It is stateless and pure — metrics are always derived
from the record — and all arithmetic is :class:`~decimal.Decimal`.

``suppressed_requests_count`` reflects the items that produced no storage
request: the framework only plans persistable items, it never persists a
suppressed one.
"""

from __future__ import annotations

from decimal import Decimal

from storage.exceptions import MetricsError
from storage.models import StorageMetrics, StorageRecord

__all__ = ["DefaultStorageMetrics"]

_ZERO = Decimal("0")


class DefaultStorageMetrics:
    """Stateless storage metrics derived from a record."""

    def calculate(self, record: StorageRecord) -> StorageMetrics:
        """Return :class:`StorageMetrics` for ``record``.

        Raises:
            MetricsError: If an unexpected failure occurs.
        """
        try:
            return self._calculate(record)
        except MetricsError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise MetricsError(str(exc)) from exc

    def _calculate(self, record: StorageRecord) -> StorageMetrics:
        sources = record.batch.sources
        items = record.batch.items
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

        if items:
            persisted = sum(1 for i in items if i.persist)
            persistence_ratio = Decimal(persisted) / Decimal(len(items))
            suppressed = len(items) - persisted
        else:
            persistence_ratio, suppressed = _ZERO, 0

        return StorageMetrics(
            total_items=record.item_count,
            total_requests=record.request_count,
            average_storage_score=avg_priority,
            highest_priority_item=highest_name,
            lowest_priority_item=lowest_name,
            persistence_ratio=persistence_ratio,
            pending_requests_count=pending,
            suppressed_requests_count=suppressed,
        )
