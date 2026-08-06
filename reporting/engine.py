"""Reporting engine — the public entry point of the Reporting Framework.

:class:`DefaultReportingEngine` receives an assembled
:class:`~reporting.context.ReportingContext` and delegates the update to an
injected :class:`~reporting.interfaces.ReportingManager`. It performs no
collection, building, export, or metrics work itself — it only starts, stops,
and coordinates. It never contacts an exchange, never saves or sends a report,
and never trains a model or calls a provider or network client.
"""

from __future__ import annotations

from core.logging import LoggerFactory
from reporting.context import ReportingContext
from reporting.interfaces import ReportingManager
from reporting.models import ReportingResult

__all__ = ["DefaultReportingEngine"]


class DefaultReportingEngine:
    """Public reporting engine coordinating updates.

    Args:
        manager: The reporting manager that runs the pipeline (abstraction).
        logger: Optional logger factory for framework logs.
    """

    def __init__(
        self, manager: ReportingManager, logger: LoggerFactory | None = None
    ) -> None:
        self._manager = manager
        self._log = logger.get_logger("reporting.engine") if logger else None

    async def start(self) -> None:
        """Start the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Reporting engine started")

    async def stop(self) -> None:
        """Stop the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Reporting engine stopped")

    async def report(self, context: ReportingContext) -> ReportingResult:
        """Produce report objects for the assembled ``context``."""
        return await self._manager.report(context)
