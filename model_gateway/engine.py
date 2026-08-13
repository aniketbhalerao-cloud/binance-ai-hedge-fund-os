"""Model Gateway engine — the public entry point of the Model Provider
Gateway Framework.

:class:`DefaultModelGatewayEngine` receives an assembled
:class:`~model_gateway.context.ModelGatewayContext` and delegates the update
to an injected :class:`~model_gateway.interfaces.ModelGatewayManager`. It
performs no collection, planning, dispatch, or metrics work itself — it
only starts, stops, and coordinates. ``invoke()`` only produces a domain
request describing desired inference; it never performs model inference,
calls an AI provider, imports a provider SDK, or makes a network or
credentialed call itself.
"""

from __future__ import annotations

from core.logging import LoggerFactory
from model_gateway.context import ModelGatewayContext
from model_gateway.interfaces import ModelGatewayManager
from model_gateway.models import ModelGatewayResult

__all__ = ["DefaultModelGatewayEngine"]


class DefaultModelGatewayEngine:
    """Public model gateway engine coordinating updates.

    Args:
        manager: The model gateway manager that runs the pipeline
            (abstraction).
        logger: Optional logger factory for framework logs.
    """

    def __init__(
        self, manager: ModelGatewayManager, logger: LoggerFactory | None = None
    ) -> None:
        self._manager = manager
        self._log = logger.get_logger("model_gateway.engine") if logger else None

    async def start(self) -> None:
        """Start the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Model gateway engine started")

    async def stop(self) -> None:
        """Stop the engine (no external I/O)."""
        if self._log is not None:
            self._log.info("Model gateway engine stopped")

    async def invoke(self, context: ModelGatewayContext) -> ModelGatewayResult:
        """Produce model invocation requests for the assembled ``context``.

        This never performs model inference — it only plans and routes an
        immutable domain request.
        """
        return await self._manager.invoke(context)
