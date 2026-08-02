"""Concrete storage for dependency registrations.

:class:`ServiceRegistry` is a thin, type-safe map from a key type to its
:class:`~core.interfaces.Registration`. It deliberately knows *nothing* about
instantiation, caching, or lifetimes beyond storing them — resolution is the
responsibility of :mod:`core.container`. This separation keeps each class small
and single-purpose (Single Responsibility Principle).

No business, trading, Binance, database, or API logic lives here.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TypeVar, cast

from core.interfaces import Lifetime, Provider, Registration

#: The type produced by a registered provider.
T = TypeVar("T")

__all__ = ["ServiceRegistry"]


class ServiceRegistry:
    """An in-memory, type-safe registry of :class:`Registration` records.

    Implements the :class:`~core.interfaces.Registry` protocol. Registering the
    same key twice overwrites the previous registration, which makes overriding
    dependencies in tests straightforward.
    """

    def __init__(self) -> None:
        self._registrations: dict[type[object], Registration[object]] = {}

    def register(
        self,
        key: type[T],
        provider: Provider[T],
        lifetime: Lifetime = Lifetime.SINGLETON,
    ) -> None:
        """Record ``provider`` for ``key`` with the given ``lifetime``.

        Args:
            key: Type used to look the dependency up later.
            provider: Factory that builds an instance of ``key``.
            lifetime: Caching policy for the produced instance.
        """
        self._registrations[key] = Registration(provider=provider, lifetime=lifetime)

    def get(self, key: type[T]) -> Registration[T]:
        """Return the registration for ``key``.

        Args:
            key: The registered type.

        Returns:
            The :class:`Registration` for ``key``.

        Raises:
            KeyError: If ``key`` is not registered.
        """
        try:
            registration = self._registrations[key]
        except KeyError as exc:
            raise KeyError(f"No registration found for {key.__name__!r}.") from exc
        # The registry stores objects invariantly; the public API restores the
        # precise generic type that was recorded via :meth:`register`.
        return cast(Registration[T], registration)

    def contains(self, key: type[object]) -> bool:
        """Return ``True`` if ``key`` is registered."""
        return key in self._registrations

    def remove(self, key: type[object]) -> None:
        """Remove the registration for ``key`` if present (no error if absent)."""
        self._registrations.pop(key, None)

    def clear(self) -> None:
        """Remove every registration."""
        self._registrations.clear()

    def __iter__(self) -> Iterator[type[object]]:
        """Iterate over the registered key types."""
        return iter(self._registrations)

    def __contains__(self, key: object) -> bool:
        """Support ``key in registry`` membership tests."""
        return key in self._registrations

    def __len__(self) -> int:
        """Return the number of registrations."""
        return len(self._registrations)
