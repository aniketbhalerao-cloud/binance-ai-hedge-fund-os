"""Model Provider Gateway Framework exceptions.

Definitions only. Internal failures are translated into these so no
implementation detail (and no credential or secret material) escapes; the
manager always returns a :class:`~model_gateway.models.ModelGatewayResult`.
"""

from __future__ import annotations

__all__ = [
    "ModelGatewayError",
    "CollectionError",
    "PlanningError",
    "DispatchError",
    "MetricsError",
    "RegistryError",
    "ModelGatewayCancelledError",
]


class ModelGatewayError(Exception):
    """Base class for all Model Provider Gateway Framework errors."""


class CollectionError(ModelGatewayError):
    """Raised when building a model invocation batch fails."""


class PlanningError(ModelGatewayError):
    """Raised when planning model invocation entries fails."""


class DispatchError(ModelGatewayError):
    """Raised when model invocation request generation fails."""


class MetricsError(ModelGatewayError):
    """Raised when a metrics calculation fails."""


class RegistryError(ModelGatewayError):
    """Raised when a registry operation fails."""


class ModelGatewayCancelledError(ModelGatewayError):
    """Raised internally to unwind a model gateway session that was cancelled."""
