"""Workflow collector.

:class:`DefaultCollector` gathers the declarative workflow definitions
supplied on a context, caps the count at ``max_items``, and builds the raw
:class:`~workflows.models.WorkflowBatch`. It preserves whatever order the
definitions were supplied in — it never resolves workflow-level or
step-level ordering, validates a dependency graph, or selects a handoff
target; those are the Planner's and Dispatcher's jobs. It is deterministic
and stateless, and it only *collects* — it never modifies any subject.
"""

from __future__ import annotations

from workflows.context import WorkflowContext
from workflows.exceptions import CollectionError
from workflows.models import WorkflowBatch

__all__ = ["DefaultCollector"]


class DefaultCollector:
    """Stateless workflow-definition collection and batch construction."""

    def collect(self, context: WorkflowContext) -> WorkflowBatch:
        """Return the raw :class:`WorkflowBatch` for ``context``.

        Raises:
            CollectionError: If an unexpected failure occurs.
        """
        try:
            max_items = context.parameters.max_items
            definitions = tuple(context.workflow_definitions[:max_items])
            return WorkflowBatch(definitions=definitions)
        except CollectionError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise CollectionError(str(exc)) from exc
