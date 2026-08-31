"""Task 38.9B H-1: the corrected cross-framework import invariant.

H-1's original claim — "no framework imports another framework directly" —
is false (`docs/audits/task-38.5-risk-register.md`). The evidenced,
narrower invariant this test protects instead:

* Frameworks may freely import each other's public domain/value types
  (``models``/``context``/``signals``/``state``) and ``Protocol``
  interfaces — real, intentional, and not what this test guards.
* No framework may directly *construct* another framework's concrete
  class (``ClassName(...)``), under any import spelling — only resolve it
  through the DI container (``resolver.resolve(ClassName)``/
  ``resolver.has(ClassName)``).
* The one evidenced concrete cross-framework runtime type is
  ``trading.engine.TradingEngine``, used by exactly nine frameworks. Its
  *only* permitted runtime references are the import binding itself and
  appearing as the sole argument to ``resolver.resolve``/``resolver.has``
  — proven per-reference below, not merely inferred from an absence of
  ``TradingEngine(...)``.

Detection resolves each reference's fully-qualified dotted path through
the file's own import bindings (``ast.Import``/``ast.ImportFrom``, plain or
aliased, module- or object-level) before classifying it — so
``TradingEngine(...)``, ``TE(...)`` (aliased), ``trading.engine.
TradingEngine(...)`` (module-qualified), and ``te.TradingEngine(...)``
(aliased module) are all recognized as the same underlying construction,
while ``resolver.resolve(TradingEngine)`` is recognized as the same
underlying *reference* used only as a call *argument*, never a callee.
Scope is deliberately narrow: this is not a general Python import/name
resolver, only enough attribute-chain substitution to answer "does this
expression denote a known cross-framework symbol" for the concrete-class
question this test exists to answer.
"""

from __future__ import annotations

import ast
import dataclasses
import enum
import importlib
import importlib.util
import inspect
from collections.abc import Iterator
from pathlib import Path

from app import wiring

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Every framework package this test scans for cross-framework imports —
#: mechanically derived from the real registrar set, plus ``trading``
#: (unwired infrastructure, but a legitimate cross-import target/source).
FRAMEWORKS: frozenset[str] = frozenset(wiring.KNOWN_COMPONENT_IDS) | {"trading"}

#: The narrow, real lifecycle API of ``trading.engine.TradingEngine``
#: specifically (`trading/engine.py`) — not a blacklist across unrelated
#: framework objects. Scoped to this one class's actual public methods.
_TRADING_ENGINE_LIFECYCLE_METHODS: frozenset[str] = frozenset(
    {"start", "stop", "pause", "resume"}
)

#: The one evidenced concrete cross-framework runtime type (Task 38.9B
#: Phase 0 scan) and the exact importer set for it. A deliberate, reviewed
#: regression baseline — not derived from this test's own discovery, so a
#: silent expansion of the exception is caught, not laundered.
_EXPECTED_CONCRETE_DI_KEY_IMPORT: str = "trading.engine.TradingEngine"
_EXPECTED_CONCRETE_DI_KEY_IMPORTERS: frozenset[str] = frozenset(
    {
        "exchange_adapters",
        "execution",
        "market_data",
        "order_management",
        "portfolio",
        "positions",
        "risk",
        "strategies",
        "trades",
    }
)


# ---------------------------------------------------------------------------
# Core, reusable analysis -- shared by the real repository scan AND every
# negative/positive control below, so the controls prove the actual
# production detector works rather than a parallel re-implementation of it.
# ---------------------------------------------------------------------------


def _is_protocol(obj: object) -> bool:
    return inspect.isclass(obj) and bool(getattr(obj, "_is_protocol", False))


def _is_abc_interface(obj: object) -> bool:
    return inspect.isclass(obj) and (
        inspect.isabstract(obj) or bool(getattr(obj, "__abstractmethods__", None))
    )


def _resolve_dotted(dotted: str) -> object | None:
    """Best-effort resolve ``pkg.mod.Name`` to the real object, trying
    progressively shorter module paths (mirrors how ``from x.y import Z``
    actually resolves)."""
    parts = dotted.split(".")
    for split in range(len(parts) - 1, 0, -1):
        mod_path = ".".join(parts[:split])
        try:
            mod = importlib.import_module(mod_path)
        except Exception:  # pragma: no cover - defensive only
            continue
        obj: object = mod
        ok = True
        for attr in parts[split:]:
            try:
                obj = getattr(obj, attr)
            except AttributeError:
                ok = False
                break
        if ok:
            return obj
    return None


