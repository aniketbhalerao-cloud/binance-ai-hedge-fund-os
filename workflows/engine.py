"""Workflow engine — the public entry point of the Workflow Orchestration
Framework.

:class:`DefaultWorkflowEngine` receives an assembled
:class:`~workflows.context.WorkflowContext` and delegates composition to an
injected :class:`~workflows.interfaces.WorkflowManager`. It performs no
collection, planning, dispatch, or metrics work itself — it only starts,
stops, and coordinates. ``compose()`` only produces a declarative
``WorkflowPlan`` and immutable ``WorkflowRequest`` handoff-intent objects; it
never executes a step, triggers an Agent, or calls another framework's
manager method itself.
"""

from __future__ import annotations

from core.logging import LoggerFactory
from workflows.context import WorkflowContext
from workflows.interfaces import WorkflowManager
from workflows.models import WorkflowResult

__all__ = ["DefaultWorkflowEngine"]


class DefaultWorkflowEngine:
    """Public workflow engine coordinating composition.

    Args:
        manager: The workflow manager that runs the pipeline (abstraction).
        logger: Optional logger factory for framework logs.
    """

    def __init__(
        self, manager: WorkflowManager, logger: LoggerFactory | None = None
    ) -> None:
        self._manager = manager
        self._log = logger.get_logger("workflows.engine") if logger else None

    async def start(self) -> None:
        """Start the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Workflow engine started")

    async def stop(self) -> None:
        """Stop the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Workflow engine stopped")

    async def compose(self, context: WorkflowContext) -> WorkflowResult:
        """Produce a declarative workflow plan and requests for ``context``.

        This never executes a step, triggers an Agent, or calls another
        framework's manager method — it only plans and routes an immutable
        domain result.
        """
        return await self._manager.compose(context)
