"""Notification collector.

:class:`DefaultCollector` gathers the standardized source readings in a context,
normalizes them into :class:`~notification.models.NotificationSource` entries
(highest-priority-first, capped by ``max_notifications``), and builds a raw
:class:`~notification.models.NotificationBatch` with one unformatted notification
per source. Channel routing and delivery are the Formatter and Dispatcher stages'
job. It is deterministic and stateless, and it only *requests* — it never modifies
any subject.
"""

from __future__ import annotations

from notification.context import NotificationContext
from notification.exceptions import CollectionError
from notification.models import (
    Notification,
    NotificationBatch,
    NotificationSource,
)

__all__ = ["DefaultCollector"]


class DefaultCollector:
    """Stateless source collection and batch construction."""

    def collect(self, context: NotificationContext) -> NotificationBatch:
        """Return the raw :class:`NotificationBatch` for ``context``.

        Raises:
            CollectionError: If an unexpected failure occurs.
        """
        try:
            sources = self._sources(context)
            notifications = tuple(Notification(source=s) for s in sources)
            return NotificationBatch(sources=sources, notifications=notifications)
        except CollectionError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise CollectionError(str(exc)) from exc

    @staticmethod
    def _sources(
        context: NotificationContext,
    ) -> tuple[NotificationSource, ...]:
        candidates = [
            *context.monitoring_sources,
            *context.dashboard_sources,
            *context.optimization_sources,
            *context.learning_sources,
        ]
        # Highest-priority-first, with a stable tiebreak by name for determinism.
        candidates.sort(key=lambda s: (-s.priority, s.source, s.name))
        return tuple(candidates[: context.parameters.max_notifications])