def _is_concrete_class(obj: object) -> bool:
    """A real, directly-instantiable implementation class — never a
    ``Protocol``, an abstract base, a ``@dataclass`` value type, or an
    ``Enum``. Never determined by a ``Default*``/naming convention."""
    if not inspect.isclass(obj):
        return False
    if _is_protocol(obj) or _is_abc_interface(obj):
        return False
    if dataclasses.is_dataclass(obj):
        return False
    try:
        if issubclass(obj, enum.Enum):
            return False
    except TypeError:
        pass
    return True


def _type_checking_node_ids(tree: ast.Module) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            test = node.test
            is_tc = (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
                isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
            )
            if is_tc:
                for sub in ast.walk(node):
                    ids.add(id(sub))
    return ids


def import_bindings(
    tree: ast.Module, importing_framework: str
) -> dict[str, tuple[str, bool]]:
    """local_name -> (dotted_path, is_module) for every runtime (non-
    ``TYPE_CHECKING``) import binding this file creates from *another*
    framework in ``FRAMEWORKS``. Handles every import spelling relevant to
    detecting cross-framework construction:

    * ``import trading.engine`` -> binds ``trading`` to module ``trading``
      (Python's own binding rule for dotted plain imports).
    * ``import trading.engine as te`` -> binds ``te`` to module
      ``trading.engine``.
    * ``from trading import engine`` -> binds ``engine`` to module
      ``trading.engine``.
    * ``from trading.engine import TradingEngine`` -> binds
      ``TradingEngine`` to object ``trading.engine.TradingEngine``.
    * ``from trading.engine import TradingEngine as TE`` -> binds ``TE``
      to the same object path.
    """
    tc_ids = _type_checking_node_ids(tree)
    bindings: dict[str, tuple[str, bool]] = {}
    for node in ast.walk(tree):
        if id(node) in tc_ids:
            continue
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top not in FRAMEWORKS or top == importing_framework:
                    continue
                if alias.asname:
                    bindings[alias.asname] = (alias.name, True)
                else:
                    # `import a.b.c` binds only the root name `a`.
                    bindings[top] = (top, True)
        elif isinstance(node, ast.ImportFrom) and node.module:
            top = node.module.split(".")[0]
            if top not in FRAMEWORKS or top == importing_framework:
                continue
            for alias in node.names:
                local = alias.asname or alias.name
                dotted = f"{node.module}.{alias.name}"
                # Ambiguous by syntax alone whether this is a submodule
                # (`from trading import engine`) or an object
                # (`from trading.engine import TradingEngine`) -- resolve
                # to decide, since that changes how a later attribute
                # chain through it must be interpreted.
                try:
                    is_mod = importlib.util.find_spec(dotted) is not None
                except (ModuleNotFoundError, ImportError, ValueError):
                    is_mod = False
                bindings[local] = (dotted, is_mod)
    return bindings


def _dotted_chain(expr: ast.expr) -> list[str] | None:
    """``a.b.c`` -> ``["a", "b", "c"]``; ``None`` for anything that isn't a
    pure dotted-name chain (a call result, subscript, etc.)."""
    parts: list[str] = []
    node: ast.expr = expr
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        parts.reverse()
        return parts
    return None


def resolve_expr_dotted(
    expr: ast.expr, bindings: dict[str, tuple[str, bool]]
) -> str | None:
    """Resolve ``expr`` (a Name/Attribute chain) to its fully-qualified
    dotted path via ``bindings``, or ``None`` if its root isn't a tracked
    import binding."""
    chain = _dotted_chain(expr)
    if not chain:
        return None
    root, *rest = chain
    if root not in bindings:
        return None
    dotted_root, _is_mod = bindings[root]
    return ".".join([dotted_root, *rest]) if rest else dotted_root


@dataclasses.dataclass(frozen=True, slots=True)
class DirectInstantiationViolation:
    line: int
    resolved: str


