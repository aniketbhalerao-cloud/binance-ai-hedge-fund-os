"""Application Bootstrap & Dry-Run Runtime Composition exceptions.

Definitions only. Internal failures are translated into these so no
implementation detail — and never a credential, secret, or stack trace —
escapes; ``bootstrap.run_dry_run_bootstrap`` always returns a
:class:`~app.models.BootstrapResult`.
"""

from __future__ import annotations

__all__ = [
    "BootstrapError",
    "PlanningError",
    "PreflightError",
    "ConfigurationError",
]


class BootstrapError(Exception):
    """Base class for all Application Bootstrap & Dry-Run errors."""


class PlanningError(BootstrapError):
    """Raised when component-graph validation or ordering fails.

    Covers an unknown component id, duplicate component identifiers,
    missing dependency references, self-dependencies, and cyclic
    dependency graphs — none of these ever produce a partial
    :class:`~app.models.BootstrapPlan`, and none ever result in a candidate
    container being created.
    """


class PreflightError(BootstrapError):
    """Raised when a declared ``required_service_keys`` entry is not present
    in :data:`app.wiring.SAFE_SERVICE_KEYS` — decided entirely from the plan
    and the allowlist, before any candidate container exists.
    """


class ConfigurationError(BootstrapError):
    """Raised when a redaction or timestamp invariant is violated.

    Covers :func:`app.wiring.build_configuration_view` being asked to copy a
    ``Settings`` field whose name matches a sensitive pattern (defence in
    depth — should be unreachable given the mechanical name filter) and
    ``BootstrapContext.requested_at`` failing the canonical-UTC check.
    """
