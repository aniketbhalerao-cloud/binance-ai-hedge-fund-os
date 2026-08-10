"""Memory engine — the public entry point of the Memory Framework.

:class:`DefaultMemoryEngine` receives an assembled
:class:`~memory.context.MemoryContext` and delegates the update to an
injected :class:`~memory.interfaces.MemoryManager`. It performs no
collection, planning, dispatch, or metrics work itself — it only starts,
stops, and coordinates. It never contacts an exchange, never calls an AI
provider, computes an embedding, or accesses a vector database, and never
trains a model or calls a network client.
"""

from __future__ import annotations

from core.logging import LoggerFactory
from memory.context import MemoryContext
from memory.interfaces import MemoryManager
from memory.models import MemoryResult

__all__ = ["DefaultMemoryEngine"]


class DefaultMemoryEngine:
    """Public memory engine coordinating updates.

    Args:
        manager: The memory manager that runs the pipeline (abstraction).
        logger: Optional logger factory for framework logs.
    """

    def __init__(
        self, manager: MemoryManager, logger: LoggerFactory | None = None
    ) -> None:
        self._manager = manager
        self._log = logger.get_logger("memory.engine") if logger else None

    async def start(self) -> None:
        """Start the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Memory engine started")

    async def stop(self) -> None:
        """Stop the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Memory engine stopped")

    async def remember(self, context: MemoryContext) -> MemoryResult:
        """Produce memory requests for the assembled ``context``."""
        return await self._manager.remember(context)
