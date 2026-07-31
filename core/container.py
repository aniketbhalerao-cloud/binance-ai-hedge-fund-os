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

import inspect
from functools import lru_cache
from threading import RLock
from typing import Any, TypeVar, cast, get_type_hints

from core.interfaces import Lifetime, Provider, Registry, Resolver
from core.lifetime import DEFAULT_LIFETIME
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

    # -- constructor injection ----------------------------------------------

    def register_class(
        self,
        key: type[T],
        cls: type[T] | None = None,
        *,
        lifetime: Lifetime = DEFAULT_LIFETIME,
    ) -> None:
        """Register a class to be built via constructor injection.

        When ``key`` is resolved, the container instantiates the class and
        supplies each annotated ``__init__`` parameter by resolving it from the
        container. Parameters that are not registered but declare a default fall
        back to that default. This lets services declare their dependencies as
        typed constructor arguments instead of hand-written factories.

        Args:
            key: The type used to resolve the service.
            cls: Concrete class to instantiate; defaults to ``key`` itself.
            lifetime: Singleton (cached) or transient (rebuilt each resolve).
        """
        target: type[T] = cls if cls is not None else key

        def _provider(resolver: Resolver) -> T:
            return self._build(target, resolver)

        self.register(key, _provider, lifetime=lifetime)

    def create(self, cls: type[T]) -> T:
        """Construct ``cls`` via constructor injection without registering it.

        Dependencies are resolved from this container; ``cls`` itself is neither
        registered nor cached.

        Args:
            cls: The class to instantiate.

        Returns:
            A new instance of ``cls``.
        """
        return self._build(cls, cast(Resolver, self))

    def _build(self, cls: type[T], resolver: Resolver) -> T:
        """Instantiate ``cls``, resolving its annotated constructor parameters.

        Args:
            cls: The class to build.
            resolver: The resolver used to obtain each dependency.

        Returns:
            A new instance of ``cls``.

        Raises:
            TypeError: If a required parameter lacks a type annotation.
            KeyError: If a required, annotated dependency is not registered.
        """
        try:
            signature = inspect.signature(cls)
        except (ValueError, TypeError):
            # Builtins / objects without an introspectable signature.
            return cls()

        try:
            hints = get_type_hints(cls.__init__)
        except Exception:  # pragma: no cover - unresolved forward refs, etc.
            hints = {}

        kwargs: dict[str, Any] = {}
        for name, parameter in signature.parameters.items():
            if parameter.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue

            annotation = hints.get(name, parameter.annotation)
            has_default = parameter.default is not inspect.Parameter.empty

            if annotation is inspect.Parameter.empty:
                if has_default:
                    continue
                raise TypeError(
                    f"Cannot inject parameter {name!r} of "
                    f"{cls.__name__}.__init__: missing type annotation."
                )

            if isinstance(annotation, type) and self.has(annotation):
                kwargs[name] = resolver.resolve(annotation)
            elif has_default:
                continue
            else:
                dependency = getattr(annotation, "__name__", annotation)
                raise KeyError(
                    f"Cannot inject parameter {name!r} of {cls.__name__}: "
                    f"no registration for {dependency!r}."
                )

        return cls(**kwargs)


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
