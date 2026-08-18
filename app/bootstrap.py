"""Composition-root orchestration — dry-run integration only.

:func:`run_dry_run_bootstrap` ties planner -> disposable container ->
wiring registration -> preflight -> artifacts together. Every run builds
its own fresh, throwaway container via ``container_factory``, registers
into that container alone, performs required-service resolution checks
against it alone, and then discards it — success or failure. Nothing this
module builds is ever returned, cached, or handed to a caller as a live,
usable container. See ``docs/prompts/task-38.md`` "Disposable Candidate
Container".

Sequence:

1. Plan the manifest (``planner.plan``). If planning fails,
   ``container_factory`` is never called.
2. Statically validate every declared service key
   (``preflight.validate_service_keys``) — the last check before any
   container exists. If it fails, ``container_factory`` is never called.
3. Call ``container_factory()`` — exactly once, regardless of what happens
   next. If the factory itself raises, that is a candidate that was never
   produced at all.
4. Register each planned component into that candidate, in plan order, via
   ``wiring.COMPONENT_REGISTRARS``. Any exception discards the candidate.
5. Run the actual preflight resolution pass (``preflight.run``) against a
   narrow resolver callable wrapping that same candidate — never the
   candidate itself. Any exception discards the candidate.
6. A report with any failed check is itself treated as a failed bootstrap
   — the object graph did not prove out, so no artifact is returned.
7. Build the immutable ``RuntimeSnapshot`` and ``LifecyclePlan`` from the
   plan and preflight report — never from the candidate itself.
8. The candidate is discarded — its last reference goes out of scope.

On any failure at any step, the run leaves zero accepted runtime state: no
candidate survives the call, no partial ``RuntimeSnapshot`` is ever
constructed or returned, and ``BootstrapResult.errors`` carries exactly one
fixed, generic message — never a raw exception, a credential, an internal
connection detail, a stack trace, or any caller-supplied value from the
manifest.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from app import planner, preflight, wiring
from app.exceptions import PlanningError, PreflightError
from app.models import (
    BootstrapContext,
    BootstrapResult,
    BootstrapResultStatus,
    LifecyclePlan,
    RuntimeSnapshot,
)
from core.container import ServiceContainer

if TYPE_CHECKING:
    from core.interfaces import Container

__all__ = ["run_dry_run_bootstrap"]


def run_dry_run_bootstrap(
    context: BootstrapContext,
    *,
    container_factory: Callable[[], Container] = ServiceContainer,
) -> BootstrapResult:
    """Run one dry-run bootstrap for ``context``.

    ``container_factory`` is the only container-related parameter — no
    function in this task accepts a container instance as a parameter; a
    candidate is only ever obtained by calling the factory. The factory
    carries a documented precondition (each call returns a newly allocated
    container exclusive to that one run) that this function trusts but
    cannot enforce against a noncompliant or malicious factory.

    Args:
        context: The deterministic bootstrap input.
        container_factory: Builds a fresh, disposable candidate container.
            Defaults to :class:`~core.container.ServiceContainer`.

    Returns:
        The immutable :class:`~app.models.BootstrapResult` for this run.
    """
    try:
        bootstrap_plan = planner.plan(context.manifest)
    except PlanningError:
        return BootstrapResult(
            status=BootstrapResultStatus.FAILED,
            errors=("component graph validation failed",),
        )

    try:
        preflight.validate_service_keys(bootstrap_plan)
    except PreflightError:
        return BootstrapResult(
            status=BootstrapResultStatus.FAILED,
            errors=("service key validation failed",),
        )

    # Exactly one factory call, regardless of what happens next. A factory
    # that raises produced no candidate at all — there is nothing to
    # discard, only a failure to report.
    try:
        container = container_factory()
    except Exception:
        return BootstrapResult(
            status=BootstrapResultStatus.FAILED,
            errors=("container factory failed to produce a candidate container",),
        )

    registered: list[str] = []
    try:
        for entry in bootstrap_plan.entries:
            wiring.COMPONENT_REGISTRARS[entry.component_id](container)
            registered.append(entry.component_id)
    except Exception:  # never leak the framework's internal exception
        return BootstrapResult(
            status=BootstrapResultStatus.FAILED,
            errors=("component registration failed",),
        )

    # A narrow, read-only capability — never the container itself. See
    # ``preflight.ServiceResolver``.
    def _resolve(service_type: type) -> object:
        return container.resolve(service_type)

    try:
        report = preflight.run(bootstrap_plan, _resolve)
    except Exception:  # defence in depth; preflight.run itself never raises
        return BootstrapResult(
            status=BootstrapResultStatus.FAILED,
            errors=("preflight resolution pass failed",),
        )

    if report.failed_checks > 0:
        # The object graph did not prove out — this is a failed bootstrap,
        # not a partial success; no artifact is returned.
        return BootstrapResult(
            status=BootstrapResultStatus.FAILED,
            errors=("preflight resolution checks failed",),
        )

    # The candidate is never inspected again past this point; every
    # artifact below is built entirely from already-known plan/report data.
    registered_ids = tuple(registered)
    snapshot = RuntimeSnapshot(
        registered_component_ids=registered_ids,
        preflight_report=report,
        configuration=context.configuration,
    )
    lifecycle_plan = LifecyclePlan(
        start_order=registered_ids,
        stop_order=tuple(reversed(registered_ids)),
    )
    return BootstrapResult(
        status=BootstrapResultStatus.SUCCESS,
        plan=bootstrap_plan,
        preflight_report=report,
        runtime_snapshot=snapshot,
        lifecycle_plan=lifecycle_plan,
    )
