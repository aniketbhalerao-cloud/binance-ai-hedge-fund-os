"""Workflow metrics.

:class:`DefaultWorkflowMetrics` derives aggregate metrics from a workflow
record: cumulative step and request counts, average step score, highest and
lowest priority step, the dispatch ratio of the current batch, and the
pending / suppressed request split. It is stateless and pure — metrics are
always derived from the record — and all arithmetic is
:class:`~decimal.Decimal`.

Every resolved plan entry deterministically produces exactly one request
(unlike Model Gateway, planning here never leaves a validated step
unresolved — an invalid definition fails planning outright rather than
suppressing individual steps). ``dispatch_ratio`` and
``suppressed_requests_count`` are still computed from the actual requests
produced this batch, for shape parity with every sibling framework.
"""

from __future__ import annotations

from decimal import Decimal

from workflows.exceptions import MetricsError
from workflows.models import WorkflowMetrics, WorkflowRecord

__all__ = ["DefaultWorkflowMetrics"]

_ZERO = Decimal("0")


class DefaultWorkflowMetrics:
    """Stateless workflow metrics derived from a record."""

    def calculate(self, record: WorkflowRecord) -> WorkflowMetrics:
        """Return :class:`WorkflowMetrics` for ``record``.

        Raises:
            MetricsError: If an unexpected failure occurs.
        """
        try:
            return self._calculate(record)
        except MetricsError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise MetricsError(str(exc)) from exc

    def _calculate(self, record: WorkflowRecord) -> WorkflowMetrics:
        steps = [s for d in record.batch.definitions for s in d.steps]
        dispatched = len(record.requests)
        pending = dispatched

        if steps:
            highest = max(steps, key=lambda s: s.priority)
            lowest = min(steps, key=lambda s: s.priority)
            avg_priority = sum((s.priority for s in steps), _ZERO) / Decimal(
                len(steps)
            )
            highest_id, lowest_id = highest.step_id, lowest.step_id
        else:
            avg_priority, highest_id, lowest_id = _ZERO, "", ""

        if steps:
            dispatch_ratio = Decimal(dispatched) / Decimal(len(steps))
            suppressed = len(steps) - dispatched
        else:
            dispatch_ratio, suppressed = _ZERO, 0

        return WorkflowMetrics(
            total_steps=record.step_count,
            total_requests=record.request_count,
            average_step_score=avg_priority,
            highest_priority_step=highest_id,
            lowest_priority_step=lowest_id,
            dispatch_ratio=dispatch_ratio,
            pending_requests_count=pending,
            suppressed_requests_count=suppressed,
        )
