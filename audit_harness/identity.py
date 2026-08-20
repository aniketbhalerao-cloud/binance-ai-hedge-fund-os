"""Harness Requirement 4: identity-first callable resolution and the
versioned exact-identity policy.

Every call/node the harness's static walk resolves to a live object is
classified into exactly one of three buckets -- there is no fourth:

1. ``project_source_available`` -- the object's defining module is one
   of the audited project packages and its real source was retrieved
   and walked. This is the only bucket for project-owned code.
2. ``exact_identity_policy`` -- the object's exact module+qualname
   identity matches a specific, individually-listed entry in
   :data:`EXACT_IDENTITY_POLICY`, each carrying its own safety
   rationale. This is never a name pattern or substring match -- it is
   a table of fully-qualified, versioned identities.
3. ``unresolved`` -- neither of the above. A project-owned object whose
   source could not be retrieved is unresolved, never silently
   accepted; an object matching no policy entry is unresolved.

A ``forbidden`` identity (``builtins.open`` and everything Harness
Requirement 6 patches to raise) is never eligible for bucket 2,
regardless of whether it would otherwise look like a well-known stdlib
identity -- this module refuses to classify a forbidden identity as
anything other than forbidden.
"""

from __future__ import annotations

import inspect
import textwrap
from dataclasses import dataclass
from typing import Literal

#: The 28 project packages Task 38.5 v4/v5 established as the audited
#: scope (24 wired frameworks + app/core/trading/exchange_adapters +
#: config/events, both load-bearing for the documented entrypoint
#: prefix and the DI mechanism).
PROJECT_TOP_LEVEL_PACKAGES: frozenset[str] = frozenset(
    {
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
        "config",
        "trading",
        "exchange_adapters",
        "events",
    }
)

#: Bumped whenever an entry is added, removed, or its rationale changes.
EXACT_IDENTITY_POLICY_VERSION = "2026-08-20.1"

