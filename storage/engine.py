"""Storage engine — the public entry point of the Storage Framework.

:class:`DefaultStorageEngine` receives an assembled
:class:`~storage.context.StorageContext` and delegates the update to an injected
:class:`~storage.interfaces.StorageManager`. It performs no collection,
serialization, persistence-planning, or metrics work itself — it only starts,
stops, and coordinates. It never contacts an exchange, never persists a request
to any storage target, and never trains a model or calls a provider or network
client.
"""

from __future__ import annotations

from core.logging import LoggerFactory
from storage.context import StorageContext
from storage.interfaces import StorageManager
from storage.models import StorageResult

__all__ = ["DefaultStorageEngine"]


class DefaultStorageEngine:
    """Public storage engine coordinating updates.

    Args:
        manager: The storage manager that runs the pipeline (abstraction).
        logger: Optional logger factory for framework logs.
    """

    def __init__(
        self, manager: StorageManager, logger: LoggerFactory | None = None
    ) -> None:
        self._manager = manager
        self._log = logger.get_logger("storage.engine") if logger else None

    async def start(self) -> None:
        """Start the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Storage engine started")

    async def stop(self) -> None:
        """Stop the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Storage engine stopped")

    async def store(self, context: StorageContext) -> StorageResult:
        """Produce storage requests for the assembled ``context``."""
        return await self._manager.store(context)
