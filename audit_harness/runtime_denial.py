"""Harness Requirement 6: runtime denial checks, paper-only.

Builds ``Settings``/``BootstrapContext`` normally first (the permitted
configuration/clock reads happen before any patching), then patches
every named forbidden-operation surface to raise, then runs the real
``app.bootstrap.run_dry_run_bootstrap`` and confirms it still succeeds
25/25 with every patch active.

No module in this file ever completes a real network, database, Redis,
or exchange connection, at any point, including during its own
self-test. ``ForbiddenOperationError`` is raised in place of the real
operation; nothing downstream of a patched target ever executes.
"""

from __future__ import annotations

import builtins
import inspect
import multiprocessing
import os
import pathlib
import socket
import subprocess
import threading
import time
from collections.abc import Callable, Iterable
from contextlib import contextmanager
from dataclasses import dataclass


class ForbiddenOperationError(RuntimeError):
    """Raised by a patched target instead of performing the real operation."""


@dataclass
class _Patch:
    category: str
    label: str
    obj: object
    attr: str
    original: object


def _boom(label: str) -> Callable[..., object]:
    def _raise(*_args: object, **_kwargs: object) -> object:
        raise ForbiddenOperationError(f"forbidden operation attempted: {label}")

    return _raise


#: (category, label, obj, attr) for every fixed (non-lifecycle,
#: non-DB/Redis/exchange) target Harness Requirement 6 names.
_FIXED_TARGETS: tuple[tuple[str, str, object, str], ...] = (
    ("file_io", "builtins.open", builtins, "open"),
    ("file_io", "pathlib.Path.open", pathlib.Path, "open"),
    ("file_io", "pathlib.Path.read_text", pathlib.Path, "read_text"),
    ("file_io", "pathlib.Path.write_text", pathlib.Path, "write_text"),
    ("file_io", "pathlib.Path.read_bytes", pathlib.Path, "read_bytes"),
    ("file_io", "pathlib.Path.write_bytes", pathlib.Path, "write_bytes"),
    ("os_low_level", "os.makedirs", os, "makedirs"),
    ("os_low_level", "os.remove", os, "remove"),
    ("os_low_level", "os.system", os, "system"),
    ("os_low_level", "os.open", os, "open"),
    ("os_low_level", "os.fdopen", os, "fdopen"),
    ("os_low_level", "os.read", os, "read"),
    ("os_low_level", "os.write", os, "write"),
    ("network", "socket.socket", socket, "socket"),
    ("network", "socket.create_connection", socket, "create_connection"),
    ("subprocess", "subprocess.Popen", subprocess, "Popen"),
    ("subprocess", "subprocess.run", subprocess, "run"),
    ("threads_processes", "threading.Thread.start", threading.Thread, "start"),
    (
        "threads_processes",
        "multiprocessing.Process.start",
        multiprocessing.Process,
        "start",
    ),
    ("sleeps", "time.sleep", time, "sleep"),
)


def _logging_targets() -> tuple[tuple[str, str, object, str], ...]:
    import asyncio
    import logging
    import logging.handlers

    return (
        ("sleeps", "asyncio.sleep", asyncio, "sleep"),
        ("logging_handlers", "logging.StreamHandler", logging, "StreamHandler"),
        (
            "logging_handlers",
            "logging.handlers.RotatingFileHandler",
            logging.handlers,
            "RotatingFileHandler",
        ),
    )


@dataclass(frozen=True, slots=True)
class LifecycleMethodTarget:
    qualname: str
    cls: type
    attr: str


LIFECYCLE_METHOD_NAMES: tuple[str, ...] = (
    "start",
    "invoke",
    "compose",
    "schedule",
    "enqueue",
    "submit_order",
    "place_order",
    "execute_trade",
    "predict",
    "infer",
)


def discover_lifecycle_targets(
    classes: Iterable[type],
) -> tuple[LifecycleMethodTarget, ...]:
    """Every ``LIFECYCLE_METHOD_NAMES`` method a class defines on itself
    (not inherited) -- enumerated from the unified node collection, not
    hand-listed.

    Two structural requirements, no package/class-name/semantic
    allowlist: the name must be owned by the class itself (``name in
    cls.__dict__``, not inherited), and the resolved attribute must
    actually be callable (``callable(getattr(cls, name))``). The second
    check is what excludes a non-method data descriptor that happens to
    share a lifecycle name -- e.g. ``range.start`` is a plain
    ``member_descriptor`` (the read-only ``start`` field of a ``range``
    instance), not a method, and setting it (to patch it) fails at the
    C level -- while still keeping any genuine method, own-package or
    third-party alike (e.g. a real ``@classmethod start()`` on a
    third-party class)."""
    out: list[LifecycleMethodTarget] = []
    for cls in classes:
        if not isinstance(cls, type):
            continue
        for name in LIFECYCLE_METHOD_NAMES:
            if name in cls.__dict__ and callable(getattr(cls, name)):
                out.append(
                    LifecycleMethodTarget(
                        f"{cls.__module__}.{cls.__qualname__}.{name}", cls, name
                    )
                )
    return tuple(sorted(out, key=lambda t: t.qualname))


