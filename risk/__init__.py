"""Risk Framework — evaluates trading signals before execution.

The Risk Engine decides *whether* a signal is allowed to proceed. It receives a
:class:`RiskContext`, runs the enabled rules through the validator, produces a
:class:`RiskDecision`, and publishes risk events on the shared event bus. It is
independent of strategies, order execution, portfolio persistence, and
exchanges — it evaluates risk only and executes nothing. New rules plug in by
subclassing :class:`BaseRiskRule`, with no changes to the framework (Open/Closed).

This module exposes the public API and the DI wiring helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import LoggerFactory
from events.bus import EventBus
from risk.context import RiskContext
from risk.engine import RiskEvaluationEngine
from risk.events import (
    RiskDecisionApproved,
    RiskDecisionRejected,
    RiskEngineStarted,
    RiskEngineStopped,
    RiskErrorOccurred,
    RiskEvaluationCompleted,
    RiskEvaluationStarted,
    RiskEvent,
    RiskRuleFailed,
    RiskRulePassed,
)
from risk.exceptions import (
    DuplicateRiskRule,
    InvalidRiskContext,
    RiskEngineError,
    RiskError,
    RiskRuleError,
    RiskValidationError,
)
from risk.interfaces import (
    RiskEngine,
    RiskManager,
    RiskPolicy,
    RiskRule,
    RiskValidator,
)
from risk.manager import DefaultRiskPolicy, RiskEvaluationManager
from risk.models import (
    PositionSizing,
    RiskDecision,
    RiskDecisionType,
    RiskMetadata,
    RiskResult,
    RiskViolation,
)
from risk.rules import BaseRiskRule
from risk.validator import RuleRiskValidator

if TYPE_CHECKING:
    from core.interfaces import Container, Resolver

__all__ = [
    # models & context
    "RiskDecisionType",
    "RiskDecision",
    "RiskViolation",
    "RiskResult",
    "RiskMetadata",
    "PositionSizing",
    "RiskContext",
    # rules / interfaces
    "BaseRiskRule",
    "RiskRule",
    "RiskValidator",
    "RiskPolicy",
    "RiskManager",
    "RiskEngine",
    # implementations
    "RuleRiskValidator",
    "DefaultRiskPolicy",
    "RiskEvaluationManager",
    "RiskEvaluationEngine",
    # events
    "RiskEvent",
    "RiskEvaluationStarted",
    "RiskEvaluationCompleted",
    "RiskRulePassed",
    "RiskRuleFailed",
    "RiskDecisionApproved",
    "RiskDecisionRejected",
    "RiskEngineStarted",
    "RiskEngineStopped",
    "RiskErrorOccurred",
    # exceptions
    "RiskError",
    "RiskValidationError",
    "RiskRuleError",
    "RiskEngineError",
    "InvalidRiskContext",
    "DuplicateRiskRule",
    # wiring
    "register_risk",
]


def register_risk(container: Container) -> None:
    """Register the Risk Framework services into a DI container.

    Registers the validator, policy, manager, and engine as singletons, bound to
    their abstractions (Dependency Inversion). ``EventBus`` is registered on
    demand; ``LoggerFactory``, ``TradingEngine``, and ``StrategyManager`` are
    injected only if already registered.

    Args:
        container: The DI container to register into.
    """
    if not container.has(EventBus):
        container.register_class(EventBus)

    container.register_class(RiskValidator, RuleRiskValidator)
    container.register_class(RiskPolicy, DefaultRiskPolicy)

    def _build_manager(resolver: Resolver) -> RiskEvaluationManager:
        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        return RiskEvaluationManager(
            resolver.resolve(EventBus),
            resolver.resolve(RiskValidator),
            resolver.resolve(RiskPolicy),
            logger=logger,
        )

    container.register_singleton(RiskEvaluationManager, _build_manager)
    container.register_singleton(
        RiskManager, lambda r: r.resolve(RiskEvaluationManager)
    )

    def _build_engine(resolver: Resolver) -> RiskEvaluationEngine:
        from strategies.interfaces import StrategyManager
        from trading.engine import TradingEngine

        logger = (
            resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None
        )
        trading_engine = (
            resolver.resolve(TradingEngine) if resolver.has(TradingEngine) else None
        )
        strategy_manager = (
            resolver.resolve(StrategyManager) if resolver.has(StrategyManager) else None
        )
        return RiskEvaluationEngine(
            resolver.resolve(RiskManager),
            resolver.resolve(EventBus),
            logger=logger,
            trading_engine=trading_engine,
            strategy_manager=strategy_manager,
        )

    container.register_singleton(RiskEvaluationEngine, _build_engine)
    container.register_singleton(RiskEngine, lambda r: r.resolve(RiskEvaluationEngine))
