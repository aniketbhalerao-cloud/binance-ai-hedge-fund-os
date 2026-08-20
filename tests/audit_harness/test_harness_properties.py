"""Task 38.6 Harness Requirement 9: harness property tests (beyond the
negative-control tests in ``test_negative_controls.py``).
"""

from __future__ import annotations

from pathlib import Path

from audit_harness.discovery import run_discovery
from audit_harness.identity import classify_callable
from audit_harness.report import build_report

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_deterministic_repeated_runs_produce_identical_report() -> None:
    """Two runs of the full audit against the same commit, no other
    input change, must produce byte-identical machine-readable output
    (Harness Requirement 1 and 9)."""
    from audit_harness.run_audit import run_full_audit

    first = run_full_audit(repo_root=REPO_ROOT)
    second = run_full_audit(repo_root=REPO_ROOT)
    assert first.canonical_json() == second.canonical_json()
    assert first.result_hash() == second.result_hash()


def test_fresh_container_isolation_by_construction() -> None:
    """Every one of the 24 ``SAFE_SERVICE_KEYS`` roots gets its own
    fresh ``ServiceContainer`` instance, plus exactly one extra
    discovery-only container (Phase A integrity fix: reads every
    *registered*, not just every *resolved*, provider -- see
    ``trace.run_trace``'s own comment) -- exactly that many, never
    fewer (a container reused across roots) and never silently more
    (a stray extra construction). Strong references are kept for every
    container for the whole test so ``id()`` can never be reused by the
    garbage collector between constructions -- an ``id()``-only check
    without retained references would not actually prove distinctness.
    """
    from app import wiring
    from core.container import ServiceContainer

    created: list[ServiceContainer] = []  # strong refs: id() is never reused
    orig_init = ServiceContainer.__init__

    def spy_init(self: ServiceContainer, *a: object, **k: object) -> None:
        orig_init(self, *a, **k)
        created.append(self)

    ServiceContainer.__init__ = spy_init  # type: ignore[method-assign]
    try:
        from audit_harness.trace import run_trace

        run_trace()
    finally:
        ServiceContainer.__init__ = orig_init  # type: ignore[method-assign]

    # 24 roots + 1 discovery container
    expected_count = len(wiring.SAFE_SERVICE_KEYS) + 1
    assert len(created) == expected_count, (
        f"expected exactly {expected_count} ServiceContainer constructions "
        f"({len(wiring.SAFE_SERVICE_KEYS)} roots + 1 discovery container), "
        f"got {len(created)}"
    )
    ids = {id(c) for c in created}
    assert len(ids) == expected_count, (
        "duplicate id() despite retained strong references -- impossible "
        "unless a container object was literally reused"
    )

    # Explicitly prove singleton/cache state does not cross roots: no
    # two containers share the same _singletons dict object, and no
    # DIFFERENT container's cache holds the identical cached instance
    # for the same key. Aliasing *within* one container (e.g. resolving
    # the abstract `AgentRegistry` interface key returns the very
    # instance already cached under the concrete `InMemoryAgentRegistry`
    # key, deliberately, via `lambda r: r.resolve(InMemoryAgentRegistry)`)
    # is intentional DI aliasing, not a cross-root leak, and is
    # excluded from this check by only ever comparing across distinct
    # container indices.
    #
    # One instance is a *documented*, deliberate exception, not a bug:
    # `app.wiring._DRY_RUN_MARKET_DATA_PROVIDER` is a single,
    # process-wide, `__slots__ = ()` (genuinely stateless -- it cannot
    # hold *any* instance attribute) singleton every registrar binds
    # `market_data.interfaces.MarketDataProvider` to via
    # `functools.partial(register_market_data, provider=...)` -- this is
    # the exact object Task 38.5's own audit examined and confirmed
    # I/O-free and safe to share by construction. It is asserted below
    # to still be `__slots__ == ()`, not merely assumed exempt by name.
    singleton_dict_ids = {id(c._singletons) for c in created}  # type: ignore[attr-defined]
    assert (
        len(singleton_dict_ids) == expected_count
    ), "two containers share the same _singletons dict object"

    from app.wiring import _DryRunMarketDataProvider

    assert _DryRunMarketDataProvider.__slots__ == (), (
        "the one documented cross-container exception is only safe because it "
        "is genuinely stateless -- this must hold, not be assumed"
    )

    populated = [c for c in created if c._singletons]  # type: ignore[attr-defined]
    assert populated, (
        "expected at least one container to have resolved something into "
        "its own cache"
    )
    # instance id -> (container index, key)
    first_seen: dict[int, tuple[int, type]] = {}
    unexpected_cross_root_shares: list[str] = []
    for ci, c in enumerate(created):
        for key, instance in c._singletons.items():  # type: ignore[attr-defined]
            instance_id = id(instance)
            if instance_id in first_seen:
                other_ci, other_key = first_seen[instance_id]
                if other_ci == ci:
                    continue  # same-container aliasing -- expected, not a leak
                if isinstance(instance, _DryRunMarketDataProvider):
                    continue  # the one documented, verified-stateless exception
                unexpected_cross_root_shares.append(
                    f"container {ci}'s {key!r} shares an instance with "
                    f"container {other_ci}'s {other_key!r}"
                )
            else:
                first_seen[instance_id] = (ci, key)

    assert not unexpected_cross_root_shares, "\n".join(unexpected_cross_root_shares)


