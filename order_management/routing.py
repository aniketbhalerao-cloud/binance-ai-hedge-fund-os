"""Order router.

:class:`DefaultOrderRouter` prepares routing information for a validated order —
it determines a neutral destination and produces an
:class:`~order_management.models.OrderRoute` with metadata for the future
Execution Layer. It is stateless. It never connects to exchanges, submits
orders, or implements exchange-specific routing.
"""

from __future__ import annotations

from order_management.models import OrderMetadata, OrderRequest, OrderRoute

__all__ = ["DefaultOrderRouter", "DEFAULT_DESTINATION"]

#: The neutral, placeholder routing destination used until real routing exists.
DEFAULT_DESTINATION = "default"


class DefaultOrderRouter:
    """Prepares routing metadata without contacting any exchange."""

    def route(self, request: OrderRequest) -> OrderRoute:
        """Return an :class:`OrderRoute` for ``request``.

        The destination is taken from the request metadata when provided,
        otherwise the neutral default is used. No connection is established.
        """
        destination = request.metadata.get("destination", DEFAULT_DESTINATION)
        return OrderRoute(
            destination=destination,
            metadata=OrderMetadata(
                {"symbol": request.symbol, "order_type": request.order_type.value}
            ),
        )