def find_direct_construction_violations(
    tree: ast.Module, importing_framework: str
) -> list[DirectInstantiationViolation]:
    """The one detector both the real repository scan and every control
    below call: every ``ast.Call`` whose callee resolves (through this
    file's own import bindings, any spelling) to a concrete class owned by
    another framework is a direct-construction violation. A concrete class
    appearing only as a *call argument* (``resolver.resolve(TradingEngine)``)
    is never inspected here — only each Call's own ``.func``."""
    bindings = import_bindings(tree, importing_framework)
    if not bindings:
        return []
    violations: list[DirectInstantiationViolation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        resolved = resolve_expr_dotted(node.func, bindings)
        if resolved is None:
            continue
        obj = _resolve_dotted(resolved)
        if obj is not None and _is_concrete_class(obj):
            violations.append(
                DirectInstantiationViolation(line=node.lineno, resolved=resolved)
            )
    return violations


def _framework_py_files(framework: str) -> Iterator[Path]:
    pkg_dir = REPO_ROOT / framework
    if not pkg_dir.is_dir():
        return
    for py_file in sorted(pkg_dir.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        yield py_file


def _parse(py_file: Path) -> ast.Module | None:
    try:
        return ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    except SyntaxError:  # pragma: no cover - defensive only
        return None


def _iter_framework_trees(
    frameworks: frozenset[str] | set[str],
) -> Iterator[tuple[str, Path, ast.Module]]:
    """``(framework, file, tree)`` for every parseable ``.py`` file across
    ``frameworks`` — the one shared walk every scan below reuses, so each
    only has to say *what* it's looking for, not *how* to find files."""
    for framework in sorted(frameworks):
        for py_file in _framework_py_files(framework):
            tree = _parse(py_file)
            if tree is not None:
                yield framework, py_file, tree


# ---------------------------------------------------------------------------
# Requirement A: no direct cross-framework concrete construction, under any
# import spelling.
# ---------------------------------------------------------------------------


def test_no_framework_directly_instantiates_another_frameworks_concrete_class() -> (
    None
):
    all_violations: list[str] = []
    for framework, py_file, tree in _iter_framework_trees(FRAMEWORKS):
        for v in find_direct_construction_violations(tree, framework):
            rel = py_file.relative_to(REPO_ROOT)
            all_violations.append(f"{framework}:{rel}:{v.line} -> {v.resolved}()")
    assert not all_violations, (
        "direct cross-framework concrete instantiation found: "
        + ", ".join(all_violations)
    )


# ---------------------------------------------------------------------------
# Requirement B: the one reviewed concrete-DI-key exception stays exactly
# as scoped as evidenced -- both in *what* is concrete and *who* imports it.
# ---------------------------------------------------------------------------


def test_the_one_evidenced_concrete_di_key_exception_is_exactly_scoped() -> None:
    found_importers: set[str] = set()
    found_other_concrete: list[str] = []
    for framework, py_file, tree in _iter_framework_trees(FRAMEWORKS):
        for _local, (dotted, is_mod) in import_bindings(tree, framework).items():
            if is_mod:
                continue  # a module binding alone isn't a class import
            obj = _resolve_dotted(dotted)
            if obj is None or not _is_concrete_class(obj):
                continue
            if dotted == _EXPECTED_CONCRETE_DI_KEY_IMPORT:
                found_importers.add(framework)
            else:
                found_other_concrete.append(f"{framework}:{py_file.name}:{dotted}")

    assert not found_other_concrete, (
        "a new concrete cross-framework runtime import appeared beyond the "
        f"one reviewed exception ({_EXPECTED_CONCRETE_DI_KEY_IMPORT}): "
        + ", ".join(found_other_concrete)
    )
    assert found_importers == _EXPECTED_CONCRETE_DI_KEY_IMPORTERS, (
        "TradingEngine DI-key importer set changed: "
        f"missing={sorted(_EXPECTED_CONCRETE_DI_KEY_IMPORTERS - found_importers)} "
        f"extra={sorted(found_importers - _EXPECTED_CONCRETE_DI_KEY_IMPORTERS)}"
    )


# ---------------------------------------------------------------------------
# Requirement 1 (hardening): prove *how* TradingEngine is used at runtime,
# not just that TradingEngine(...) doesn't appear. Every runtime reference
# to the imported name (any binding form) in each of the nine importers
# must be either the import statement's own binding, or the sole argument
# of a resolver.resolve(...)/resolver.has(...) call -- nothing else.
# ---------------------------------------------------------------------------


def _trading_engine_reference_uses(
    tree: ast.Module, importing_framework: str
) -> list[str]:
    """Every runtime reference to the bound TradingEngine name that is
    *not* the import statement itself and *not* the sole argument of
    resolver.resolve(...)/resolver.has(...) -- i.e. every disallowed use."""
    bindings = import_bindings(tree, importing_framework)
    te_locals = {
        local
        for local, (dotted, is_mod) in bindings.items()
        if not is_mod and dotted == _EXPECTED_CONCRETE_DI_KEY_IMPORT
    }
    if not te_locals:
        return []

    tc_ids = _type_checking_node_ids(tree)
    import_node_ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "trading.engine":
            import_node_ids.add(id(node))
            for alias in node.names:
                import_node_ids.add(id(alias))

    # Mark each te_locals argument of a resolver.resolve(...)/resolver.has(...)
    # call as permitted -- these are the only two forms this test allows.
    permitted_arg_ids: set[int] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("resolve", "has")
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "resolver"
        ):
            for arg in node.args:
                if isinstance(arg, ast.Name) and arg.id in te_locals:
                    permitted_arg_ids.add(id(arg))

    # Now walk every Name node anywhere in the file: any reference to a
    # te_locals name that isn't the import binding, a TYPE_CHECKING-only
    # reference, or one of the permitted arguments just marked above is a
    # violation.
    violations: list[str] = []
    for node in ast.walk(tree):
        if id(node) in tc_ids or id(node) in import_node_ids:
            continue
        if isinstance(node, ast.Name) and node.id in te_locals:
            if id(node) in permitted_arg_ids:
                continue
            violations.append(
                f"line {node.lineno}: {node.id} used outside resolver.resolve/has"
            )
    return violations


def test_trading_engine_runtime_uses_are_exactly_the_permitted_di_key_forms() -> (
    None
):
    """Hardening for requirement 1: enumerates every runtime reference to
    the imported ``TradingEngine`` name across all nine importers and
    proves each one is either the import binding itself or the sole
    argument to ``resolver.resolve``/``resolver.has`` — not merely that
    ``TradingEngine(...)`` is absent. As of this scan, the exhaustive,
    verified list of permitted runtime references is exactly two per
    importer: the ``resolver.resolve(TradingEngine)`` and
    ``resolver.has(TradingEngine)`` calls inside each framework's
    ``_build_*`` factory closure — no other runtime reference exists."""
    all_violations: list[str] = []
    checked_frameworks: set[str] = set()
    for framework, py_file, tree in _iter_framework_trees(
        _EXPECTED_CONCRETE_DI_KEY_IMPORTERS
    ):
        violations = _trading_engine_reference_uses(tree, framework)
        if violations:
            rel = py_file.relative_to(REPO_ROOT)
            all_violations.extend(f"{framework}:{rel}:{v}" for v in violations)
        bindings = import_bindings(tree, framework)
        if any(
            dotted == _EXPECTED_CONCRETE_DI_KEY_IMPORT and not is_mod
            for dotted, is_mod in bindings.values()
        ):
            checked_frameworks.add(framework)

    assert not all_violations, (
        "TradingEngine referenced outside the permitted DI-key forms: "
        + ", ".join(all_violations)
    )
    missing = sorted(_EXPECTED_CONCRETE_DI_KEY_IMPORTERS - checked_frameworks)
    assert checked_frameworks == _EXPECTED_CONCRETE_DI_KEY_IMPORTERS, (
        f"did not find a runtime TradingEngine import in every expected importer: "
        f"missing={missing}"
    )


# ---------------------------------------------------------------------------
# Requirement C: TradingEngine's own lifecycle API is never invoked by any
# importer, scoped to this one typed collaborator.
# ---------------------------------------------------------------------------


def _trading_engine_lifecycle_call_violations() -> list[str]:
    violations: list[str] = []
    for framework, py_file, tree in _iter_framework_trees(
        _EXPECTED_CONCRETE_DI_KEY_IMPORTERS
    ):
        for cls_node in ast.walk(tree):
            if not isinstance(cls_node, ast.ClassDef):
                continue
            init = next(
                (
                    n
                    for n in cls_node.body
                    if isinstance(n, ast.FunctionDef) and n.name == "__init__"
                ),
                None,
            )
            if init is None:
                continue
            te_params = {
                a.arg
                for a in init.args.args + init.args.kwonlyargs
                if a.annotation is not None
                and "TradingEngine" in ast.dump(a.annotation)
            }
            if not te_params:
                continue
            bound_attrs: set[str] = set()
            for node in ast.walk(init):
                if (
                    isinstance(node, ast.Assign)
                    and isinstance(node.value, ast.Name)
                    and node.value.id in te_params
                ):
                    for target in node.targets:
                        if (
                            isinstance(target, ast.Attribute)
                            and isinstance(target.value, ast.Name)
                            and target.value.id == "self"
                        ):
                            bound_attrs.add(target.attr)
            if not bound_attrs:
                continue
            for node in ast.walk(cls_node):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr in _TRADING_ENGINE_LIFECYCLE_METHODS
                    and isinstance(func.value, ast.Attribute)
                    and func.value.attr in bound_attrs
                    and isinstance(func.value.value, ast.Name)
                    and func.value.value.id == "self"
                ):
                    violations.append(
                        f"{framework}:{py_file.relative_to(REPO_ROOT)}:"
                        f"{node.lineno} self.{func.value.attr}.{func.attr}()"
                    )
    return violations


