"""Workflow dispatcher.

:class:`DefaultDispatcher` turns an already-ordered, already-validated
:class:`~workflows.models.WorkflowPlan` into deterministic, immutable
:class:`~workflows.models.WorkflowRequest` domain objects — one per resolved
step, in resolved order. It is a planning boundary only: it never executes a
workflow step, triggers an Agent, calls ``ModelGatewayManager.invoke()``,
``SchedulerManager.schedule()``, or ``WorkerManager.enqueue()``, executes a
trade, performs inference, or makes a network call. It is stateless and
fully deterministic — every request is derived from immutable plan data.

Handoff-target validity is normally already guaranteed by the Planner (the
primary validation boundary); the dispatcher re-validates every entry's
handoff target against :data:`~workflows.models.SUPPORTED_HANDOFF_TARGETS`
before constructing *any* ``WorkflowRequest``, as defence-in-depth against a
plan assembled or mutated outside the normal collect-plan pipeline. On an
invalid target, zero requests are constructed and :class:`DispatchError` is
raised — never a partial result.
"""

from __future__ import annotations

from workflows.context import WorkflowContext
from workflows.exceptions import DispatchError
from workflows.models import SUPPORTED_HANDOFF_TARGETS, WorkflowPlan, WorkflowRequest

__all__ = ["DefaultDispatcher"]


class DefaultDispatcher:
    """Stateless, deterministic workflow-request generation."""

    def dispatch(
        self, plan: WorkflowPlan, context: WorkflowContext
    ) -> tuple[WorkflowRequest, ...]:
        """Return one workflow request per resolved plan entry, in order.

        Raises:
            DispatchError: If any entry's handoff target is invalid (zero
                requests are constructed) or an unexpected failure occurs.
        """
        try:
            for entry in plan.entries:
                if entry.step.handoff_target not in SUPPORTED_HANDOFF_TARGETS:
                    raise DispatchError(
                        f"workflow {entry.workflow_id!r} step "
                        f"{entry.step.step_id!r} has invalid handoff target "
                        f"{entry.step.handoff_target!r}"
                    )
            return tuple(
                WorkflowRequest(
                    subject=entry.step.step_id,
                    source=entry.workflow_id,
                    handoff_target=entry.step.handoff_target,
                    priority=entry.step.priority,
                    position=entry.position,
                    detail=entry.step.detail,
                )
                for entry in plan.entries
            )
        except DispatchError:
            raise
        except Exception as exc:  # translate; never leak internals
            raise DispatchError(str(exc)) from exc
