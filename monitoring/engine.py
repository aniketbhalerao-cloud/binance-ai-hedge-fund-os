"""Monitoring engine — the public entry point of the Monitoring Framework.

:class:`DefaultMonitoringEngine` receives an assembled
:class:`~monitoring.context.MonitoringContext` and delegates the update to an
injected :class:`~monitoring.interfaces.MonitoringManager`. It performs no
collection, diagnostics, alerting, or metrics work itself — it only starts, stops,
and coordinates. It never contacts an exchange, never sends an alert, and never
trains a model or calls a provider or network client.
"""

from __future__ import annotations

from core.logging import LoggerFactory
from monitoring.context import MonitoringContext
from monitoring.interfaces import MonitoringManager
from monitoring.models import MonitoringResult

__all__ = ["DefaultMonitoringEngine"]


class DefaultMonitoringEngine:
    """Public monitoring engine coordinating updates.

    Args:
        manager: The monitoring manager that runs the pipeline (abstraction).
        logger: Optional logger factory for framework logs.
    """

    def __init__(
        self, manager: MonitoringManager, logger: LoggerFactory | None = None
    ) -> None:
        self._manager = manager
        self._log = logger.get_logger("monitoring.engine") if logger else None

    async def start(self) -> None:
        """Start the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Monitoring engine started")

    async def stop(self) -> None:
        """Stop the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Monitoring engine stopped")

    async def monitor(self, context: MonitoringContext) -> MonitoringResult:
        """Observe system health for the assembled ``context``."""
        return await self._manager.monitor(context)
