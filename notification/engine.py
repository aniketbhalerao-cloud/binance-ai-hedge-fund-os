"""Notification engine — the public entry point of the Notification Framework.

:class:`DefaultNotificationEngine` receives an assembled
:class:`~notification.context.NotificationContext` and delegates the update to an
injected :class:`~notification.interfaces.NotificationManager`. It performs no
collection, formatting, dispatch, or metrics work itself — it only starts, stops,
and coordinates. It never contacts an exchange, never sends a real notification, and
never trains a model or calls a provider or network client.
"""

from __future__ import annotations

from core.logging import LoggerFactory
from notification.context import NotificationContext
from notification.interfaces import NotificationManager
from notification.models import NotificationResult

__all__ = ["DefaultNotificationEngine"]


class DefaultNotificationEngine:
    """Public notification engine coordinating updates.

    Args:
        manager: The notification manager that runs the pipeline (abstraction).
        logger: Optional logger factory for framework logs.
    """

    def __init__(
        self, manager: NotificationManager, logger: LoggerFactory | None = None
    ) -> None:
        self._manager = manager
        self._log = logger.get_logger("notification.engine") if logger else None

    async def start(self) -> None:
        """Start the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Notification engine started")

    async def stop(self) -> None:
        """Stop the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Notification engine stopped")

    async def notify(self, context: NotificationContext) -> NotificationResult:
        """Produce notification requests for the assembled ``context``."""
        return await self._manager.notify(context)