@dataclass(frozen=True, slots=True)
class RuntimeDenialResult:
    categories_patched: tuple[str, ...]
    labels_patched: tuple[str, ...]
    lifecycle_methods_patched: tuple[str, ...]
    db_clients_found: tuple[str, ...]
    redis_clients_found: tuple[str, ...]
    exchange_adapter_connections_found: tuple[str, ...]
    bootstrap_status: str
    preflight_total: int
    preflight_passed: int
    preflight_failed: int
    forbidden_call_observed: str | None
    """Non-None means a patched target actually fired during the real
    run -- the audit itself found a reachable forbidden call. This is
    the finding, not a harness bug."""

    @property
    def success(self) -> bool:
        """The expected whole-system composition count is a deliberate,
        hand-set baseline -- never derived from ``COMPONENT_REGISTRARS``,
        ``KNOWN_COMPONENT_IDS``, manifest length, or this result's own
        observed counts. The point is to fail loudly if the expected count
        drifts unexpectedly; a real, reviewed change to the wired framework
        count must update this literal deliberately, in the same change.

        24 -> 25: Task 38.9A (H-2 remediation) intentionally wires
        ``exchange_adapters`` into the dry-run composition root.
        """
        return (
            self.bootstrap_status == "SUCCESS"
            and self.preflight_total == 25
            and self.preflight_passed == 25
            and self.preflight_failed == 0
            and self.forbidden_call_observed is None
        )


_STATIC_MISSING = object()


def _save_original(obj: object, attr: str) -> object:
    """The exact object to restore ``obj.attr`` to when this patch is
    undone -- never the *bound* result plain ``getattr`` would produce
    for a classmethod/staticmethod/descriptor found on a class. Plain
    ``getattr(cls, name)`` on a ``@classmethod`` returns a fresh bound
    method each time; saving *that* and later ``setattr``-ing it back
    permanently replaces the class's own ``classmethod`` descriptor
    with a plain bound-method object -- a real, observed corruption
    (`dotenv.parser.Position.start`, a third-party ``@classmethod``
    matching ``LIFECYCLE_METHOD_NAMES``) that silently changes what a
    *later*, unrelated static analysis pass sees on the very same class
    object for the rest of the process, breaking Harness Requirement 1's
    byte-identical-repeated-runs guarantee. ``inspect.getattr_static``
    reads the *stored* attribute value directly (never invoking a
    descriptor's own ``__get__``), so it preserves the original
    classmethod/staticmethod/descriptor object exactly; it falls back to
    plain ``getattr`` only for objects it cannot introspect this way
    (e.g. some C-implemented modules)."""
    static = inspect.getattr_static(obj, attr, _STATIC_MISSING)
    return static if static is not _STATIC_MISSING else getattr(obj, attr)


@contextmanager
def _apply_patches(extra_targets: Iterable[tuple[str, str, object, str]] = ()):  # type: ignore[no-untyped-def]
    applied: list[_Patch] = []
    try:
        for category, label, obj, attr in (
            *_FIXED_TARGETS,
            *_logging_targets(),
            *extra_targets,
        ):
            original = _save_original(obj, attr)
            setattr(obj, attr, _boom(label))
            applied.append(_Patch(category, label, obj, attr, original))
        yield applied
    finally:
        for p in reversed(applied):
            setattr(p.obj, p.attr, p.original)


