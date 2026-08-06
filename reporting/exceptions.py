"""Reporting Framework exceptions.

Definitions only. Internal failures are translated into these so no
implementation detail escapes; the manager always returns a
:class:`~reporting.models.ReportingResult`.
"""

from __future__ import annotations

__all__ = [
    "ReportingError",
    "CollectionError",
    "BuildError",
    "ExportError",
    "MetricsError",
    "RegistryError",
    "ReportingCancelledError",
]


class ReportingError(Exception):
    """Base class for all Reporting Framework errors."""


class CollectionError(ReportingError):
    """Raised when building a reporting batch fails."""


class BuildError(ReportingError):
    """Raised when building report domain objects fails."""


class ExportError(ReportingError):
    """Raised when export request generation fails."""


class MetricsError(ReportingError):
    """Raised when a metrics calculation fails."""


class RegistryError(ReportingError):
    """Raised when a registry operation fails."""


class ReportingCancelledError(ReportingError):
    """Raised internally to unwind a reporting session that was cancelled."""