#: module.qualname -> per-entry safety rationale. Every entry is a
#: single, individually reviewed, exact identity -- never a pattern.
EXACT_IDENTITY_POLICY: dict[str, str] = {
    "builtins.len": (
        "CPython stdlib builtin: pure length computation, no I/O by definition."
    ),
    "builtins.isinstance": (
        "CPython stdlib builtin: pure type check, no I/O by definition."
    ),
    "builtins.getattr": (
        "CPython stdlib builtin: pure attribute lookup, no I/O by definition."
    ),
    "builtins.sorted": "CPython stdlib builtin: pure sort, no I/O by definition.",
    "builtins.str": (
        "CPython stdlib builtin type constructor: pure value type, no I/O by "
        "definition."
    ),
    "builtins.tuple": (
        "CPython stdlib builtin type constructor: pure value type, no I/O by "
        "definition."
    ),
    "builtins.set": (
        "CPython stdlib builtin type constructor: pure value type, no I/O by "
        "definition."
    ),
    "builtins.any": "CPython stdlib builtin: pure predicate, no I/O by definition.",
    "builtins.sum": "CPython stdlib builtin: pure reduction, no I/O by definition.",
    "builtins.reversed": "CPython stdlib builtin: pure iterator, no I/O by definition.",
    "builtins.enumerate": (
        "CPython stdlib builtin: pure iterator, no I/O by definition."
    ),
    "builtins.super": (
        "CPython stdlib builtin: MRO dispatch mechanism, no I/O by definition."
    ),
    "builtins.object.__setattr__": (
        "CPython stdlib builtin: direct attribute write on an object already "
        "owned by the caller (the frozen-dataclass __post_init__ normalization "
        "pattern), no I/O by definition."
    ),
    "builtins.object.__init__": (
        "CPython stdlib builtin: no-op base constructor, no I/O by definition."
    ),
    "builtins.BaseException.__init__": (
        "CPython stdlib builtin: stores *args on the instance, no I/O by definition."
    ),
    "builtins.Exception.__init__": (
        "CPython stdlib builtin: stores *args on the instance, no I/O by definition."
    ),
    "_thread.allocate_lock": (
        "CPython stdlib synchronization primitive constructor "
        "(threading.Lock): in-process only, no I/O by definition."
    ),
    "asyncio.locks.Lock.__init__": (
        "CPython stdlib synchronization primitive constructor: in-process only, no I/O "
        "by definition."
    ),
    "decimal.Decimal.__new__": (
        "CPython stdlib numeric type constructor: pure value type, no I/O by "
        "definition."
    ),
    "collections.defaultdict.__init__": (
        "CPython stdlib container type constructor: pure value type, no I/O by "
        "definition."
    ),
    "collections.defaultdict.__new__": (
        "CPython stdlib container type constructor: pure value type, no I/O by "
        "definition."
    ),
    "dataclasses.field": (
        "CPython stdlib dataclass field-descriptor factory: pure metadata, no I/O by "
        "definition."
    ),
    "dataclasses.dataclass": (
        "CPython stdlib class decorator: pure metaprogramming, no I/O by definition."
    ),
    "functools.lru_cache": (
        "CPython stdlib memoizing-decorator factory: in-process only, no I/O by "
        "definition."
    ),
    "types.MappingProxyType": (
        "CPython stdlib read-only view constructor: pure, no I/O by definition."
    ),
    "inspect.signature": "CPython stdlib introspection: pure, no I/O by definition.",
    "typing.get_type_hints": (
        "CPython stdlib introspection: pure (reads __annotations__ / module globals "
        "only), no I/O by definition."
    ),
    "typing.cast": (
        "CPython stdlib typing helper: identity function at runtime, no I/O by "
        "definition."
    ),
    "_heapq.heapify": (
        "CPython stdlib pure in-memory heap operation "
        "(C-accelerated _heapq), no I/O by definition."
    ),
    "_heapq.heappush": (
        "CPython stdlib pure in-memory heap operation "
        "(C-accelerated _heapq), no I/O by definition."
    ),
    "_heapq.heappop": (
        "CPython stdlib pure in-memory heap operation "
        "(C-accelerated _heapq), no I/O by definition."
    ),
    "dict.fromkeys": (
        "CPython stdlib builtin: pure dict construction, no I/O by definition."
    ),
    "datetime.now": (
        "CPython stdlib builtin: reads the wall clock only when called as the "
        "documented _utc_now/clock boundary; the bare method identity itself performs "
        "no I/O beyond that permitted read (see app.main._utc_now)."
    ),
    "builtins.dict": (
        "CPython stdlib builtin type constructor: pure value type, no I/O by "
        "definition."
    ),
    "builtins.dict.get": (
        "CPython stdlib builtin: pure dict read, no I/O by definition."
    ),
    "builtins.dict.pop": (
        "CPython stdlib builtin: pure in-process dict mutation, no I/O by definition."
    ),
    "builtins.dict.clear": (
        "CPython stdlib builtin: pure in-process dict mutation, no I/O by definition."
    ),
    "builtins.dict.items": (
        "CPython stdlib builtin: pure dict view, no I/O by definition."
    ),
    "builtins.set.add": (
        "CPython stdlib builtin: pure in-process set mutation, no I/O by definition."
    ),
    "builtins.set.discard": (
        "CPython stdlib builtin: pure in-process set mutation, no I/O by definition."
    ),
    "builtins.str.rsplit": (
        "CPython stdlib builtin: pure string operation, no I/O by definition."
    ),
    "builtins.str.lower": (
        "CPython stdlib builtin: pure string operation, no I/O by definition."
    ),
    "builtins.mappingproxy": (
        "CPython stdlib read-only view type (types.MappingProxyType), pure, no I/O by "
        "definition."
    ),
    "builtins.KeyError": (
        "CPython stdlib builtin exception type constructor: pure, no I/O by definition."
    ),
    "builtins.TypeError": (
        "CPython stdlib builtin exception type constructor: pure, no I/O by definition."
    ),
    "builtins.RuntimeError": (
        "CPython stdlib builtin exception type constructor: pure, no I/O by definition."
    ),
    "decimal.Decimal": (
        "CPython stdlib numeric type constructor: pure value type, no I/O by "
        "definition."
    ),
    "collections.defaultdict": (
        "CPython stdlib container type constructor: pure value type, no I/O by "
        "definition."
    ),
    "datetime.timedelta": (
        "CPython stdlib value type constructor: pure, no I/O by definition."
    ),
    "asyncio.locks.Lock": (
        "CPython stdlib synchronization primitive constructor: in-process only, no I/O "
        "by definition."
    ),
    # __init__/__new__ of C-implemented builtin/stdlib types encountered
    # as constructed nodes (module is None for several of these C-level
    # __new__ slots -- see identity.module_and_qualname / _identity_key
    # -- so the key is the bare qualname for those).
    "builtins.Exception.__new__": (
        "CPython stdlib builtin: no-op allocation, no I/O by definition."
    ),
    "builtins.KeyError.__init__": (
        "CPython stdlib builtin exception: stores *args on the instance, no I/O by "
        "definition."
    ),
    "builtins.LookupError.__new__": (
        "CPython stdlib builtin: no-op allocation, no I/O by definition."
    ),
    "builtins.RuntimeError.__init__": (
        "CPython stdlib builtin exception: stores *args on the instance, no I/O by "
        "definition."
    ),
    "builtins.RuntimeError.__new__": (
        "CPython stdlib builtin: no-op allocation, no I/O by definition."
    ),
    "builtins.TypeError.__init__": (
        "CPython stdlib builtin exception: stores *args on the instance, no I/O by "
        "definition."
    ),
    "builtins.TypeError.__new__": (
        "CPython stdlib builtin: no-op allocation, no I/O by definition."
    ),
    "builtins.ValueError.__init__": (
        "CPython stdlib builtin exception: stores *args on the instance, no I/O by "
        "definition."
    ),
    "builtins.ValueError.__new__": (
        "CPython stdlib builtin: no-op allocation, no I/O by definition."
    ),
    "builtins.dict.__init__": (
        "CPython stdlib builtin: pure value-type construction, no I/O by definition."
    ),
    "builtins.dict.__new__": (
        "CPython stdlib builtin: no-op allocation, no I/O by definition."
    ),
    "builtins.enumerate.__new__": (
        "CPython stdlib builtin: no-op allocation, no I/O by definition."
    ),
    "builtins.list.__init__": (
        "CPython stdlib builtin: pure value-type construction, no I/O by definition."
    ),
    "builtins.list.__new__": (
        "CPython stdlib builtin: no-op allocation, no I/O by definition."
    ),
    "builtins.reversed.__new__": (
        "CPython stdlib builtin: no-op allocation, no I/O by definition."
    ),
    "builtins.set.__init__": (
        "CPython stdlib builtin: pure value-type construction, no I/O by definition."
    ),
    "builtins.set.__new__": (
        "CPython stdlib builtin: no-op allocation, no I/O by definition."
    ),
    "builtins.str.__new__": (
        "CPython stdlib builtin: no-op allocation, no I/O by definition."
    ),
    "builtins.super.__init__": (
        "CPython stdlib builtin: MRO-dispatch proxy construction, no I/O by definition."
    ),
    "builtins.super.__new__": (
        "CPython stdlib builtin: no-op allocation, no I/O by definition."
    ),
    "builtins.tuple.__new__": (
        "CPython stdlib builtin: no-op allocation, no I/O by definition."
    ),
    "builtins.mappingproxy.__new__": (
        "CPython stdlib builtin: no-op allocation, no I/O by definition."
    ),
    "datetime.timedelta.__new__": (
        "CPython stdlib builtin: no-op allocation, no I/O by definition."
    ),
    "logging.Filter.__init__": (
        "CPython stdlib logging infrastructure: stores a name string, no I/O by "
        "definition."
    ),
    "logging.Formatter.__init__": (
        "CPython stdlib logging infrastructure: stores formatting "
        "configuration, no I/O by definition."
    ),
    "logging.StreamHandler.__init__": (
        "CPython stdlib logging infrastructure: stores a stream reference only "
        "(defaults to the already-open sys.stderr, opens nothing itself); the "
        "construction *call site* is separately classified forbidden (Harness "
        "Requirement 6) since it is the entrypoint the runtime denial check "
        "patches -- this entry covers only this node's own constructor body, "
        "which performs no I/O of its own."
    ),
}

