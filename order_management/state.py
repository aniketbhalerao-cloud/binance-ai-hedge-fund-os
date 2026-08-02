"""Order lifecycle states.

Pure data: the finite set of order lifecycle states plus the legal transition
table. This task drives orders only from ``CREATED`` to ``READY_FOR_EXECUTION``;
the later states (``SUBMITTED`` … ``FILLED``) are declared for the future
Execution Layer. No execution logic lives here.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["OrderState", "can_transition", "VALID_TRANSITIONS"]


class OrderState(str, Enum):
    """Lifecycle state of an order."""

    CREATED = "created"
    VALIDATED = "validated"
    ROUTED = "routed"
    READY_FOR_EXECUTION = "ready_for_execution"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


#: Allowed forward transitions. ``REJECTED`` is reachable from the pre-execution
#: states and is handled explicitly by the manager rather than listed everywhere.
VALID_TRANSITIONS: dict[OrderState, frozenset[OrderState]] = {
    OrderState.CREATED: frozenset({OrderState.VALIDATED, OrderState.REJECTED}),
    OrderState.VALIDATED: frozenset({OrderState.ROUTED, OrderState.REJECTED}),
    OrderState.ROUTED: frozenset(
        {OrderState.READY_FOR_EXECUTION, OrderState.REJECTED}
    ),
    OrderState.READY_FOR_EXECUTION: frozenset({OrderState.SUBMITTED}),
    OrderState.SUBMITTED: frozenset(
        {
            OrderState.PARTIALLY_FILLED,
            OrderState.FILLED,
            OrderState.CANCELLED,
            OrderState.EXPIRED,
            OrderState.REJECTED,
        }
    ),
    OrderState.PARTIALLY_FILLED: frozenset(
        {OrderState.FILLED, OrderState.CANCELLED, OrderState.EXPIRED}
    ),
    OrderState.FILLED: frozenset(),
    OrderState.CANCELLED: frozenset(),
    OrderState.REJECTED: frozenset(),
    OrderState.EXPIRED: frozenset(),
}


def can_transition(source: OrderState, target: OrderState) -> bool:
    """Return ``True`` if moving from ``source`` to ``target`` is permitted."""
    return target in VALID_TRANSITIONS.get(source, frozenset())
