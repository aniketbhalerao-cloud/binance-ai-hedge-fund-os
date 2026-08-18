"""Helpers for Application Bootstrap & Dry-Run Runtime Composition tests.

Standalone support module (existing support files unchanged). Builds
deterministic component specs, dependencies, manifests, and bootstrap
contexts. No network, no sleeps, no randomness, no model training, and no
calls into another framework's manager or engine anywhere.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

from app.models import (
    BootstrapContext,
    ComponentDependency,
    ComponentManifest,
    ComponentSpec,
    ConfigurationView,
)

__all__ = [
    "make_component",
    "make_dependency",
    "make_manifest",
    "make_context",
    "CANONICAL_UTC",
]

#: A fixed, canonical-UTC timestamp for deterministic fixtures.
CANONICAL_UTC = datetime(2024, 1, 1, tzinfo=UTC)


def make_component(
    component_id: str,
    priority: str = "0",
    *,
    required_service_keys: Sequence[str] = (),
    detail: str = "",
) -> ComponentSpec:
    """Build a component spec with a given priority."""
    return ComponentSpec(
        component_id=component_id,
        priority=Decimal(priority),
        required_service_keys=tuple(required_service_keys),
        detail=detail,
    )


def make_dependency(component_id: str, depends_on: str) -> ComponentDependency:
    """Build a dependency edge: ``component_id`` depends on ``depends_on``."""
    return ComponentDependency(component_id=component_id, depends_on=depends_on)


def make_manifest(
    components: Sequence[ComponentSpec],
    dependencies: Sequence[ComponentDependency] = (),
) -> ComponentManifest:
    """Build a component manifest from the given components/dependencies."""
    return ComponentManifest(
        components=tuple(components), dependencies=tuple(dependencies)
    )


def make_context(
    *,
    manifest: ComponentManifest | None = None,
    configuration: ConfigurationView | None = None,
    correlation_id: str = "test-corr",
    requested_at: datetime = CANONICAL_UTC,
) -> BootstrapContext:
    """Build a deterministic bootstrap context.

    Defaults to an empty manifest and the default ``ConfigurationView``
    unless overridden.
    """
    return BootstrapContext(
        manifest=manifest if manifest is not None else ComponentManifest(),
        configuration=(
            configuration if configuration is not None else ConfigurationView()
        ),
        correlation_id=correlation_id,
        requested_at=requested_at,
    )
