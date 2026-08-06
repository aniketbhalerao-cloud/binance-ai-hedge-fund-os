"""Notification dispatcher.

:class:`DefaultDispatcher` turns the deliverable notifications in a formatted batch
into deterministic :class:`~notification.models.NotificationRequest` domain objects
— a subject, its source, its channel, and the delivery detail. It is stateless and
deterministic, and it **never sends** a real notification through any channel and
never modifies strategies, agents, or portfolios; it only produces requests.
"""

from __future__ import annotations

from notification.context import NotificationContext
from notification.exceptions import DispatchError
from notification.models import NotificationBatch, NotificationRequest

__all__ = ["DefaultDispatcher"]


class DefaultDispatcher:
    """Stateless, deterministic request generation (domain objects only)."""

    def dispatch(
        self, batch: NotificationBatch, context: NotificationContext
    ) -> tuple[NotificationRequest, ...]:
        """Return one request per deliverable notification in ``batch``.

        Raises:
            DispatchError: If an unexpected failure occurs.
        """
        try:
            return tuple(
                NotificationRequest(
                    subject=notification.source.name,
                    source=notification.source.source,
                    channel=notification.channel,
                    category=notification.source.category,
                    priority=notification.source.priority,
                    detail=notification.detail,
                )
                for notification in batch.notifications
                if notification.deliver
            )
        except DispatchError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise DispatchError(str(exc)) from exc
