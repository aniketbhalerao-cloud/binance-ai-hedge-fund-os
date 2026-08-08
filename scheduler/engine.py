"""Scheduler engine — the public entry point of the Scheduler Framework.

:class:`DefaultSchedulerEngine` receives an assembled
:class:`~scheduler.context.SchedulerContext` and delegates the update to an
injected :class:`~scheduler.interfaces.SchedulerManager`. It performs no
collection, planning, dispatch, or metrics work itself — it only starts,
stops, and coordinates. It never contacts an exchange, never executes,
runs, or triggers a scheduled job, and never trains a model or calls a
provider or network client.
"""

from __future__ import annotations

from core.logging import LoggerFactory
from scheduler.context import SchedulerContext
from scheduler.interfaces import SchedulerManager
from scheduler.models import SchedulerResult

__all__ = ["DefaultSchedulerEngine"]


class DefaultSchedulerEngine:
    """Public scheduler engine coordinating updates.

    Args:
        manager: The scheduler manager that runs the pipeline (abstraction).
        logger: Optional logger factory for framework logs.
    """

    def __init__(
        self, manager: SchedulerManager, logger: LoggerFactory | None = None
    ) -> None:
        self._manager = manager
        self._log = logger.get_logger("scheduler.engine") if logger else None

    async def start(self) -> None:
        """Start the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Scheduler engine started")

    async def stop(self) -> None:
        """Stop the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Scheduler engine stopped")

    async def schedule(self, context: SchedulerContext) -> SchedulerResult:
        """Produce schedule requests for the assembled ``context``."""
        return await self._manager.schedule(context)
