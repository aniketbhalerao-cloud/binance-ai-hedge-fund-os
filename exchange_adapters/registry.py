"""Exchange adapter registry.

:class:`ExchangeAdapterRegistry` maintains the registered adapters. It is
thread-safe and its only responsibility is registration and lookup — it never
creates adapters (creation belongs to the DI container / composition root).
"""

from __future__ import annotations

from threading import Lock

from exchange_adapters.exceptions import (
    DuplicateAdapterError,
    ExchangeRegistrationError,
)
from exchange_adapters.interfaces import ExchangeAdapter

__all__ = ["ExchangeAdapterRegistry"]


class ExchangeAdapterRegistry:
    """A thread-safe registry of exchange adapters, keyed by name."""

    def __init__(self) -> None:
        self._adapters: dict[str, ExchangeAdapter] = {}
        self._lock = Lock()

    def register(self, adapter: ExchangeAdapter) -> None:
        """Register ``adapter``.

        Raises:
            DuplicateAdapterError: If an adapter with the same name exists.
        """
        with self._lock:
            if adapter.name in self._adapters:
                raise DuplicateAdapterError(
                    f"Adapter {adapter.name!r} already registered."
                )
            self._adapters[adapter.name] = adapter

    def unregister(self, name: str) -> None:
        """Remove the adapter named ``name``.

        Raises:
            ExchangeRegistrationError: If ``name`` is not registered.
        """
        with self._lock:
            if name not in self._adapters:
                raise ExchangeRegistrationError(f"Adapter {name!r} is not registered.")
            del self._adapters[name]

    def exists(self, name: str) -> bool:
        """Return ``True`` if an adapter named ``name`` is registered."""
        with self._lock:
            return name in self._adapters

    def get(self, name: str) -> ExchangeAdapter:
        """Return the adapter named ``name``.

        Raises:
            ExchangeRegistrationError: If ``name`` is not registered.
        """
        with self._lock:
            adapter = self._adapters.get(name)
        if adapter is None:
            raise ExchangeRegistrationError(f"Adapter {name!r} is not registered.")
        return adapter

    def list(self) -> list[ExchangeAdapter]:
        """Return all registered adapters."""
        with self._lock:
            return list(self._adapters.values())