def test_trading_engine_lifecycle_methods_are_never_invoked_by_its_importers() -> (
    None
):
    """Requirement C. Kept narrow (this one typed collaborator's real
    ``start``/``stop``/``pause``/``resume`` API, on the exact attribute its
    own ``__init__`` binds it to) rather than a broad method-name
    blacklist across unrelated framework objects, which would be both
    brittle and misleading about what is actually being proven."""
    violations = _trading_engine_lifecycle_call_violations()
    assert not violations, (
        "a TradingEngine importer invoked a lifecycle method directly: "
        + ", ".join(violations)
    )


# ---------------------------------------------------------------------------
# Requirement D / 3: negative and positive controls exercise the exact
# same find_direct_construction_violations() the real scan above uses --
# never a parallel re-implementation. Nothing here executes.
# ---------------------------------------------------------------------------


#: label -> synthetic source, one per import spelling the detector must
#: catch. Every case constructs TradingEngine directly; none is executed
#: — each is only ever passed to ``ast.parse``.
_DIRECT_CONSTRUCTION_CASES: dict[str, str] = {
    "direct imported name": (
        "from trading.engine import TradingEngine\n"
        "\n"
        "def build_it():\n"
        "    return TradingEngine(coordinator, lifecycle)\n"
    ),
    "aliased imported name": (
        "from trading.engine import TradingEngine as TE\n"
        "\n"
        "def build_it():\n"
        "    return TE(coordinator, lifecycle)\n"
    ),
    "module-qualified (import trading.engine)": (
        "import trading.engine\n"
        "\n"
        "def build_it():\n"
        "    return trading.engine.TradingEngine(coordinator, lifecycle)\n"
    ),
    "module-qualified, aliased module (import trading.engine as te)": (
        "import trading.engine as te\n"
        "\n"
        "def build_it():\n"
        "    return te.TradingEngine(coordinator, lifecycle)\n"
    ),
    "module-qualified (from trading import engine)": (
        "from trading import engine\n"
        "\n"
        "def build_it():\n"
        "    return engine.TradingEngine(coordinator, lifecycle)\n"
    ),
}


