"""Worker engine — the public entry point of the Background Workers Framework.

:class:`DefaultWorkerEngine` receives an assembled
:class:`~workers.context.WorkerContext` and delegates the update to an
injected :class:`~workers.interfaces.WorkerManager`. It performs no
collection, planning, dispatch, or metrics work itself — it only starts,
stops, and coordinates. It never contacts an exchange, never executes, runs,
or triggers a background job, and never trains a model or calls a provider or
network client.
"""

from __future__ import annotations

from core.logging import LoggerFactory
from workers.context import WorkerContext
from workers.interfaces import WorkerManager
from workers.models import WorkerResult

__all__ = ["DefaultWorkerEngine"]


class DefaultWorkerEngine:
    """Public worker engine coordinating updates.

    Args:
        manager: The worker manager that runs the pipeline (abstraction).
        logger: Optional logger factory for framework logs.
    """

    def __init__(
        self, manager: WorkerManager, logger: LoggerFactory | None = None
    ) -> None:
        self._manager = manager
        self._log = logger.get_logger("workers.engine") if logger else None

    async def start(self) -> None:
        """Start the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Worker engine started")

    async def stop(self) -> None:
        """Stop the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Worker engine stopped")

    async def enqueue(self, context: WorkerContext) -> WorkerResult:
        """Produce worker requests for the assembled ``context``."""
        return await self._manager.enqueue(context)
