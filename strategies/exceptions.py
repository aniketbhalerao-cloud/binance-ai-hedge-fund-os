"""Strategy Framework exceptions.

Definitions only — no handling logic. These isolate strategy failures so a
single misbehaving strategy never crashes the framework.
"""

from __future__ import annotations

__all__ = [
    "StrategyError",
    "StrategyRegistrationError",
    "StrategyExecutionError",
    "InvalidStrategyError",
    "DuplicateStrategyError",
    "StrategyDisabledError",
]


class StrategyError(Exception):
    """Base class for all Strategy Framework errors."""


class StrategyRegistrationError(StrategyError):
    """Raised when a strategy cannot be registered or unregistered."""


class StrategyExecutionError(StrategyError):
    """Raised when a strategy fails during execution."""


class InvalidStrategyError(StrategyError):
    """Raised when an object is not a valid strategy or is unknown."""


class DuplicateStrategyError(StrategyRegistrationError):
    """Raised when registering a strategy whose name already exists."""


class StrategyDisabledError(StrategyError):
    """Raised when an operation requires an enabled strategy but it is disabled."""