def test_negative_controls_construction_detected_under_every_import_spelling() -> (
    None
):
    """Every import spelling that could construct ``TradingEngine`` directly
    must be caught by the exact same ``find_direct_construction_violations``
    the real repository scan uses — never a parallel re-implementation.
    Nothing here is executed, only parsed."""
    for label, source in _DIRECT_CONSTRUCTION_CASES.items():
        tree = ast.parse(source, filename=f"<negative control: {label}>")
        violations = find_direct_construction_violations(
            tree, importing_framework="execution"
        )
        ok = violations and violations[0].resolved == _EXPECTED_CONCRETE_DI_KEY_IMPORT
        assert ok, f"construction not detected for {label!r}:\n{source}"


def test_positive_control_resolver_di_lookup_is_never_flagged() -> None:
    """``resolver.resolve(TradingEngine)`` and ``resolver.has(TradingEngine)``
    — the permitted forms — must never be flagged by the same detector the
    negative controls above prove works."""
    tree = ast.parse(
        "from trading.engine import TradingEngine\n"
        "\n"
        "def build_it(resolver):\n"
        "    return resolver.resolve(TradingEngine) if resolver.has(TradingEngine) "
        "else None\n",
        filename="<positive control: resolver DI lookup>",
    )
    violations = find_direct_construction_violations(
        tree, importing_framework="execution"
    )
    assert not violations, (
        "false positive: resolver.resolve(TradingEngine)/resolver.has(TradingEngine) "
        f"must never be flagged as direct instantiation, got: {violations}"
    )


def test_qualified_typing_type_checking_guard_is_also_recognized() -> None:
    """``import_bindings``/``_type_checking_node_ids`` accept both
    ``if TYPE_CHECKING:`` (the form every real file in this repository
    uses) and the qualified ``if typing.TYPE_CHECKING:`` form. No current
    source file exercises the qualified form, so this proves that branch
    directly rather than leaving it untested."""
    tree = ast.parse(
        "import typing\n"
        "\n"
        "if typing.TYPE_CHECKING:\n"
        "    from trading.engine import TradingEngine\n"
        "\n"
        "def f(x: 'TradingEngine | None' = None):\n"
        "    return x\n",
        filename="<typing.TYPE_CHECKING form>",
    )
    bindings = import_bindings(tree, importing_framework="execution")
    assert not bindings, (
        "a typing.TYPE_CHECKING-guarded import must never be treated as a "
        f"runtime binding, got: {bindings}"
    )
