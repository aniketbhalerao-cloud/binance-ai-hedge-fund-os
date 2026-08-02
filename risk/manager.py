"""Risk manager and default decision policy.

:class:`RiskEvaluationManager` coordinates a full evaluation: it invokes the
validator, publishes the per-rule and decision events, applies a
:class:`~risk.interfaces.RiskPolicy` to turn the result into a decision, and
returns the :class:`~risk.models.RiskDecision`. It contains no rule logic.

:class:`DefaultRiskPolicy` provides the framework's default mapping from a
:class:`~risk.models.RiskResult` to a decision (approve when clean, reject when
any violation) — a placeholder policy carrying no actual risk thresholds.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from core.logging import LoggerFactory
from events.bus import EventBus
from risk.context import RiskContext
from risk.events import (
    RiskDecisionApproved,
    RiskDecisionRejected,
    RiskErrorOccurred,
    RiskEvaluationCompleted,
    RiskEvaluationStarted,
    RiskRuleFailed,
    RiskRulePassed,
)
from risk.interfaces import RiskPolicy, RiskValidator
from risk.models import RiskDecision, RiskDecisionType, RiskResult

__all__ = ["DefaultRiskPolicy", "RiskEvaluationManager"]


class DefaultRiskPolicy:
    """Default policy: reject on any violation, otherwise approve."""

    def decide(self, result: RiskResult, context: RiskContext) -> RiskDecision:
        """Map ``result`` to an approval :class:`RiskDecision`."""
        decision_type = (
            RiskDecisionType.REJECTED
            if result.violations
            else RiskDecisionType.APPROVED
        )
        return RiskDecision(
            id=uuid.uuid4().hex,
            decision_type=decision_type,
            timestamp=datetime.now(UTC),
            triggered_rules=tuple(v.rule_name for v in result.violations),
            violations=result.violations,
        )


class RiskEvaluationManager:
    """Coordinates validation, decision, and event publication.

    Args:
        bus: The event bus used to publish risk events.
        validator: The rule validator (abstraction).
        policy: The decision policy (abstraction).
        logger: Optional logger factory for framework logs.
    """

    def __init__(
        self,
        bus: EventBus,
        validator: RiskValidator,
        policy: RiskPolicy,
        logger: LoggerFactory | None = None,
    ) -> None:
        self._bus = bus
        self._validator = validator
        self._policy = policy
        self._log = logger.get_logger("risk.manager") if logger else None

    async def evaluate(self, context: RiskContext) -> RiskDecision:
        """Evaluate ``context`` and return the resulting decision.

        Always produces a decision: rule errors are surfaced as
        ``RiskErrorOccurred`` events and do not abort the evaluation.
        """
        self._info("Risk evaluation started", context.symbol)
        await self._bus.publish(RiskEvaluationStarted(symbol=context.symbol))

        result = await self._validator.validate(context)

        for name in result.passed_rules:
            await self._bus.publish(RiskRulePassed(rule=name))
        for violation in result.violations:
            await self._bus.publish(
                RiskRuleFailed(rule=violation.rule_name, message=violation.message)
            )
        for name, message in result.errors:
            self._error(name, message)
            await self._bus.publish(RiskErrorOccurred(rule=name, message=message))

        decision = self._policy.decide(result, context)

        if decision.approved:
            await self._bus.publish(RiskDecisionApproved(decision=decision))
        else:
            await self._bus.publish(RiskDecisionRejected(decision=decision))

        await self._bus.publish(RiskEvaluationCompleted(decision=decision))
        self._info(
            f"Risk evaluation completed: {decision.decision_type.value}", context.symbol
        )
        return decision

    def _info(self, message: str, symbol: str) -> None:
        if self._log is not None:
            self._log.info(message, extra={"symbol": symbol})

    def _error(self, rule: str, message: str) -> None:
        if self._log is not None:
            self._log.error("Risk rule error", extra={"rule": rule, "error": message})
