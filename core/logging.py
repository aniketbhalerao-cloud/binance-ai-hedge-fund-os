"""Structured logging infrastructure.

A small, dependency-free logging stack built on the Python standard library. It
provides structured (JSON) and human-readable console output, rotating file
output, per-context correlation IDs, and clean registration through the DI
container.

Design principles
-----------------
* **Infrastructure, not business logic** — components ask for a logger and call
  it; they never format or route logs themselves.
* **Decoupled** — this module imports neither :mod:`config` nor :mod:`events`.
  Settings are passed in as a plain :class:`LoggingConfig` at the composition
  root, and the Event Bus is deliberately *not* referenced, so the two stay
  independent.
* **Correlation-ID ready** — a :class:`contextvars.ContextVar` and
  :class:`CorrelationIdFilter` stamp every record with the current correlation
  ID, so request/trade tracing can be switched on without touching call sites.

Only the Python 3.12 standard library is used.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.interfaces import Container

__all__ = [
    "LogFormat",
    "LoggingConfig",
    "CorrelationIdFilter",
    "JsonFormatter",
    "TextFormatter",
    "LoggerFactory",
    "configure_logging",
    "get_logger",
    "register_logging",
    "set_correlation_id",
    "get_correlation_id",
    "clear_correlation_id",
    "correlation_id_scope",
]

#: Value reported when no correlation ID has been set.
NO_CORRELATION_ID = "-"

# ---------------------------------------------------------------------------
# Correlation ID context
# ---------------------------------------------------------------------------

_correlation_id: ContextVar[str] = ContextVar(
    "correlation_id", default=NO_CORRELATION_ID
)


def set_correlation_id(value: str) -> Token[str]:
    """Set the correlation ID for the current context.

    Args:
        value: The correlation identifier to apply.

    Returns:
        A token that can be passed to :func:`contextvars.ContextVar.reset`.
    """
    return _correlation_id.set(value)


def get_correlation_id() -> str:
    """Return the correlation ID for the current context (or ``"-"``)."""
    return _correlation_id.get()


def clear_correlation_id() -> None:
    """Reset the correlation ID for the current context to the default."""
    _correlation_id.set(NO_CORRELATION_ID)


@contextmanager
def correlation_id_scope(value: str) -> Iterator[str]:
    """Bind ``value`` as the correlation ID for the duration of the ``with`` block.

    Args:
        value: The correlation identifier to apply within the scope.

    Yields:
        The applied correlation identifier.
    """
    token = _correlation_id.set(value)
    try:
        yield value
    finally:
        _correlation_id.reset(token)


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

#: Standard :class:`logging.LogRecord` attributes, used to separate caller-
#: supplied structured ``extra`` fields from built-in ones.
_RESERVED_RECORD_ATTRS: frozenset[str] = frozenset(
    {
        "args",
        "asctime",
        "created",
        "correlation_id",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


def _extra_fields(record: logging.LogRecord) -> dict[str, Any]:
    """Return caller-supplied structured fields attached to ``record``."""
    return {
        key: value
        for key, value in record.__dict__.items()
        if key not in _RESERVED_RECORD_ATTRS and not key.startswith("_")
    }


class CorrelationIdFilter(logging.Filter):
    """Ensure every record carries a ``correlation_id`` attribute."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Attach the current correlation ID if the record lacks one."""
        if not hasattr(record, "correlation_id"):
            record.correlation_id = get_correlation_id()
        return True


class JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON objects (structured logging)."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize ``record`` to a JSON string."""
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(
                record, "correlation_id", get_correlation_id()
            ),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        payload.update(_extra_fields(record))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """Human-readable console formatter that includes the correlation ID."""

    DEFAULT_FORMAT = (
        "%(asctime)s | %(levelname)-8s | %(name)s | "
        "%(correlation_id)s | %(message)s"
    )

    def __init__(self, fmt: str | None = None) -> None:
        super().__init__(fmt or self.DEFAULT_FORMAT)

    def format(self, record: logging.LogRecord) -> str:
        """Format ``record`` and append any structured extra fields."""
        if not hasattr(record, "correlation_id"):
            record.correlation_id = get_correlation_id()
        message = super().format(record)
        extras = _extra_fields(record)
        if extras:
            message = f"{message} | {json.dumps(extras, default=str)}"
        return message


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class LogFormat(str, Enum):
    """Output rendering style for a handler."""

    TEXT = "text"
    JSON = "json"


@dataclass(frozen=True, slots=True)
class LoggingConfig:
    """Declarative configuration for the logging system.

    Attributes:
        level: Minimum level to emit, as a name (``"INFO"``) or numeric level.
        root_logger_name: Logger the handlers are attached to; ``""`` (root)
            means every module logger propagates into this configuration.
        console_enabled: Whether to log to the console (stderr).
        console_format: Rendering style for the console handler.
        file_path: Destination for rotating file logs; ``None`` disables file
            logging.
        file_format: Rendering style for the file handler.
        max_bytes: Rotate the log file once it reaches this size.
        backup_count: Number of rotated files to keep.
        encoding: File encoding.
    """

    level: str | int = "INFO"
    root_logger_name: str = ""
    console_enabled: bool = True
    console_format: LogFormat = LogFormat.TEXT
    file_path: str | None = None
    file_format: LogFormat = LogFormat.JSON
    max_bytes: int = 10 * 1024 * 1024
    backup_count: int = 5
    encoding: str = "utf-8"


