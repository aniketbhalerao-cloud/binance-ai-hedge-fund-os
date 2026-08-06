"""Notification formatter.

:class:`DefaultFormatter` formats a raw notification batch: it assigns each
notification to a channel, resolves whether it clears the priority threshold for
delivery, and produces the arranged batch whose notifications carry their routing.
It is deterministic and stateless, and it **never sends** anything — it only
arranges the requests.
"""

from __future__ import annotations

from notification.context import NotificationContext
from notification.exceptions import FormattingError
from notification.models import (
    Notification,
    NotificationBatch,
    NotificationParameters,
    NotificationSource,
)

__all__ = ["DefaultFormatter"]


class DefaultFormatter:
    """Stateless batch formatting (arrangement only, never sent)."""

    def format(
        self, batch: NotificationBatch, context: NotificationContext
    ) -> NotificationBatch:
        """Return the arranged batch (notifications carry their routing).

        Raises:
            FormattingError: If an unexpected failure occurs.
        """
        try:
            notifications = tuple(
                _notification(s, context.parameters) for s in batch.sources
            )
            return NotificationBatch(
                sources=batch.sources, notifications=notifications
            )
        except FormattingError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise FormattingError(str(exc)) from exc


def _notification(
    source: NotificationSource, parameters: NotificationParameters
) -> Notification:
    if source.priority >= parameters.priority_threshold:
        deliver, detail = True, "eligible for delivery"
    else:
        deliver, detail = False, "below priority threshold"
    return Notification(
        source=source, deliver=deliver, channel=source.source, detail=detail
    )