#: Identities that must never be classified as anything but forbidden,
#: regardless of whether they resemble a well-known stdlib shape.
#: Mirrors the set Harness Requirement 6 patches to raise.
FORBIDDEN_IDENTITIES: frozenset[str] = frozenset(
    {
        # Real resolved (module, qualname) pairs -- verified directly
        # (`obj.__module__`/`obj.__qualname__`), not assumed from the
        # dotted path a caller would type. Several of these differ from
        # the "logical" path because CPython backs the `os`-module
        # function with a C-implemented `posix`/`_io` function that
        # carries its *own* __module__ (e.g. `os.open` resolves to
        # `posix.open`, `open` resolves to `_io.open`, `asyncio.sleep`
        # resolves to `asyncio.tasks.sleep`).
        "builtins.open",
        "_io.open",
        "io.open",
        "posix.open",
        "os.fdopen",
        "posix.read",
        "posix.write",
        "os.makedirs",
        "posix.remove",
        "posix.system",
        "socket.socket",
        "socket.socket.connect",
        "socket.create_connection",
        "subprocess.Popen",
        "subprocess.run",
        "threading.Thread.start",
        "multiprocessing.process.BaseProcess.start",
        "time.sleep",
        "asyncio.tasks.sleep",
        "logging.StreamHandler",
        "logging.handlers.RotatingFileHandler",
        # RotatingFileHandler.__init__ itself calls FileHandler._open() by
        # default (delay=False) -- the constructor performs the real file
        # open, not merely the bare class-construction call site.
        "logging.handlers.RotatingFileHandler.__init__",
    }
)