def _coerce_level(level: str | int) -> int:
    """Translate a level name or number into a numeric logging level."""
    if isinstance(level, int):
        return level
    mapping = logging.getLevelNamesMapping()
    try:
        return mapping[level.upper()]
    except KeyError as exc:
        valid = ", ".join(sorted(mapping))
        raise ValueError(
            f"Unknown log level {level!r}. Valid levels: {valid}."
        ) from exc


def _make_formatter(style: LogFormat) -> logging.Formatter:
    """Build the formatter for the given rendering ``style``."""
    return JsonFormatter() if style is LogFormat.JSON else TextFormatter()


# ---------------------------------------------------------------------------
# Logger factory
# ---------------------------------------------------------------------------


class LoggerFactory:
    """Configures logging and hands out named loggers.

    A single :class:`LoggerFactory` is intended to be built once (typically as a
    DI singleton), which idempotently installs the console/file handlers on the
    configured root logger. Components then call :meth:`get_logger` to obtain a
    standard :class:`logging.Logger`.
    """

    #: Marker set on handlers this factory installs, so re-configuration can
    #: replace them without disturbing handlers owned by other code.
    _MANAGED_FLAG = "_hedge_fund_managed"

    def __init__(self, config: LoggingConfig | None = None) -> None:
        self._config = config or LoggingConfig()
        self._configured = False

    @property
    def config(self) -> LoggingConfig:
        """Return the configuration this factory was built with."""
        return self._config

    def configure(self) -> LoggerFactory:
        """Install handlers on the configured logger. Idempotent.

        Any handlers previously installed by this factory are removed first, so
        calling :meth:`configure` again (for example after a settings reload)
        does not duplicate output.

        Returns:
            This factory, to allow ``LoggerFactory(cfg).configure()`` chaining.
        """
        logger = logging.getLogger(self._config.root_logger_name)
        logger.setLevel(_coerce_level(self._config.level))

        for handler in list(logger.handlers):
            if getattr(handler, self._MANAGED_FLAG, False):
                logger.removeHandler(handler)

        correlation_filter = CorrelationIdFilter()
        for handler in self._build_handlers():
            handler.addFilter(correlation_filter)
            setattr(handler, self._MANAGED_FLAG, True)
            logger.addHandler(handler)

        self._configured = True
        return self

    def get_logger(self, name: str | None = None) -> logging.Logger:
        """Return a logger, configuring the factory on first use if needed.

        Args:
            name: Logger name; ``None`` returns the configured root logger.

        Returns:
            A standard :class:`logging.Logger`.
        """
        if not self._configured:
            self.configure()
        if name is None:
            name = self._config.root_logger_name
        return logging.getLogger(name)

    def _build_handlers(self) -> list[logging.Handler]:
        """Create the handlers described by the configuration."""
        handlers: list[logging.Handler] = []

        if self._config.console_enabled:
            console = logging.StreamHandler()
            console.setFormatter(_make_formatter(self._config.console_format))
            handlers.append(console)

        if self._config.file_path:
            directory = os.path.dirname(self._config.file_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            file_handler = RotatingFileHandler(
                self._config.file_path,
                maxBytes=self._config.max_bytes,
                backupCount=self._config.backup_count,
                encoding=self._config.encoding,
            )
            file_handler.setFormatter(_make_formatter(self._config.file_format))
            handlers.append(file_handler)

        return handlers


# ---------------------------------------------------------------------------
# Module-level convenience (non-DI usage)
# ---------------------------------------------------------------------------

_default_factory: LoggerFactory | None = None


def configure_logging(config: LoggingConfig | None = None) -> LoggerFactory:
    """Configure the process-wide default :class:`LoggerFactory`.

    Args:
        config: Logging configuration; defaults are used when omitted.

    Returns:
        The configured default factory.
    """
    global _default_factory
    _default_factory = LoggerFactory(config).configure()
    return _default_factory


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger from the default factory, configuring it if necessary.

    Args:
        name: Logger name; ``None`` returns the configured root logger.

    Returns:
        A standard :class:`logging.Logger`.
    """
    if _default_factory is None:
        configure_logging()
    assert _default_factory is not None  # for type checkers
    return _default_factory.get_logger(name)


# ---------------------------------------------------------------------------
# Dependency-injection integration
# ---------------------------------------------------------------------------


def register_logging(
    container: Container, config: LoggingConfig | None = None
) -> LoggerFactory:
    """Register a configured :class:`LoggerFactory` as a DI singleton.

    The factory is built and configured eagerly, then registered as an instance
    so every consumer resolves the same, already-initialised logging setup.

    Args:
        container: The DI container to register into.
        config: Logging configuration; defaults are used when omitted.

    Returns:
        The configured :class:`LoggerFactory` that was registered.
    """
    factory = LoggerFactory(config).configure()
    container.register_instance(LoggerFactory, factory)
    return factory
