"""Agent registry.

:class:`InMemoryAgentRegistry` is a thread-safe store of agents keyed by role. It
never creates agents (creation and injection are Dependency Injection's job) — it
only registers, looks up, lists, and clears them. Mutable state is guarded by a
:class:`threading.Lock`.
"""

from __future__ import annotations

from threading import Lock

from agents.exceptions import AgentNotFoundError
from agents.interfaces import Agent
from agents.models import AgentRole

__all__ = ["InMemoryAgentRegistry"]


class InMemoryAgentRegistry:
    """A thread-safe registry of agents, keyed by role."""

    def __init__(self) -> None:
        self._agents: dict[AgentRole, Agent] = {}
        self._lock = Lock()

    def register(self, agent: Agent) -> None:
        """Store ``agent`` under its role (insert or replace)."""
        with self._lock:
            self._agents[agent.role] = agent

    def unregister(self, role: AgentRole) -> None:
        """Remove the agent for ``role`` if present."""
        with self._lock:
            self._agents.pop(role, None)

    def get(self, role: AgentRole) -> Agent:
        """Return the agent for ``role``.

        Raises:
            AgentNotFoundError: If no agent is registered for the role.
        """
        with self._lock:
            agent = self._agents.get(role)
        if agent is None:
            raise AgentNotFoundError(f"no agent registered for role {role.value!r}")
        return agent

    def exists(self, role: AgentRole) -> bool:
        """Return ``True`` if an agent is registered for ``role``."""
        with self._lock:
            return role in self._agents

    def list(self) -> list[Agent]:
        """Return all registered agents."""
        with self._lock:
            return list(self._agents.values())

    def clear(self) -> None:
        """Remove all registered agents."""
        with self._lock:
            self._agents.clear()
