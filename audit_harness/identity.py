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

import collections
import inspect
import textwrap
import types
from dataclasses import dataclass
from typing import Literal

#: The 28 project packages Task 38.5 v4/v5 established as the audited
#: scope (24 wired frameworks + app/core/trading/exchange_adapters +
#: config/events, both load-bearing for the documented entrypoint
#: prefix and the DI mechanism). As of Task 38.7 Category A, this no
#: longer gates whether ``classify_callable`` attempts to retrieve an
#: object's source -- that attempt now applies uniformly to any
#: module, project-owned or third-party (see ``classify_callable``'s
#: own docstring). Retained as the documented definition of the
#: audited project scope for anything that still needs it.
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
#: 2026-08-22.1 (Task 38.7 Phase A): builtins.str.strip and
#: builtins.list.append added, each individually rationalized, per the
#: two ADR-032 Phase 0 authorizations recorded 2026-08-22
#: (Aniket Bhalerao -- project owner/reviewer). builtins.str.upper was
#: NOT added -- explicitly deferred, per that same ADR-032 entry.
EXACT_IDENTITY_POLICY_VERSION = "2026-08-22.1"

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
        "CPython stdlib read-only view constructor: pure, no I/O by definition. "
        "The type's own raw __module__/__qualname__ metadata reads "
        "'builtins'/'mappingproxy'; module_and_qualname() corrects it to this "
        "key before classification (Task 38.7 mappingproxy fix)."
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
    "builtins.list.append": (
        "CPython stdlib builtin: pure in-process list mutation, no I/O by "
        "definition -- same operational boundary as builtins.set.add/"
        "builtins.dict.pop/.clear above. ADR-032 Phase 0 authorization "
        "(2026-08-22, Aniket Bhalerao -- project owner/reviewer), recorded "
        "prior to this entry per Task 38.7's Two-Phase Provenance."
    ),
    "builtins.str.rsplit": (
        "CPython stdlib builtin: pure string operation, no I/O by definition."
    ),
    "builtins.str.lower": (
        "CPython stdlib builtin: pure string operation, no I/O by definition."
    ),
    "builtins.str.strip": (
        "CPython stdlib builtin: pure string operation, no I/O by "
        "definition -- same operational boundary as builtins.str.lower/"
        ".rsplit above. ADR-032 Phase 0 authorization (2026-08-22, Aniket "
        "Bhalerao -- project owner/reviewer), recorded prior to this entry "
        "per Task 38.7's Two-Phase Provenance."
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
        # `types.MappingProxyType` -- the only public, importable path to
        # this type -- carries its own C-level __module__/__qualname__ as
        # "builtins"/"mappingproxy", which is *not* itself an attribute of
        # the `builtins` module (`hasattr(builtins, "mappingproxy")` is
        # False). Left uncorrected, a node/call resolving to this exact
        # object reports a qualname nothing can actually import. Identity
        # comparison (not a name/text match) singles out this one known
        # CPython aliasing quirk; `mappingproxy` is a singleton type, so
        # this is the only object this branch will ever match.
        if (
            module == "builtins"
            and qualname == "mappingproxy"
            and obj is types.MappingProxyType
        ):
            return "types", "MappingProxyType"
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


#: ``code`` object attributes compared directly (equality) between a
#: candidate ``__new__`` and the freshly-built reference generated
#: ``__new__`` -- every semantically relevant attribute except
#: ``co_filename``/``co_firstlineno``/``co_qualname``/``co_name``
#: (irrelevant metadata the body-equivalence rule must never key on) and
#: ``co_varnames`` (compared separately: only the field-parameter names
#: carry behavioral meaning, not the leading ``cls``-like parameter's
#: literal spelling).
_GENERATED_NEW_CODE_ATTRS: tuple[str, ...] = (
    "co_argcount",
    "co_posonlyargcount",
    "co_kwonlyargcount",
    "co_nlocals",
    "co_stacksize",
    "co_flags",
    "co_consts",
    "co_names",
    "co_freevars",
    "co_cellvars",
    "co_code",
)


def _defaults_identity_equal(candidate: object, reference: object) -> bool:
    """``__defaults__`` tuples compared by length and per-element
    identity (``is``), never ``==`` -- a user-controlled default object
    could define an ``__eq__`` that executes arbitrary code merely by
    being compared; identity comparison never invokes any method on
    either operand."""
    cand = candidate if isinstance(candidate, tuple) else ()
    ref = reference if isinstance(reference, tuple) else ()
    return len(cand) == len(ref) and all(
        c is r for c, r in zip(cand, ref, strict=True)
    )


def _generated_new_body_matches_reference(
    candidate_new: object, fields: tuple[str, ...]
) -> bool:
    """The hardened core of this mechanism: proves ``candidate_new``'s
    own *body* -- not merely its signature or the surrounding class's
    API -- is structurally indistinguishable from the ``__new__`` a real
    ``collections.namedtuple`` factory call with the same field/default
    shape actually generates, *and* that its bytecode's one global
    reference genuinely resolves to ``tuple.__new__`` rather than an
    arbitrary rebound callable (matching bytecode alone proves nothing
    about what a global *name* resolves to at call time). Any failure to
    even construct the reference (a malformed ``_fields`` entry) is
    itself treated as "not verified" -- never approved.
    """
    candidate_code = getattr(candidate_new, "__code__", None)
    if candidate_code is None:
        return False
    # The one global the real generated body ever references must
    # resolve, right now, to the real `tuple.__new__` -- not merely be
    # *named* `_tuple_new`. A forged function can steal the exact code
    # object of a real generated `__new__` (byte-identical bytecode) and
    # simply rebind what `_tuple_new` points to in its own `__globals__`;
    # bytecode comparison alone cannot see that.
    if candidate_new.__globals__.get("_tuple_new") is not tuple.__new__:  # type: ignore[attr-defined]
        return False
    # No closure: the real generated `__new__` has zero free variables
    # (`_tuple_new` is a plain global, not a captured cell) -- a nonzero
    # closure is itself already disqualifying, checked before any
    # further comparison.
    if candidate_new.__closure__ is not None:  # type: ignore[attr-defined]
        return False
    try:
        reference_cls = collections.namedtuple(  # type: ignore[misc]
            "_AuditReferenceNamedTuple",
            fields,
        )
        reference_code = reference_cls.__new__.__code__
    except Exception:  # noqa: BLE001 - any construction/introspection failure
        # means this candidate's shape cannot be verified against a real
        # reference -- reject, never approve on an exception path.
        return False

    if candidate_code.co_varnames[1:] != reference_code.co_varnames[1:]:
        return False
    for attr in _GENERATED_NEW_CODE_ATTRS:
        if getattr(candidate_code, attr) != getattr(reference_code, attr):
            return False
    # co_exceptiontable (PEP 657, present on this interpreter but not on
    # every version this table might run under -- compared only when
    # both code objects actually carry it).
    cand_exc = getattr(candidate_code, "co_exceptiontable", None)
    ref_exc = getattr(reference_code, "co_exceptiontable", None)
    if cand_exc is not None and ref_exc is not None and cand_exc != ref_exc:
        return False

    return _defaults_identity_equal(
        getattr(candidate_new, "__defaults__", None),
        reference_cls.__new__.__defaults__,
    )


def is_namedtuple_generated_new(cls: type, new_method: object) -> bool:
    """Structural detection of a ``collections.namedtuple``/
    ``typing.NamedTuple``-synthesized ``__new__`` -- never by package
    name, class name, module-name allowlist, or qualname substring
    match, and never by trusting a descriptor's return value (``_fields``
    and ``__new__`` are both read directly from ``cls.__dict__``, never
    via ``getattr``/``hasattr``, so a malicious descriptor is never
    invoked). ``True`` only if every one of the following holds:

    * ``cls`` is a genuine subclass of ``tuple`` (not ``tuple`` itself);
    * ``cls.__dict__["_fields"]`` exists and is a tuple whose every
      element is ``type(field) is str`` exactly (not merely
      ``isinstance`` -- a ``str`` subclass could carry its own
      overridden behavior);
    * ``cls.__dict__["__new__"]`` is literally a ``staticmethod``
      wrapping ``new_method`` (the one, single way both
      ``collections.namedtuple`` and ``typing.NamedTuple`` ever store a
      generated ``__new__`` -- anything else, including an inherited or
      otherwise indirectly-reached method, is never approved);
    * ``new_method``'s own parameter list, after the leading ``cls``-like
      first parameter (CPython's real generated template names it
      ``_cls``, not ``cls`` -- checked positionally, never by name), is
      *exactly* ``_fields`` in order;
    * **the body-equivalence check** (see
      :func:`_generated_new_body_matches_reference`): every semantically
      relevant ``code`` object attribute matches a freshly-built
      reference of the same field shape, the function's one referenced
      global (``_tuple_new``) is live-checked to actually be
      ``tuple.__new__`` right now (not merely named the same), and it
      has no closure. Matching only the class-level API or only the
      parameter shape is deliberately *not* sufficient -- a forged tuple
      subclass that copies the entire generated API, uses the exact
      expected signature, and even reuses byte-identical bytecode stolen
      from a real generated ``__new__``, but whose ``_tuple_new`` global
      is rebound to an arbitrary callable, still fails this check and is
      never silently approved as generated.

    Deliberately **not** checked: the presence of ``_make``/``_asdict``/
    ``_replace``/``_field_defaults`` on ``cls``. Reading those via
    ``hasattr``/``getattr`` would invoke arbitrary descriptor code before
    any safety judgment is made -- the checks above are the sole
    authoritative proof this mechanism relies on.
    """
    if not (isinstance(cls, type) and issubclass(cls, tuple) and cls is not tuple):
        return False
    fields = cls.__dict__.get("_fields")
    if not isinstance(fields, tuple) or not all(type(f) is str for f in fields):  # noqa: E721
        return False
    raw_new = cls.__dict__.get("__new__")
    if not isinstance(raw_new, staticmethod):
        return False
    own_new = raw_new.__func__
    if own_new is not new_method or not inspect.isfunction(own_new):
        return False
    try:
        params = list(inspect.signature(own_new).parameters)
    except (TypeError, ValueError):
        return False
    if len(params) != len(fields) + 1 or tuple(params[1:]) != fields:
        return False
    return _generated_new_body_matches_reference(own_new, fields)


def classify_callable(
    obj: object,
    *,
    module: str | None,
    qualname: str | None,
    is_dataclass_generated: bool = False,
    is_namedtuple_generated: bool = False,
) -> IdentityVerdict:
    """Classify one resolved live callable per Harness Requirement 4.

    ``is_dataclass_generated`` must be set by the caller only after
    structurally confirming the object is a ``@dataclass``-synthesized
    method (``dataclasses.is_dataclass`` true on the owning class and no
    hand-written override exists) -- this function does not re-derive
    that fact itself. ``is_namedtuple_generated`` is the same discipline
    for a ``collections.namedtuple``/``typing.NamedTuple``-synthesized
    ``__new__``: the caller must have already confirmed it via
    :func:`is_namedtuple_generated_new`, structurally, before setting
    this flag -- this function does not re-derive that fact either.
    """
    key = _identity_key(module, qualname)

    if key is not None and key in FORBIDDEN_IDENTITIES:
        return IdentityVerdict(
            module, qualname, "forbidden", "Named forbidden operation.", False
        )

    # An individually-listed, reviewed exact-identity-policy entry is
    # authoritative and checked *before* attempting a generic source
    # walk: a hand-reviewed "this specific identity is safe, no I/O by
    # definition" decision must not be silently shadowed by the fact
    # that the identity also happens to have retrievable source (true
    # for most pure-Python stdlib entries in this table, e.g.
    # `inspect.signature`) -- walking further into an already-reviewed,
    # already-safe primitive's own internals serves no audit purpose
    # and is exactly the unbounded-crawl risk Task 38.7's termination
    # requirement exists to prevent (StaticWalker.walk only recurses on
    # a `project_source_available` verdict, precisely so this ordering
    # controls recursion, not just classification).
    if key is not None and key in EXACT_IDENTITY_POLICY:
        return IdentityVerdict(
            module, qualname, "exact_identity_policy", EXACT_IDENTITY_POLICY[key], False
        )

    # Task 38.7 Category A: any Python callable with genuinely retrievable
    # source is walked the same way project-owned code is walked --
    # third-party origin is not, by itself, a reason to stop. This is not
    # "trust third-party code": every call reached inside that source is
    # still resolved and classified by this same three-bucket rule,
    # recursively (audit_harness.trace.StaticWalker.walk recurses exactly
    # when this returns `project_source_available`). Only *whose* source
    # gets walked changes here -- what counts as resolved once reached is
    # unchanged. `module in PROJECT_TOP_LEVEL_PACKAGES` is no longer a
    # gate on attempting this at all.
    try:
        src = inspect.getsource(obj)  # type: ignore[arg-type]
        textwrap.dedent(src)
        return IdentityVerdict(module, qualname, "project_source_available", None, True)
    except (OSError, TypeError):
        pass

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

    if is_namedtuple_generated:
        return IdentityVerdict(
            module,
            qualname,
            "exact_identity_policy",
            (
                "NamedTuple-synthesized __new__: exec-generated by "
                "collections.namedtuple/typing.NamedTuple, not read from "
                "a hand-written .py body; fields already fully enumerated "
                "via the class's own _fields, and the __new__ signature "
                "itself is structurally verified (is_namedtuple_generated_new) "
                "to do nothing but assemble those exact fields into a "
                "tuple, no arbitrary code possible."
            ),
            False,
        )

    return IdentityVerdict(module, qualname, "unresolved", None, False)
