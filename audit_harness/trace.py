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
import typing
from collections.abc import Callable
from dataclasses import dataclass

from audit_harness.identity import (
    PROJECT_TOP_LEVEL_PACKAGES as _PROJECT_PACKAGES,
)
from audit_harness.identity import (
    IdentityVerdict,
    classify_callable,
    defining_module_of_method,
    module_and_qualname,
)

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
#: assignment already does.
_STDLIB_RETURN_TYPES: dict[str, type] = {"inspect.signature": inspect.Signature}


def _underlying(func: object) -> object:
    unbound = getattr(func, "__func__", func)
    # Unwrap a @lru_cache/@cache decorator too -- its wrapper object has
    # no __globals__/__annotations__/__qualname__ of its own for our
    # purposes; inspect.getsource already follows __wrapped__
    # automatically, but attribute access does not.
    return getattr(unbound, "__wrapped__", unbound)


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
    ) -> None:
        self.visited_funcs: set[int] = set()
        self.call_records: list[CallRecord] = []
        self.unified_nodes: dict[str, type] = {}
        self.sites_without_source: list[str] = []
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

    def _collect_local_var_types(
        self,
        tree: ast.Module,
        g: dict[str, object],
        loc: dict[str, object],
        param_hints: dict[str, type],
    ) -> dict[str, type]:
        out: dict[str, type] = {}
        for node in _shallow_descendants(tree):
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Call)
            ):
                callee_obj: object = None
                if isinstance(node.value.func, ast.Name):
                    callee_obj = loc.get(node.value.func.id) or g.get(
                        node.value.func.id
                    )
                elif isinstance(node.value.func, ast.Attribute) and isinstance(
                    node.value.func.value, ast.Name
                ):
                    base_obj = loc.get(node.value.func.value.id) or g.get(
                        node.value.func.value.id
                    )
                    callee_obj = getattr(base_obj, node.value.func.attr, None)
                if inspect.isclass(callee_obj):
                    out[node.targets[0].id] = callee_obj
                else:
                    mod_name = getattr(callee_obj, "__module__", None)
                    qname = getattr(callee_obj, "__qualname__", None)
                    key = f"{mod_name}.{qname}" if mod_name and qname else None
                    if key in _STDLIB_RETURN_TYPES:
                        out[node.targets[0].id] = _STDLIB_RETURN_TYPES[key]
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
        return out

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
    ) -> tuple[object, str]:
        fn = node.func
        try:
            if isinstance(fn, ast.Name):
                if fn.id in local_helper_names:
                    return "local-helper", "local-helper-inline"
                if fn.id in loc:
                    return loc[fn.id], "closure-lookup"
                if fn.id in g:
                    return g[fn.id], "global-lookup"
                return getattr(builtins, fn.id, None), "builtins-lookup"

            if isinstance(fn, ast.Attribute):
                base = fn.value
                if isinstance(base, ast.Name):
                    base_name = base.id

                    if base_name in ("self", "cls") and owner_class is not None:
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
        except Exception:  # noqa: BLE001
            return None, "resolution-error"
        return None, "no-target"

    def _record_call(
        self, site_label: str, node: ast.Call, target: object, mechanism: str
    ) -> None:
        callee_text = ast.unparse(node.func)
        if mechanism == "local-helper-inline":
            # A local nested `def opt(key): ...`-style helper, verified
            # (Requirement 4) by inlining its own body into this same
            # walk rather than treating the call-to-it as an opaque,
            # separately-classified identity -- its calls already appear
            # as their own CallRecords in this same site.
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
            return
        module, qualname = module_and_qualname(target)
        if inspect.isclass(target):
            qn = f"{module}.{qualname}"
            self.unified_nodes[qn] = target
        verdict = classify_callable(target, module=module, qualname=qualname)
        self.call_records.append(
            CallRecord(site_label, callee_text, mechanism, verdict)
        )

    def walk(
        self,
        func: object,
        site_label: str,
        depth: int = 0,
        max_depth: int = 10,
        owner_class: type | None = None,
        always_follow_modules: frozenset[str] = frozenset(),
        forced_param_hints: dict[str, type] | None = None,
    ) -> None:
        real_func = _underlying(func)
        fid = id(real_func)
        if fid in self.visited_funcs or depth > max_depth:
            return
        self.visited_funcs.add(fid)

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

        param_hints = {
            **self._enclosing_function_param_hints(real_func, g),
            **self._real_param_types(real_func),
            **(forced_param_hints or {}),
        }
        local_var_types = self._collect_local_var_types(tree, g, loc, param_hints)
        local_helper_names = _local_helper_names(tree)

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
                        depth + 1,
                        max_depth,
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
            )
            self._record_call(site_label, node, target, mechanism)

            if inspect.isfunction(target) or inspect.ismethod(target):
                target_module = getattr(target, "__module__", None)
                # Requirement 4: a project-owned callable's real source is
                # always retrieved and walked -- recursion is not limited
                # to the same module or a hand-picked "mechanism" set,
                # or a call like logger.get_logger() -> configure() ->
                # StreamHandler() would stop at the first project-owned
                # frame and never reach the real forbidden operation two
                # levels down.
                is_project_owned = (
                    target_module is not None
                    and target_module.split(".")[0] in _PROJECT_PACKAGES
                )
                always_follow = target_module in always_follow_modules
                if is_project_owned or always_follow:
                    new_owner: type | None = None
                    qualname = getattr(target, "__qualname__", "")
                    if "." in qualname:
                        owner_name = qualname.rsplit(".", 1)[0]
                        mod = (
                            sys.modules.get(target_module)
                            if target_module is not None
                            else None
                        )
                        candidate = getattr(mod, owner_name, None) if mod else None
                        new_owner = candidate if inspect.isclass(candidate) else None
                    self.walk(
                        target,
                        f"{site_label} -> {ast.unparse(node.func)}()",
                        depth + 1,
                        max_depth,
                        owner_class=new_owner,
                        always_follow_modules=always_follow_modules,
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

                def classify_ctor(
                    method: object, cls: type = cls, is_dc: bool = is_dc
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
                        method, module=mod, qualname=qname, is_dataclass_generated=is_dc
                    )

                init_verdict = (
                    classify_ctor(cls.__init__)  # type: ignore[misc]
                    if custom_init
                    else IdentityVerdict(
                        None, None, "project_source_available", None, True
                    )
                )
                new_verdict = (
                    classify_ctor(cls.__new__)
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


def run_trace() -> TraceResult:
    """Run the full real-codebase fresh-container trace + static walk
    (Harness Requirements 1 and 3). Imports the real ``app``/``core``
    packages lazily, inside this function, so importing
    :mod:`audit_harness.trace` alone never touches production module
    state."""
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
        walker.walk(
            provider,
            f"provider:{getattr(provider, '__qualname__', pid)}",
            always_follow_modules=_MECHANISM_MODULES,
            forced_param_hints=forced,
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
