"""Model Gateway planner.

:class:`DefaultPlanner` plans a raw model invocation batch into immutable
entries: it resolves whether each entry clears the priority threshold for
dispatch and produces the planned batch. It is deterministic and stateless,
and it **never applies changes** — it never calls a provider, performs
inference, or modifies a source framework; it only constructs the planned
entries. Provider selection itself is the Dispatcher stage's job.
"""

from __future__ import annotations

from model_gateway.context import ModelGatewayContext
from model_gateway.exceptions import PlanningError
from model_gateway.models import (
    ModelGatewayParameters,
    ModelInvocationBatch,
    ModelInvocationEntry,
    ModelInvocationSource,
)

__all__ = ["DefaultPlanner"]


class DefaultPlanner:
    """Stateless batch planning (entry construction only, never applied)."""

    def plan(
        self, batch: ModelInvocationBatch, context: ModelGatewayContext
    ) -> ModelInvocationBatch:
        """Return the planned batch (entries carry their dispatch eligibility).

        Raises:
            PlanningError: If an unexpected failure occurs.
        """
        try:
            entries = tuple(
                _entry(s, context.parameters) for s in batch.sources
            )
            return ModelInvocationBatch(sources=batch.sources, entries=entries)
        except PlanningError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise PlanningError(str(exc)) from exc


def _entry(
    source: ModelInvocationSource, parameters: ModelGatewayParameters
) -> ModelInvocationEntry:
    if source.priority >= parameters.priority_threshold:
        dispatch, detail = True, "eligible for dispatch"
    else:
        dispatch, detail = False, "below priority threshold"
    return ModelInvocationEntry(source=source, dispatch=dispatch, detail=detail)
