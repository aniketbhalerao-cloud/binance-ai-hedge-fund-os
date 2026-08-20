"""Task 38.6 Harness Requirement 7: negative-control fixtures.

Five deliberately unsafe shapes, one per named requirement-7 case. Not
imported by any production module, never registered with
``app.wiring``, never executed for real by anything except the harness
tests that prove each one is *detected*.
"""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FixtureWithForbiddenPostInit:
    """A ``__post_init__`` performing a forbidden operation (opens a
    real file). Requirement 7, case 1."""

    path: str

    def __post_init__(self) -> None:
        open(self.path)  # noqa: SIM115 - deliberately forbidden, never actually run


def fixture_unresolvable_call(mystery: object) -> object:
    """A call the harness's identity resolution genuinely cannot pin to
    a live object: ``mystery`` carries no annotation and is not a
    project-owned/known type, so its attribute access has no resolvable
    identity. Requirement 7, case 2."""
    return mystery.do_something_unverifiable()  # type: ignore[attr-defined]


_fixture_module_global: dict[str, int] = {}


def fixture_mutates_module_global_from_plain_function() -> None:
    """An ordinary (non-nested) function mutating a module-global dict
    via subscript assignment and a mutating method call. Requirement 7,
    case 3 -- exactly the shape M-7 gap 3 named as previously
    undetected."""
    _fixture_module_global["mutated"] = 1
    _fixture_module_global.update({"other": 2})


def fixture_calls_os_open_directly() -> None:
    """A direct ``os.open`` call -- the lower-level file-descriptor
    primitive M-7 gap 2 named as unpatched by the v5 runtime check.
    Requirement 7, case 4."""
    fd = os.open("/tmp/audit-harness-fixture-must-never-run", os.O_RDONLY)
    os.close(fd)


class FixtureDBClient:
    """Simulates a DB client's ``connect()`` -- routes through
    ``socket.create_connection`` (the primitive a TCP-based DB driver,
    e.g. psycopg/asyncpg, eventually reaches), so the runtime-denial
    patch on that primitive intercepts it, without this fixture ever
    completing a real connection. Requirement 7, case 5 (one of three)."""

    def connect(self) -> None:
        socket.create_connection(("127.0.0.1", 1), timeout=0.01)


class FixtureRedisClient:
    """Simulates a Redis client's ``connect()`` -- routes through the
    lower-level ``socket.socket()`` + ``.connect()`` two-step pattern
    real Redis clients typically use (distinct from
    ``FixtureDBClient``'s single-call ``create_connection`` shape), so
    the runtime-denial patch on the ``socket.socket`` *class itself*
    intercepts construction before any connection is even attempted.
    Requirement 7, case 5 (one of three)."""

    def connect(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", 1))


class FixtureExchangeAdapterClient:
    """Simulates an exchange-adapter connection -- a third, independent
    named client (distinct code path from the DB and Redis fixtures)
    routing through the same socket primitives a real
    ``exchange_adapters``/CCXT-backed connection would eventually reach.
    Requirement 7, case 5 (one of three)."""

    def connect(self) -> None:
        with socket.create_connection(("127.0.0.1", 1), timeout=0.01) as sock:
            sock.send(b"never reached")
