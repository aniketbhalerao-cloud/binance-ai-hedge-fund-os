"""Runtime environment detection and ``.env`` file loading.

Defines the :class:`Environment` enumeration (the four supported deployment
targets) and the helpers that locate and load the appropriate dotenv files
using :mod:`dotenv`.

Loading strategy
----------------
1. A base ``.env`` file is loaded first (without overriding real process
   environment variables).
2. The active environment is resolved from ``APP_ENV`` (falling back to
   ``ENVIRONMENT``, then ``development``).
3. An environment-specific ``.env.<environment>`` file, if present, is loaded
   with ``override=True`` so it wins over the base file.

This module contains no business logic; it only prepares ``os.environ`` so that
:mod:`config.settings` can build a validated settings object.
"""

from __future__ import annotations

import os
from enum import Enum

from dotenv import find_dotenv, load_dotenv

#: Environment variables consulted, in order, to determine the environment.
ENVIRONMENT_ENV_VARS: tuple[str, ...] = ("APP_ENV", "ENVIRONMENT")


class Environment(str, Enum):
    """Supported deployment environments."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PAPER = "paper"
    PRODUCTION = "production"

    @classmethod
    def from_str(cls, value: str | None) -> "Environment":
        """Coerce an arbitrary string into an :class:`Environment`.

        Args:
            value: Raw string (case-insensitive) or ``None``.

        Returns:
            The matching :class:`Environment`.

        Raises:
            ValueError: If ``value`` does not match a known environment.
        """
        if value is None:
            return cls.DEVELOPMENT
        normalized = value.strip().lower()
        aliases = {
            "dev": cls.DEVELOPMENT,
            "develop": cls.DEVELOPMENT,
            "test": cls.TESTING,
            "prod": cls.PRODUCTION,
        }
        if normalized in aliases:
            return aliases[normalized]
        try:
            return cls(normalized)
        except ValueError as exc:
            valid = ", ".join(member.value for member in cls)
            raise ValueError(
                f"Unknown environment '{value}'. Valid options: {valid}."
            ) from exc

    @property
    def is_production(self) -> bool:
        """Return ``True`` when this is the production environment."""
        return self is Environment.PRODUCTION

    @property
    def is_live_capable(self) -> bool:
        """Return ``True`` if live trading may be permitted in this environment."""
        return self is Environment.PRODUCTION


def active_environment() -> Environment:
    """Resolve the active environment from the process environment.

    Returns:
        The :class:`Environment` named by ``APP_ENV``/``ENVIRONMENT``, or
        :attr:`Environment.DEVELOPMENT` when neither is set.
    """
    for var in ENVIRONMENT_ENV_VARS:
        raw = os.getenv(var)
        if raw:
            return Environment.from_str(raw)
    return Environment.DEVELOPMENT


def load_environment(*, override: bool = False) -> Environment:
    """Load dotenv files for the active environment into ``os.environ``.

    A base ``.env`` is loaded first, then the environment-specific
    ``.env.<environment>`` override (if it exists).

    Args:
        override: When ``True``, values from the base ``.env`` also override
            variables already present in the process environment. The
            environment-specific file always overrides the base file.

    Returns:
        The resolved active :class:`Environment`.
    """
    base = find_dotenv(".env", usecwd=True)
    if base:
        load_dotenv(base, override=override)

    environment = active_environment()

    specific = find_dotenv(f".env.{environment.value}", usecwd=True)
    if specific:
        load_dotenv(specific, override=True)

    return environment
