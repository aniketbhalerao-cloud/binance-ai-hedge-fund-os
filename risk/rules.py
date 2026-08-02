"""Abstract base class for risk rules.

:class:`BaseRiskRule` is the reusable framework every future rule (Maximum
Position Size, Daily Loss Limit, Leverage Limit, …) inherits from. Rules are
**stateless**: they receive a :class:`~risk.context.RiskContext` and return a
:class:`~risk.models.RiskViolation` when they fail (or ``None`` when they pass).
No concrete trading rule is implemented here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from risk.context import RiskContext
from risk.models import RiskMetadata, RiskViolation

__all__ = ["BaseRiskRule"]


class BaseRiskRule(ABC):
    """Base class implementing the :class:`~risk.interfaces.RiskRule` contract.

    Subclasses implement :meth:`check`. Instances must remain stateless so they
    can be evaluated concurrently and safely reused.
    """

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        """Return this rule's unique name."""
        return self._name

    async def evaluate(self, context: RiskContext) -> RiskViolation | None:
        """Evaluate the rule against ``context`` (delegates to :meth:`check`)."""
        return await self.check(context)

    @abstractmethod
    async def check(self, context: RiskContext) -> RiskViolation | None:
        """Return a violation if the rule fails, else ``None`` (subclass logic)."""

    def make_violation(
        self, message: str, metadata: RiskMetadata | None = None
    ) -> RiskViolation:
        """Build a :class:`RiskViolation` stamped with this rule's name."""
        return RiskViolation(
            rule_name=self.name,
            message=message,
            metadata=metadata or RiskMetadata(),
        )
