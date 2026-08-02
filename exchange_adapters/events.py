"""Exchange Adapter Framework events.

Each inherits the existing :class:`events.base.Event` and is immutable. The
framework publishes **only** these — never strategy, risk, order, execution, or
portfolio events.
"""

from __future__ import annotations

from dataclasses import dataclass

from events.base import Event

__all__ = [
    "ExchangeEvent",
    "ExchangeAdapterRegistered",
    "ExchangeAdapterUnregistered",
    "ExchangeAuthenticationStarted",
    "ExchangeAuthenticationSucceeded",
    "ExchangeAuthenticationFailed",
    "ExchangeConnectionOpened",
    "ExchangeConnectionClosed",
    "ExchangeValidationSucceeded",
    "ExchangeValidationFailed",
    "ExchangeRoutingCompleted",
    "ExchangeEngineStarted",
    "ExchangeEngineStopped",
    "ExchangeErrorOccurred",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class ExchangeEvent(Event):
    """Base class for all exchange adapter events."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ExchangeAdapterRegistered(ExchangeEvent):
    """An adapter was registered."""

    name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ExchangeAdapterUnregistered(ExchangeEvent):
    """An adapter was unregistered."""

    name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ExchangeAuthenticationStarted(ExchangeEvent):
    """Authentication coordination began."""

    exchange: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ExchangeAuthenticationSucceeded(ExchangeEvent):
    """Authentication coordination succeeded."""

    exchange: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ExchangeAuthenticationFailed(ExchangeEvent):
    """Authentication coordination failed."""

    exchange: str
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ExchangeConnectionOpened(ExchangeEvent):
    """A connection was opened (abstraction)."""

    exchange: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ExchangeConnectionClosed(ExchangeEvent):
    """A connection was closed (abstraction)."""

    exchange: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ExchangeValidationSucceeded(ExchangeEvent):
    """The exchange request passed validation."""

    exchange: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ExchangeValidationFailed(ExchangeEvent):
    """The exchange request failed validation."""

    exchange: str
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ExchangeRoutingCompleted(ExchangeEvent):
    """Routing selected the target adapter."""

    adapter_name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ExchangeEngineStarted(ExchangeEvent):
    """The exchange engine started."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ExchangeEngineStopped(ExchangeEvent):
    """The exchange engine stopped."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ExchangeErrorOccurred(ExchangeEvent):
    """An error occurred during framework coordination."""

    message: str
