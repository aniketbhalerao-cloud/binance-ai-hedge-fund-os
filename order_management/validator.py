"""Order validator.

:class:`DefaultOrderValidator` checks an :class:`OrderRequest` for structural
consistency (required fields, quantity, price/stop by order type) and produces an
:class:`OrderValidationResult`. It is stateless. It performs no risk evaluation,
indicator calculation, exchange access, or submission.
"""

from __future__ import annotations

from models import OrderType

from order_management.models import OrderRequest, OrderValidationResult

__all__ = ["DefaultOrderValidator"]

_PRICE_REQUIRED = {OrderType.LIMIT, OrderType.STOP_LIMIT}
_STOP_REQUIRED = {OrderType.STOP, OrderType.STOP_LIMIT}


class DefaultOrderValidator:
    """Validates the consistency of an :class:`OrderRequest`."""

    def validate(self, request: OrderRequest) -> OrderValidationResult:
        """Return a validation result listing any structural problems."""
        errors: list[str] = []

        if not request.symbol:
            errors.append("symbol must not be empty")
        if request.quantity <= 0:
            errors.append("quantity must be greater than 0")

        if request.order_type in _PRICE_REQUIRED:
            if request.price is None or request.price <= 0:
                errors.append(f"{request.order_type.value} order requires a positive price")
        if request.order_type in _STOP_REQUIRED:
            if request.stop_price is None or request.stop_price <= 0:
                errors.append(
                    f"{request.order_type.value} order requires a positive stop price"
                )

        return OrderValidationResult(valid=not errors, errors=tuple(errors))
