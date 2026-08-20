"""Harness Requirement 8: stable machine-readable output.

Emits one JSON result per run with a documented, versioned schema.
Deterministic by construction: no wall-clock timestamp, random value,
or unordered-iteration artifact is ever written into the result -- two
runs against the same commit, with no other input change, produce
byte-identical output (Requirement 9's determinism test asserts this
directly). The narrative assurance report (a separate Markdown file)
is where a generation timestamp belongs, not this file.

"Zero unresolved" is only a valid, gate-relevant claim when every
negative control fired on the same run -- ``self_test_failed`` is a
distinct field precisely so a broken detector cannot report a clean
bill of health (Requirement 8's own wording).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

SCHEMA_VERSION = "38.6.0"


@dataclass(frozen=True, slots=True)
class Report:
    data: dict[str, Any]

    def canonical_json(self) -> str:
        return json.dumps(self.data, indent=2, sort_keys=True, ensure_ascii=True) + "\n"

    def result_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def build_report(
    *,
    commit_sha: str,
    discovery: dict[str, Any],
    trace: dict[str, Any],
    module_state: dict[str, Any],
    runtime_denial: dict[str, Any],
    negative_controls: dict[str, Any],
) -> Report:
    """Assemble the full machine-readable result and compute
    ``exit_code`` per the Gate Rule: 0 only if every unresolved/
    unexplained count is zero, every runtime-denial category passed,
    and every negative control was detected on this same run."""
    nodes_total = trace["nodes_total"]
    nodes_unresolved = trace["nodes_unresolved"]
    calls_total = trace["calls_total"]
    calls_unresolved = trace["calls_unresolved"]
    module_state_total = module_state["candidates_total"]
    module_state_unexplained = module_state["unexplained_total"]

    negative_controls_total = negative_controls["total"]
    negative_controls_detected = negative_controls["detected"]
    self_test_failed = negative_controls_detected != negative_controls_total

    runtime_denial_ok = bool(runtime_denial.get("success", False))

    all_clear = (
        nodes_unresolved == 0
        and calls_unresolved == 0
        and module_state_unexplained == 0
        and runtime_denial_ok
        and not self_test_failed
        and discovery.get("parse_errors_total", 0) == 0
        and module_state.get("parse_errors_total", 0) == 0
        and trace.get("roots_with_error_total", 0) == 0
    )
    exit_code = 0 if all_clear else 1

    data = {
        "schema_version": SCHEMA_VERSION,
        "commit_sha": commit_sha,
        "roots_traced": trace["roots_traced"],
        "roots_with_error": trace["roots_with_error"],
        "nodes_total": nodes_total,
        "nodes_unresolved": nodes_unresolved,
        "nodes_unresolved_detail": trace["nodes_unresolved_detail"],
        "calls_total": calls_total,
        "calls_unresolved": calls_unresolved,
        "calls_unresolved_detail": trace["calls_unresolved_detail"],
        "identity_resolution_buckets": trace["identity_resolution_buckets"],
        "exact_identity_policy_version": trace["exact_identity_policy_version"],
        "module_state_candidates_total": module_state_total,
        "module_state_unexplained": module_state_unexplained,
        "module_state_unexplained_detail": module_state["unexplained_detail"],
        "module_state_buckets": module_state["buckets"],
        "module_state_parse_errors": module_state.get("parse_errors", []),
        "discovery": discovery,
        "runtime_denial_checks": runtime_denial,
        "negative_controls_total": negative_controls_total,
        "negative_controls_detected": negative_controls_detected,
        "negative_controls_detail": negative_controls["detail"],
        "self_test_failed": self_test_failed,
        "exit_code": exit_code,
    }
    return Report(data)
