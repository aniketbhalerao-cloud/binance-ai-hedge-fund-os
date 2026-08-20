"""Harness Requirement 2: ``register_*`` package discovery vs.
``COMPONENT_REGISTRARS``.

Independently re-derives, from a directory-wide scan for
``^def register_`` in every top-level package's ``__init__.py``, the
complete set of packages exposing a ``register_<framework>`` function --
the same check Task 38.5 Area 1 and finding H-2 performed by hand -- and
diffs it against ``app.wiring.COMPONENT_REGISTRARS``.

Diagnostic evidence only. This module never mutates
``COMPONENT_REGISTRARS`` and never fixes H-2 -- see
``docs/prompts/task-38.6.md`` Non-Goals.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

_REGISTER_DEF = re.compile(r"^def (register_\w+)\(", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    """Every field is sorted so the result is deterministic (Requirement 1)."""

    discovered_functions: tuple[str, ...]
    discovered_packages: tuple[str, ...]
    registered_component_ids: tuple[str, ...]
    missing_from_component_registrars: tuple[str, ...]


def discover_register_functions(repo_root: Path) -> tuple[str, ...]:
    """Scan every top-level package's ``__init__.py`` for ``def register_*``.

    Skips hidden/dunder directories and anything without an
    ``__init__.py`` (not a package). A file that cannot be read is
    skipped, never raising -- a missing/unreadable package directory is
    not itself a finding this discovery step makes.
    """
    found: list[str] = []
    for entry in sorted(repo_root.iterdir()):
        if not entry.is_dir() or entry.name.startswith((".", "_")):
            continue
        init_file = entry / "__init__.py"
        if not init_file.is_file():
            continue
        try:
            source = init_file.read_text(encoding="utf-8")
        except OSError:
            continue
        found.extend(match.group(1) for match in _REGISTER_DEF.finditer(source))
    return tuple(sorted(set(found)))


def run_discovery(
    repo_root: Path, component_registrars: Mapping[str, object]
) -> DiscoveryResult:
    """Diff discovered ``register_*`` packages against ``component_registrars``.

    ``component_registrars`` is the caller-supplied mapping to diff
    against (``app.wiring.COMPONENT_REGISTRARS`` for a real run; a
    fixture mapping for the discovery-completeness test).
    """
    discovered = discover_register_functions(repo_root)
    packages = tuple(sorted({name.removeprefix("register_") for name in discovered}))
    registered = tuple(sorted(component_registrars))
    missing = tuple(sorted(set(packages) - set(registered)))
    return DiscoveryResult(
        discovered_functions=discovered,
        discovered_packages=packages,
        registered_component_ids=registered,
        missing_from_component_registrars=missing,
    )
