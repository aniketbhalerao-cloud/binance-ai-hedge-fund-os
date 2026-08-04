"""AI Decision Engine exceptions.

Definitions only. Internal failures are translated into these so no
implementation detail escapes; the manager always returns a
:class:`~agents.models.DecisionResult`.
"""

from __future__ import annotations

__all__ = [
    "DecisionError",
    "AgentError",
    "ConsensusError",
    "MetricsError",
    "HistoryError",
    "RegistryError",
    "AgentNotFoundError",
    "DecisionRejectedError",
]


class DecisionError(Exception):
    """Base class for all AI Decision Engine errors."""


class AgentError(DecisionError):
    """Raised when an agent fails to produce an opinion.

    Carries the optional ``role`` of the failing agent so the manager can publish
    a role-tagged error event.
    """

    def __init__(self, message: str, role: object | None = None) -> None:
        super().__init__(message)
        self.role = role


class ConsensusError(DecisionError):
    """Raised when consensus resolution fails."""


class MetricsError(DecisionError):
    """Raised when a metrics calculation fails."""


class HistoryError(DecisionError):
    """Raised when a history update fails."""


class RegistryError(DecisionError):
    """Raised when a registry operation fails."""


class AgentNotFoundError(RegistryError):
    """Raised when an agent role is not registered."""


class DecisionRejectedError(DecisionError):
    """Raised internally when a strict-mode decision is rejected."""
