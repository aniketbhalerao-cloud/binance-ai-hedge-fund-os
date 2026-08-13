"""Model Gateway collector.

:class:`DefaultCollector` gathers the standardized source readings in a
context, normalizes them into
:class:`~model_gateway.models.ModelInvocationSource` entries
(highest-priority-first, capped by ``max_items``), and builds a raw
:class:`~model_gateway.models.ModelInvocationBatch` with one unplanned entry
per source. Provider routing is entirely the Dispatcher stage's job — the
collector never selects a provider. It is deterministic and stateless, and
it only *collects* — it never modifies any subject.
"""

from __future__ import annotations

from model_gateway.context import ModelGatewayContext
from model_gateway.exceptions import CollectionError
from model_gateway.models import (
    ModelInvocationBatch,
    ModelInvocationEntry,
    ModelInvocationSource,
)

__all__ = ["DefaultCollector"]


class DefaultCollector:
    """Stateless source collection and batch construction."""

    def collect(self, context: ModelGatewayContext) -> ModelInvocationBatch:
        """Return the raw :class:`ModelInvocationBatch` for ``context``.

        Raises:
            CollectionError: If an unexpected failure occurs.
        """
        try:
            sources = self._sources(context)
            entries = tuple(ModelInvocationEntry(source=s) for s in sources)
            return ModelInvocationBatch(sources=sources, entries=entries)
        except CollectionError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise CollectionError(str(exc)) from exc

    @staticmethod
    def _sources(
        context: ModelGatewayContext,
    ) -> tuple[ModelInvocationSource, ...]:
        candidates = [
            *context.agent_sources,
            *context.memory_sources,
            *context.learning_sources,
            *context.optimization_sources,
        ]
        # Highest-priority-first, with a stable tiebreak by name for determinism.
        candidates.sort(key=lambda s: (-s.priority, s.source, s.name))
        return tuple(candidates[: context.parameters.max_items])
