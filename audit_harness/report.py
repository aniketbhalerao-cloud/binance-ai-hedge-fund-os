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

#: 38.8.0 (Task 38.8 Phase A.1, ADR-032 Option D): additive-only bump
#: adding the new ``implicit_dispatch`` section -- ``syntax_sites_total``,
#: ``dispatch_candidates_total``, ``resolved_dispatches``,
#: ``unresolved_dispatches``, ``resolved_non_descriptor_exclusion``,
#: ``explicit_path_duplicates`` (an annotation on already-counted sites,
#: never a fifth addend), ``dispatch_events_by_method`` (the
#: context-manager enter/exit/aenter/aexit and descriptor
#: get/set/delete breakdown, each counted independently), and the two
#: fields required regardless of architecture:
#: ``mechanized_protocol_families`` and ``unsupported_protocol_families``
#: (ADR-032's own exact 9-family list, verbatim). No existing field is
#: removed, renamed, or redefined -- ``nodes_unresolved``/
#: ``calls_unresolved`` remain explicit-call-only, exactly as `docs/prompts/
#: task-38.8.md` §8 requires. Per Task 38.8 §6's "nonzero keeps the gate
#: at HOLD" discipline, ``all_clear`` below additionally requires
#: ``unresolved_dispatches == 0``.
SCHEMA_VERSION = "38.8.0"


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
    implicit_dispatch: dict[str, Any],
) -> Report:
    """Assemble the full machine-readable result and compute
    ``exit_code`` per the Gate Rule: 0 only if every unresolved/
    unexplained count is zero, every runtime-denial category passed,
    and every negative control was detected on this same run.

    ``implicit_dispatch`` is Task 38.8 Phase A.1's own additive section
    (schema 38.8.0, §8) -- required, never defaulted, so a caller can
    never silently omit it and have this function assume a clean
    result on its behalf. Its own ``unresolved_dispatches`` is held to
    the identical "nonzero keeps the gate at HOLD" discipline as
    ``nodes_unresolved``/``calls_unresolved`` (§6)."""
    nodes_total = trace["nodes_total"]
    nodes_unresolved = trace["nodes_unresolved"]
    calls_total = trace["calls_total"]
    calls_unresolved = trace["calls_unresolved"]
    module_state_total = module_state["candidates_total"]
    module_state_unexplained = module_state["unexplained_total"]
    implicit_dispatch_unresolved = implicit_dispatch["unresolved_dispatches"]

    negative_controls_total = negative_controls["total"]
    negative_controls_detected = negative_controls["detected"]
    self_test_failed = negative_controls_detected != negative_controls_total

    runtime_denial_ok = bool(runtime_denial.get("success", False))

    all_clear = (
        nodes_unresolved == 0
        and calls_unresolved == 0
        and module_state_unexplained == 0
        and implicit_dispatch_unresolved == 0
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
        "calls_unresolved_detail_multiplicity": trace[
            "calls_unresolved_detail_multiplicity"
        ],
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
        "implicit_dispatch": implicit_dispatch,
        "self_test_failed": self_test_failed,
        "exit_code": exit_code,
    }
    return Report(data)
