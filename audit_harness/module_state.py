"""Harness Requirement 5: module-state detection, specified-pattern
coverage.

Detects, per module in the audited scope:

* a module-level variable rebound via ``global`` inside a function;
* a module-level variable rebound via ``nonlocal`` from a nested scope;
* a module-global object mutated from inside an ordinary (non-nested)
  function via a method call or an augmented assignment -- the shape
  M-7 gap 3 named as undetected by every prior pass's closure-only scan;
* a module-global object mutated via attribute or subscript assignment,
  from any scope;
* the v4/v5 categories carried forward: module-level ``Call``
  assignments, comprehensions, ``@cache``/``@lru_cache`` functions,
  class-level mutable defaults, closure-captured mutables.

This list is a specified contract, not a claim every conceivable
mutation shape in Python has been enumerated -- see
``docs/prompts/task-38.6.md`` Harness Requirement 5.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

_MUTATING_METHODS = frozenset(
    {
        "update",
        "append",
        "add",
        "pop",
        "extend",
        "remove",
        "insert",
        "setdefault",
        "discard",
        "clear",
    }
)

Classification = Literal[
    "immutable_constant",
    "intentional_documented_shared_instance",
    "mutable_never_mutated_lookup",
    "unexplained_shared_mutable_state",
]


_IMMUTABLE_CONSTRUCTORS = frozenset(
    {"Decimal", "frozenset", "TypeVar", "MappingProxyType"}
)


@dataclass(frozen=True, slots=True)
class Candidate:
    file: str
    line: int
    kind: str
    detail: str
    classification: Classification
    subject: str | None = None
    """The bare name this candidate tracks, for the cross-scope
    never-mutated check in :func:`_finalize_classifications`. ``None``
    when a candidate's safety doesn't depend on tracking a name (e.g. a
    comprehension or a class-level default, already conservatively
    classified at the point of detection)."""


def _module_level_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _locally_bound_names(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[set[str], set[str], set[str]]:
    """Return (locally_bound, globals_declared, nonlocals_declared) for
    ``func``'s own direct body -- not descending into nested defs."""
    locally_bound = {a.arg for a in func.args.args}
    locally_bound.update(a.arg for a in func.args.posonlyargs)
    locally_bound.update(a.arg for a in func.args.kwonlyargs)
    if func.args.vararg:
        locally_bound.add(func.args.vararg.arg)
    if func.args.kwarg:
        locally_bound.add(func.args.kwarg.arg)
    globals_declared: set[str] = set()
    nonlocals_declared: set[str] = set()
    for node in ast.walk(func):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
            and node is not func
        ):
            continue
        if isinstance(node, ast.Global):
            globals_declared.update(node.names)
        elif isinstance(node, ast.Nonlocal):
            nonlocals_declared.update(node.names)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    locally_bound.add(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            locally_bound.add(node.target.id)
    locally_bound -= globals_declared
    locally_bound -= nonlocals_declared
    return locally_bound, globals_declared, nonlocals_declared


def _direct_body_calls_and_assigns(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.AST]:
    """Every Call/Assign/AugAssign in ``func``'s own body, not descending
    into a nested function/lambda's own body (those are scanned when
    that nested function is itself visited)."""
    out: list[ast.AST] = []

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
            if node is func:
                self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
            if node is func:
                self.generic_visit(node)

        def visit_Lambda(self, node: ast.Lambda) -> None:  # noqa: N802
            return  # never descend into a lambda's own body here

        def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
            out.append(node)
            self.generic_visit(node)

        def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
            out.append(node)
            self.generic_visit(node)

        def visit_AugAssign(self, node: ast.AugAssign) -> None:  # noqa: N802
            out.append(node)
            self.generic_visit(node)

    Visitor().visit(func)
    return out


def scan_module(rel_path: str, source: str) -> tuple[Candidate, ...] | None:
    """Scan one module's source. Returns ``None`` on a parse error
    (caller records it separately -- never silently dropped)."""
    try:
        tree = ast.parse(source, filename=rel_path)
    except SyntaxError:
        return None

    candidates: list[Candidate] = []
    module_names = _module_level_names(tree)

    # -- module-level Call assignments, comprehensions ---------------
    for node in tree.body:
        target_names: list[str] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            target_names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            value = node.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.value is not None
        ):
            target_names = [node.target.id]
            value = node.value
        if not target_names or value is None:
            continue
        if isinstance(value, ast.Call):
            call_text = ast.unparse(value.func)
            provisional: Classification = (
                "immutable_constant"
                if call_text in _IMMUTABLE_CONSTRUCTORS
                else "mutable_never_mutated_lookup"
            )
            candidates.append(
                Candidate(
                    rel_path,
                    node.lineno,
                    "module_level_call_assignment",
                    f"{'/'.join(target_names)} = {call_text}(...)",
                    provisional,
                    subject=target_names[0]
                    if call_text not in _IMMUTABLE_CONSTRUCTORS
                    else None,
                )
            )
        elif isinstance(
            value, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)
        ):
            candidates.append(
                Candidate(
                    rel_path,
                    node.lineno,
                    "module_level_comprehension",
                    f"{'/'.join(target_names)} = <{type(value).__name__}>",
                    "unexplained_shared_mutable_state",
                )
            )
        elif isinstance(value, (ast.Dict, ast.List, ast.Set)):
            # A bare mutable-literal module global (e.g. `__all__ = [...]`,
            # `VALID_TRANSITIONS = {...}`) -- the v3-v5 category, carried
            # forward. `__all__` itself is the standard export-list
            # convention (confirmed never mutated by the cross-scope check
            # below, same as every other candidate with a `subject`).
            candidates.append(
                Candidate(
                    rel_path,
                    node.lineno,
                    "module_level_mutable_literal",
                    f"{'/'.join(target_names)} = <{type(value).__name__} literal>",
                    "mutable_never_mutated_lookup",
                    subject=target_names[0],
                )
            )
        elif isinstance(value, ast.Constant):
            pass  # scalars/None: the global/nonlocal-rebind scan below covers these

    # -- @cache / @lru_cache decorated functions ----------------------
    for walk_node in ast.walk(tree):
        if isinstance(walk_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in walk_node.decorator_list:
                dec_name = None
                if isinstance(dec, ast.Name):
                    dec_name = dec.id
                elif isinstance(dec, ast.Attribute):
                    dec_name = dec.attr
                elif isinstance(dec, ast.Call):
                    f = dec.func
                    dec_name = (
                        f.id if isinstance(f, ast.Name) else getattr(f, "attr", None)
                    )
                if dec_name in ("cache", "lru_cache"):
                    candidates.append(
                        Candidate(
                            rel_path,
                            walk_node.lineno,
                            "cache_decorated_function",
                            walk_node.name,
                            "intentional_documented_shared_instance",
                        )
                    )

    # -- class-level mutable defaults ----------------------------------
    for class_node in ast.walk(tree):
        if isinstance(class_node, ast.ClassDef):
            for item in class_node.body:
                target = None
                value2: ast.expr | None = None
                if (
                    isinstance(item, ast.Assign)
                    and len(item.targets) == 1
                    and isinstance(item.targets[0], ast.Name)
                ):
                    target, value2 = item.targets[0].id, item.value
                elif (
                    isinstance(item, ast.AnnAssign)
                    and isinstance(item.target, ast.Name)
                    and item.value is not None
                ):
                    target, value2 = item.target.id, item.value
                if target is None:
                    continue
                if isinstance(
                    value2,
                    (
                        ast.List,
                        ast.Dict,
                        ast.Set,
                        ast.ListComp,
                        ast.DictComp,
                        ast.SetComp,
                    ),
                ):
                    candidates.append(
                        Candidate(
                            rel_path,
                            item.lineno,
                            "class_level_mutable_default",
                            f"{class_node.name}.{target}",
                            "unexplained_shared_mutable_state",
                        )
                    )
                elif (
                    isinstance(value2, ast.Call)
                    and isinstance(value2.func, ast.Name)
                    and value2.func.id in ("dict", "list", "set")
                ):
                    candidates.append(
                        Candidate(
                            rel_path,
                            item.lineno,
                            "class_level_mutable_default",
                            f"{class_node.name}.{target} = {value2.func.id}()",
                            "unexplained_shared_mutable_state",
                        )
                    )

    # -- module-level None/scalar variables, checked for rebinding -----
    scalar_candidates: dict[str, tuple[int, str]] = {}
    for node in tree.body:
        target = None
        value3: ast.expr | None = None
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            target, value3 = node.targets[0].id, node.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.value is not None
        ):
            target, value3 = node.target.id, node.value
        if target is None or target.startswith("__"):
            continue
        if isinstance(value3, ast.Constant):
            scalar_candidates[target] = (node.lineno, ast.unparse(value3))

    rebound_via_global: set[str] = set()

    # -- per-function scans: global-rebind, nonlocal-rebind, plain-
    #    function module-global mutation via method-call/subscript/
    #    attribute/augmented-assignment.
    enclosing_function_locals: dict[
        int, set[str]
    ] = {}  # id(FunctionDef) -> its own locally_bound
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        locally_bound, globals_declared, nonlocals_declared = _locally_bound_names(func)
        enclosing_function_locals[id(func)] = locally_bound

        for stmt in _direct_body_calls_and_assigns(func):
            if isinstance(stmt, ast.Assign):
                for t in stmt.targets:
                    if (
                        isinstance(t, ast.Name)
                        and t.id in globals_declared
                        and t.id in scalar_candidates
                    ):
                        rebound_via_global.add(t.id)
                        candidates.append(
                            Candidate(
                                rel_path,
                                stmt.lineno,
                                "global_rebind",
                                f"global {t.id}; {t.id} = ... (in {func.name})",
                                "intentional_documented_shared_instance",
                                subject=t.id,
                            )
                        )
                    if isinstance(t, ast.Name) and t.id in nonlocals_declared:
                        candidates.append(
                            Candidate(
                                rel_path,
                                stmt.lineno,
                                "nonlocal_rebind",
                                f"nonlocal {t.id}; {t.id} = ... (in {func.name})",
                                "unexplained_shared_mutable_state",
                            )
                        )
                    if (
                        isinstance(t, ast.Attribute)
                        and isinstance(t.value, ast.Name)
                        and t.value.id in module_names
                        and t.value.id not in locally_bound
                    ):
                        candidates.append(
                            Candidate(
                                rel_path,
                                stmt.lineno,
                                "module_global_attribute_assignment",
                                f"{t.value.id}.{t.attr} = ... (in {func.name})",
                                "unexplained_shared_mutable_state",
                            )
                        )
                    if (
                        isinstance(t, ast.Subscript)
                        and isinstance(t.value, ast.Name)
                        and t.value.id in module_names
                        and t.value.id not in locally_bound
                    ):
                        candidates.append(
                            Candidate(
                                rel_path,
                                stmt.lineno,
                                "module_global_subscript_assignment",
                                f"{t.value.id}[...] = ... (in {func.name})",
                                "unexplained_shared_mutable_state",
                            )
                        )
            elif isinstance(stmt, ast.AugAssign):
                if (
                    isinstance(stmt.target, ast.Name)
                    and stmt.target.id in module_names
                    and (
                        stmt.target.id in globals_declared
                        or stmt.target.id in nonlocals_declared
                    )
                ):
                    candidates.append(
                        Candidate(
                            rel_path,
                            stmt.lineno,
                            "module_global_augmented_assignment",
                            f"{stmt.target.id} {type(stmt.op).__name__}=... "
                            f"(in {func.name})",
                            "unexplained_shared_mutable_state",
                        )
                    )
            elif isinstance(stmt, ast.Call) and isinstance(stmt.func, ast.Attribute):
                base = stmt.func.value
                if (
                    isinstance(base, ast.Name)
                    and base.id in module_names
                    and base.id not in locally_bound
                    and stmt.func.attr in _MUTATING_METHODS
                ):
                    candidates.append(
                        Candidate(
                            rel_path,
                            stmt.lineno,
                            "module_global_mutated_via_method_call",
                            f"{base.id}.{stmt.func.attr}(...) (in {func.name})",
                            "unexplained_shared_mutable_state",
                        )
                    )

    for name, (line, initial) in scalar_candidates.items():
        if name not in rebound_via_global:
            candidates.append(
                Candidate(
                    rel_path,
                    line,
                    "module_level_scalar_never_rebound",
                    f"{name} = {initial}",
                    "immutable_constant",
                )
            )

    # -- closure-captured mutables (v4 category, carried forward): a
    #    nested function mutating a mutable literal its ENCLOSING
    #    function assigned to a local -- distinct from a module global.
    for outer in ast.walk(tree):
        if not isinstance(outer, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        mutable_locals: dict[str, str] = {}
        for stmt in ast.walk(outer):
            # `stmt` is narrowed to ast.Assign by the isinstance check;
            # an Assign node can never *be* `outer` (a FunctionDef), so
            # no identity check against it is needed here.
            if isinstance(stmt, ast.Assign):
                for t in stmt.targets:
                    if isinstance(t, ast.Name) and isinstance(
                        stmt.value, (ast.List, ast.Dict, ast.Set)
                    ):
                        mutable_locals[t.id] = type(stmt.value).__name__
        if not mutable_locals:
            continue
        for inner in ast.walk(outer):
            if (
                not isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef))
                or inner is outer
            ):
                continue
            for call in ast.walk(inner):
                if (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Attribute)
                    and isinstance(call.func.value, ast.Name)
                    and call.func.value.id in mutable_locals
                    and call.func.attr in _MUTATING_METHODS
                ):
                    candidates.append(
                        Candidate(
                            rel_path,
                            call.lineno,
                            "closure_captured_mutable",
                            f"{call.func.value.id}.{call.func.attr}(...) in "
                            f"nested {inner.name} (enclosing {outer.name}'s "
                            f"own {mutable_locals[call.func.value.id]} local)",
                            "unexplained_shared_mutable_state",
                        )
                    )

    return tuple(candidates)


