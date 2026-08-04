"""Paper trading registry.

:class:`InMemoryPaperTradingRegistry` is a thread-safe store that **owns the
running sessions**, keyed by session id. It never creates sessions (creation is
the manager's job) — it only registers (insert or replace), looks up, lists, and
clears them. The manager loads the current session, processes one update, and
writes back a new immutable session. Mutable state is guarded by a
:class:`threading.Lock`.
"""

from __future__ import annotations

from threading import Lock

from paper_trading.exceptions import RegistryError
from paper_trading.models import PaperSession

__all__ = ["InMemoryPaperTradingRegistry"]


class InMemoryPaperTradingRegistry:
    """A thread-safe registry that owns running sessions, keyed by id."""

    def __init__(self) -> None:
        self._sessions: dict[str, PaperSession] = {}
        self._lock = Lock()

    def register(self, session: PaperSession) -> None:
        """Store ``session`` (insert or replace)."""
        with self._lock:
            self._sessions[session.id] = session

    def unregister(self, session_id: str) -> None:
        """Remove ``session_id`` if present."""
        with self._lock:
            self._sessions.pop(session_id, None)

    def get(self, session_id: str) -> PaperSession:
        """Return the session for ``session_id``.

        Raises:
            RegistryError: If it is not registered.
        """
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            raise RegistryError(f"session {session_id!r} not found")
        return session

    def exists(self, session_id: str) -> bool:
        """Return ``True`` if ``session_id`` is registered."""
        with self._lock:
            return session_id in self._sessions

    def list(self) -> list[PaperSession]:
        """Return all registered sessions."""
        with self._lock:
            return list(self._sessions.values())

    def clear(self) -> None:
        """Remove all registered sessions."""
        with self._lock:
            self._sessions.clear()
