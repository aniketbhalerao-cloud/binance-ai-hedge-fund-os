"""Execution router.

:class:`DefaultExecutionRouter` prepares execution routing for a validated
request — it determines a neutral destination and produces an
:class:`ExecutionRoute` with metadata for the future Exchange Adapter. It is
stateless. It never communicates with brokers, submits requests, or implements
broker-specific routing.
"""

from __future__ import annotations

from execution.models import ExecutionMetadata, ExecutionRequest, ExecutionRoute

__all__ = ["DefaultExecutionRouter", "DEFAULT_DESTINATION"]

#: The neutral, placeholder routing destination used until real routing exists.
DEFAULT_DESTINATION = "default"


class DefaultExecutionRouter:
    """Prepares routing metadata without contacting any broker."""

    def route(self, request: ExecutionRequest) -> ExecutionRoute:
        """Return an :class:`ExecutionRoute` for ``request`` (no connection)."""
        destination = request.metadata.get("destination")
        if destination is None and request.order_route is not None:
            destination = request.order_route.destination
        if destination is None:
            destination = DEFAULT_DESTINATION
        return ExecutionRoute(
            destination=destination,
            metadata=ExecutionMetadata(
                {"symbol": request.symbol, "exchange": request.exchange}
            ),
        )
