"""Reusable, side-effect-free validation helpers for the config layer.

Each function validates a single value and either returns the (normalized)
value or raises :class:`ValueError` with an actionable message. They are used
by the Pydantic field validators in :mod:`config.settings`.

The helpers are deliberately framework-agnostic: they accept and return plain
Python values so they can be unit-tested in isolation and reused anywhere.
"""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlparse

from config.constants import (
    MAX_PORT,
    MIN_API_KEY_LENGTH,
    MIN_PORT,
    MIN_SECRET_LENGTH,
)

__all__ = [
    "validate_port",
    "validate_url",
    "validate_api_key",
    "validate_secret",
    "validate_fraction",
    "validate_positive",
    "validate_non_negative",
    "split_csv",
]


def validate_port(value: int, *, field: str = "port") -> int:
    """Validate that ``value`` is a usable TCP port.

    Args:
        value: Candidate port number.
        field: Name used in error messages.

    Returns:
        The validated port.

    Raises:
        ValueError: If the port is outside ``[MIN_PORT, MAX_PORT]``.
    """
    if not MIN_PORT <= value <= MAX_PORT:
        raise ValueError(
            f"{field} must be between {MIN_PORT} and {MAX_PORT}, got {value}."
        )
    return value


def validate_url(
    value: str,
    *,
    schemes: Iterable[str],
    field: str = "url",
    require_host: bool = True,
) -> str:
    """Validate that ``value`` is a well-formed URL with an allowed scheme.

    Args:
        value: Candidate URL.
        schemes: Allowed URL schemes (e.g. ``{"http", "https"}``).
        field: Name used in error messages.
        require_host: Whether a network location (host) is required. Disabled
            for schemes such as ``sqlite`` that may omit a host.

    Returns:
        The validated URL, stripped of surrounding whitespace.

    Raises:
        ValueError: If the URL is malformed or uses a disallowed scheme.
    """
    candidate = value.strip()
    if not candidate:
        raise ValueError(f"{field} must not be empty.")

    parsed = urlparse(candidate)
    allowed = set(schemes)
    if parsed.scheme not in allowed:
        pretty = ", ".join(sorted(allowed))
        raise ValueError(
            f"{field} scheme '{parsed.scheme or '<missing>'}' is not allowed; "
            f"expected one of: {pretty}."
        )

    host_missing = require_host and parsed.scheme != "sqlite" and not parsed.netloc
    if host_missing:
        raise ValueError(f"{field} must include a host, got '{value}'.")

    return candidate


def validate_api_key(
    value: str,
    *,
    field: str = "api_key",
    required: bool = False,
    min_length: int = MIN_API_KEY_LENGTH,
) -> str:
    """Validate an API credential.

    Empty values are permitted unless ``required`` is ``True`` (credentials are
    typically optional in development and only mandatory for live trading).

    Args:
        value: Candidate credential.
        field: Name used in error messages.
        required: Whether a non-empty value is mandatory.
        min_length: Minimum length enforced when a value is provided.

    Returns:
        The validated credential (whitespace stripped).

    Raises:
        ValueError: If the credential is missing while required, or too short.
    """
    candidate = value.strip()
    if not candidate:
        if required:
            raise ValueError(f"{field} is required but was not provided.")
        return candidate
    if len(candidate) < min_length:
        raise ValueError(
            f"{field} looks invalid: expected at least {min_length} characters."
        )
    return candidate


def validate_secret(
    value: str,
    *,
    field: str = "secret",
    min_length: int = MIN_SECRET_LENGTH,
) -> str:
    """Validate a strong secret (e.g. a signing key).

    Args:
        value: Candidate secret.
        field: Name used in error messages.
        min_length: Minimum acceptable length.

    Returns:
        The validated secret.

    Raises:
        ValueError: If the secret is empty or shorter than ``min_length``.
    """
    candidate = value.strip()
    if len(candidate) < min_length:
        raise ValueError(f"{field} must be at least {min_length} characters long.")
    return candidate


def validate_fraction(
    value: float,
    *,
    field: str = "fraction",
    allow_zero: bool = False,
    upper: float = 1.0,
) -> float:
    """Validate a fractional value, typically a risk ratio in ``(0, 1]``.

    Args:
        value: Candidate fraction.
        field: Name used in error messages.
        allow_zero: Whether ``0`` is acceptable.
        upper: Inclusive upper bound (defaults to ``1.0``).

    Returns:
        The validated fraction.

    Raises:
        ValueError: If the value falls outside the permitted range.
    """
    lower_ok = value >= 0 if allow_zero else value > 0
    if not lower_ok or value > upper:
        bound = "[0" if allow_zero else "(0"
        raise ValueError(f"{field} must be within {bound}, {upper}], got {value}.")
    return value


def validate_positive(value: float, *, field: str = "value") -> float:
    """Validate that ``value`` is strictly greater than zero."""
    if value <= 0:
        raise ValueError(f"{field} must be greater than 0, got {value}.")
    return value


def validate_non_negative(value: float, *, field: str = "value") -> float:
    """Validate that ``value`` is greater than or equal to zero."""
    if value < 0:
        raise ValueError(f"{field} must be zero or greater, got {value}.")
    return value


def split_csv(value: object) -> object:
    """Normalize a comma-separated string into a list of trimmed strings.

    Intended as a ``mode="before"`` validator so that list-valued settings may
    be provided either as JSON arrays or plain ``a,b,c`` strings in ``.env``.
    Non-string inputs are returned unchanged for Pydantic to handle.

    Args:
        value: Raw value from the environment.

    Returns:
        A list of strings when ``value`` is a non-JSON CSV string, otherwise
        the original value.
    """
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        # Leave JSON arrays for Pydantic's native parser.
        if stripped.startswith("["):
            return value
        return [item.strip() for item in stripped.split(",") if item.strip()]
    return value
