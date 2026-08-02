"""Trading engine — the orchestration layer's public entry point.

:class:`TradingEngine` coordinates the Sprint 1 infrastructure. It owns a
:class:`~trading.state.RuntimeState`, drives an injected
:class:`~trading.lifecycle.LifecycleManager` through legal transitions, delegates
all infrastructure work to an injected :class:`~trading.interfaces.Coordinator`,
logs via the injected :class:`~core.logging.LoggerFactory`, and publishes engine
lifecycle events on the shared event bus.

It is intentionally small: it performs **no** trading, strategy, risk, exchange,
execution, portfolio, or notification logic — every business decision is
delegated elsewhere. All collaborators are supplied through dependency
injection; the engine never instantiates them.
"""

from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock
from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from database.service import PersistenceService
from events.bus import EventBus
from trading.coordinator import TradingCoordinator
from trading.exceptions import (
    EngineAlreadyRunningError,
    EngineInitializationError,
    EngineNotRunningError,
)
from trading.interfaces import Coordinator
from trading.lifecycle import (
    EngineFailed,
    EngineInitializing,
    EnginePaused,
    EngineResumed,
    EngineStarted,
    EngineStarting,
    EngineStopped,
    EngineStopping,
    LifecycleManager,
)
from trading.state import EngineState, RuntimeState

if TYPE_CHECKING:
    from adapters.interfaces import ExchangeInterface
    from core.interfaces import Container, Resolver

__all__ = ["TradingEngine", "register_trading_engine"]

#: States from which the engine may be (re)started.
_STARTABLE = frozenset({EngineState.CREATED, EngineState.STOPPED, EngineState.FAILED})


class TradingEngine:
    """Orchestrates the trading system's start/stop/pause/resume lifecycle.

    Args:
        coordinator: The coordination unit driven during lifecycle changes.
        lifecycle: The lifecycle state machine (injected, never constructed here).
        logger: Optional logger factory for engine-level lifecycle logs.
    """

    def __init__(
        self,
        coordinator: Coordinator,
        lifecycle: LifecycleManager,
        logger: LoggerFactory | None = None,
    ) -> None:
        self._coordinator = coordinator
        self._lifecycle = lifecycle
        self._log = logger.get_logger("trading.engine") if logger else None
        self._runtime = RuntimeState(state=lifecycle.current_state())
        self._lock = Lock()

    # -- introspection -------------------------------------------------------

    def state(self) -> EngineState:
        """Return the engine's current lifecycle state."""
        return self._lifecycle.current_state()

    @property
    def is_running(self) -> bool:
        """Return ``True`` while the engine is running."""
        return self._lifecycle.is_running

    def status(self) -> RuntimeState:
        """Return an immutable snapshot of the engine's runtime state."""
        with self._lock:
            return self._runtime

    def statistics(self) -> dict[str, int]:
        """Return the engine's processing counters."""
        with self._lock:
            return self._runtime.statistics()

    def health(self) -> bool:
        """Return ``True`` if the engine is currently healthy (running)."""
        return self._lifecycle.current_state() is EngineState.RUNNING

    def uptime(self) -> float:
        """Return seconds since the engine last started, or ``0.0``."""
        with self._lock:
            started = self._runtime.started_at
        if started is None:
            return 0.0
        return (datetime.now(UTC) - started).total_seconds()

    # -- lifecycle -----------------------------------------------------------

    async def start(self) -> None:
        """Initialize, start services, and enter the RUNNING state.

        Raises:
            EngineAlreadyRunningError: If the engine is already active.
            EngineInitializationError: If start-up fails (after failing safely).
        """
        if self._lifecycle.current_state() not in _STARTABLE:
            raise EngineAlreadyRunningError(
                f"Cannot start engine from state "
                f"{self._lifecycle.current_state().value!r}."
            )
        try:
            self._enter(EngineState.INITIALIZING)
            self._info("Engine initializing")
            await self._coordinator.publish_event(EngineInitializing())

            self._enter(EngineState.STARTING)
            self._info("Engine starting")
            await self._coordinator.publish_event(EngineStarting())
            await self._coordinator.start_services()

            self._enter(EngineState.RUNNING)
            self._mark_started()
            self._info("Engine started")
            await self._coordinator.publish_event(EngineStarted())
        except Exception as exc:  # fail safely — never crash the application
            await self._fail(exc)
            raise EngineInitializationError(str(exc)) from exc

    async def stop(self) -> None:
        """Stop services and enter the STOPPED state.

        Raises:
            EngineNotRunningError: If the engine is not running or paused.
        """
        if self._lifecycle.current_state() not in {
            EngineState.RUNNING,
            EngineState.PAUSED,
        }:
            raise EngineNotRunningError("Engine is not running.")
        try:
            self._enter(EngineState.STOPPING)
            self._info("Engine stopping")
            await self._coordinator.publish_event(EngineStopping())
            await self._coordinator.stop_services()

            self._enter(EngineState.STOPPED)
            self._info("Engine stopped")
            await self._coordinator.publish_event(EngineStopped())
        except Exception as exc:
            await self._fail(exc)
            raise

    async def pause(self) -> None:
        """Pause a running engine.

        Raises:
            EngineNotRunningError: If the engine is not running.
        """
        if self._lifecycle.current_state() is not EngineState.RUNNING:
            raise EngineNotRunningError("Engine is not running; cannot pause.")
        self._enter(EngineState.PAUSED)
        self._info("Engine paused")
        await self._coordinator.publish_event(EnginePaused())

    async def resume(self) -> None:
        """Resume a paused engine.

        Raises:
            EngineNotRunningError: If the engine is not paused.
        """
        if self._lifecycle.current_state() is not EngineState.PAUSED:
            raise EngineNotRunningError("Engine is not paused; cannot resume.")
        self._enter(EngineState.RUNNING)
        self._info("Engine resumed")
        await self._coordinator.publish_event(EngineResumed())

    # -- internals -----------------------------------------------------------

    def _enter(self, target: EngineState) -> None:
        """Transition the lifecycle and mirror the new state into runtime."""
        self._lifecycle.transition(target)
        now = datetime.now(UTC)
        with self._lock:
            self._runtime = self._runtime.with_state(target, now=now)

    def _mark_started(self) -> None:
        now = datetime.now(UTC)
        with self._lock:
            self._runtime = self._runtime.mark_started(now=now)

    async def _fail(self, exc: Exception) -> None:
        """Fail safely: log, record the error, FAIL the machine, emit event."""
        self._lifecycle.fail()
        now = datetime.now(UTC)
        with self._lock:
            self._runtime = self._runtime.with_error(str(exc), now=now)
        if self._log is not None:
            self._log.error("Engine failed", extra={"error": str(exc)})
        try:
            await self._coordinator.publish_event(EngineFailed(reason=str(exc)))
        except Exception:  # pragma: no cover - never mask the original failure
            pass

    def _info(self, message: str) -> None:
        if self._log is not None:
            self._log.info(message)


