"""AI decision engine — the public entry point of the AI Decision Engine.

:class:`DefaultDecisionEngine` receives an assembled
:class:`~agents.context.DecisionContext` and delegates the decision to an injected
:class:`~agents.interfaces.DecisionManager`. It performs no agent, consensus, or
metrics work itself — it only starts, stops, and coordinates. It never contacts an
exchange and never calls a model, provider, or network client.
"""

from __future__ import annotations

from agents.context import DecisionContext
from agents.interfaces import DecisionManager
from agents.models import DecisionResult
from core.logging import LoggerFactory

__all__ = ["DefaultDecisionEngine"]


class DefaultDecisionEngine:
    """Public decision engine coordinating decisions.

    Args:
        manager: The decision manager that runs the pipeline (abstraction).
        logger: Optional logger factory for framework logs.
    """

    def __init__(
        self, manager: DecisionManager, logger: LoggerFactory | None = None
    ) -> None:
        self._manager = manager
        self._log = logger.get_logger("agents.engine") if logger else None

    async def start(self) -> None:
        """Start the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Decision engine started")

    async def stop(self) -> None:
        """Stop the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Decision engine stopped")

    async def decide(self, context: DecisionContext) -> DecisionResult:
        """Produce a decision for the assembled ``context``."""
        return await self._manager.decide(context)
