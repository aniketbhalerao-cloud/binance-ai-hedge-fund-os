"""Storage persistence planner.

:class:`DefaultPersistencePlanner` turns the persistable items in a serialized
batch into deterministic :class:`~storage.models.StorageRequest` domain objects
— a subject, its source, its storage target, and the persistence detail. It is
stateless and deterministic, and it **never writes, uploads, or persists**
anything to any storage target and never modifies strategies, agents, or
portfolios; it only produces immutable storage request objects.
"""

from __future__ import annotations

from storage.context import StorageContext
from storage.exceptions import PersistenceError
from storage.models import StorageBatch, StorageRequest

__all__ = ["DefaultPersistencePlanner"]


class DefaultPersistencePlanner:
    """Stateless, deterministic storage request generation (domain objects only)."""

    def plan(
        self, batch: StorageBatch, context: StorageContext
    ) -> tuple[StorageRequest, ...]:
        """Return one storage request per persistable item in ``batch``.

        Raises:
            PersistenceError: If an unexpected failure occurs.
        """
        try:
            return tuple(
                StorageRequest(
                    subject=item.source.name,
                    source=item.source.source,
                    target=item.target,
                    category=item.source.category,
                    priority=item.source.priority,
                    detail=item.detail,
                )
                for item in batch.items
                if item.persist
            )
        except PersistenceError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise PersistenceError(str(exc)) from exc
