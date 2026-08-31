"""Composition-root wiring — the sanctioned site for registrar and
concrete-implementation imports.

``app/wiring.py`` is the composition-root site permitted to import every
completed framework's ``register_<framework>`` function and, where dry-run
resolution requires it, a framework's concrete ``Manager``/service
implementation — the one place, in ``app/`` or anywhere else, that assembles
the whole-system object graph.

Framework packages themselves are **not** globally import-isolated.
Existing frameworks legitimately share public domain/value types
(``models``, ``context``, ``signals``, ``state``) and ``Protocol``
interfaces directly with one another — a real, evidenced, intentional
pattern (`docs/audits/task-38.5-risk-register.md` H-1; investigated in
Task 38.9B, disposition still Open pending its own Phase B/C), not
something this module's own permission is meant to prevent. A narrow
existing exception additionally uses ``trading.engine.TradingEngine`` — a
concrete class, not a ``Protocol`` — as an optional, ``resolver.has()``-
gated DI lookup key in nine frameworks; proven, per reference, never
instantiated directly and never invoked for a business/lifecycle operation
by any of them (`tests/test_h1_cross_framework_boundary.py`).

Framework registration and construction never directly construct another
framework's concrete implementation — proven generally, for any
cross-framework concrete import under any import spelling, by
``tests/test_h1_cross_framework_boundary.py``. That same test additionally
proves the one reviewed concrete collaborator above, specifically, is never
invoked for a business/lifecycle operation (its own real
``.start()``/``.stop()``/``.pause()``/``.resume()`` API) by any of its nine
importers — this is not asserted as a general, every-cross-framework-pair
guarantee, only as what is actually evidenced for that one collaborator.
Construction of a concrete cross-framework collaborator happens only here,
mediated by the DI container — that permission (importing each framework's
``register_<framework>`` function to perform that construction) is confined
to this module: nowhere else in ``app/``, and nowhere outside ``app/``,
gains it.

Holds exactly three things:

1. :data:`COMPONENT_REGISTRARS` (plus the :data:`KNOWN_COMPONENT_IDS`
   frozenset derived from it) — every completed framework's registrar,
   keyed by its stable component id.
2. :data:`SAFE_SERVICE_KEYS` — the explicit, I/O-free allowlist of service
   keys a component may declare on ``required_service_keys``. Every listed
   type is a framework's ``Manager``/service abstraction, each of which only
   ever accepts already-constructed, in-process collaborators
   (``EventBus``, ``LoggerFactory``, the framework's own registry/collector/
   planner/dispatcher). No real network client, database client, Redis
   client, or exchange adapter type is ever added here, under any name.
3. :func:`build_configuration_view` and :func:`build_default_manifest`.

Never calls a business method (``.start()``, ``.invoke()``, ``.schedule()``,
``.enqueue()``, ``.compose()``) on anything, and never constructs a real
network, database, or Redis client.
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Mapping
from decimal import Decimal
from types import MappingProxyType
from typing import TYPE_CHECKING

from agents import DefaultDecisionManager, register_agents
from app.exceptions import ConfigurationError
from app.models import ComponentManifest, ComponentSpec, ConfigurationView
from backtesting import DefaultBacktestManager, register_backtesting
from dashboard import DefaultDashboardManager, register_dashboard
from exchange_adapters import DefaultExchangeManager, register_exchange_adapters
from execution import DefaultExecutionManager, register_execution
from learning import DefaultLearningManager, register_learning
from market_data import MarketDataPipelineService, register_market_data
from memory import DefaultMemoryManager, register_memory
from model_gateway import DefaultModelGatewayManager, register_model_gateway
from monitoring import DefaultMonitoringManager, register_monitoring
from notification import DefaultNotificationManager, register_notification
from optimization import DefaultOptimizationManager, register_optimization
from order_management import DefaultOrderManager, register_order_management
from paper_trading import DefaultPaperTradingManager, register_paper_trading
from performance import DefaultPerformanceManager, register_performance
from portfolio import DefaultPortfolioManager, register_portfolio
from positions import DefaultPositionManager, register_positions
from reporting import DefaultReportingManager, register_reporting
from risk import RiskEvaluationManager, register_risk
from scheduler import DefaultSchedulerManager, register_scheduler
from storage import DefaultStorageManager, register_storage
from strategies import StrategyExecutionManager, register_strategies
from trades import DefaultTradeManager, register_trades
from workers import DefaultWorkerManager, register_workers
from workflows import DefaultWorkflowManager, register_workflows

if TYPE_CHECKING:
    from config.settings import Settings
    from core.interfaces import Container
    from market_data.interfaces import RawHandler

__all__ = [
    "COMPONENT_REGISTRARS",
    "KNOWN_COMPONENT_IDS",
    "SAFE_SERVICE_KEYS",
    "build_configuration_view",
    "build_default_manifest",
]


class _DryRunMarketDataProvider:
    """A deterministic, genuinely stateless stand-in for a real
    ``MarketDataProvider`` — never a real exchange client or adapter.

    Exists solely so ``market_data`` and the frameworks that optionally
    pull in ``MarketDataService`` (``strategies``, ``backtesting``,
    ``paper_trading``) can resolve during a dry-run preflight check without
    a real, credentialed provider. ``__slots__ = ()`` means an instance has
    no instance dict and cannot hold any attribute at all — nothing can be
    stored on it, by this class or by any caller, ever.

    ``MarketDataPipelineService.__init__`` unconditionally calls
    ``provider.on_data(handler)`` to register its own callback.
    :meth:`on_data` accepts that handler and immediately discards it —
    never stored, never retained, never called — so resolving this
    provider can never leak a bound service callback across bootstrap runs
    or create shared mutable state. Every method that would actually touch
    a network — ``connect``/``disconnect`` — fails closed: it raises
    immediately rather than doing anything, so this can never be mistaken
    for, or misused as, a usable provider.
    """

    __slots__ = ()

    @property
    def is_connected(self) -> bool:
        return False

    def on_data(self, handler: RawHandler) -> None:
        del handler  # accepted, then discarded — nothing is ever stored

    async def connect(self) -> None:
        raise RuntimeError("_DryRunMarketDataProvider performs no I/O")

    async def disconnect(self) -> None:
        raise RuntimeError("_DryRunMarketDataProvider performs no I/O")


#: A single, genuinely stateless (``__slots__ = ()``), I/O-free instance
#: shared across every dry-run bootstrap — never a real client, and never
#: anything a caller could use to reach a real exchange or retain state
#: across runs.
_DRY_RUN_MARKET_DATA_PROVIDER = _DryRunMarketDataProvider()

#: Every completed package exposing a ``register_<framework>`` function —
#: all 25 of them. ``trading/`` has no ``register_trading`` function and is
#: deliberately excluded — there is nothing to wire. ``market_data`` is
#: bound via ``functools.partial`` to the dry-run provider above, so
#: ``market_data`` itself (and every framework that optionally resolves
#: ``MarketDataService``) can complete preflight resolution without a real
#: provider. ``exchange_adapters`` registers the same way every other
#: framework does (H-2, ``docs/audits/task-38.5-risk-register.md``) — its
#: registrar declares no broker adapter, no credentials, and no connect/
#: authenticate/route/submit call of its own (see ``_COMPONENT_SERVICE``).
COMPONENT_REGISTRARS: Mapping[str, Callable[[Container], None]] = MappingProxyType(
    {
        "agents": register_agents,
        "backtesting": register_backtesting,
        "dashboard": register_dashboard,
        "exchange_adapters": register_exchange_adapters,
        "execution": register_execution,
        "learning": register_learning,
        "market_data": functools.partial(
            register_market_data, provider=_DRY_RUN_MARKET_DATA_PROVIDER
        ),
        "memory": register_memory,
        "model_gateway": register_model_gateway,
        "monitoring": register_monitoring,
        "notification": register_notification,
        "optimization": register_optimization,
        "order_management": register_order_management,
        "paper_trading": register_paper_trading,
        "performance": register_performance,
        "portfolio": register_portfolio,
        "positions": register_positions,
        "reporting": register_reporting,
        "risk": register_risk,
        "scheduler": register_scheduler,
        "storage": register_storage,
        "strategies": register_strategies,
        "trades": register_trades,
        "workers": register_workers,
        "workflows": register_workflows,
    }
)

#: Every known ``component_id`` — the planner rejects any id outside this
#: set before any other validation, and before any container is created.
KNOWN_COMPONENT_IDS: frozenset[str] = frozenset(COMPONENT_REGISTRARS)

#: ``component_id -> (safe service key, I/O-free type to resolve)``. The
#: single source of truth both ``SAFE_SERVICE_KEYS`` and
#: ``build_default_manifest`` derive from, so the two can never drift apart.
#: Every listed type is a framework's ``Manager``/service abstraction, built
#: only from already-registered, in-process collaborators — proven free of
#: I/O in its constructor by that framework's own registrar (see the module
#: docstring). ``exchange_adapters`` -> ``DefaultExchangeManager`` is chosen
#: over ``DefaultExchangeEngine`` deliberately: the manager's constructor
#: alone forces resolution of every one of the framework's own collaborators
#: (``ExchangeAuthentication``, ``ExchangeConnection``, ``ExchangeValidator``,
#: ``ExchangeRouter``, ``ExchangeRegistry``, ``EventBus``) — proving
#: ``exchange_adapters``' own DI graph wires — without ever calling
#: ``.authenticate()``/``.open()``/``.route()``/``.validate()``/``.submit()``/
#: ``.process()`` (all `async def`, never invoked by construction). The
#: engine would additionally, optionally reach into ``execution``/``trading``
#: for no proof this framework's own registration needs.
_COMPONENT_SERVICE: Mapping[str, tuple[str, type]] = MappingProxyType(
    {
        "agents": ("agents.manager", DefaultDecisionManager),
        "backtesting": ("backtesting.manager", DefaultBacktestManager),
        "dashboard": ("dashboard.manager", DefaultDashboardManager),
        "exchange_adapters": ("exchange_adapters.manager", DefaultExchangeManager),
        "execution": ("execution.manager", DefaultExecutionManager),
        "learning": ("learning.manager", DefaultLearningManager),
        "market_data": ("market_data.service", MarketDataPipelineService),
        "memory": ("memory.manager", DefaultMemoryManager),
        "model_gateway": ("model_gateway.manager", DefaultModelGatewayManager),
        "monitoring": ("monitoring.manager", DefaultMonitoringManager),
        "notification": ("notification.manager", DefaultNotificationManager),
        "optimization": ("optimization.manager", DefaultOptimizationManager),
        "order_management": ("order_management.manager", DefaultOrderManager),
        "paper_trading": ("paper_trading.manager", DefaultPaperTradingManager),
        "performance": ("performance.manager", DefaultPerformanceManager),
        "portfolio": ("portfolio.manager", DefaultPortfolioManager),
        "positions": ("positions.manager", DefaultPositionManager),
        "reporting": ("reporting.manager", DefaultReportingManager),
        "risk": ("risk.manager", RiskEvaluationManager),
        "scheduler": ("scheduler.manager", DefaultSchedulerManager),
        "storage": ("storage.manager", DefaultStorageManager),
        "strategies": ("strategies.manager", StrategyExecutionManager),
        "trades": ("trades.manager", DefaultTradeManager),
        "workers": ("workers.manager", DefaultWorkerManager),
        "workflows": ("workflows.manager", DefaultWorkflowManager),
    }
)

#: The explicit, safe service-key allowlist. Only types already proven to
#: have I/O-free constructors are ever listed — see the module docstring.
SAFE_SERVICE_KEYS: Mapping[str, type] = MappingProxyType(
    {key: cls for key, cls in _COMPONENT_SERVICE.values()}
)

_DEFAULT_PRIORITY = Decimal("0")

#: A second, mechanical layer of defence, independent of the positive
#: allowlist expressed by ``build_configuration_view``'s explicit field
#: list below: any ``Settings`` field whose name contains one of these
#: fragments is never copied, whether or not it happens to embed userinfo or
#: query-string credentials — no URL is ever partially sanitized and
#: included; it is excluded outright.
_SENSITIVE_NAME_FRAGMENTS: tuple[str, ...] = (
    "key",
    "secret",
    "token",
    "credential",
    "password",
    "url",
    "dsn",
)

def _is_sensitive_field_name(name: str) -> bool:
    lowered = name.lower()
    return any(fragment in lowered for fragment in _SENSITIVE_NAME_FRAGMENTS)


def _safe[V](settings_path: str, value: V) -> V:
    """Return ``value`` after asserting ``settings_path``'s leaf field name
    is not sensitive.

    Defence in depth, independent of ``build_configuration_view`` only
    calling this for fields already on its curated positive allowlist —
    should be unreachable.
    """
    leaf = settings_path.rsplit(".", 1)[-1]
    if _is_sensitive_field_name(leaf):
        raise ConfigurationError(
            f"refusing to copy Settings field {settings_path!r} into "
            "ConfigurationView: name matches a sensitive pattern"
        )
    return value


def _decimal(value: float) -> Decimal:
    return Decimal(str(value))


def build_configuration_view(settings: Settings) -> ConfigurationView:
    """Return the redacted, allowlisted subset of ``settings``.

    The only function in the codebase permitted to read a real ``Settings``
    object for this task's purposes. Copies only an explicit allowlist of
    fields already known to be free of secrets — every field is passed
    through :func:`_safe`, which mechanically rejects (never partially
    includes) any field whose name matches a sensitive pattern, independent
    of this function only ever calling it for curated fields.

    Args:
        settings: The validated master settings object.

    Returns:
        A ``ConfigurationView`` containing only non-sensitive scalar/
        collection values.

    Raises:
        ConfigurationError: If asked to copy a field whose name matches a
            sensitive pattern — defence in depth; unreachable given the
            curated field list below.
    """
    application = settings.application
    trading = settings.trading
    dashboard = settings.dashboard
    monitoring = settings.monitoring
    logging_settings = settings.logging
    risk = settings.risk
    backtesting = settings.backtesting
    simulation = settings.simulation

    return ConfigurationView(
        application_name=_safe("application.name", application.name),
        application_version=_safe("application.version", application.version),
        application_debug=_safe("application.debug", application.debug),
        application_timezone=_safe("application.timezone", application.timezone),
        environment=_safe("environment", settings.environment.value),
        trading_mode=_safe("trading.mode", trading.mode.value),
        trading_base_currency=_safe("trading.base_currency", trading.base_currency),
        trading_symbols=_safe("trading.symbols", tuple(trading.symbols)),
        dashboard_enabled=_safe("dashboard.enabled", dashboard.enabled),
        dashboard_host=_safe("dashboard.host", dashboard.host),
        dashboard_port=_safe("dashboard.port", dashboard.port),
        monitoring_enabled=_safe("monitoring.enabled", monitoring.enabled),
        monitoring_metrics_port=_safe(
            "monitoring.metrics_port", monitoring.metrics_port
        ),
        logging_level=_safe("logging.level", logging_settings.level.value),
        logging_format=_safe("logging.format", logging_settings.format.value),
        risk_max_position_size_pct=_safe(
            "risk.max_position_size_pct", _decimal(risk.max_position_size_pct)
        ),
        risk_risk_per_trade_pct=_safe(
            "risk.risk_per_trade_pct", _decimal(risk.risk_per_trade_pct)
        ),
        risk_max_daily_drawdown_pct=_safe(
            "risk.max_daily_drawdown_pct", _decimal(risk.max_daily_drawdown_pct)
        ),
        risk_max_total_drawdown_pct=_safe(
            "risk.max_total_drawdown_pct", _decimal(risk.max_total_drawdown_pct)
        ),
        risk_stop_loss_pct=_safe(
            "risk.stop_loss_pct", _decimal(risk.stop_loss_pct)
        ),
        risk_take_profit_pct=_safe(
            "risk.take_profit_pct", _decimal(risk.take_profit_pct)
        ),
        risk_max_leverage=_safe("risk.max_leverage", _decimal(risk.max_leverage)),
        risk_max_open_positions=_safe(
            "risk.max_open_positions", risk.max_open_positions
        ),
        backtesting_initial_balance=_safe(
            "backtesting.initial_balance", _decimal(backtesting.initial_balance)
        ),
        backtesting_commission_pct=_safe(
            "backtesting.commission_pct", _decimal(backtesting.commission_pct)
        ),
        backtesting_slippage_pct=_safe(
            "backtesting.slippage_pct", _decimal(backtesting.slippage_pct)
        ),
        simulation_initial_balance=_safe(
            "simulation.initial_balance", _decimal(simulation.initial_balance)
        ),
        simulation_latency_ms=_safe(
            "simulation.latency_ms", simulation.latency_ms
        ),
        simulation_fill_ratio=_safe(
            "simulation.fill_ratio", _decimal(simulation.fill_ratio)
        ),
        simulation_commission_pct=_safe(
            "simulation.commission_pct", _decimal(simulation.commission_pct)
        ),
        simulation_slippage_pct=_safe(
            "simulation.slippage_pct", _decimal(simulation.slippage_pct)
        ),
        simulation_random_seed=_safe(
            "simulation.random_seed", simulation.random_seed
        ),
        binance_testnet=_safe("binance.testnet", settings.binance.testnet),
    )


def build_default_manifest() -> ComponentManifest:
    """Return the default manifest: one ``ComponentSpec`` per known
    component id, zero declared dependencies — no completed framework's
    ``register_<framework>`` function requires another to already be
    registered. Used by ``main.py``'s default run.
    """
    components = tuple(
        ComponentSpec(
            component_id=component_id,
            priority=_DEFAULT_PRIORITY,
            required_service_keys=(_COMPONENT_SERVICE[component_id][0],),
            detail=f"{component_id} framework registration",
        )
        for component_id in sorted(KNOWN_COMPONENT_IDS)
    )
    return ComponentManifest(components=components)
