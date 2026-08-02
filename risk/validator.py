"""Risk validator.

:class:`RuleRiskValidator` coordinates rule execution: it holds the registered
rules and their enabled state (thread-safe), runs the enabled ones against a
:class:`~risk.context.RiskContext`, collects violations, and always produces a
:class:`~risk.models.RiskResult`. A rule that raises is isolated and recorded as
an error — it never stops the others. The validator contains no rule logic and
never executes trades or modifies positions.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

from risk.context import RiskContext
from risk.exceptions import DuplicateRiskRule, InvalidRiskContext
from risk.interfaces import RiskRule
from risk.models import RiskResult, RiskViolation

__all__ = ["RuleRiskValidator"]


@dataclass(slots=True)
class _Entry:
    rule: RiskRule
    enabled: bool = True


class RuleRiskValidator:
    """A thread-safe validator implementing ``RiskValidator``."""

    def __init__(self) -> None:
        self._entries: dict[str, _Entry] = {}
        self._lock = Lock()

    def add_rule(self, rule: RiskRule) -> None:
        """Register ``rule`` (enabled by default).

        Raises:
            DuplicateRiskRule: If a rule with the same name exists.
        """
        with self._lock:
            if rule.name in self._entries:
                raise DuplicateRiskRule(f"Rule {rule.name!r} already registered.")
            self._entries[rule.name] = _Entry(rule=rule)

    def enable(self, name: str) -> None:
        """Enable the rule named ``name``."""
        self._set_enabled(name, True)

    def disable(self, name: str) -> None:
        """Disable the rule named ``name``."""
        self._set_enabled(name, False)

    def rules(self) -> list[RiskRule]:
        """Return all registered rules."""
        with self._lock:
            return [entry.rule for entry in self._entries.values()]

    async def validate(self, context: RiskContext) -> RiskResult:
        """Run every enabled rule against ``context`` and aggregate the outcome.

        Raises:
            InvalidRiskContext: If ``context`` is ``None``.
        """
        if context is None:
            raise InvalidRiskContext("RiskContext must not be None.")

        with self._lock:
            enabled = [e.rule for e in self._entries.values() if e.enabled]

        passed: list[str] = []
        violations: list[RiskViolation] = []
        errors: list[tuple[str, str]] = []

        for rule in enabled:
            try:
                outcome = await rule.evaluate(context)
            except Exception as exc:  # isolate a failing rule
                errors.append((rule.name, str(exc)))
                continue
            if outcome is None:
                passed.append(rule.name)
            else:
                violations.append(outcome)

        return RiskResult(
            passed=not violations,
            violations=tuple(violations),
            passed_rules=tuple(passed),
            errors=tuple(errors),
        )

    def _set_enabled(self, name: str, enabled: bool) -> None:
        with self._lock:
            entry = self._entries.get(name)
            if entry is None:
                raise DuplicateRiskRule(f"Rule {name!r} is not registered.")
            entry.enabled = enabled
