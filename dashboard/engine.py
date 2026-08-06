"""Dashboard engine — the public entry point of the Dashboard Framework.

:class:`DefaultDashboardEngine` receives an assembled
:class:`~dashboard.context.DashboardContext` and delegates the update to an injected
:class:`~dashboard.interfaces.DashboardManager`. It performs no aggregation,
composition, widget, or metrics work itself — it only starts, stops, and
coordinates. It never contacts an exchange, never renders to a real display, and
never trains a model or calls a provider or network client.
"""

from __future__ import annotations

from core.logging import LoggerFactory
from dashboard.context import DashboardContext
from dashboard.interfaces import DashboardManager
from dashboard.models import DashboardResult

__all__ = ["DefaultDashboardEngine"]


class DefaultDashboardEngine:
    """Public dashboard engine coordinating updates.

    Args:
        manager: The dashboard manager that runs the pipeline (abstraction).
        logger: Optional logger factory for framework logs.
    """

    def __init__(
        self, manager: DashboardManager, logger: LoggerFactory | None = None
    ) -> None:
        self._manager = manager
        self._log = logger.get_logger("dashboard.engine") if logger else None

    async def start(self) -> None:
        """Start the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Dashboard engine started")

    async def stop(self) -> None:
        """Stop the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Dashboard engine stopped")

    async def render(self, context: DashboardContext) -> DashboardResult:
        """Render a dashboard for the assembled ``context``."""
        return await self._manager.render(context)
