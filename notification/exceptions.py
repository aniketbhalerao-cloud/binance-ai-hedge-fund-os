"""Notification Framework exceptions.

Definitions only. Internal failures are translated into these so no
implementation detail escapes; the manager always returns a
:class:`~notification.models.NotificationResult`.
"""

from __future__ import annotations

__all__ = [
    "NotificationError",
    "CollectionError",
    "FormattingError",
    "DispatchError",
    "MetricsError",
    "RegistryError",
    "NotificationCancelledError",
]


class NotificationError(Exception):
    """Base class for all Notification Framework errors."""


class CollectionError(NotificationError):
    """Raised when building a notification batch fails."""


class FormattingError(NotificationError):
    """Raised when formatting a notification batch fails."""


class DispatchError(NotificationError):
    """Raised when notification request generation fails."""


class MetricsError(NotificationError):
    """Raised when a metrics calculation fails."""


class RegistryError(NotificationError):
    """Raised when a registry operation fails."""


class NotificationCancelledError(NotificationError):
    """Raised internally to unwind a notification session that was cancelled."""
