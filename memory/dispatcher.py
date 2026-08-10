"""Memory dispatcher.

:class:`DefaultDispatcher` turns the commit-eligible entries in a planned
batch into deterministic :class:`~memory.models.MemoryRequest` domain
objects — a subject, its source, its memory scope, and the commit detail. It
is stateless and deterministic, and it **never modifies strategies, agents,
or portfolios**, never calls an AI provider, computes an embedding, or
accesses a vector database; it only produces immutable memory request
objects.
"""

from __future__ import annotations

from memory.context import MemoryContext
from memory.exceptions import DispatchError
from memory.models import MemoryBatch, MemoryRequest

__all__ = ["DefaultDispatcher"]


class DefaultDispatcher:
    """Stateless, deterministic memory request generation (domain objects only)."""

    def dispatch(
        self, batch: MemoryBatch, context: MemoryContext
    ) -> tuple[MemoryRequest, ...]:
        """Return one memory request per commit-eligible entry in ``batch``.

        Raises:
            DispatchError: If an unexpected failure occurs.
        """
        try:
            return tuple(
                MemoryRequest(
                    subject=entry.source.name,
                    source=entry.source.source,
                    scope=entry.scope,
                    category=entry.source.category,
                    priority=entry.source.priority,
                    detail=entry.detail,
                )
                for entry in batch.entries
                if entry.commit
            )
        except DispatchError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise DispatchError(str(exc)) from exc