def test_discovery_completeness_generalizes_past_exchange_adapters(
    tmp_path: Path,
) -> None:
    """A fixture package exposing register_fixture_framework, added to a
    temporary directory tree, is found by the discovery step and
    correctly reported absent from a fixture COMPONENT_REGISTRARS-
    equivalent -- proving the mechanism generalizes past the one real
    exchange_adapters case."""
    fixture_pkg = tmp_path / "fixture_framework"
    fixture_pkg.mkdir()
    (fixture_pkg / "__init__.py").write_text(
        "def register_fixture_framework(container):\n    pass\n"
    )
    other_pkg = tmp_path / "already_wired"
    other_pkg.mkdir()
    (other_pkg / "__init__.py").write_text(
        "def register_already_wired(container):\n    pass\n"
    )

    result = run_discovery(tmp_path, component_registrars={"already_wired": None})
    assert "register_fixture_framework" in result.discovered_functions
    assert "fixture_framework" in result.missing_from_component_registrars
    assert "already_wired" not in result.missing_from_component_registrars


def test_false_negative_fixture_sets_self_test_failed() -> None:
    """If a negative control were NOT detected, self_test_failed would
    be True and exit_code nonzero -- proving the harness fails closed on
    its own detector breaking, not just on a real codebase problem."""
    report = build_report(
        commit_sha="deadbeef",
        discovery={"parse_errors_total": 0, "missing_from_component_registrars": []},
        trace={
            "roots_traced": 24,
            "roots_with_error": (),
            "roots_with_error_total": 0,
            "nodes_total": 1,
            "nodes_unresolved": 0,
            "nodes_unresolved_detail": [],
            "calls_total": 1,
            "calls_unresolved": 0,
            "calls_unresolved_detail": [],
            "identity_resolution_buckets": {},
            "exact_identity_policy_version": "test",
        },
        module_state={
            "candidates_total": 1,
            "unexplained_total": 0,
            "unexplained_detail": [],
            "buckets": {},
            "parse_errors": [],
            "parse_errors_total": 0,
        },
        runtime_denial={"success": True},
        negative_controls={
            "total": 5,
            "detected": 4,
            "detail": ["one deliberately missed for this test"],
        },
    )
    assert report.data["self_test_failed"] is True
    assert report.data["exit_code"] != 0

    # And the inverse: all detected -> self_test_failed False (still
    # subject to every other gate condition being clear, as here).
    clean = build_report(
        commit_sha="deadbeef",
        discovery={"parse_errors_total": 0, "missing_from_component_registrars": []},
        trace={
            "roots_traced": 24,
            "roots_with_error": (),
            "roots_with_error_total": 0,
            "nodes_total": 1,
            "nodes_unresolved": 0,
            "nodes_unresolved_detail": [],
            "calls_total": 1,
            "calls_unresolved": 0,
            "calls_unresolved_detail": [],
            "identity_resolution_buckets": {},
            "exact_identity_policy_version": "test",
        },
        module_state={
            "candidates_total": 1,
            "unexplained_total": 0,
            "unexplained_detail": [],
            "buckets": {},
            "parse_errors": [],
            "parse_errors_total": 0,
        },
        runtime_denial={"success": True},
        negative_controls={"total": 5, "detected": 5, "detail": []},
    )
    assert clean.data["self_test_failed"] is False
    assert clean.data["exit_code"] == 0


