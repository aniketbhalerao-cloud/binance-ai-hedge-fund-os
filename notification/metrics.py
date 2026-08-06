"""Notification metrics.

:class:`DefaultNotificationMetrics` derives aggregate metrics from a notification
record: cumulative notification and request counts, average priority score, highest
and lowest priority notification, the delivery ratio of the current batch, and the
pending / suppressed request split. It is stateless and pure — metrics are always
derived from the record — and all arithmetic is :class:`~decimal.Decimal`.

``suppressed_requests_count`` reflects the notifications that produced no request:
the framework only requests deliverable notifications, it never sends a suppressed
one.
"""

from __future__ import annotations

from decimal import Decimal

from notification.exceptions import MetricsError
from notification.models import NotificationMetrics, NotificationRecord

__all__ = ["DefaultNotificationMetrics"]

_ZERO = Decimal("0")


class DefaultNotificationMetrics:
    """Stateless notification metrics derived from a record."""

    def calculate(self, record: NotificationRecord) -> NotificationMetrics:
        """Return :class:`NotificationMetrics` for ``record``.

        Raises:
            MetricsError: If an unexpected failure occurs.
        """
        try:
            return self._calculate(record)
        except MetricsError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise MetricsError(str(exc)) from exc

    def _calculate(self, record: NotificationRecord) -> NotificationMetrics:
        sources = record.batch.sources
        notifications = record.batch.notifications
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

        if notifications:
            deliverable = sum(1 for n in notifications if n.deliver)
            delivery = Decimal(deliverable) / Decimal(len(notifications))
            suppressed = len(notifications) - deliverable
        else:
            delivery, suppressed = _ZERO, 0

        return NotificationMetrics(
            total_notifications=record.notification_count,
            total_requests=record.request_count,
            average_priority_score=avg_priority,
            highest_priority_notification=highest_name,
            lowest_priority_notification=lowest_name,
            delivery_ratio=delivery,
            pending_requests_count=pending,
            suppressed_requests_count=suppressed,
        )
