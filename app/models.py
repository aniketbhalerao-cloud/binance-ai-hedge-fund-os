"""Application Bootstrap & Dry-Run Runtime Composition domain models.

Immutable, credential-free value objects only. No model defined here may
ever carry a callable reference to a registrar/manager/engine, a network
client, a database client, or credentials/API keys/secrets — the
identifier-to-callable mapping lives only in :mod:`app.wiring`, never in
model data. No identifier or timestamp is generated inside any model —
every timestamp on ``BootstrapContext`` is supplied by the caller.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Any

from app.exceptions import ConfigurationError

__all__ = [
    "ComponentSpec",
    "ComponentDependency",
    "ComponentManifest",
    "ConfigurationView",
    "BootstrapContext",
    "BootstrapPlanEntry",
    "BootstrapPlan",
    "PreflightEntry",
    "PreflightReport",
    "RuntimeSnapshot",
    "LifecyclePlan",
    "BootstrapResultStatus",
    "BootstrapResult",
]

_ZERO = Decimal("0")


def _is_canonical_utc(value: datetime) -> bool:
    """Return ``True`` if ``value`` is timezone-aware with a zero UTC offset."""
    if value.tzinfo is None:
        return False
    offset = value.utcoffset()
    return offset is not None and offset == timedelta(0)


# ---------------------------------------------------------------------------
# Component manifest — graph structure only
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ComponentSpec:
    """One declared component, one entry per completed framework.

    Attributes:
        component_id: Stable identifier — must be a member of
            :data:`app.wiring.KNOWN_COMPONENT_IDS`.
        priority: Deterministic registration priority (higher preferred).
        required_service_keys: Keys this component wants resolved during the
            preflight pass; each must exist in
            :data:`app.wiring.SAFE_SERVICE_KEYS`.
        detail: Free-form descriptive detail.
        metadata: Optional read-only extra detail.
    """

    component_id: str
    priority: Decimal = _ZERO
    required_service_keys: tuple[str, ...] = ()
    detail: str = ""
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "required_service_keys", tuple(self.required_service_keys)
        )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ComponentDependency:
    """An immutable directed edge, scoped to one ``ComponentManifest``.

    Attributes:
        component_id: The dependent component identifier.
        depends_on: The component identifier it depends on.
    """

    component_id: str
    depends_on: str


@dataclass(frozen=True, slots=True)
class ComponentManifest:
    """The full declared component graph for one bootstrap run."""

    components: tuple[ComponentSpec, ...] = ()
    dependencies: tuple[ComponentDependency, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "components", tuple(self.components))
        object.__setattr__(self, "dependencies", tuple(self.dependencies))


# ---------------------------------------------------------------------------
# Configuration view — redacted Settings subset
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConfigurationView:
    """The redacted, allowlisted subset of ``Settings``.

    Built only by :func:`app.wiring.build_configuration_view`. Contains only
    scalar/collection values already proven non-sensitive; never a raw
    ``Settings`` reference, and never a field whose name contains ``key``,
    ``secret``, ``token``, ``credential``, ``password``, ``url``, or ``dsn``.
    """

    application_name: str = "binance-ai-hedge-fund-os"
    application_version: str = "0.1.0"
    application_debug: bool = True
    application_timezone: str = "UTC"
    environment: str = "development"
    trading_mode: str = "paper"
    trading_base_currency: str = "USDT"
    trading_symbols: tuple[str, ...] = ("BTCUSDT",)
    dashboard_enabled: bool = True
    dashboard_host: str = "0.0.0.0"
    dashboard_port: int = 8501
    monitoring_enabled: bool = True
    monitoring_metrics_port: int = 9090
    logging_level: str = "INFO"
    logging_format: str = "json"
    risk_max_position_size_pct: Decimal = Decimal("0.10")
    risk_risk_per_trade_pct: Decimal = Decimal("0.01")
    risk_max_daily_drawdown_pct: Decimal = Decimal("0.05")
    risk_max_total_drawdown_pct: Decimal = Decimal("0.20")
    risk_stop_loss_pct: Decimal = Decimal("0.02")
    risk_take_profit_pct: Decimal = Decimal("0.04")
    risk_max_leverage: Decimal = Decimal("1")
    risk_max_open_positions: int = 5
    backtesting_initial_balance: Decimal = Decimal("100000")
    backtesting_commission_pct: Decimal = Decimal("0.001")
    backtesting_slippage_pct: Decimal = Decimal("0.0005")
    simulation_initial_balance: Decimal = Decimal("100000")
    simulation_latency_ms: int = 50
    simulation_fill_ratio: Decimal = Decimal("1")
    simulation_commission_pct: Decimal = Decimal("0.001")
    simulation_slippage_pct: Decimal = Decimal("0.0005")
    simulation_random_seed: int | None = None
    binance_testnet: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "trading_symbols", tuple(self.trading_symbols))


# ---------------------------------------------------------------------------
# Bootstrap context — deterministic pipeline input
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BootstrapContext:
    """The deterministic input to one dry-run bootstrap.

    Attributes:
        manifest: The declared component graph to plan and register.
        configuration: The redacted configuration view to carry on the
            produced ``RuntimeSnapshot``.
        correlation_id: Correlation id for this run.
        requested_at: Canonical-UTC timestamp the run was requested at —
            timezone-aware with ``utcoffset() == timedelta(0)``. A naive
            value, a ``tzinfo`` whose ``utcoffset()`` is ``None``, or any
            non-zero-offset value is rejected.
        metadata: Optional read-only extra context.

    Raises:
        ConfigurationError: If ``requested_at`` is not canonical UTC.
    """

    manifest: ComponentManifest
    configuration: ConfigurationView
    correlation_id: str
    requested_at: datetime
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not _is_canonical_utc(self.requested_at):
            raise ConfigurationError(
                "BootstrapContext.requested_at must be a canonical-UTC "
                "datetime (timezone-aware, utcoffset() == timedelta(0))."
            )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


# ---------------------------------------------------------------------------
# Bootstrap plan — deterministic resolved registration order
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BootstrapPlanEntry:
    """One resolved position in a ``BootstrapPlan``.

    Attributes:
        position: The deterministic, zero-based resolved ordering position.
        component_id: The resolved component's identifier.
        priority: The component's declared priority — explains the ordering
            outcome.
        required_service_keys: The component's own declared service keys,
            carried forward so ``preflight`` can operate from the plan
            alone.
        dependencies: The component's own ``depends_on`` identifiers,
            canonicalized to lexical-ascending order.
    """

    position: int
    component_id: str
    priority: Decimal = _ZERO
    required_service_keys: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "required_service_keys", tuple(self.required_service_keys)
        )
        object.__setattr__(self, "dependencies", tuple(self.dependencies))


@dataclass(frozen=True, slots=True)
class BootstrapPlan:
    """A deterministic, declarative registration plan — never registers
    anything itself; it only describes the order a candidate container
    would be registered in."""

    entries: tuple[BootstrapPlanEntry, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "entries", tuple(self.entries))


# ---------------------------------------------------------------------------
# Preflight report
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PreflightEntry:
    """One component's resolution-check outcome.

    Attributes:
        component_id: The component the check was run for.
        service_key: The declared service key that was resolved.
        resolved: Whether resolution succeeded.
        detail: Already-redacted/safe detail — never a raw exception.
    """

    component_id: str
    service_key: str
    resolved: bool
    detail: str = ""


@dataclass(frozen=True, slots=True)
class PreflightReport:
    """The resolution-check outcome for every declared service key in a
    ``BootstrapPlan``.

    ``total_checks``/``passed_checks``/``failed_checks`` are derived once,
    here, from ``entries`` — never accepted as separate constructor
    arguments, so there is only ever one source of truth for the counts.
    """

    entries: tuple[PreflightEntry, ...] = ()
    total_checks: int = field(init=False, default=0)
    passed_checks: int = field(init=False, default=0)
    failed_checks: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        object.__setattr__(self, "entries", tuple(self.entries))
        total = len(self.entries)
        passed = sum(1 for entry in self.entries if entry.resolved)
        object.__setattr__(self, "total_checks", total)
        object.__setattr__(self, "passed_checks", passed)
        object.__setattr__(self, "failed_checks", total - passed)


# ---------------------------------------------------------------------------
# Runtime snapshot & lifecycle plan
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RuntimeSnapshot:
    """An immutable, redacted view of what the disposable candidate
    container looked like for one run.

    Built entirely from already-known plan/report data — never by
    inspecting or holding onto the container itself. Never a live container
    reference, never a resolved instance.
    """

    registered_component_ids: tuple[str, ...] = ()
    preflight_report: PreflightReport = field(default_factory=PreflightReport)
    configuration: ConfigurationView = field(default_factory=ConfigurationView)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "registered_component_ids", tuple(self.registered_component_ids)
        )


@dataclass(frozen=True, slots=True)
class LifecyclePlan:
    """A declarative start/stop order — consumed by a future live-runtime
    task; never acted on here.

    ``stop_order`` must be the exact reverse of ``start_order`` — enforced
    here, not merely produced that way by one construction site.

    Raises:
        ConfigurationError: If ``stop_order`` is not the exact reverse of
            ``start_order``.
    """

    start_order: tuple[str, ...] = ()
    stop_order: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        start = tuple(self.start_order)
        stop = tuple(self.stop_order)
        object.__setattr__(self, "start_order", start)
        object.__setattr__(self, "stop_order", stop)
        if stop != tuple(reversed(start)):
            raise ConfigurationError(
                "LifecyclePlan.stop_order must be the exact reverse of "
                "start_order"
            )


# ---------------------------------------------------------------------------
# Bootstrap result
# ---------------------------------------------------------------------------


# (str, Enum) matches the project-wide convention used by every sibling
# framework.
class BootstrapResultStatus(str, Enum):  # noqa: UP042
    """Coarse outcome of one dry-run bootstrap."""

    SUCCESS = "success"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    """The immutable outcome of one dry-run bootstrap.

    On any failure, every artifact field stays ``None`` and only safe,
    already-redacted-input-derived messages appear in ``errors`` — never a
    raw exception, credential, or stack trace.
    """

    status: BootstrapResultStatus
    plan: BootstrapPlan | None = None
    preflight_report: PreflightReport | None = None
    runtime_snapshot: RuntimeSnapshot | None = None
    lifecycle_plan: LifecyclePlan | None = None
    errors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "errors", tuple(self.errors))

    @property
    def succeeded(self) -> bool:
        """Return ``True`` when the run completed successfully."""
        return self.status is BootstrapResultStatus.SUCCESS
