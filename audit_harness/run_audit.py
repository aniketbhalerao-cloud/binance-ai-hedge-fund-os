"""Harness orchestration entrypoint.

Item 5 of the Task 38.6 implementation instructions: run the harness's
own self-tests (the five Requirement-7 negative controls) *first*. If
any is missed, the run stops short of trusting its own "clean gate"
claim -- ``self_test_failed`` propagates into the machine-readable
result and forces ``exit_code`` nonzero, per Harness Requirement 8.

Usage: ``python -m audit_harness.run_audit`` from the repository root.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from collections import Counter
from pathlib import Path

from audit_harness import discovery, module_state, runtime_denial
from audit_harness.identity import EXACT_IDENTITY_POLICY_VERSION
from audit_harness.report import Report, build_report
from audit_harness.self_test import run_self_tests
from audit_harness.trace import run_trace

_MODULE_STATE_PACKAGES: tuple[str, ...] = (
    "agents",
    "backtesting",
    "dashboard",
    "execution",
    "learning",
    "market_data",
    "memory",
    "model_gateway",
    "monitoring",
    "notification",
    "optimization",
    "order_management",
    "paper_trading",
    "performance",
    "portfolio",
    "positions",
    "reporting",
    "risk",
    "scheduler",
    "storage",
    "strategies",
    "trades",
    "workers",
    "workflows",
    "app",
    "core",
    "trading",
    "exchange_adapters",
    "config",
    "events",
)


def _commit_sha(repo_root: Path) -> str:
    try:
        out = subprocess.run(  # noqa: S603, S607 - fixed args, read-only git metadata
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _load_classes(qualnames: list[str]) -> tuple[list[type], list[str]]:
    """Import every discovered node's class for the runtime-denial check.

    Returns ``(classes, unimportable)`` -- ``unimportable`` carries one
    fixed, generic entry per failure (``"<qualname>: import failed"``),
    never the raw exception text, a traceback, or a filesystem path. A
    class this audit's own static walk discovers failing to import is
    itself worth recording, not silently dropped (this was observed
    once, for ``builtins.mappingproxy``, before Task 38.7's
    ``module_and_qualname`` fix corrected that node's reported qualname
    to the real, importable ``types.MappingProxyType``).
    """
    classes: list[type] = []
    unimportable: list[str] = []
    for qn in sorted(qualnames):
        mod_name, _, cls_name = qn.rpartition(".")
        try:
            mod = importlib.import_module(mod_name)
            classes.append(getattr(mod, cls_name))
        except Exception:  # noqa: BLE001 - sanitized below; never propagate a raw exception
            unimportable.append(f"{qn}: import failed")
    return classes, unimportable


def run_full_audit(repo_root: Path) -> Report:
    """Run the complete Task 38.6 audit and return the deterministic
    machine-readable :class:`~audit_harness.report.Report`."""
    self_test_results = run_self_tests()
    negative_controls = {
        "total": len(self_test_results),
        "detected": sum(1 for r in self_test_results if r.detected),
        "detail": [
            f"{r.name}: {'detected' if r.detected else 'MISSED'} -- {r.detail}"
            for r in self_test_results
        ],
    }

    from app import wiring

    disc = discovery.run_discovery(repo_root, wiring.COMPONENT_REGISTRARS)
    discovery_dict = {
        "discovered_functions": list(disc.discovered_functions),
        "discovered_packages": list(disc.discovered_packages),
        "registered_component_ids": list(disc.registered_component_ids),
        "missing_from_component_registrars": list(
            disc.missing_from_component_registrars
        ),
        "parse_errors_total": 0,
    }

    tr = run_trace()
    unresolved_detail_counts = Counter(
        f"{c.site} :: {c.callee_text}"
        for c in tr.calls
        if c.verdict.category == "unresolved"
    )
    trace_dict = {
        "roots_traced": tr.roots_traced,
        "roots_with_error": [list(e) for e in tr.roots_with_error],
        "roots_with_error_total": len(tr.roots_with_error),
        "nodes_total": len(tr.nodes),
        "nodes_unresolved": tr.nodes_unresolved,
        "nodes_unresolved_detail": [n.qualname for n in tr.nodes if n.unresolved],
        "calls_total": len(tr.calls),
        "calls_unresolved": tr.calls_unresolved,
        "calls_unresolved_detail": sorted(unresolved_detail_counts),
        # Task 38.7 Requirement: the raw `calls_unresolved` count and the
        # deduplicated `calls_unresolved_detail` list differ by design --
        # several call sites are reached and recorded more than once by
        # the walker's fixed-point traversal. This field makes that
        # reconciliation a directly checkable invariant on the JSON
        # output itself: sum(calls_unresolved_detail_multiplicity.values())
        # == calls_unresolved, always.
        "calls_unresolved_detail_multiplicity": dict(
            sorted(unresolved_detail_counts.items())
        ),
        "identity_resolution_buckets": {
            "project_source_available": sum(
                1 for c in tr.calls if c.verdict.category == "project_source_available"
            ),
            "exact_identity_policy": sum(
                1 for c in tr.calls if c.verdict.category == "exact_identity_policy"
            ),
            "forbidden": sum(1 for c in tr.calls if c.verdict.category == "forbidden"),
            "unresolved": sum(
                1 for c in tr.calls if c.verdict.category == "unresolved"
            ),
        },
        "exact_identity_policy_version": EXACT_IDENTITY_POLICY_VERSION,
        "market_data_provider_runtime_type": tr.market_data_provider_runtime_type,
        "sites_without_source": list(tr.sites_without_source),
    }

    candidates, parse_errors = module_state.scan_scope(
        repo_root, _MODULE_STATE_PACKAGES
    )
    bucket_counts = Counter(c.classification for c in candidates)
    module_state_dict = {
        "candidates_total": len(candidates),
        "unexplained_total": bucket_counts.get("unexplained_shared_mutable_state", 0),
        "unexplained_detail": [
            f"{c.file}:{c.line} {c.kind} {c.detail}"
            for c in candidates
            if c.classification == "unexplained_shared_mutable_state"
        ],
        "buckets": dict(bucket_counts),
        "parse_errors": list(parse_errors),
        "parse_errors_total": len(parse_errors),
    }

    node_classes, unimportable_nodes = _load_classes([n.qualname for n in tr.nodes])
    denial = runtime_denial.run_paper_only_denial_check(node_classes)
    runtime_denial_dict = {
        "success": denial.success,
        "categories_patched": list(denial.categories_patched),
        "labels_patched": list(denial.labels_patched),
        "lifecycle_methods_patched": list(denial.lifecycle_methods_patched),
        "unimportable_nodes": unimportable_nodes,
        "db_clients_found": list(denial.db_clients_found),
        "redis_clients_found": list(denial.redis_clients_found),
        "exchange_adapter_connections_found": list(
            denial.exchange_adapter_connections_found
        ),
        "bootstrap_status": denial.bootstrap_status,
        "preflight_total": denial.preflight_total,
        "preflight_passed": denial.preflight_passed,
        "preflight_failed": denial.preflight_failed,
        "forbidden_call_observed": denial.forbidden_call_observed,
    }

    return build_report(
        commit_sha=_commit_sha(repo_root),
        discovery=discovery_dict,
        trace=trace_dict,
        module_state=module_state_dict,
        runtime_denial=runtime_denial_dict,
        negative_controls=negative_controls,
    )


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    report = run_full_audit(repo_root)
    print(report.canonical_json())  # noqa: T201 - the harness's own CLI output, not library logging
    return int(report.data["exit_code"])


if __name__ == "__main__":
    sys.exit(main())
