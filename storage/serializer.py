"""Storage serializer.

:class:`DefaultSerializer` serializes a raw storage batch into immutable storage
items: it assigns each item a storage target, resolves whether it clears the
priority threshold for persistence, and produces the serialized batch whose
items carry their routing. It is deterministic and stateless, and it **never
applies changes** — it only constructs the storage items.
"""

from __future__ import annotations

from storage.context import StorageContext
from storage.exceptions import SerializationError
from storage.models import (
    SUPPORTED_STORAGE_TARGETS,
    StorageBatch,
    StorageItem,
    StorageParameters,
    StorageSource,
)

__all__ = ["DefaultSerializer"]


class DefaultSerializer:
    """Stateless batch serialization (item construction only, never applied)."""

    def serialize(
        self, batch: StorageBatch, context: StorageContext
    ) -> StorageBatch:
        """Return the serialized batch (items carry their routing).

        Raises:
            SerializationError: If an unexpected failure occurs.
        """
        try:
            items = tuple(
                _item(s, context.parameters) for s in batch.sources
            )
            return StorageBatch(sources=batch.sources, items=items)
        except SerializationError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise SerializationError(str(exc)) from exc


def _item(source: StorageSource, parameters: StorageParameters) -> StorageItem:
    if source.priority >= parameters.priority_threshold:
        persist, detail = True, "eligible for persistence"
    else:
        persist, detail = False, "below priority threshold"
    target = (
        source.category if source.category in SUPPORTED_STORAGE_TARGETS else "database"
    )
    return StorageItem(
        source=source, persist=persist, target=target, detail=detail
    )
