"""Decision history.

:class:`DefaultDecisionHistory` appends decisions to an append-only
:class:`~agents.models.DecisionHistory`. It is stateless — it returns a new
history and never mutates existing records, so the decision timeline is immutable
and can never be rewritten.
"""

from __future__ import annotations

from agents.models import Decision, DecisionHistory

__all__ = ["DefaultDecisionHistory"]


class DefaultDecisionHistory:
    """Stateless, append-only decision-history service."""

    def append(self, history: DecisionHistory, decision: Decision) -> DecisionHistory:
        """Return a new history with ``decision`` appended."""
        return history.append(decision)
