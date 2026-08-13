"""Model Gateway metrics.

:class:`DefaultModelGatewayMetrics` derives aggregate metrics from a model
gateway record: cumulative entry and request counts, average invocation
score, highest and lowest priority entry, the dispatch ratio of the current
batch, and the pending / suppressed request split. It is stateless and pure
— metrics are always derived from the record — and all arithmetic is
:class:`~decimal.Decimal`.

Unlike the sibling frameworks (Storage/Scheduler/Workers/Memory), whose
single planning stage fully determines which entries produce a request,
Model Gateway has a *second* filtering stage: an entry can be
``dispatch``-eligible after planning yet still produce no request because
no provider candidate was eligible or the routing tie was unresolvable (see
``model_gateway.dispatcher``). Counting the entry-level ``dispatch`` flag
alone would therefore overstate how many entries actually got dispatched.
``dispatch_ratio`` and ``suppressed_requests_count`` are computed from the
*actual* requests produced this batch (``record.requests``) instead.
"""

from __future__ import annotations

from decimal import Decimal

from model_gateway.exceptions import MetricsError
from model_gateway.models import ModelGatewayMetrics, ModelInvocationRecord

__all__ = ["DefaultModelGatewayMetrics"]

_ZERO = Decimal("0")


class DefaultModelGatewayMetrics:
    """Stateless model gateway metrics derived from a record."""

    def calculate(self, record: ModelInvocationRecord) -> ModelGatewayMetrics:
        """Return :class:`ModelGatewayMetrics` for ``record``.

        Raises:
            MetricsError: If an unexpected failure occurs.
        """
        try:
            return self._calculate(record)
        except MetricsError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise MetricsError(str(exc)) from exc

    def _calculate(self, record: ModelInvocationRecord) -> ModelGatewayMetrics:
        sources = record.batch.sources
        entries = record.batch.entries
        dispatched = len(record.requests)
        pending = dispatched

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
            dispatch_ratio = Decimal(dispatched) / Decimal(len(entries))
            suppressed = len(entries) - dispatched
        else:
            dispatch_ratio, suppressed = _ZERO, 0

        return ModelGatewayMetrics(
            total_entries=record.entry_count,
            total_requests=record.request_count,
            average_invocation_score=avg_priority,
            highest_priority_entry=highest_name,
            lowest_priority_entry=lowest_name,
            dispatch_ratio=dispatch_ratio,
            pending_requests_count=pending,
            suppressed_requests_count=suppressed,
        )