def register_trading_engine(container: Container) -> None:
    """Register the lifecycle manager, coordinator, and engine as singletons.

    Wiring reuses whatever infrastructure is already registered:

    * :class:`~events.bus.EventBus` is registered on demand if absent;
    * :class:`~core.logging.LoggerFactory`,
      :class:`~database.service.PersistenceService`, and
      :class:`~adapters.interfaces.ExchangeInterface` are injected only if
      registered.

    Registers :class:`LifecycleManager`, :class:`TradingCoordinator` (also under
    the :class:`~trading.interfaces.Coordinator` abstraction), and
    :class:`TradingEngine`.

    Args:
        container: The DI container to register into.
    """
    if not container.has(EventBus):
        container.register_class(EventBus)

    container.register_class(LifecycleManager)

    def _build_coordinator(resolver: Resolver) -> TradingCoordinator:
        from adapters.interfaces import ExchangeInterface

        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        persistence = (
            resolver.resolve(PersistenceService)
            if resolver.has(PersistenceService)
            else None
        )
        exchange: ExchangeInterface | None = (
            resolver.resolve(ExchangeInterface)
            if resolver.has(ExchangeInterface)
            else None
        )
        return TradingCoordinator(
            resolver.resolve(EventBus),
            logger=logger,
            persistence=persistence,
            exchange=exchange,
        )

    container.register_singleton(TradingCoordinator, _build_coordinator)
    container.register_singleton(Coordinator, lambda r: r.resolve(TradingCoordinator))

    def _build_engine(resolver: Resolver) -> TradingEngine:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return TradingEngine(
            resolver.resolve(Coordinator),
            resolver.resolve(LifecycleManager),
            logger=logger,
        )

    container.register_singleton(TradingEngine, _build_engine)
