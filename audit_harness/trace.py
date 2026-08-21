"""Harness Requirements 1 and 3: fresh-container recursive tracing plus
specified-pattern static analysis coverage.

Builds a fresh, independently, fully-registered ``ServiceContainer`` for
each of the 24 ``SAFE_SERVICE_KEYS`` roots (no container or its
singleton cache reused across roots), traces ``resolve()``, and
statically walks every registrar body, provider closure, the
container/registry/planner/preflight machinery itself, every
discovered node's ``__init__``/``__new__``/``__post_init__``, every
dataclass ``default_factory``, and the real MRO base of every
``super().__init__()`` call -- adding every class this discovers into
one unified node collection, and classifying every call site via
:mod:`audit_harness.identity`.

:class:`StaticWalker` is the reusable static-analysis engine: it takes
an arbitrary list of seed callables (real registrars for a real run,
fixture functions for a negative-control test) and produces the same
node/call classification either way -- Requirement 9's negative-control
tests exercise this exact class, not a re-implementation of it.

Deterministic: every collection this module returns is sorted before
being handed to the caller (Requirement 1). No wall-clock read, no
random value, no reliance on unordered dict/set iteration in the
output.
"""

from __future__ import annotations

import ast
import builtins
import dataclasses
import functools
import inspect
import sys
import textwrap
import types
import typing
from collections.abc import Callable
from dataclasses import dataclass

from audit_harness.identity import (
    IdentityVerdict,
    classify_callable,
    defining_module_of_method,
    is_namedtuple_generated_new,
    module_and_qualname,
)

#: Task 38.7 Requirement (termination): walking third-party source must
#: be a bounded, deterministic fixed-point traversal, never an
#: unbounded descent -- but the bound must be package-neutral, never
#: conditioned on whether a frame happens to be project-owned or not
#: (a per-origin depth cap is exactly the "depth cap tied to package
#: origin" the requirement forbids, and any per-branch depth cap at all
#: is a bound with no principled, package-neutral size). This is the
#: walker's *only* traversal bound -- there is no depth-based early
#: return of any kind; the specialization-aware visited-state dedup
#: (`visited_funcs`) is what actually terminates a cycle, and this is a
#: single *total node count* budget applied identically to every
#: module: the walker may visit at most this many distinct (callable,
#: call-site specialization) states in one instance's lifetime, full
#: stop. The real Task 38.7 trace visits ~1,519 distinct states,
#: uncapped (verified directly against `StaticWalker.visited_funcs` on
#: the live codebase) -- this budget is set to roughly 5x that headroom
#: so the real trace always reaches its own fixed point before the
#: budget is ever touched, while a cyclic or adversarially large graph
#: still terminates deterministically instead of running away.
_MAX_TOTAL_WALK_STEPS = 8000

# ---------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ResolveEvent:
    root: str
    key: str
    provider_symbol: str
    result_type: str


@dataclass(frozen=True, slots=True)
class NodeRecord:
    qualname: str
    is_dataclass: bool
    custom_init: bool
    custom_new: bool
    has_post_init: bool
    init: IdentityVerdict
    new: IdentityVerdict
    post_init: IdentityVerdict | None
    default_factories: tuple[tuple[str, IdentityVerdict], ...]

    @property
    def unresolved(self) -> bool:
        verdicts = [self.init, self.new, *([self.post_init] if self.post_init else [])]
        verdicts += [v for _name, v in self.default_factories]
        return any(v.category == "unresolved" for v in verdicts)


@dataclass(frozen=True, slots=True)
class CallRecord:
    site: str
    callee_text: str
    resolution_mechanism: str
    verdict: IdentityVerdict


_REGISTRATION_METHODS = frozenset(
    {"register", "register_singleton", "register_factory", "register_instance"}
)

#: A local variable assigned the return value of one of these stdlib
#: functions has a fixed, documented return type -- a structural fact
#: from each function's own stdlib contract, not a guess. Lets
#: ``signature = inspect.signature(cls); signature.parameters.items()``
#: resolve ``signature``'s own type the same way a class-constructor
#: assignment already does. Explicit and versioned the same way
#: ``EXACT_IDENTITY_POLICY`` is -- each entry is one C-implemented or
#: otherwise unintrospectable stdlib callable whose return type
#: ``typing.get_type_hints`` cannot recover at runtime (Task 38.7
#: Category C).
_STDLIB_RETURN_TYPES: dict[str, type] = {
    "inspect.signature": inspect.Signature,
    "typing.get_type_hints": dict,
    "os.getenv": str,
    # `str`'s own pure string-transformation methods return `str` --
    # CPython's documented contract, needed so a *chained* call
    # (`value.strip().lower()`) can resolve its second hop through the
    # first call's own return type (Task 38.7 Category C/D chained
    # calls -- `_infer_type`'s Call branch looks up a resolved callee's
    # module+qualname here the same way an assignment's RHS does).
    "builtins.str.strip": str,
    "builtins.str.lower": str,
    "builtins.str.upper": str,
    "builtins.str.rstrip": str,
    "builtins.str.lstrip": str,
}

#: A *property* (not a called function) on one of these types has a
#: fixed, documented value type -- read from the stdlib's own
#: documented contract, the same non-guess discipline as
#: ``_STDLIB_RETURN_TYPES`` (Task 38.7 Category B/C, multi-hop chains
#: such as ``inspect.signature(cls).parameters.items()``).
_ATTR_RETURN_TYPES: dict[str, type] = {
    "inspect.Signature.parameters": types.MappingProxyType,
}


def _underlying(func: object) -> object:
    unbound = getattr(func, "__func__", func)
    # Unwrap a @lru_cache/@cache decorator too -- its wrapper object has
    # no __globals__/__annotations__/__qualname__ of its own for our
    # purposes; inspect.getsource already follows __wrapped__
    # automatically, but attribute access does not.
    return getattr(unbound, "__wrapped__", unbound)


def _owner_class_from_qualname(
    qualname: str, module_name: str | None
) -> type | None:
    """The real owning class for a resolved target's qualname -- e.g.
    ``ServiceContainer.register_instance.<locals>.<lambda>`` ->
    ``ServiceContainer``. A plain ``rsplit(".", 1)`` (as used for an
    ordinary method's ``Class.method`` qualname) mis-splits a
    ``<locals>``-nested target: the *last* dot sits between
    ``<locals>`` and the nested name, not between the class and its
    method, so a naive split would try (and fail) to ``getattr`` a
    literal ``"...​<locals>"`` attribute name. Task 38.7 Category E: this
    is exactly the shape a provider lambda's own qualname has, and
    fixing this general case is what actually lets that lambda's own
    ``self.<attr>`` calls resolve, no per-lambda AST relocation needed --
    the walker was simply never given the right owner_class to begin
    with."""
    head = qualname.split(".<locals>.")[0]
    if "." not in head:
        return None
    owner_name = head.rsplit(".", 1)[0]
    mod = sys.modules.get(module_name) if module_name is not None else None
    candidate = getattr(mod, owner_name, None) if mod else None
    return candidate if inspect.isclass(candidate) else None


def _local_helper_names(tree: ast.Module) -> frozenset[str]:
    """Names of nested `def`s in the root function's own direct body
    that are local helpers (called by name from within the same body),
    as opposed to a nested `def` passed BY NAME as a registration
    provider (walked separately -- see :func:`_shallow_descendants`)."""
    if not tree.body or not isinstance(
        tree.body[0], (ast.FunctionDef, ast.AsyncFunctionDef)
    ):
        return frozenset()
    root = tree.body[0]
    separately_walked: set[str] = set()
    nested_names: set[str] = set()
    for node in ast.walk(root):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _REGISTRATION_METHODS
        ):
            for arg in node.args:
                if isinstance(arg, ast.Name):
                    separately_walked.add(arg.id)
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node is not root
        ):
            nested_names.add(node.name)
    return frozenset(nested_names - separately_walked)


def _dedented_source(func: object) -> str | None:
    try:
        return textwrap.dedent(inspect.getsource(func))  # type: ignore[arg-type]
    except (OSError, TypeError):
        return None


