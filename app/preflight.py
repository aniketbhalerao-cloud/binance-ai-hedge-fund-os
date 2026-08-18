"""Composition-root preflight checks.

Exposes two functions, deliberately run at two different points of the
dry-run pipeline (see ``docs/prompts/task-38.md`` "Disposable Candidate
Container"): :func:`validate_service_keys` is a static check with no
container in scope, run *before* any candidate exists; only :func:`run`
ever touches the one candidate a bootstrap run obtained.

Neither function calls a business method (``.start()``, ``.invoke()``,
``.schedule()``, ``.enqueue()``, ``.compose()``) on anything, performs a
real network/DB/Redis call, or mutates another framework's state. Together
they only prove the object graph *would* wire.
"""

from __future__ import annotations

from collections.abc import Callable

from app import wiring
from app.exceptions import PreflightError
from app.models import BootstrapPlan, PreflightEntry, PreflightReport

__all__ = ["ServiceResolver", "validate_service_keys", "run"]

#: A minimal, read-only capability — resolve one type from the disposable
#: candidate container. Deliberately narrower than the full ``Container``
#: contract (which also grants registration): the public API of this task
#: accepts no container instance anywhere, only this restricted callable.
ServiceResolver = Callable[[type], object]


def validate_service_keys(plan: BootstrapPlan) -> None:
    """Statically validate every declared ``required_service_keys`` entry in
    ``plan`` against :data:`app.wiring.SAFE_SERVICE_KEYS`.

    Runs before any candidate container exists. Validates only the service
    keys a component actually declares — never invents a check for a key
    nobody declared, and never skips a declared key.

    Raises:
        PreflightError: If any declared key is not present in
            :data:`app.wiring.SAFE_SERVICE_KEYS`.
    """
    try:
        for entry in plan.entries:
            for key in entry.required_service_keys:
                if key not in wiring.SAFE_SERVICE_KEYS:
                    raise PreflightError(
                        "component manifest declares a service key that is "
                        "not present in the safe service-key allowlist"
                    )
    except PreflightError:
        raise
    except Exception as exc:  # translate; never echo internals or input values
        raise PreflightError("service key validation failed") from exc


def run(plan: BootstrapPlan, resolve: ServiceResolver) -> PreflightReport:
    """Run the actual resolution pass via ``resolve``.

    By the time this is called, every key on every component has already
    passed :func:`validate_service_keys`, so nothing is rejected here for
    being unknown — only resolution itself can still fail. For each
    component in plan order and each of its already-validated keys, resolve
    the mapped type via ``resolve`` (the disposable candidate container's
    ordinary constructor-injection path — the same mechanism
    ``register_class`` already uses everywhere) and record success; a
    resolution failure (missing registration, construction error) is
    recorded as a failed :class:`~app.models.PreflightEntry` with a safe,
    generic detail message — never a raw exception, stack trace, or any
    value drawn from ``Settings``.

    Args:
        plan: The resolved bootstrap plan.
        resolve: A narrow, read-only capability — resolves one type from
            the disposable candidate container. Never the container itself.

    Returns:
        The immutable :class:`~app.models.PreflightReport` for this run.
    """
    entries: list[PreflightEntry] = []
    for plan_entry in plan.entries:
        for key in plan_entry.required_service_keys:
            service_type = wiring.SAFE_SERVICE_KEYS[key]
            try:
                resolve(service_type)
            except Exception:  # recorded as a failed entry, never re-raised
                entries.append(
                    PreflightEntry(
                        component_id=plan_entry.component_id,
                        service_key=key,
                        resolved=False,
                        detail="service resolution failed",
                    )
                )
            else:
                entries.append(
                    PreflightEntry(
                        component_id=plan_entry.component_id,
                        service_key=key,
                        resolved=True,
                        detail="service resolved successfully",
                    )
                )
    return PreflightReport(entries=tuple(entries))