def find_db_redis_exchange_clients(
    module_names: Iterable[str],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Requirement 6: 'if no such client is constructible from any
    reachable path, the harness must say so explicitly.' Scans the
    already-imported module set (not a live network probe) for a
    recognizable DB/Redis client import, and separately for a reachable
    exchange_adapters connection method. Empty tuples are a valid,
    positive result -- reported, never silently omitted."""
    import sys

    db_hits: set[str] = set()
    redis_hits: set[str] = set()
    exchange_hits: set[str] = set()
    db_markers = ("psycopg", "sqlite3", "sqlalchemy", "asyncpg", "pymongo")
    for name in module_names:
        mod = sys.modules.get(name)
        if mod is None:
            continue
        source_file = getattr(mod, "__file__", "") or ""
        if any(marker in source_file for marker in db_markers):
            db_hits.add(name)
        if "redis" in source_file:
            redis_hits.add(name)
    try:
        import exchange_adapters

        if hasattr(exchange_adapters, "register_exchange_adapters"):
            # exchange_adapters exists but is outside SAFE_SERVICE_KEYS /
            # COMPONENT_REGISTRARS (H-2) -- not reachable from the traced
            # 24-root graph. Recorded as a named package, not as a
            # "reachable" connection target; see the assurance report.
            exchange_hits.add(
                "exchange_adapters (present, not wired into "
                "COMPONENT_REGISTRARS -- see H-2)"
            )
    except ImportError:
        pass
    return (
        tuple(sorted(db_hits)),
        tuple(sorted(redis_hits)),
        tuple(sorted(exchange_hits)),
    )


def run_paper_only_denial_check(
    lifecycle_classes: Iterable[type],
) -> RuntimeDenialResult:
    """Build settings/context normally, patch the full forbidden-operation
    surface, then run the real ``run_dry_run_bootstrap``. Never touches
    a real network, DB, Redis, or exchange connection."""
    import sys
    from datetime import UTC, datetime

    from app import wiring
    from app.bootstrap import run_dry_run_bootstrap
    from app.models import BootstrapContext
    from config.settings import get_settings
    from core.container import ServiceContainer

    # Permitted impure reads happen before any patch is active.
    settings = get_settings()
    context = BootstrapContext(
        manifest=wiring.build_default_manifest(),
        configuration=wiring.build_configuration_view(settings),
        correlation_id="audit-harness-paper-only-denial-check",
        requested_at=datetime.now(UTC),
    )

    lifecycle_targets = discover_lifecycle_targets(lifecycle_classes)
    expected_qualnames = frozenset(t.qualname for t in lifecycle_targets)
    lifecycle_extra = tuple(
        ("lifecycle_methods", t.qualname, t.cls, t.attr) for t in lifecycle_targets
    )
    db_found, redis_found, exchange_found = find_db_redis_exchange_clients(
        list(sys.modules)
    )

    forbidden_observed: str | None = None
    with _apply_patches(lifecycle_extra) as applied:
        # Assert the patched set equals the independently-derived
        # discovery set exactly, before running anything -- a mismatch
        # here means the patch loop and the discovery function have
        # silently diverged (e.g. a dedup bug), which is a harness
        # defect that must fail loudly, not produce an under- or
        # over-patched runtime-denial run.
        patched_lifecycle_qualnames = frozenset(
            p.label for p in applied if p.category == "lifecycle_methods"
        )
        if patched_lifecycle_qualnames != expected_qualnames:
            missing = expected_qualnames - patched_lifecycle_qualnames
            extra = patched_lifecycle_qualnames - expected_qualnames
            raise AssertionError(
                "lifecycle denial patch set does not match the independently "
                f"discovered set: missing={sorted(missing)} extra={sorted(extra)}"
            )
        try:
            result = run_dry_run_bootstrap(context, container_factory=ServiceContainer)
        except ForbiddenOperationError as exc:
            forbidden_observed = str(exc)
            result = None

    categories = tuple(sorted({p.category for p in applied}))
    labels = tuple(sorted({p.label for p in applied}))

    if result is None:
        return RuntimeDenialResult(
            categories_patched=categories,
            labels_patched=labels,
            lifecycle_methods_patched=tuple(t.qualname for t in lifecycle_targets),
            db_clients_found=db_found,
            redis_clients_found=redis_found,
            exchange_adapter_connections_found=exchange_found,
            bootstrap_status="ERROR",
            preflight_total=0,
            preflight_passed=0,
            preflight_failed=0,
            forbidden_call_observed=forbidden_observed,
        )

    report = result.preflight_report
    total = len(report.entries) if report is not None else 0
    passed = sum(1 for e in report.entries if e.resolved) if report is not None else 0
    failed = total - passed

    return RuntimeDenialResult(
        categories_patched=categories,
        labels_patched=labels,
        lifecycle_methods_patched=tuple(t.qualname for t in lifecycle_targets),
        db_clients_found=db_found,
        redis_clients_found=redis_found,
        exchange_adapter_connections_found=exchange_found,
        bootstrap_status=result.status.name,
        preflight_total=total,
        preflight_passed=passed,
        preflight_failed=failed,
        forbidden_call_observed=forbidden_observed,
    )