def _shallow_descendants(tree: ast.Module) -> list[ast.AST]:
    """Every node belonging to the *one* function this parsed tree's
    source came from, excluding the body of any nested function/lambda
    defined inside it.

    ``inspect.getsource`` on a normal ``def`` returns exactly that
    function's own statement, so ``tree.body[0]`` is the outer
    FunctionDef -- walking without this filter would let ``ast.walk``
    descend into a nested closure's body while still using the OUTER
    function's own parameter/local-variable context, silently
    mis-resolving (or failing to resolve) every call inside the nested
    closure. That closure is walked correctly on its own, separately,
    once it is reached as a provider or a same-module function
    reference -- this function's job is only to avoid double-counting
    it here with the wrong context.

    ``inspect.getsource`` on a lambda instead returns the whole
    enclosing *statement* (a well-known quirk), so ``tree.body[0]`` is
    not a FunctionDef there -- that shape is intentionally exempted
    from the filter, since the enclosing statement (e.g. a
    ``container.register_singleton(X, lambda r: ...)`` call) is exactly
    what provider-callback type inference needs to see in the same
    tree as the lambda itself.
    """
    if not tree.body or not isinstance(
        tree.body[0], (ast.FunctionDef, ast.AsyncFunctionDef)
    ):
        return list(ast.walk(tree))

    root = tree.body[0]

    # A nested `def NAME(...):` that is itself passed BY NAME as a
    # registration-method's provider argument (e.g.
    # `container.register_singleton(X, _build_manager)`) is walked
    # separately, on its own, once it is reached that way (from
    # providers_seen for a real run) -- exploring it here too, inline,
    # would process it a second time with the wrong (root's own)
    # parameter/local context. A nested `def NAME(...):` that is never
    # registered that way -- a plain local helper, e.g.
    # `def opt(key): return resolver.resolve(key) if resolver.has(key)
    # else None`, only ever *called* from within root's own body -- is
    # never walked any other way, so it must be explored inline here,
    # using root's own g/loc/param_hints (which is exactly right: nested
    # functions share their enclosing scope in real Python).
    separately_walked_names: set[str] = set()
    for node in ast.walk(root):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _REGISTRATION_METHODS
        ):
            for arg in node.args:
                if isinstance(arg, ast.Name):
                    separately_walked_names.add(arg.id)

    out: list[ast.AST] = []

    class _Collector(ast.NodeVisitor):
        def __init__(self) -> None:
            self._at_root = True

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
            if node is root and self._at_root:
                self._at_root = False
                out.append(node)
                self.generic_visit(node)
                return
            if node.name in separately_walked_names:
                return  # walked on its own elsewhere; do not double-process
            out.append(node)  # a local helper -- explore inline, root's scope applies
            self.generic_visit(node)

        visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

        def visit_Lambda(self, node: ast.Lambda) -> None:  # noqa: N802
            out.append(node)  # visible as a value/argument, body not explored

        def generic_visit(self, node: ast.AST) -> None:  # noqa: N802
            if node is not root:
                out.append(node)
            super().generic_visit(node)

    _Collector().visit(root)
    return out


