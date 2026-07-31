"""Service lifetime policy for the dependency-injection container.

A *lifetime* describes how long a resolved service instance lives:

* :attr:`Lifetime.SINGLETON` — built once and cached; every resolve returns the
  same instance (appropriate for shared, stateless-ish services such as the
  event bus, logger, and configuration).
* :attr:`Lifetime.TRANSIENT` — rebuilt on every resolve (appropriate for
  short-lived, stateful objects).

The authoritative :class:`Lifetime` enum is defined in :mod:`core.interfaces`.
It is **re-exported** here (not redefined) so this module can be the discoverable
home for lifetime concerns while preserving full backwards compatibility:
``from core.interfaces import Lifetime`` and ``from core.lifetime import Lifetime``
resolve to the exact same object.
"""

from __future__ import annotations

from core.interfaces import Lifetime

__all__ = ["Lifetime", "DEFAULT_LIFETIME", "is_singleton", "is_transient"]

#: The lifetime applied when a caller does not specify one. Singleton is the
#: safe, cheap default for the shared services a DI container typically holds.
DEFAULT_LIFETIME: Lifetime = Lifetime.SINGLETON


def is_singleton(lifetime: Lifetime) -> bool:
    """Return ``True`` if ``lifetime`` denotes a cached, shared instance."""
    return lifetime is Lifetime.SINGLETON


def is_transient(lifetime: Lifetime) -> bool:
    """Return ``True`` if ``lifetime`` denotes a freshly-built instance."""
    return lifetime is Lifetime.TRANSIENT
