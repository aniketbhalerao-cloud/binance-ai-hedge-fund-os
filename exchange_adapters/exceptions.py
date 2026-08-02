"""Exchange Adapter Framework exceptions.

Definitions only — no handling logic. These isolate framework failures so the
framework always produces an :class:`~exchange_adapters.models.ExchangeResult`.
"""

from __future__ import annotations

__all__ = [
    "ExchangeError",
    "ExchangeAuthenticationError",
    "ExchangeConnectionError",
    "ExchangeValidationError",
    "ExchangeRoutingError",
    "ExchangeRegistrationError",
    "ExchangeEngineError",
    "InvalidExchangeRequest",
    "DuplicateAdapterError",
]


class ExchangeError(Exception):
    """Base class for all Exchange Adapter Framework errors."""


class ExchangeAuthenticationError(ExchangeError):
    """Raised when authentication coordination fails."""


class ExchangeConnectionError(ExchangeError):
    """Raised when connection coordination fails."""


class ExchangeValidationError(ExchangeError):
    """Raised when validation cannot be performed."""


class ExchangeRoutingError(ExchangeError):
    """Raised when routing cannot be prepared."""


class ExchangeRegistrationError(ExchangeError):
    """Raised when an adapter cannot be registered or unregistered."""


class ExchangeEngineError(ExchangeError):
    """Raised when the engine fails to coordinate the framework."""


class InvalidExchangeRequest(ExchangeError):
    """Raised when an exchange request is missing or structurally invalid."""


class DuplicateAdapterError(ExchangeRegistrationError):
    """Raised when registering an adapter whose name already exists."""
