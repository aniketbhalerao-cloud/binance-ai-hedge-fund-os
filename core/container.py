"""Dependency-injection container (composition root).

:class:`ServiceContainer` resolves dependencies from a
:class:`~core.registry.ServiceRegistry`, applying each registration's
:class:`~core.interfaces.Lifetime`:

* **singletons** are built lazily on first resolve and cached thereafter;
* **transients** (factories) are rebuilt on every resolve.

The container depends only on the abstractions in :mod:`core.interfaces` and on
the registry it is given, so it stays loosely coupled and easy to test. It
holds no knowledge of trading, Binance, database, or API concerns — those are
wired in later via providers at the application's composition root.
"""

from __future__ import annotations

from functools import lru_cache
from threading import RLock
from typing import TypeVar, cast

from core.interfaces import Lifetime, Provider, Registry, Resolver
from core.registry import ServiceRegistry

#: The type produced by a provider / resolved from the container.
T = TypeVar("T")

__all__ = ["ServiceContainer", "get_container", "reset_container"]


class ServiceContainer:
    """A thread-safe DI container implementing :class:`core.interfaces.Container`.

    Args:
        registry: The registration store to resolve from. A fresh
            :class:`~core.registry.ServiceRegistry` is created when omitted,
            allowing the container to be used stand-alone.
    """

    def __init__(self, registry: Registry | None = None) -> None:
        self._registry: Registry = registry if registry is not None else ServiceRegistry()
        self._singletons: dict[type[object], object] = {}
        self._resolving: set[type[object]] = set()
        self._lock = RLock()

    # -- registration --------------------------------------------------------

    def register(
        self,
        key: type[T],
        provider: Provider[T],
        *,
        lifetime: Lifetime = Lifetime.SINGLETON,
    ) -> None:
        """Register ``provider`` for ``key`` with an explicit ``lifetime``.

        Registering a key clears any singleton previously cached for it, so the
        next resolve reflects the new provider.
        """
        with self._lock:
            self._registry.register(key, provider, lifetime)
            self._singletons.pop(key, None)

    def register_singleton(self, key: type[T], provider: Provider[T]) -> None:
        """Register a provider whose result is cached and shared."""
        self.register(key, provider, lifetime=Lifetime.SINGLETON)

    def register_factory(self, key: type[T], provider: Provider[T]) -> None:
        """Register a provider invoked on every resolve (transient lifetime)."""
        self.register(key, provider, lifetime=Lifetime.TRANSIENT)

    def register_instance(self, key: type[T], instance: T) -> None:
        """Register an already-constructed singleton ``instance``.

        The instance is cached immediately and returned by every resolve.
        """
        with self._lock:
            self._registry.register(
                key, lambda _resolver: instance, Lifetime.SINGLETON
            )
            self._singletons[key] = instance

    # -- resolution ----------------------------------------------------------

    def resolve(self, key: type[T]) -> T:
        """Resolve and return the dependency registered for ``key``.

        Args:
            key: The type to resolve.

        Returns:
            An instance of ``key``, honouring the registered lifetime.

        Raises:
            KeyError: If ``key`` is not registered.
            RuntimeError: If a circular dependency is detected.
        """
        with self._lock:
            cached = self._singletons.get(key)
            if cached is not None:
                return cast(T, cached)

            registration = self._registry.get(key)

            if key in self._resolving:
                chain = " -> ".join(k.__name__ for k in self._resolving)
                raise RuntimeError(
                    f"Circular dependency detected while resolving "
                    f"{key.__name__!r} (chain: {chain})."
                )

            self._resolving.add(key)
            try:
                instance = registration.provider(cast(Resolver, self))
            finally:
                self._resolving.discard(key)

            if registration.lifetime is Lifetime.SINGLETON:
                self._singletons[key] = instance
            return cast(T, instance)

    def has(self, key: type[object]) -> bool:
        """Return ``True`` if ``key`` is registered (or already cached)."""
        return key in self._singletons or self._registry.contains(key)

    # -- lifecycle -----------------------------------------------------------

    def reset(self) -> None:
        """Drop all cached singletons, keeping registrations intact.

        The next resolve of each singleton rebuilds it. Useful for tests and
        for reloading after configuration changes.
        """
        with self._lock:
            self._singletons.clear()


@lru_cache(maxsize=1)
def get_container() -> ServiceContainer:
    """Return the process-wide :class:`ServiceContainer` singleton.

    This is the application's composition root. It is created lazily and cached
    for the lifetime of the process. Concrete providers (settings, adapters,
    services) are wired here in later tasks — none are registered yet to keep
    this layer free of business logic.

    Returns:
        The shared :class:`ServiceContainer`.
    """
    return ServiceContainer()


def reset_container() -> None:
    """Clear the cached container so the next :func:`get_container` rebuilds it.

    Primarily intended for tests that mutate the environment or registrations.
    """
    get_container.cache_clear()