Category = Literal[
    "project_source_available", "exact_identity_policy", "forbidden", "unresolved"
]


@dataclass(frozen=True, slots=True)
class IdentityVerdict:
    """The classification of one resolved live object."""

    module: str | None
    qualname: str | None
    category: Category
    rationale: str | None
    source_available: bool


def module_and_qualname(obj: object) -> tuple[str | None, str | None]:
    """Best-effort (module, qualname) for an arbitrary resolved callable.

    Most callables carry ``__module__``/``__qualname__`` directly. A few
    C-implemented descriptors do not: a ``wrapper_descriptor`` (e.g.
    ``object.__setattr__`` accessed via the class) exposes
    ``__objclass__``/``__name__`` instead of ``__module__``/
    ``__qualname__``. Falling back to those keeps such an identity
    exactly as specific (module + qualname), not a looser match.
    """
    module = getattr(obj, "__module__", None)
    qualname = getattr(obj, "__qualname__", None)
    if module is not None and qualname is not None:
        return module, qualname
    owner = getattr(obj, "__objclass__", None)
    name = getattr(obj, "__name__", None)
    if owner is not None and name is not None:
        return getattr(owner, "__module__", None), f"{owner.__qualname__}.{name}"
    return module, qualname


def _identity_key(module: str | None, qualname: str | None) -> str | None:
    if qualname is None:
        return None
    if module is None:
        # Some C-implemented builtin_function_or_method objects (e.g.
        # dict.fromkeys, datetime.now) report __module__ = None but a
        # real, unique __qualname__ -- use the qualname alone as the key
        # rather than discarding a resolvable identity.
        return qualname
    return f"{module}.{qualname}"


def defining_module_of_method(cls: type, method: object) -> str | None:
    """The module that actually implements ``method`` -- for an inherited
    slot wrapper (e.g. ``Exception.__init__``), that is the base class's
    own module, not the subclass's module."""
    owner = getattr(method, "__objclass__", None)
    if owner is not None:
        return getattr(owner, "__module__", None)
    qualname = getattr(method, "__qualname__", "")
    owner_name = qualname.rsplit(".", 1)[0] if "." in qualname else None
    if owner_name and owner_name != cls.__name__:
        for base in cls.__mro__:
            if base.__name__ == owner_name:
                return base.__module__
    return cls.__module__


def classify_callable(
    obj: object,
    *,
    module: str | None,
    qualname: str | None,
    is_dataclass_generated: bool = False,
) -> IdentityVerdict:
    """Classify one resolved live callable per Harness Requirement 4.

    ``is_dataclass_generated`` must be set by the caller only after
    structurally confirming the object is a ``@dataclass``-synthesized
    method (``dataclasses.is_dataclass`` true on the owning class and no
    hand-written override exists) -- this function does not re-derive
    that fact itself.
    """
    key = _identity_key(module, qualname)

    if key is not None and key in FORBIDDEN_IDENTITIES:
        return IdentityVerdict(
            module, qualname, "forbidden", "Named forbidden operation.", False
        )

    if module is not None and module.split(".")[0] in PROJECT_TOP_LEVEL_PACKAGES:
        try:
            src = inspect.getsource(obj)  # type: ignore[arg-type]
            textwrap.dedent(src)
            return IdentityVerdict(
                module, qualname, "project_source_available", None, True
            )
        except (OSError, TypeError):
            if is_dataclass_generated:
                return IdentityVerdict(
                    module,
                    qualname,
                    "exact_identity_policy",
                    (
                        "dataclass-synthesized method: exec-generated by the "
                        "@dataclass decorator, not read from a .py file; fields "
                        "already fully enumerated via dataclasses.fields(), no "
                        "arbitrary code possible in a synthesized __init__."
                    ),
                    False,
                )
            return IdentityVerdict(module, qualname, "unresolved", None, False)

    if key is not None and key in EXACT_IDENTITY_POLICY:
        return IdentityVerdict(
            module, qualname, "exact_identity_policy", EXACT_IDENTITY_POLICY[key], False
        )

    return IdentityVerdict(module, qualname, "unresolved", None, False)
