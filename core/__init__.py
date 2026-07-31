"""core package for Binance AI Hedge Fund OS.

Exposes the dependency-injection layer: the service :class:`ServiceContainer`
and its process-wide accessor, the :class:`ServiceRegistry` store, the
abstractions in :mod:`core.interfaces`, and the :class:`Lifetime` policy.
"""

from __future__ import annotations

from core.container import ServiceContainer, get_container, reset_container
from core.interfaces import (
    Container,
    Disposable,
    Provider,
    Registration,
    Registry,
    Resolver,
)
from core.lifetime import DEFAULT_LIFETIME, Lifetime, is_singleton, is_transient
from core.registry import ServiceRegistry

__all__ = [
    "ServiceContainer",
    "get_container",
    "reset_container",
    "ServiceRegistry",
    "Container",
    "Disposable",
    "Provider",
    "Registration",
    "Registry",
    "Resolver",
    "Lifetime",
    "DEFAULT_LIFETIME",
    "is_singleton",
    "is_transient",
]
