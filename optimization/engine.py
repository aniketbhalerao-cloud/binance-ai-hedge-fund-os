"""Optimization engine — the public entry point of the Optimization Framework.

:class:`DefaultOptimizationEngine` receives an assembled
:class:`~optimization.context.OptimizationContext` and delegates the update to an
injected :class:`~optimization.interfaces.OptimizationManager`. It performs no
planning, optimizing, recommendation, or metrics work itself — it only starts,
stops, and coordinates. It never contacts an exchange, never applies a
recommendation, and never trains a model or calls a provider or network client.
"""

from __future__ import annotations

from core.logging import LoggerFactory
from optimization.context import OptimizationContext
from optimization.interfaces import OptimizationManager
from optimization.models import OptimizationResult

__all__ = ["DefaultOptimizationEngine"]


class DefaultOptimizationEngine:
    """Public optimization engine coordinating updates.

    Args:
        manager: The optimization manager that runs the pipeline (abstraction).
        logger: Optional logger factory for framework logs.
    """

    def __init__(
        self, manager: OptimizationManager, logger: LoggerFactory | None = None
    ) -> None:
        self._manager = manager
        self._log = logger.get_logger("optimization.engine") if logger else None

    async def start(self) -> None:
        """Start the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Optimization engine started")

    async def stop(self) -> None:
        """Stop the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Optimization engine stopped")

    async def optimize(self, context: OptimizationContext) -> OptimizationResult:
        """Produce optimization proposals for the assembled ``context``."""
        return await self._manager.optimize(context)