class StaticWalker:
    """The reusable AST call-graph engine (Harness Requirement 3) plus
    identity-first resolution (Harness Requirement 4). Instantiate once
    per run/test; state does not carry over between instances."""

    def __init__(
        self,
        *,
        protocol_implementer: dict[object, type] | None = None,
        protocol_name_implementer: dict[str, type] | None = None,
        provider_class: type | None = None,
        provider_owner_module: str | None = None,
        max_total_walk_steps: int = _MAX_TOTAL_WALK_STEPS,
    ) -> None:
        #: Keyed by (callable identity, call-site specialization
        #: identity) -- Task 38.7's "distinct concrete specialization"
        #: requirement: a generic function (e.g. `_build`'s own
        #: `cls: type[T]`) bound to two different real classes by two
        #: different call sites is walked once per distinct
        #: specialization, not merged into a single cached visit keyed
        #: on the function alone.
        self.visited_funcs: set[tuple[int, tuple[object, ...]]] = set()
        self.call_records: list[CallRecord] = []
        self.unified_nodes: dict[str, type] = {}
        self.sites_without_source: list[str] = []
        #: The package-neutral total-work budget (see
        #: `_MAX_TOTAL_WALK_STEPS`) for this one walker instance.
        #: Overridable so tests can inject a tiny budget and observe
        #: deterministic, explicit exhaustion rather than reproducing the
        #: full real trace.
        self.max_total_walk_steps = max_total_walk_steps
        #: Sites where the total-work budget (Requirement 1's
        #: deterministic fixed-point traversal, Task 38.7's termination
        #: requirement) was exhausted before a call graph reached a
        #: fixed point -- reported explicitly, never silently truncated.
        self.depth_exceeded: list[str] = []
        self.protocol_implementer = protocol_implementer or {}
        self.protocol_name_implementer = protocol_name_implementer or {}
        # Runtime-instance-assertion support for self._provider.on_data()
        # -- provider_class is the live type asserted by the caller
        # (Part A of a real run); provider_owner_module names the module
        # whose classes may use this assertion (market_data.service).
        self.provider_class = provider_class
        self.provider_owner_module = provider_owner_module
        #: (owner_class, attribute_name) -> the real type of that instance
        #: attribute, for the small number of ``self.<attr>.<method>()``
        #: chains this codebase's own container/registry machinery uses
        #: (e.g. ``ServiceContainer._registry`` is a ``Registry``, always
        #: ``ServiceRegistry`` -- read directly from ``core/container.py``'s
        #: own ``__init__``, not guessed). A real run's caller populates
        #: this; a fixture-only test leaves it empty.
        self.instance_attribute_types: dict[tuple[type, str], type] = {}

    # -- resolution helpers ------------------------------------------

    def _real_param_types(self, func: object) -> dict[str, type]:
        """Resolve each parameter's real annotated type, one name at a
        time -- not via a single ``typing.get_type_hints(func)`` call,
        which raises (and yields nothing for *any* parameter) the moment
        even one unrelated parameter's forward reference cannot be
        evaluated (e.g. a sibling ``engine: TradingEngine | None``
        parameter whose type is TYPE_CHECKING-only, on a function whose
        ``logger: LoggerFactory | None`` parameter is perfectly
        resolvable). Evaluating per-name means one bad annotation never
        hides a good one."""
        out: dict[str, type] = {}
        raw = getattr(func, "__annotations__", {}) or {}
        module_globals = getattr(func, "__globals__", {})
        for name, raw_ann in raw.items():
            hinted: object | None = raw_ann if isinstance(raw_ann, type) else None
            ann_text = (
                raw_ann
                if isinstance(raw_ann, str)
                else getattr(raw_ann, "__name__", "")
            )
            if hinted is None and isinstance(raw_ann, str):
                try:
                    hinted = eval(raw_ann, module_globals)  # noqa: S307 - project's own annotation source
                except Exception:  # noqa: BLE001
                    hinted = None
            if hinted is not None and not isinstance(hinted, type):
                # Unwrap `X | None` / `Optional[X]` to the one real
                # non-None member -- a structural fact from the type
                # itself (typing.get_args), not a guess.
                args = [a for a in typing.get_args(hinted) if a is not type(None)]
                if len(args) == 1 and isinstance(args[0], type):
                    hinted = args[0]
            if isinstance(hinted, type):
                impl = self.protocol_implementer.get(hinted, hinted)
                if isinstance(impl, type):
                    out[name] = impl
                    continue
            for proto_name, impl2 in self.protocol_name_implementer.items():
                if proto_name in ann_text:
                    out[name] = impl2
                    break
        return out

    def _enclosing_function_param_hints(
        self, real_func: object, g: dict[str, object]
    ) -> dict[str, type]:
        """A lambda carries no annotations of its own -- but
        ``inspect.getsource`` on a lambda returns the whole *enclosing
        statement* (a well-known Python quirk), which is exactly why a
        registration call's own ``container``/``resolver`` parameter
        name can appear in the same parsed tree as the lambda without
        being resolvable from the lambda's own closure (it is not a
        free variable of the lambda -- the lambda's own body never
        references it). A lambda's ``__qualname__`` names its lexically
        enclosing function (e.g. ``register_agents.<locals>.<lambda>``);
        that enclosing function's own real, annotated parameters are a
        structural fact, not a name guess, and are what actually let
        the outer part of the shared statement resolve correctly."""
        qualname = getattr(real_func, "__qualname__", "")
        if not qualname.endswith(".<lambda>"):
            return {}
        parts = qualname.split(".<locals>.")
        if len(parts) < 2:
            return {}
        enclosing_name = parts[0].rsplit(".", 1)[-1]
        enclosing = g.get(enclosing_name)
        if not inspect.isfunction(enclosing):
            return {}
        return self._real_param_types(enclosing)

    def _return_type_of(self, obj: object) -> type | None:
        """The real return type of a resolved callable, read from its
        own annotation -- generalizes ``_STDLIB_RETURN_TYPES`` to any
        project or third-party callable with a real return annotation,
        rather than requiring a hand-listed table entry for every one
        (Task 38.7 Category C/D). Per-callable, never letting one
        callable's unresolvable forward reference hide another's real
        annotation (the same discipline ``_real_param_types`` already
        uses). A generic alias (``Registration[T]``) unwraps to its
        origin class; an ``X | None`` union unwraps to its one non-None
        member the same way a parameter annotation already does."""
        try:
            hints = typing.get_type_hints(obj)
        except Exception:  # noqa: BLE001
            return None
        ret = hints.get("return")
        if ret is None:
            return None
        origin = typing.get_origin(ret)
        if origin is not None:
            ret = origin
        if not isinstance(ret, type):
            args = [a for a in typing.get_args(ret) if a is not type(None)]
            if len(args) == 1 and isinstance(args[0], type):
                ret = args[0]
        return ret if isinstance(ret, type) else None

    def _eval_annotation_head(
        self, ann: ast.expr, g: dict[str, object]
    ) -> type | None:
        """The outermost class an annotation AST node names --
        ``dict[str, X]`` -> ``dict``, ``list[X]`` -> ``list``, ``str`` ->
        ``str``, ``X | None`` -> ``X``. Reads the annotation's own AST
        structure directly (never evaluates it as a runtime value), so
        this works under ``from __future__ import annotations`` (a
        string annotation) without any forward-reference/generic-erasure
        concern (Task 38.7 Category C subscript-target chains)."""
        if isinstance(ann, ast.Subscript):
            return self._eval_annotation_head(ann.value, g)
        if isinstance(ann, ast.Name):
            obj = g.get(ann.id) or getattr(builtins, ann.id, None)
            return obj if inspect.isclass(obj) else None
        if isinstance(ann, ast.BinOp) and isinstance(ann.op, ast.BitOr):
            left = self._eval_annotation_head(ann.left, g)
            right = self._eval_annotation_head(ann.right, g)
            candidates = [t for t in (left, right) if t is not None]
            candidates = [t for t in candidates if t is not type(None)]
            return candidates[0] if len(candidates) == 1 else None
        return None

    def _eval_dict_value_head(
        self, ann: ast.expr, g: dict[str, object]
    ) -> type | None:
        """For a ``dict[K, V]`` annotation, ``V``'s own outermost class
        -- ``dict[str, list[str]]`` -> ``list``. What
        ``container_expr[key].method(...)`` needs to resolve ``.method``
        against, since Python's runtime generics are erased and the
        declared annotation's AST is the only place this information
        survives (Task 38.7 Category C subscript-target chains)."""
        if isinstance(ann, ast.Subscript) and isinstance(ann.value, ast.Name):
            if ann.value.id == "dict" and isinstance(ann.slice, ast.Tuple):
                if len(ann.slice.elts) == 2:
                    return self._eval_annotation_head(ann.slice.elts[1], g)
        return None

    def _none_guarded_names(self, tree: ast.Module) -> frozenset[str]:
        """Names ``V`` for which this function's own body contains an
        ``if V is None: <return/raise>`` guard at statement level --
        exactly (and only) the shape that makes narrowing ``V`` from
        ``X | None`` to ``X`` for the rest of the enclosing block sound.
        No other shape (an ``if V:`` truthiness check, a guard that does
        not end in return/raise, a guard on a *different* name) is
        recognized -- this proves narrowing, it does not assume the
        non-``None`` branch was ever checked (Task 38.7 Category C
        flow-sensitive narrowing)."""
        guarded: set[str] = set()
        for node in _shallow_descendants(tree):
            if not isinstance(node, ast.If):
                continue
            test = node.test
            if not (
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and len(test.ops) == 1
                and isinstance(test.ops[0], ast.Is)
                and len(test.comparators) == 1
                and isinstance(test.comparators[0], ast.Constant)
                and test.comparators[0].value is None
            ):
                continue
            if node.body and isinstance(node.body[-1], (ast.Return, ast.Raise)):
                guarded.add(test.left.id)
        return frozenset(guarded)

    def _resolve_object_chain(
        self, expr: ast.expr, g: dict[str, object], loc: dict[str, object]
    ) -> object:
        """A dotted attribute chain rooted in a plain global/closure name
        (e.g. ``os.path`` -> the real ``posixpath`` module object) --
        resolved via real ``getattr``, not type inference, since a
        module is not a ``type`` (Task 38.7 multi-hop module-attribute
        chains such as ``os.path.dirname(...)``)."""
        if isinstance(expr, ast.Name):
            return loc.get(expr.id) or g.get(expr.id)
        if isinstance(expr, ast.Attribute):
            base_obj = self._resolve_object_chain(expr.value, g, loc)
            if base_obj is not None:
                return getattr(base_obj, expr.attr, None)
        return None

    def _infer_type(
        self,
        expr: ast.expr,
        g: dict[str, object],
        loc: dict[str, object],
        owner_class: type | None,
        param_hints: dict[str, type],
        local_var_types: dict[str, type],
    ) -> type | None:
        """Best-effort static type of an arbitrary expression -- the
        shared engine behind multi-hop attribute/call/subscript chains
        (Task 38.7 Categories B/C/D): ``x.y().z``, ``d[k].m()``,
        ``"...".join``. Recurses on the base expression so a chain
        resolves the same way whether it is the outermost call or one
        hop in."""
        if isinstance(expr, ast.Name):
            if expr.id in local_var_types:
                return local_var_types[expr.id]
            if expr.id in param_hints:
                return param_hints[expr.id]
            if expr.id in ("self", "cls") and owner_class is not None:
                return owner_class
            return None
        if isinstance(expr, ast.Constant) and expr.value is not None:
            return type(expr.value)
        if isinstance(expr, ast.Attribute):
            if (
                isinstance(expr.value, ast.Name)
                and expr.value.id == "self"
                and owner_class is not None
                and (owner_class, expr.attr) in self.instance_attribute_types
            ):
                return self.instance_attribute_types[(owner_class, expr.attr)]
            base_type = self._infer_type(
                expr.value, g, loc, owner_class, param_hints, local_var_types
            )
            if base_type is not None:
                bt_mod = getattr(base_type, "__module__", None)
                bt_qn = getattr(base_type, "__qualname__", None)
                key = f"{bt_mod}.{bt_qn}.{expr.attr}"
                if key in _ATTR_RETURN_TYPES:
                    return _ATTR_RETURN_TYPES[key]
            return None
        if isinstance(expr, ast.Call):
            callee_obj: object = None
            if isinstance(expr.func, ast.Name):
                obj = loc.get(expr.func.id) or g.get(expr.func.id)
                if inspect.isclass(obj):
                    return obj
                callee_obj = obj
            elif isinstance(expr.func, ast.Attribute):
                base_type = self._infer_type(
                    expr.func.value, g, loc, owner_class, param_hints, local_var_types
                )
                if base_type is not None:
                    callee_obj = getattr(base_type, expr.func.attr, None)
            if callee_obj is not None:
                # `module_and_qualname` (not a raw `__module__` read) --
                # a C method like `str.strip`/`dict.get` carries no
                # `__module__` of its own; it falls back to its
                # `__objclass__`'s module, the same identity
                # `classify_callable` itself uses.
                mod_name, qname = module_and_qualname(callee_obj)
                key2 = f"{mod_name}.{qname}" if mod_name and qname else qname
                if key2 in _STDLIB_RETURN_TYPES:
                    return _STDLIB_RETURN_TYPES[key2]
                return self._return_type_of(callee_obj)
            return None
        return None

    def _collect_local_var_types(
        self,
        tree: ast.Module,
        g: dict[str, object],
        loc: dict[str, object],
        owner_class: type | None,
        param_hints: dict[str, type],
    ) -> tuple[dict[str, type], dict[str, type]]:
        """Returns ``(local_var_types, subscript_value_types)`` --
        ``subscript_value_types`` is a container-local's ``dict[K, V]``
        value-type head, keyed by the container's own name, for
        resolving ``container_expr[key].method(...)`` (Task 38.7
        Category C)."""
        out: dict[str, type] = {}
        subscript_value_types: dict[str, type] = {}
        guarded = self._none_guarded_names(tree)
        for node in _shallow_descendants(tree):
            if (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.annotation is not None
            ):
                name = node.target.id
                is_union = isinstance(node.annotation, ast.BinOp) and isinstance(
                    node.annotation.op, ast.BitOr
                )
                # A `X | None`-annotated local is only narrowed to `X`
                # once a real `if name is None: return/raise` guard
                # proves it -- never assumed just because the code
                # "probably" checked it (Task 38.7 Category C).
                if not is_union or name in guarded:
                    head = self._eval_annotation_head(node.annotation, g)
                    if head is not None:
                        out[name] = head
                dict_value_head = self._eval_dict_value_head(node.annotation, g)
                if dict_value_head is not None:
                    subscript_value_types[name] = dict_value_head
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Call)
            ):
                callee_obj = self._resolve_assign_callee(
                    node.value.func, g, loc, owner_class, out
                )
                if inspect.isclass(callee_obj):
                    out[node.targets[0].id] = callee_obj
                elif callee_obj is not None:
                    mod_name = getattr(callee_obj, "__module__", None)
                    qname = getattr(callee_obj, "__qualname__", None)
                    key = f"{mod_name}.{qname}" if mod_name and qname else None
                    if key in _STDLIB_RETURN_TYPES:
                        out[node.targets[0].id] = _STDLIB_RETURN_TYPES[key]
                    else:
                        rt = self._return_type_of(callee_obj)
                        if rt is not None:
                            out[node.targets[0].id] = rt
            # Provider-callback type inference: a Lambda passed as the
            # provider argument of a registration call has its own sole
            # parameter typed Resolver -- a structural fact read from
            # core.interfaces.Provider = Callable[[Resolver], T] and the
            # registration method signatures, never a name-based guess.
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                base = node.func.value
                base_type: type | None = None
                if isinstance(base, ast.Name):
                    base_type = param_hints.get(base.id) or out.get(base.id)
                    if base_type is None:
                        obj = loc.get(base.id) or g.get(base.id)
                        if inspect.isclass(obj):
                            base_type = obj
                if (
                    base_type is not None
                    and base_type in self.protocol_implementer.values()
                    and node.func.attr in _REGISTRATION_METHODS
                ):
                    for arg in node.args:
                        if isinstance(arg, ast.Lambda) and arg.args.args:
                            out[arg.args.args[0].arg] = base_type
        return out, subscript_value_types

    def _resolve_alias_rhs(
        self,
        expr: ast.expr,
        g: dict[str, object],
        loc: dict[str, object],
        local_var_types: dict[str, type],
    ) -> object:
        """The live callable a local callable-alias's RHS names -- a bare
        ``Name`` or a single-level ``Attribute`` on a ``Name``, resolved
        purely through the walker's existing global/closure/
        local-variable-type-inference mechanisms (never a new one, never
        executing the expression or invoking an unknown descriptor --
        only ``getattr`` on an object/type this walker already resolved
        by its own established rules)."""
        if isinstance(expr, ast.Name):
            if expr.id in loc:
                return loc[expr.id]
            if expr.id in g:
                return g[expr.id]
            return getattr(builtins, expr.id, None)
        if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
            base_name = expr.value.id
            if base_name in local_var_types:
                base_type = local_var_types[base_name]
                if hasattr(base_type, expr.attr):
                    return getattr(base_type, expr.attr)
            base_obj = loc.get(base_name) or g.get(base_name)
            if base_obj is not None and hasattr(base_obj, expr.attr):
                return getattr(base_obj, expr.attr)
        return None

    def _collect_local_callable_aliases(
        self,
        tree: ast.Module,
        g: dict[str, object],
        loc: dict[str, object],
        local_var_types: dict[str, type],
    ) -> dict[str, tuple[object, int]]:
        """Task 38.7 local-callable-alias mechanism -- the smallest
        conservative shape, deliberately not full control-flow analysis:
        a plain local ``x = y`` / ``x: T = y`` assignment qualifies only
        if *all* of the following hold --

        * ``x`` is a bare ``Name`` target;
        * the RHS ``y`` is a ``Name`` or single-level ``Attribute`` that
          :meth:`_resolve_alias_rhs` resolves to a real, callable object;
        * the assignment is a *direct* statement of the function's own
          body -- never nested inside an ``if``/``for``/``while``/
          ``try``/``with`` block, so it trivially dominates every later
          statement in program order without needing real control-flow
          analysis;
        * ``x`` is written **exactly once** anywhere in the same function
          scope (excluding nested functions/lambdas) -- a second write of
          *any* kind (``Assign``, ``AnnAssign``, ``AugAssign``,
          ``NamedExpr``, or ``Delete``) disqualifies the name entirely,
          regardless of whether that write is itself part of a candidate
          assignment or occurs before or after the qualifying one.

        Returns ``name -> (resolved_callable, definition_lineno)`` --
        the caller is responsible for also checking that a given call
        site's own line number is strictly after ``definition_lineno``
        (definite assignment before use; this mechanism does no
        reachability analysis beyond that one ordering check).
        """
        if not tree.body or not isinstance(
            tree.body[0], (ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            return {}
        root = tree.body[0]
        root_body_ids = {id(stmt) for stmt in root.body}

        write_counts: dict[str, int] = {}
        candidates: dict[str, tuple[ast.stmt, object]] = {}

        for node in _shallow_descendants(tree):
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        write_counts[tgt.id] = write_counts.get(tgt.id, 0) + 1
                if (
                    len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and id(node) in root_body_ids
                ):
                    resolved = self._resolve_alias_rhs(
                        node.value, g, loc, local_var_types
                    )
                    if resolved is not None and callable(resolved):
                        candidates[node.targets[0].id] = (node, resolved)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                write_counts[node.target.id] = write_counts.get(node.target.id, 0) + 1
                if node.value is not None and id(node) in root_body_ids:
                    resolved = self._resolve_alias_rhs(
                        node.value, g, loc, local_var_types
                    )
                    if resolved is not None and callable(resolved):
                        candidates[node.target.id] = (node, resolved)
            elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
                write_counts[node.target.id] = write_counts.get(node.target.id, 0) + 1
            elif isinstance(node, ast.NamedExpr) and isinstance(node.target, ast.Name):
                write_counts[node.target.id] = write_counts.get(node.target.id, 0) + 1
            elif isinstance(node, ast.Delete):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        write_counts[tgt.id] = write_counts.get(tgt.id, 0) + 1

        out: dict[str, tuple[object, int]] = {}
        for name, (def_node, resolved) in candidates.items():
            if write_counts.get(name, 0) == 1:
                out[name] = (resolved, def_node.lineno)
        return out

    def _resolve_assign_callee(
        self,
        func: ast.expr,
        g: dict[str, object],
        loc: dict[str, object],
        owner_class: type | None,
        local_var_types: dict[str, type],
    ) -> object:
        """The live callable an assignment's RHS ``func(...)`` calls --
        single-hop (``f()``/``obj.method()``) or the ``self.<attr>.<method>()``
        two-hop shape ``instance_attribute_types`` already tracks (e.g.
        ``registration = self._registry.get(key)``, Task 38.7 Category D)."""
        if isinstance(func, ast.Name):
            return loc.get(func.id) or g.get(func.id)
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            base_obj = loc.get(func.value.id) or g.get(func.value.id)
            return getattr(base_obj, func.attr, None)
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Attribute)
            and isinstance(func.value.value, ast.Name)
            and func.value.value.id == "self"
            and owner_class is not None
            and (owner_class, func.value.attr) in self.instance_attribute_types
        ):
            attr_type = self.instance_attribute_types[(owner_class, func.value.attr)]
            return getattr(attr_type, func.attr, None)
        return None

    def _super_init_target(
        self, owner_class: type | None
    ) -> tuple[type | None, object | None]:
        if owner_class is None:
            return None, None
        mro = owner_class.__mro__
        try:
            idx = mro.index(owner_class)
        except ValueError:
            return None, None
        for base in mro[idx + 1 :]:
            if "__init__" in base.__dict__:
                return base, base.__dict__["__init__"]
        return None, None

    def _resolve_target(
        self,
        node: ast.Call,
        g: dict[str, object],
        loc: dict[str, object],
        owner_class: type | None,
        param_hints: dict[str, type],
        local_var_types: dict[str, type],
        local_helper_names: frozenset[str] = frozenset(),
        subscript_value_types: dict[str, type] | None = None,
        first_param_name: str | None = None,
        local_callable_aliases: dict[str, tuple[object, int]] | None = None,
    ) -> tuple[object, str]:
        fn = node.func
        subscript_value_types = subscript_value_types or {}
        local_callable_aliases = local_callable_aliases or {}
        try:
            if isinstance(fn, ast.Name):
                if fn.id in local_helper_names:
                    return "local-helper", "local-helper-inline"
                if fn.id in loc:
                    return loc[fn.id], "closure-lookup"
                if fn.id in g:
                    return g[fn.id], "global-lookup"
                # A classmethod's own `cls` (or an instance method's
                # `self`), called directly -- `cls(normalized)` inside a
                # classmethod IS a construction of the owning class. Uses
                # the same tracked owner_class context every other
                # self/cls resolution already relies on, not a name guess
                # (Task 38.7 Category C).
                if fn.id in ("cls", "self") and owner_class is not None:
                    return owner_class, "owner-class-direct-call"
                # Local callable-alias (Task 38.7): `_len = len; _len(x)`,
                # `emit = code.append; emit(x)` -- resolved before the
                # builtins fallback below, so it never shadows any of the
                # already-checked, higher-confidence mechanisms above.
                # `node.lineno > def_lineno` is the mechanism's one
                # ordering check -- definite assignment before use, no
                # broader control-flow analysis (see
                # `_collect_local_callable_aliases`).
                if fn.id in local_callable_aliases:
                    resolved, def_lineno = local_callable_aliases[fn.id]
                    if node.lineno > def_lineno:
                        return resolved, "local-callable-alias"
                return getattr(builtins, fn.id, None), "builtins-lookup"

            if isinstance(fn, ast.Attribute):
                base = fn.value
                if isinstance(base, ast.Name):
                    base_name = base.id
                    # Not every instance method actually names its own
                    # first parameter "self" -- pydantic's own
                    # BaseModel.__init__ names it `__pydantic_self__`, a
                    # real, observed third-party convention Task 38.7
                    # Category A's broadened source-walking now reaches.
                    # `first_param_name` is this walked function's own
                    # real first parameter, whatever it is named, not a
                    # hardcoded literal.
                    is_self_like = base_name in ("self", "cls") or (
                        first_param_name is not None and base_name == first_param_name
                    )

                    if is_self_like and owner_class is not None:
                        if hasattr(owner_class, fn.attr):
                            return getattr(
                                owner_class, fn.attr
                            ), "owner-class-attribute"

                    if base_name in local_var_types:
                        obj = local_var_types[base_name]
                        if hasattr(obj, fn.attr):
                            return getattr(
                                obj, fn.attr
                            ), "local-variable-type-inference"

                    if base_name in param_hints:
                        impl = param_hints[base_name]
                        if inspect.isclass(impl) and hasattr(impl, fn.attr):
                            return getattr(
                                impl, fn.attr
                            ), "parameter-annotation-substitution"

                    global_or_closure_obj = loc.get(base_name) or g.get(base_name)
                    if global_or_closure_obj is not None and hasattr(
                        global_or_closure_obj, fn.attr
                    ):
                        return (
                            getattr(global_or_closure_obj, fn.attr),
                            "global-or-closure-attribute",
                        )

                    builtin_obj = getattr(builtins, base_name, None)
                    if builtin_obj is not None and hasattr(builtin_obj, fn.attr):
                        return getattr(builtin_obj, fn.attr), "builtins-attribute"

                if isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name):
                    is_self_like_base = base.value.id in ("self", "cls") or (
                        first_param_name is not None
                        and base.value.id == first_param_name
                    )
                    # `<self-like>.__class__.<attr>` -- e.g. pydantic's
                    # BaseModel.__init__ doing
                    # `__pydantic_self__.__class__._settings_build_values(...)`
                    # -- `.__class__` on the instance parameter IS the
                    # (sub)class already tracked as owner_class.
                    if (
                        is_self_like_base
                        and base.attr == "__class__"
                        and owner_class is not None
                        and hasattr(owner_class, fn.attr)
                    ):
                        return getattr(
                            owner_class, fn.attr
                        ), "self-dot-class-attribute"

                    if (
                        base.value.id == "self"
                        and owner_class is not None
                        and (owner_class, base.attr) in self.instance_attribute_types
                    ):
                        attr_type = self.instance_attribute_types[
                            (owner_class, base.attr)
                        ]
                        if hasattr(attr_type, fn.attr):
                            return getattr(
                                attr_type, fn.attr
                            ), "instance-attribute-type-table"

                    if (
                        self.provider_class is not None
                        and self.provider_owner_module is not None
                    ):
                        if (
                            base.value.id == "self"
                            and base.attr == "_provider"
                            and owner_class is not None
                            and owner_class.__module__ == self.provider_owner_module
                            and hasattr(self.provider_class, fn.attr)
                        ):
                            return getattr(
                                self.provider_class, fn.attr
                            ), "runtime-instance-assertion"

                # `container_expr[key].method(...)` -- the container's
                # own `dict[K, V]` annotation names V's outermost class
                # directly (Task 38.7 Category C subscript-target chains).
                if (
                    isinstance(base, ast.Subscript)
                    and isinstance(base.value, ast.Name)
                    and base.value.id in subscript_value_types
                ):
                    elem_type = subscript_value_types[base.value.id]
                    if hasattr(elem_type, fn.attr):
                        return getattr(
                            elem_type, fn.attr
                        ), "subscript-value-type-inference"

                # A string/bytes/etc. literal's own method
                # (`" -> ".join(...)`) -- the literal's Python type is
                # known directly from the AST constant, no inference
                # needed (Task 38.7 Category D).
                if isinstance(base, ast.Constant) and base.value is not None:
                    lit_type = type(base.value)
                    if hasattr(lit_type, fn.attr):
                        return getattr(lit_type, fn.attr), "literal-type-inference"

                # A dotted module-attribute chain (`os.path.dirname`) --
                # resolved via real getattr on the actual module/object
                # chain, not type inference (a module is not a `type`).
                if isinstance(base, ast.Attribute):
                    base_obj = self._resolve_object_chain(base, g, loc)
                    if base_obj is not None and hasattr(base_obj, fn.attr):
                        return getattr(
                            base_obj, fn.attr
                        ), "module-attribute-chain"

                # A chained call's own return value
                # (`value.strip().lower()`'s outer `.lower()`) -- resolve
                # the inner call's return type through the same
                # multi-hop engine used for local-variable assignment
                # inference (Task 38.7 Category C/D chained-method calls).
                if isinstance(base, (ast.Call, ast.Attribute)):
                    base_type = self._infer_type(
                        base, g, loc, owner_class, param_hints, local_var_types
                    )
                    if base_type is not None and hasattr(base_type, fn.attr):
                        return getattr(
                            base_type, fn.attr
                        ), "chained-expression-type-inference"
        except Exception:  # noqa: BLE001
            return None, "resolution-error"
        return None, "no-target"

    def _bind_call_site_locals(
        self,
        node: ast.Call,
        target: object,
        g: dict[str, object],
        loc: dict[str, object],
        local_var_types: dict[str, type] | None = None,
        mechanism: str | None = None,
    ) -> dict[str, object]:
        """Call-site specialization (Task 38.7 Category D): map this
        call's actual AST arguments to ``target``'s own parameter names,
        for every argument that is a bare Name whose real object is
        already known in the *caller's* own scope (a closure capturing a
        concrete class, e.g. ``ServiceContainer.register_class``'s
        ``_provider`` closing over ``target: type[T]`` and passing it
        into ``self._build(target, resolver)``). This substitutes from
        the caller's own KNOWN ARGUMENT VALUE at this one call site --
        distinct from (and a generalization beyond) resolving from a
        static parameter annotation, which cannot pin a generic
        ``cls: type[T]`` to one concrete class at all.

        ``local_var_types`` is the caller's own already-collected
        local-variable type table (e.g. ``source = Tokenizer(str)`` in
        ``re._parser.parse``) -- a third source, checked last, after
        ``loc`` (closure) and a global class. This never infers anything
        new and never executes anything: it only reads a *type* this
        walker's own :meth:`_collect_local_var_types` already derived
        for the caller, the same discipline every other propagation
        source here already follows.

        ``mechanism`` is the resolution mechanism :meth:`_resolve_target`
        used for *this* call -- checked for exactly one shape: when it
        is ``"local-variable-type-inference"``, ``target`` was reached
        via ``getattr(a_type, attr)`` on a *type* (local-variable-type
        inference never holds a live instance, only a type), which for
        an ordinary method yields the UNBOUND function -- its own first
        parameter is a receiver slot the AST call's explicit arguments
        never fill, so ``sig.bind_partial(*node.args)`` alone silently
        shifts every argument one position early (e.g.
        ``state.checklookbehindgroup(gid, source)`` binding ``self <-
        gid, gid <- source``, losing ``source`` entirely). Prepending
        the receiver's own AST expression (``node.func.value``) fixes
        this -- but only once ``inspect.getattr_static`` proves, without
        invoking anything, that the raw stored attribute is a plain
        Python ``function``: never a ``staticmethod`` (no receiver
        needed at all), never a ``classmethod`` (``getattr`` already
        returns it bound), and never a C descriptor or anything else
        ``getattr_static`` cannot cleanly classify -- left exactly as
        before, never guessed from a parameter's name."""
        args: list[ast.expr] = list(node.args)
        if (
            mechanism == "local-variable-type-inference"
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and local_var_types is not None
            and node.func.value.id in local_var_types
        ):
            receiver_type = local_var_types[node.func.value.id]
            try:
                raw_attr = inspect.getattr_static(receiver_type, node.func.attr)
            except AttributeError:
                raw_attr = None
            if inspect.isfunction(raw_attr):
                args = [node.func.value, *args]

        try:
            sig = inspect.signature(target)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return {}
        try:
            bound = sig.bind_partial(
                *args, **{kw.arg: kw.value for kw in node.keywords if kw.arg}
            )
        except TypeError:
            return {}
        local_var_types = local_var_types or {}
        out: dict[str, object] = {}
        for name, value_node in bound.arguments.items():
            if isinstance(value_node, ast.Name):
                if value_node.id in loc:
                    out[name] = loc[value_node.id]
                elif inspect.isclass(g.get(value_node.id)):
                    out[name] = g[value_node.id]
                elif value_node.id in local_var_types:
                    out[name] = local_var_types[value_node.id]
        return out

    def _record_call(
        self, site_label: str, node: ast.Call, target: object, mechanism: str
    ) -> IdentityVerdict | None:
        callee_text = ast.unparse(node.func)
        if mechanism == "local-helper-inline":
            # A local nested `def opt(key): ...`-style helper, verified
            # (Requirement 4) by inlining its own body into this same
            # walk rather than treating the call-to-it as an opaque,
            # separately-classified identity -- its calls already appear
            # as their own CallRecords in this same site. Its body is
            # already inlined (never a separate recursion target), so
            # this returns None rather than a verdict the caller might
            # otherwise use to decide whether to recurse.
            verdict = IdentityVerdict(
                None,
                None,
                "project_source_available",
                "local helper nested in this same function; its own body "
                "is inlined into this walk, not a separate identity",
                True,
            )
            self.call_records.append(
                CallRecord(site_label, callee_text, mechanism, verdict)
            )
            return None
        module, qualname = module_and_qualname(target)
        if inspect.isclass(target):
            qn = f"{module}.{qualname}"
            self.unified_nodes[qn] = target
        verdict = classify_callable(target, module=module, qualname=qualname)
        self.call_records.append(
            CallRecord(site_label, callee_text, mechanism, verdict)
        )
        return verdict

    def _specialization_key(
        self,
        owner_class: type | None,
        forced_locals: dict[str, object] | None,
        forced_param_hints: dict[str, type] | None,
    ) -> tuple[object, ...]:
        """A deterministic, hashable identity for the concrete values a
        call site pins a generic function's parameters to (Task 38.7's
        "distinct concrete specialization" requirement) -- built from
        real module+qualname identities, never `id()`/`repr()` of a raw
        object (both non-deterministic across runs/processes), so two
        runs of the same trace always produce the same key for the same
        specialization."""

        def ident(value: object) -> str:
            mod = getattr(value, "__module__", None)
            qn = getattr(value, "__qualname__", None)
            return f"{mod}.{qn}" if mod and qn else repr(type(value))

        parts: list[tuple[str, str, str]] = []
        if owner_class is not None:
            parts.append(("owner", "", ident(owner_class)))
        for name, val in sorted((forced_locals or {}).items()):
            parts.append(("local", name, ident(val)))
        for name, val in sorted((forced_param_hints or {}).items()):
            parts.append(("hint", name, ident(val)))
        return tuple(parts)

    def walk(
        self,
        func: object,
        site_label: str,
        owner_class: type | None = None,
        always_follow_modules: frozenset[str] = frozenset(),
        forced_param_hints: dict[str, type] | None = None,
        forced_locals: dict[str, object] | None = None,
    ) -> None:
        real_func = _underlying(func)
        fid = id(real_func)
        # No depth-based early return: the specialization-aware visited
        # set (below) is what actually prevents runaway recursion on a
        # cycle -- a depth cap would only re-introduce a bound with no
        # principled, package-neutral size, and Task 38.7 forbids one
        # tied to package origin specifically. The one remaining bound
        # is the total-work budget just below, package-neutral by
        # construction (a plain state count, not a per-branch counter).
        specialization_key = self._specialization_key(
            owner_class, forced_locals, forced_param_hints
        )
        visit_key = (fid, specialization_key)
        if visit_key in self.visited_funcs:
            return
        if len(self.visited_funcs) >= self.max_total_walk_steps:
            # The package-neutral total-work budget (Task 38.7's
            # termination requirement: "no depth cap tied to package
            # origin") -- applies identically whether this state is
            # project-owned or not. Deterministic, explicit termination:
            # recorded here, never silently dropped.
            self.depth_exceeded.append(site_label)
            return
        self.visited_funcs.add(visit_key)

        src = _dedented_source(real_func)
        if src is None:
            self.sites_without_source.append(site_label)
            return
        try:
            tree = ast.parse(src)
        except SyntaxError:
            self.sites_without_source.append(site_label + " (parse-error)")
            return

        g = getattr(real_func, "__globals__", {})
        loc: dict[str, object] = {}
        closure = getattr(real_func, "__closure__", None)
        code = getattr(real_func, "__code__", None)
        if closure and code:
            for name, cell in zip(
                code.co_freevars,
                closure,
                strict=True,
            ):
                try:
                    loc[name] = cell.cell_contents
                except ValueError:
                    pass
        # Call-site specialization (Task 38.7 Category D): the caller's
        # own KNOWN ARGUMENT VALUE at this one call site, bound to this
        # function's parameter names -- distinct from (and applied after)
        # closure capture, since it comes from the specific call, not
        # this function's own lexical scope.
        loc.update(forced_locals or {})

        param_hints = {
            **self._enclosing_function_param_hints(real_func, g),
            **self._real_param_types(real_func),
            **(forced_param_hints or {}),
        }
        local_var_types, subscript_value_types = self._collect_local_var_types(
            tree, g, loc, owner_class, param_hints
        )
        local_callable_aliases = self._collect_local_callable_aliases(
            tree, g, loc, local_var_types
        )
        local_helper_names = _local_helper_names(tree)
        first_param_name = code.co_varnames[0] if code and code.co_argcount else None

        for node in _shallow_descendants(tree):
            if not isinstance(node, ast.Call):
                continue

            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "__init__"
                and isinstance(node.func.value, ast.Call)
                and isinstance(node.func.value.func, ast.Name)
                and node.func.value.func.id == "super"
            ):
                base_cls, base_init = self._super_init_target(owner_class)
                callee_text = ast.unparse(node.func)
                if base_cls is not None and base_init is not None:
                    base_qn = f"{base_cls.__module__}.{base_cls.__qualname__}"
                    self.unified_nodes[base_qn] = base_cls
                    verdict = classify_callable(
                        base_init,
                        module=base_cls.__module__,
                        qualname=f"{base_cls.__qualname__}.__init__",
                    )
                    self.call_records.append(
                        CallRecord(
                            site_label, callee_text, "super-mro-resolution", verdict
                        )
                    )
                    self.walk(
                        base_init,
                        f"{site_label} -> super().__init__() [{base_cls.__qualname__}]",
                        owner_class=base_cls,
                        always_follow_modules=always_follow_modules,
                    )
                else:
                    self.call_records.append(
                        CallRecord(
                            site_label,
                            callee_text,
                            "super-mro-resolution",
                            IdentityVerdict(None, None, "unresolved", None, False),
                        )
                    )
                continue

            target, mechanism = self._resolve_target(
                node,
                g,
                loc,
                owner_class,
                param_hints,
                local_var_types,
                local_helper_names,
                subscript_value_types,
                first_param_name,
                local_callable_aliases,
            )
            call_verdict = self._record_call(site_label, node, target, mechanism)

            if inspect.isfunction(target) or inspect.ismethod(target):
                target_module = getattr(target, "__module__", None)
                # Requirement 4, extended by Task 38.7 Category A: ANY
                # callable with genuinely retrievable source is walked --
                # third-party origin is not, by itself, a reason to stop.
                # Recursion is not limited to project packages or a
                # hand-picked "mechanism" set, or a call like
                # logger.get_logger() -> configure() -> StreamHandler()
                # would stop at the first project-owned frame and never
                # reach the real forbidden operation two levels down (nor
                # would a third-party call like pydantic-settings' own
                # internals ever be checked at all). `visited_funcs`
                # ((callable, specialization) dedup, above) and
                # `max_total_walk_steps` (this function's own entry
                # guard, package-neutral by construction) bound this to a
                # fixed-point traversal -- no per-branch depth cap at
                # all.
                #
                # Recursion is warranted exactly when the verdict this
                # call just received is `project_source_available` --
                # source was found and this is exactly where a nested
                # forbidden call could hide. An `exact_identity_policy`
                # or `forbidden` verdict is already a complete, final
                # answer (a reviewed, individually-justified identity, or
                # a confirmed-forbidden one) -- walking further into a
                # *safe, no-I/O-by-definition* stdlib primitive like
                # `inspect.signature`'s own internals serves no audit
                # purpose and is exactly the unbounded-crawl risk the
                # termination requirement exists to prevent. An
                # `unresolved` verdict has no source to walk anyway.
                always_follow = target_module in always_follow_modules
                source_verdict = (
                    call_verdict is not None
                    and call_verdict.category == "project_source_available"
                )
                if source_verdict or always_follow:
                    qualname = getattr(target, "__qualname__", "")
                    new_owner = _owner_class_from_qualname(qualname, target_module)
                    self.walk(
                        target,
                        f"{site_label} -> {ast.unparse(node.func)}()",
                        owner_class=new_owner,
                        always_follow_modules=always_follow_modules,
                        forced_locals=self._bind_call_site_locals(
                            node, target, g, loc, local_var_types, mechanism
                        ),
                    )

    def classify_nodes(self) -> dict[str, NodeRecord]:
        """Walk every discovered node's __init__/__new__/__post_init__/
        default_factory to a fixed point. Call after seeding via
        :meth:`walk` for every entrypoint/registrar/provider."""
        node_records: dict[str, NodeRecord] = {}
        processed: set[str] = set()
        changed = True
        while changed:
            changed = False
            for qn, cls in list(self.unified_nodes.items()):
                if qn in processed:
                    continue
                processed.add(qn)
                changed = True

                is_dc = dataclasses.is_dataclass(cls)
                # `cls` is a `type`, not an instance -- comparing its
                # resolved (MRO-inherited) __init__/__new__ against
                # object's is exactly what "custom ctor?" means here, but
                # mypy's soundness check (a subclass instance's __init__
                # could differ from its declared type's) and its builtin
                # overload handling both assume an instance access, which
                # this deliberately is not.
                custom_init = cls.__init__ is not object.__init__  # type: ignore[misc]
                custom_new = cls.__new__ is not object.__new__  # type: ignore[comparison-overlap]
                # NamedTuple only ever synthesizes __new__ (never
                # __init__), so this is only ever checked -- and only
                # ever passed to classify_ctor -- for the __new__ side.
                is_nt_new = custom_new and is_namedtuple_generated_new(
                    cls, cls.__new__
                )

                def classify_ctor(
                    method: object,
                    cls: type = cls,
                    is_dc: bool = is_dc,
                    is_nt_new: bool = False,
                ) -> IdentityVerdict:
                    mod = defining_module_of_method(cls, method)
                    # A C-implemented slot wrapper (e.g. `dict.__new__`)
                    # has no __qualname__ at all -- module_and_qualname's
                    # __objclass__/__name__ fallback recovers it; a plain
                    # Python method (e.g. inherited `logging.Filter.__init__`)
                    # already has a real __qualname__ and this is a no-op.
                    qname = (
                        getattr(method, "__qualname__", None)
                        or module_and_qualname(method)[1]
                    )
                    return classify_callable(
                        method,
                        module=mod,
                        qualname=qname,
                        is_dataclass_generated=is_dc,
                        is_namedtuple_generated=is_nt_new,
                    )

                init_verdict = (
                    classify_ctor(cls.__init__)  # type: ignore[misc]
                    if custom_init
                    else IdentityVerdict(
                        None, None, "project_source_available", None, True
                    )
                )
                new_verdict = (
                    classify_ctor(cls.__new__, is_nt_new=is_nt_new)
                    if custom_new
                    else IdentityVerdict(
                        None, None, "project_source_available", None, True
                    )
                )
                if custom_init:
                    self.walk(cls.__init__, f"__init__:{qn}", owner_class=cls)  # type: ignore[misc]
                if custom_new:
                    self.walk(cls.__new__, f"__new__:{qn}", owner_class=cls)

                has_post_init = "__post_init__" in cls.__dict__
                post_init_verdict: IdentityVerdict | None = None
                if has_post_init:
                    post_init = cls.__dict__["__post_init__"]
                    post_init_verdict = classify_callable(
                        post_init,
                        module=cls.__module__,
                        qualname=f"{cls.__qualname__}.__post_init__",
                    )
                    self.walk(post_init, f"__post_init__:{qn}", owner_class=cls)

                factories: list[tuple[str, IdentityVerdict]] = []
                if is_dc:
                    for f in sorted(dataclasses.fields(cls), key=lambda fl: fl.name):
                        if f.default_factory is dataclasses.MISSING:
                            continue
                        factory = f.default_factory
                        if inspect.isclass(factory):
                            fqn = f"{factory.__module__}.{factory.__qualname__}"
                            self.unified_nodes[fqn] = factory
                            factories.append(
                                (
                                    f.name,
                                    classify_callable(
                                        factory,
                                        module=factory.__module__,
                                        qualname=factory.__qualname__,
                                    ),
                                )
                            )
                        else:
                            verdict = classify_callable(
                                factory,
                                module=getattr(factory, "__module__", None),
                                qualname=getattr(factory, "__qualname__", None),
                            )
                            factories.append((f.name, verdict))
                            self.walk(factory, f"default_factory:{qn}.{f.name}")

                node_records[qn] = NodeRecord(
                    qualname=qn,
                    is_dataclass=is_dc,
                    custom_init=custom_init,
                    custom_new=custom_new,
                    has_post_init=has_post_init,
                    init=init_verdict,
                    new=new_verdict,
                    post_init=post_init_verdict,
                    default_factories=tuple(factories),
                )
        return node_records


