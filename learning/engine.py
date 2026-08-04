"""Learning engine — the public entry point of the Learning Framework.

:class:`DefaultLearningEngine` receives an assembled
:class:`~learning.context.LearningContext` and delegates the learning update to an
injected :class:`~learning.interfaces.LearningManager`. It performs no journal,
evaluation, feedback, or metrics work itself — it only starts, stops, and
coordinates. It never contacts an exchange and never trains a model or calls a
provider or network client.
"""

from __future__ import annotations

from core.logging import LoggerFactory
from learning.context import LearningContext
from learning.interfaces import LearningManager
from learning.models import LearningResult

__all__ = ["DefaultLearningEngine"]


class DefaultLearningEngine:
    """Public learning engine coordinating learning updates.

    Args:
        manager: The learning manager that runs the pipeline (abstraction).
        logger: Optional logger factory for framework logs.
    """

    def __init__(
        self, manager: LearningManager, logger: LoggerFactory | None = None
    ) -> None:
        self._manager = manager
        self._log = logger.get_logger("learning.engine") if logger else None

    async def start(self) -> None:
        """Start the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Learning engine started")

    async def stop(self) -> None:
        """Stop the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Learning engine stopped")

    async def learn(self, context: LearningContext) -> LearningResult:
        """Learn from the completed outcome in ``context``."""
        return await self._manager.learn(context)
