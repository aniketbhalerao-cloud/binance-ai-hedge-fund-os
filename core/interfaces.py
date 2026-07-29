"""Abstractions for the dependency-injection layer.

This module defines the *contracts* (Protocols), the value objects, and the
enumerations that the DI implementation depends on. Nothing here has behaviour
beyond simple data holding — concrete logic lives in :mod:`core.registry`
(storage) and :mod:`core.container` (resolution).

Keeping the abstractions separate lets callers depend on interfaces rather than
concrete classes (Dependency Inversion Principle), which keeps the system
loosely coupled and trivially mockable in tests.

No business, trading, Binance, database, or API logic lives here.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Generic, Protocol, TypeVar, runtime_checkable

#: The type produced by a provider / stored under a key.
T = TypeVar("T")

__all__ = [
    "Lifetime",
    "Provider",
    "Registration",
    "Resolver",
    "Registry",
    "Container",
    "Disposable",
]


class Lifetime(str, Enum):
    """Lifecycle policy for a registered dependency.

    * ``SINGLETON`` — created once and cached; every resolve returns the same
      instance.
    * ``TRANSIENT`` — created fresh on every resolve (factory semantics).
    """

    SINGLETON = "singleton"
    TRANSIENT = "transient"


@runtime_checkable
class Resolver(Protocol):
    """Read-only view of a container: the ability to resolve dependencies.

    Providers receive a :class:`Resolver` (not the full container) so they can
    obtain their own collaborators without gaining registration privileges.
    """

    def resolve(self, key: type[T]) -> T:
        """Return an instance registered for ``key``."""
        ...

    def has(self, key: type[object]) -> bool:
        """Return ``True`` if ``key`` can be resolved."""
        ...


#: A factory that builds a value of type ``T`` given a :class:`Resolver` for
#: resolving its own dependencies.
Provider = Callable[[Resolver], T]


@dataclass(frozen=True, slots=True)
class Registration(Generic[T]):
    """An immutable record describing how to build a dependency.

    Attributes:
        provider: Factory that produces the instance.
        lifetime: Whether the instance is cached (singleton) or rebuilt
            (transient) on each resolve.
    """

    provider: Provider[T]
    lifetime: Lifetime = field(default=Lifetime.SINGLETON)


@runtime_checkable
class Registry(Protocol):
    """Contract for the store of registrations keyed by type."""

    def register(
        self,
        key: type[T],
        provider: Provider[T],
        lifetime: Lifetime = Lifetime.SINGLETON,
    ) -> None:
        """Record a ``provider`` for ``key`` with the given ``lifetime``."""
        ...

    def get(self, key: type[T]) -> Registration[T]:
        """Return the :class:`Registration` for ``key`` (raises if missing)."""
        ...

    def contains(self, key: type[object]) -> bool:
        """Return ``True`` if ``key`` is registered."""
        ...

    def remove(self, key: type[object]) -> None:
        """Remove the registration for ``key`` if present."""
        ...

    def clear(self) -> None:
        """Remove all registrations."""
        ...

    def __iter__(self) -> Iterator[type[object]]:
        """Iterate over the registered keys."""
        ...


@runtime_checkable
class Container(Resolver, Protocol):
    """Contract for the composition root: registration plus resolution."""

    def register(
        self,
        key: type[T],
        provider: Provider[T],
        *,
        lifetime: Lifetime = Lifetime.SINGLETON,
    ) -> None:
        """Register a ``provider`` for ``key`` with an explicit ``lifetime``."""
        ...

    def register_singleton(self, key: type[T], provider: Provider[T]) -> None:
        """Register a provider whose result is cached and shared."""
        ...

    def register_factory(self, key: type[T], provider: Provider[T]) -> None:
        """Register a provider that is invoked on every resolve (transient)."""
        ...

    def register_instance(self, key: type[T], instance: T) -> None:
        """Register an already-constructed singleton ``instance``."""
        ...

    def reset(self) -> None:
        """Drop cached singletons while keeping registrations."""
        ...


@runtime_checkable
class Disposable(Protocol):
    """Optional contract for dependencies that need deterministic teardown."""

    def dispose(self) -> None:
        """Release any resources held by the instance."""
        ...
