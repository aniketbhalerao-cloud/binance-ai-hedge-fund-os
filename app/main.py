"""Application entrypoint for Binance AI Hedge Fund OS.

A safe, preflight-only entrypoint. ``main()`` runs the dry-run composition
pipeline against a fresh disposable container and returns a success/failure
exit status. It never starts live mode, never starts a framework's engine,
never trades, never performs inference, never makes a real network/
database/Redis connection, never executes a workflow step, and never does
background work. ``config.settings.get_settings()`` is the only external
read anywhere in this run.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app import wiring
from app.bootstrap import run_dry_run_bootstrap
from app.models import BootstrapContext, BootstrapResultStatus
from config.settings import get_settings
from core.container import ServiceContainer

if TYPE_CHECKING:
    from collections.abc import Callable

    from core.interfaces import Container

__all__ = ["main"]

#: Fixed correlation id for the default preflight-only run.
_CORRELATION_ID = "app-bootstrap-dry-run"


def _utc_now() -> datetime:
    """Return the current time as a canonical-UTC ``datetime``.

    A module-level, named function rather than an inline lambda default,
    which Ruff flags as an ambiguous mutable/call-in-default-expression
    pattern. The one place in this task allowed to read a real wall clock —
    this function is the impure entrypoint boundary; everything ``main()``
    calls afterward is deterministic given the ``BootstrapContext`` built
    from its result.
    """
    return datetime.now(UTC)


def main(
    argv: list[str] | None = None,
    *,
    container_factory: Callable[[], Container] = ServiceContainer,
    clock: Callable[[], datetime] = _utc_now,
) -> int:
    """Run a dry-run bootstrap preflight and return a process exit status.

    Builds a ``BootstrapContext`` from ``wiring.build_default_manifest()``,
    a ``ConfigurationView`` built from ``config.settings.get_settings()``, a
    fixed correlation id, and ``requested_at=clock()``. Never starts live
    mode, a framework engine, trading, inference, or any network/DB/Redis/
    file/thread/process work.

    Args:
        argv: Unused — no CLI flags are defined; accepted for interface
            stability with ``pyproject.toml``'s console-script entry point.
        container_factory: Builds the fresh, disposable candidate container
            for this run. Defaults to
            :class:`~core.container.ServiceContainer`.
        clock: Returns the canonical-UTC ``requested_at`` timestamp.
            Defaults to :func:`_utc_now`.

    Returns:
        ``0`` if the dry run succeeded, ``1`` otherwise. A failure anywhere
        in this boundary — reading settings, building the redacted
        configuration view, constructing the context, or running the dry
        run itself — is caught here and reported only as exit code ``1``;
        no raw exception is ever printed or logged.
    """
    del argv
    try:
        settings = get_settings()
        context = BootstrapContext(
            manifest=wiring.build_default_manifest(),
            configuration=wiring.build_configuration_view(settings),
            correlation_id=_CORRELATION_ID,
            requested_at=clock(),
        )
        result = run_dry_run_bootstrap(context, container_factory=container_factory)
    except Exception:  # never print/log a raw exception; report failure only
        return 1
    return 0 if result.status is BootstrapResultStatus.SUCCESS else 1


if __name__ == "__main__":
    raise SystemExit(main())