def _assert_repo_relative_and_sanitized(entries: list[str], tmp_path: Path) -> None:
    """Shared assertions across all three safe-failure tests: every
    recorded string is a repo-relative path (or a fixed generic label),
    never the tmp_path's own absolute prefix, never a Python exception
    class name/repr/traceback fragment."""
    absolute_prefix = str(tmp_path)
    for entry in entries:
        assert absolute_prefix not in entry, f"leaked absolute temp path in: {entry!r}"
        assert not entry.startswith("/"), f"leaked an absolute path in: {entry!r}"
        assert "Traceback" not in entry
        assert "line " not in entry  # a traceback frame reference
        for leaky_word in ("Error(", "Errno", "Exception(", ".py\", line"):
            assert leaky_word not in entry, f"leaked exception detail in: {entry!r}"


def test_safe_failure_sanitization_on_unreadable_source(tmp_path: Path) -> None:
    """A file that exists but cannot be *read* (permission denied) is
    recorded with a fixed, generic, repo-relative entry -- never a raw
    OSError/PermissionError message, never the tmp_path's own absolute
    prefix."""
    import os

    from audit_harness.module_state import scan_scope

    pkg = tmp_path / "unreadable_pkg"
    pkg.mkdir()
    bad_file = pkg / "unreadable.py"
    bad_file.write_text("x = 1\n")
    os.chmod(bad_file, 0o000)
    try:
        candidates, parse_errors = scan_scope(tmp_path, ("unreadable_pkg",))
    finally:
        os.chmod(bad_file, 0o644)  # restore so pytest's own cleanup can remove it

    assert "unreadable_pkg/unreadable.py" in parse_errors
    assert candidates == ()
    _assert_repo_relative_and_sanitized(list(parse_errors), tmp_path)


def test_safe_failure_sanitization_on_unparseable_source(tmp_path: Path) -> None:
    """A file with invalid Python syntax is recorded the same
    sanitized, repo-relative way -- distinct scenario from an unreadable
    file (this one *is* readable; ``ast.parse`` is what fails), same
    safety contract."""
    from audit_harness.module_state import scan_scope

    pkg = tmp_path / "unparseable_pkg"
    pkg.mkdir()
    bad_file = pkg / "broken.py"
    bad_file.write_text("def f(:\n    pass\n")  # a genuine SyntaxError
    candidates, parse_errors = scan_scope(tmp_path, ("unparseable_pkg",))
    assert "unparseable_pkg/broken.py" in parse_errors
    assert candidates == ()
    _assert_repo_relative_and_sanitized(list(parse_errors), tmp_path)


def test_safe_failure_sanitization_on_unimportable_module(tmp_path: Path) -> None:
    """A module whose source is valid Python and fully readable, but
    that raises on *import* (a third scenario, distinct from unreadable
    and unparseable) is recorded as one fixed, generic entry per
    qualname -- never the raw ImportError/AttributeError text."""
    import sys

    from audit_harness.run_audit import _load_classes

    pkg_name = "audit_harness_test_fixture_unimportable_pkg"
    pkg_dir = tmp_path / pkg_name
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("raise ImportError('deliberately broken')\n")
    sys.path.insert(0, str(tmp_path))
    try:
        classes, unimportable = _load_classes([f"{pkg_name}.SomeClass"])
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop(pkg_name, None)

    assert classes == []
    assert unimportable == [f"{pkg_name}.SomeClass: import failed"]
    _assert_repo_relative_and_sanitized(unimportable, tmp_path)


def test_classify_callable_never_raises_on_arbitrary_input() -> None:
    """classify_callable must not raise for any object -- a broken
    identity lookup must degrade to 'unresolved', never propagate an
    exception into the audit run."""
    for weird in (None, object(), 42, "a string", lambda: None, type):
        verdict = classify_callable(weird, module=None, qualname=None)
        assert verdict.category in (
            "unresolved",
            "forbidden",
            "exact_identity_policy",
            "project_source_available",
        )
