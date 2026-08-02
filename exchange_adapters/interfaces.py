"""Exchange Adapter Framework interfaces.

Protocols only — no implementations. Every component depends on these
abstractions so future broker adapters plug in without modification
(Open/Closed).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from exchange_adapters.context import ExchangeContext
from exchange_adapters.models import (
    ExchangeRequest,
    ExchangeResponse,
    ExchangeResult,
    ExchangeRoute,
    ExchangeValidationResult,
)
from exchange_adapters.state import AuthenticationState, ConnectionState

__all__ = [
    "ExchangeAuthentication",
    "ExchangeConnection",
    "ExchangeAdapter",
    "ExchangeValidator",
    "ExchangeRouter",
    "ExchangeRegistry",
    "ExchangeManager",
    "ExchangeEngine",
]


@runtime_checkable
class ExchangeAuthentication(Protocol):
    """Authentication abstraction (no credentials/keys/signatures)."""

    async def authenticate(self, context: ExchangeContext) -> AuthenticationState: ...


@runtime_checkable
class ExchangeConnection(Protocol):
    """Connectivity abstraction (no REST/WebSocket/SDK)."""

    async def open(self, context: ExchangeContext) -> ConnectionState: ...
    async def close(self) -> ConnectionState: ...


@runtime_checkable
class ExchangeAdapter(Protocol):
    """A broker adapter that accepts translated requests (abstract contract)."""

    @property
    def name(self) -> str: ...
    async def submit(self, request: ExchangeRequest) -> ExchangeResponse: ...


@runtime_checkable
class ExchangeValidator(Protocol):
    """Validates a translated exchange request."""

    def validate(self, request: ExchangeRequest) -> ExchangeValidationResult: ...


@runtime_checkable
class ExchangeRouter(Protocol):
    """Determines which adapter should receive a request."""

    def route(self, context: ExchangeContext) -> ExchangeRoute: ...


@runtime_checkable
class ExchangeRegistry(Protocol):
    """Maintains registered adapters (never creates them)."""

    def register(self, adapter: ExchangeAdapter) -> None: ...
    def unregister(self, name: str) -> None: ...
    def exists(self, name: str) -> bool: ...
    def get(self, name: str) -> ExchangeAdapter: ...
    def list(self) -> list[ExchangeAdapter]: ...


@runtime_checkable
class ExchangeManager(Protocol):
    """Coordinates auth → connection → validation → routing → adapter."""

    async def process(self, context: ExchangeContext) -> ExchangeResult: ...


@runtime_checkable
class ExchangeEngine(Protocol):
    """Public entry point coordinating the exchange-adapter framework."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def process(self, context: ExchangeContext) -> ExchangeResult: ...
