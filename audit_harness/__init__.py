"""Task 38.6 audit-assurance harness.

Source-controlled, deterministic, reusable replacement for the one-off
``/tmp`` scripts Task 38.5's v1-v5 passes each wrote and discarded (see
``docs/prompts/task-38.6.md``). This package is infrastructure, never a
framework: it is not one of the 24 packages exposing a
``register_<framework>`` function, is never added to
``app.wiring.COMPONENT_REGISTRARS``, and is never imported by
``app/`` or any production framework. It analyzes the codebase from
outside the composition root's own import graph, the same way a linter
or a test suite does.

Every check this package performs is static analysis or a disposable,
paper-only runtime check against ``app.bootstrap.run_dry_run_bootstrap``.
No module in this package ever opens a real network, database, Redis,
or exchange connection, reads a real credential, submits an order, or
calls a model.
"""

from __future__ import annotations

__all__: list[str] = []