def _finalize_classifications(
    candidates: tuple[Candidate, ...], full_scope_text: str
) -> tuple[Candidate, ...]:
    """Cross-scope never-mutated check: a candidate with a ``subject``
    name is upgraded from its provisional bucket to
    ``unexplained_shared_mutable_state`` if that name is used anywhere
    in the audited scope in a mutation-shaped call (``name.method(``
    for a mutating method) or a subscript-assignment shape
    (``name[...] =``) -- the same mechanical "confirmed never mutated"
    grep methodology Task 38.5 v3-v5 used, applied here to every
    candidate this scan finds, not a fixed hand-picked list."""
    out: list[Candidate] = []
    for c in candidates:
        if c.subject is None:
            out.append(c)
            continue
        name = c.subject
        mutated = any(f"{name}.{m}(" in full_scope_text for m in _MUTATING_METHODS) or (
            f"{name}[" in full_scope_text
            and f"{name}[" in full_scope_text
            and any(
                line.strip().startswith(f"{name}[") and "=" in line and "==" not in line
                for line in full_scope_text.splitlines()
                if f"{name}[" in line
            )
        )
        if mutated:
            out.append(
                Candidate(
                    c.file,
                    c.line,
                    c.kind,
                    c.detail,
                    "unexplained_shared_mutable_state",
                    c.subject,
                )
            )
        else:
            out.append(c)
    return tuple(out)


def scan_scope(
    repo_root: Path, packages: tuple[str, ...]
) -> tuple[tuple[Candidate, ...], tuple[str, ...]]:
    """Scan every ``.py`` file (production source, ``tests/`` excluded)
    under each of ``packages``. Returns (candidates, parse_error_files)."""
    all_candidates: list[Candidate] = []
    parse_errors: list[str] = []
    source_blobs: list[str] = []
    for pkg in packages:
        base = repo_root / pkg
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            if "__pycache__" in path.parts or "tests" in path.parts:
                continue
            rel = str(path.relative_to(repo_root))
            try:
                source = path.read_text(encoding="utf-8")
            except OSError:
                parse_errors.append(rel)
                continue
            source_blobs.append(source)
            result = scan_module(rel, source)
            if result is None:
                parse_errors.append(rel)
                continue
            all_candidates.extend(result)
    finalized = _finalize_classifications(
        tuple(all_candidates), "\n".join(source_blobs)
    )
    return (
        tuple(sorted(finalized, key=lambda c: (c.file, c.line, c.kind))),
        tuple(sorted(parse_errors)),
    )