@dataclass(frozen=True, slots=True)
class TraceResult:
    roots_traced: int
    roots_with_error: tuple[tuple[str, str], ...]
    resolve_events: tuple[ResolveEvent, ...]
    distinct_provider_symbols: int
    distinct_result_types: int
    market_data_provider_runtime_type: str | None
    nodes: tuple[NodeRecord, ...]
    calls: tuple[CallRecord, ...]
    sites_without_source: tuple[str, ...]

    @property
    def nodes_unresolved(self) -> int:
        return sum(1 for n in self.nodes if n.unresolved)

    @property
    def calls_unresolved(self) -> int:
        return sum(1 for c in self.calls if c.verdict.category == "unresolved")


_MECHANISM_MODULES = frozenset(
    {"core.container", "core.registry", "app.planner", "app.preflight"}
)


def run_trace(*, max_total_walk_steps: int = _MAX_TOTAL_WALK_STEPS) -> TraceResult:
    """Run the full real-codebase fresh-container trace + static walk
    (Harness Requirements 1 and 3). Imports the real ``app``/``core``
    packages lazily, inside this function, so importing
    :mod:`audit_harness.trace` alone never touches production module
    state.

    ``max_total_walk_steps`` overrides the static walker's
    package-neutral total-work budget -- the real caller never needs
    to pass this (the module default is sized for the real trace); it
    exists so a test can inject a tiny budget and observe deterministic
    exhaustion without reproducing the full trace's node count."""
    from app import bootstrap as app_bootstrap
    from app import main as app_main
    from app import planner as app_planner
    from app import preflight as app_preflight
    from app import wiring
    from config import settings as config_settings
    from core.container import ServiceContainer
    from core.interfaces import Container, Registry, Resolver
    from core.registry import ServiceRegistry

    protocol_implementer: dict[object, type] = {
        Resolver: ServiceContainer,
        Container: ServiceContainer,
        Registry: ServiceRegistry,
    }
    protocol_name_implementer: dict[str, type] = {
        "Resolver": ServiceContainer,
        "Container": ServiceContainer,
        "Registry": ServiceRegistry,
    }

    safe_service_keys = wiring.SAFE_SERVICE_KEYS
    component_registrars = wiring.COMPONENT_REGISTRARS

    # -- Part A: 24 independent fresh-container traces --------------------
    all_resolve_events: list[ResolveEvent] = []
    providers_seen: dict[int, Callable[..., object]] = {}
    provider_symbol_counts: dict[str, int] = {}
    result_classes: dict[str, type] = {}
    result_instances_by_type: dict[str, object] = {}
    roots_traced = 0
    roots_with_error: list[tuple[str, str]] = []

    for root_key in sorted(safe_service_keys):
        container = ServiceContainer()
        try:
            for cid in sorted(component_registrars):
                component_registrars[cid](container)
        except Exception as exc:  # noqa: BLE001
            roots_with_error.append((root_key, f"registration: {exc!r}"))
            continue

        orig_resolve = ServiceContainer.resolve

        def make_traced(
            orig: Callable[..., object], root_id: str
        ) -> Callable[..., object]:
            def traced(self: object, key: type) -> object:
                registration = self._registry.get(key)  # type: ignore[attr-defined]
                provider = registration.provider
                result = orig(self, key)
                rt = type(result)
                qn = f"{rt.__module__}.{rt.__qualname__}"
                result_classes[qn] = rt
                result_instances_by_type.setdefault(qn, result)
                sym = getattr(provider, "__qualname__", repr(provider))
                provider_symbol_counts[sym] = provider_symbol_counts.get(sym, 0) + 1
                providers_seen[id(_underlying(provider))] = provider
                all_resolve_events.append(
                    ResolveEvent(
                        root=root_id,
                        key=f"{key.__module__}.{key.__qualname__}",
                        provider_symbol=sym,
                        result_type=qn,
                    )
                )
                return result

            return traced

        ServiceContainer.resolve = make_traced(orig_resolve, root_key)  # type: ignore[method-assign, assignment]
        try:
            container.resolve(safe_service_keys[root_key])
            roots_traced += 1
        except Exception as exc:  # noqa: BLE001
            roots_with_error.append((root_key, f"resolve: {exc!r}"))
        finally:
            ServiceContainer.resolve = orig_resolve  # type: ignore[method-assign]

    # A provider registered but never resolved by any of the 24 roots
    # (e.g. every framework's `Engine`, registered alongside its
    # `Manager` but never itself a required dependency of anything the
    # SAFE_SERVICE_KEYS roots pull in) is never captured by the
    # traced_resolve wrapper above -- that wrapper only fires for keys
    # actually resolved. `container.register_singleton(X, provider)`
    # still stores `provider` in the registry's own Registration record
    # regardless of whether X is ever resolved, so one extra,
    # representative, fully-registered container (registrations are
    # identical across all 24 roots; only the resolved root differs) is
    # built here solely to read every registered provider directly from
    # its registry -- not to resolve anything from it.
    discovery_container = ServiceContainer()
    for cid in sorted(component_registrars):
        component_registrars[cid](discovery_container)
    for key in discovery_container._registry:
        registration = discovery_container._registry.get(key)
        discovered_provider = registration.provider
        sym = getattr(discovered_provider, "__qualname__", repr(discovered_provider))
        providers_seen.setdefault(
            id(_underlying(discovered_provider)), discovered_provider
        )
        provider_symbol_counts.setdefault(sym, 0)

    mdps_qn = "market_data.service.MarketDataPipelineService"
    mdps_instance = result_instances_by_type.get(mdps_qn)
    provider_attr_type = (
        type(mdps_instance._provider) if mdps_instance is not None else None  # type: ignore[attr-defined]
    )
    market_data_provider_runtime_type = (
        f"{provider_attr_type.__module__}.{provider_attr_type.__qualname__}"
        if provider_attr_type is not None
        else None
    )

    # -- Part B: AST call inventory with identity-first resolution -------
    walker = StaticWalker(
        protocol_implementer=protocol_implementer,
        protocol_name_implementer=protocol_name_implementer,
        provider_class=provider_attr_type,
        provider_owner_module="market_data.service",
        max_total_walk_steps=max_total_walk_steps,
    )
    walker.unified_nodes.update(result_classes)
    # Read directly from core/container.py and core/registry.py's own
    # __init__ source: ServiceContainer._registry is a Registry (sole
    # implementer ServiceRegistry); ServiceContainer._singletons/
    # _resolving and ServiceRegistry._registrations are plain dict/set
    # instance attributes -- not guessed, confirmed by direct reading.
    walker.instance_attribute_types.update(
        {
            (ServiceContainer, "_registry"): ServiceRegistry,
            (ServiceContainer, "_singletons"): dict,
            (ServiceContainer, "_resolving"): set,
            (ServiceRegistry, "_registrations"): dict,
        }
    )

    for cid in sorted(component_registrars):
        reg = component_registrars[cid]
        real = reg.func if isinstance(reg, functools.partial) else reg
        walker.walk(real, f"registrar:{cid}", always_follow_modules=_MECHANISM_MODULES)

    for pid, provider in providers_seen.items():
        # `Provider = Callable[[Resolver], T]` (core.interfaces) is the
        # type contract for *every* object registered as a provider --
        # a structural fact about anything captured via providers_seen
        # (Part A's real trace), not a name-based guess. This is what
        # lets a bare `lambda r: r.resolve(X)` resolve `r` correctly even
        # when inspect.getsource returns a truncated fragment that omits
        # the enclosing `container.register_singleton(...)` call entirely
        # (a real quirk observed for some lambda argument positions).
        forced: dict[str, type] = {}
        try:
            sig = inspect.signature(provider)
            params = list(sig.parameters.values())
            if len(params) == 1:
                forced[params[0].name] = ServiceContainer
        except (TypeError, ValueError):
            pass
        provider_qualname = getattr(provider, "__qualname__", "")
        walker.walk(
            provider,
            f"provider:{provider_qualname or pid}",
            always_follow_modules=_MECHANISM_MODULES,
            forced_param_hints=forced,
            owner_class=_owner_class_from_qualname(
                provider_qualname, getattr(provider, "__module__", None)
            ),
        )

    walker.walk(
        app_main.main,
        "entrypoint:app.main.main",
        always_follow_modules=_MECHANISM_MODULES,
    )
    walker.walk(
        config_settings.get_settings,
        "entrypoint:config.settings.get_settings",
        always_follow_modules=_MECHANISM_MODULES,
    )
    walker.walk(
        app_main._utc_now,
        "entrypoint:app.main._utc_now",
        always_follow_modules=_MECHANISM_MODULES,
    )
    walker.walk(
        wiring.build_configuration_view,
        "entrypoint:app.wiring.build_configuration_view",
        always_follow_modules=_MECHANISM_MODULES,
    )
    walker.walk(
        wiring.build_default_manifest,
        "entrypoint:app.wiring.build_default_manifest",
        always_follow_modules=_MECHANISM_MODULES,
    )
    walker.walk(
        app_bootstrap.run_dry_run_bootstrap,
        "entrypoint:app.bootstrap.run_dry_run_bootstrap",
        always_follow_modules=_MECHANISM_MODULES,
    )

    mechanism_targets: tuple[tuple[object, str, type | None], ...] = (
        (
            ServiceContainer.resolve,
            "mechanism:core.container.ServiceContainer.resolve",
            ServiceContainer,
        ),
        (
            ServiceContainer._build,
            "mechanism:core.container.ServiceContainer._build",
            ServiceContainer,
        ),
        (
            ServiceContainer.register,
            "mechanism:core.container.ServiceContainer.register",
            ServiceContainer,
        ),
        (
            ServiceContainer.register_class,
            "mechanism:core.container.ServiceContainer.register_class",
            ServiceContainer,
        ),
        (
            ServiceContainer.register_singleton,
            "mechanism:core.container.ServiceContainer.register_singleton",
            ServiceContainer,
        ),
        (
            ServiceContainer.register_factory,
            "mechanism:core.container.ServiceContainer.register_factory",
            ServiceContainer,
        ),
        (
            ServiceContainer.register_instance,
            "mechanism:core.container.ServiceContainer.register_instance",
            ServiceContainer,
        ),
        (
            ServiceContainer.create,
            "mechanism:core.container.ServiceContainer.create",
            ServiceContainer,
        ),
        (
            ServiceContainer.has,
            "mechanism:core.container.ServiceContainer.has",
            ServiceContainer,
        ),
        (
            ServiceContainer.reset,
            "mechanism:core.container.ServiceContainer.reset",
            ServiceContainer,
        ),
        (
            ServiceRegistry.register,
            "mechanism:core.registry.ServiceRegistry.register",
            ServiceRegistry,
        ),
        (
            ServiceRegistry.get,
            "mechanism:core.registry.ServiceRegistry.get",
            ServiceRegistry,
        ),
        (
            ServiceRegistry.contains,
            "mechanism:core.registry.ServiceRegistry.contains",
            ServiceRegistry,
        ),
        (
            ServiceRegistry.remove,
            "mechanism:core.registry.ServiceRegistry.remove",
            ServiceRegistry,
        ),
        (
            ServiceRegistry.clear,
            "mechanism:core.registry.ServiceRegistry.clear",
            ServiceRegistry,
        ),
        (app_planner.plan, "mechanism:app.planner.plan", None),
        (
            app_preflight.validate_service_keys,
            "mechanism:app.preflight.validate_service_keys",
            None,
        ),
        (app_preflight.run, "mechanism:app.preflight.run", None),
    )
    for target, label, owner in mechanism_targets:
        walker.walk(
            target, label, owner_class=owner, always_follow_modules=_MECHANISM_MODULES
        )

    node_records = walker.classify_nodes()

    # Task 38.7 termination requirement: "No silent truncation." The
    # package-neutral total-work budget is the walker's only traversal
    # bound (no depth cap of any kind); its exhaustion is not a root
    # trace, but `roots_with_error` is the one existing field
    # `build_report`'s Gate Rule already reads to force `exit_code`
    # nonzero -- reusing it (rather than adding a new schema field) is
    # what actually makes exhaustion block a clean-gate claim.
    work_budget_exhausted = sorted(set(walker.depth_exceeded))
    if work_budget_exhausted:
        roots_with_error.append(
            (
                "static_walk_budget_exceeded",
                f"total-work budget ({walker.max_total_walk_steps}) exhausted "
                f"at {len(work_budget_exhausted)} distinct site(s): "
                + "; ".join(work_budget_exhausted),
            )
        )

    return TraceResult(
        roots_traced=roots_traced,
        roots_with_error=tuple(sorted(roots_with_error)),
        resolve_events=tuple(
            sorted(
                all_resolve_events,
                key=lambda e: (e.root, e.key, e.provider_symbol, e.result_type),
            )
        ),
        distinct_provider_symbols=len(provider_symbol_counts),
        distinct_result_types=len(result_classes),
        market_data_provider_runtime_type=market_data_provider_runtime_type,
        nodes=tuple(sorted(node_records.values(), key=lambda n: n.qualname)),
        calls=tuple(
            sorted(
                walker.call_records,
                key=lambda c: (c.site, c.callee_text, c.verdict.category),
            )
        ),
        sites_without_source=tuple(sorted(set(walker.sites_without_source))),
    )
