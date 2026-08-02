"""Exchange request validator.

:class:`DefaultExchangeValidator` verifies a translated
:class:`~exchange_adapters.models.ExchangeRequest` — required fields and
translation integrity — producing an
:class:`~exchange_adapters.models.ExchangeValidationResult`. It is stateless. It
performs no risk checks, strategy evaluation, or broker communication.
"""

from __future__ import annotations

from exchange_adapters.models import ExchangeRequest, ExchangeValidationResult

__all__ = ["DefaultExchangeValidator"]


class DefaultExchangeValidator:
    """Validates the integrity of a translated :class:`ExchangeRequest`."""

    def validate(self, request: ExchangeRequest) -> ExchangeValidationResult:
        """Return a validation result listing any structural problems."""
        errors: list[str] = []
        if not request.symbol:
            errors.append("symbol must not be empty")
        if request.execution_request is None:
            errors.append("execution_request is required")
        if not request.exchange:
            errors.append("exchange must not be empty")
        return ExchangeValidationResult(valid=not errors, errors=tuple(errors))
