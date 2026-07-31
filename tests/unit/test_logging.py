"""Unit tests for logging.

Two complementary styles are shown:

* the **fake logger** (:class:`~tests.support.fakes.FakeLoggerFactory`) is used to
  assert that a component emits the expected log calls, without configuring real
  handlers; and
* the **real** :class:`~core.logging.JsonFormatter` is verified with an in-memory
  ``logging.Handler`` so its structured output and correlation-ID support are
  checked against actual records.
"""

from __future__ import annotations

import json
import logging
import unittest

from core.logging import JsonFormatter, correlation_id_scope
from tests.support import FakeLoggerFactory


class _MemoryHandler(logging.Handler):
    """A stdlib handler that keeps formatted records in memory."""

    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


class FakeLoggerTests(unittest.TestCase):
    def test_fake_logger_captures_calls_and_extra(self) -> None:
        factory = FakeLoggerFactory()
        logger = factory.get_logger("component")

        logger.info("started", extra={"symbol": "BTCUSDT"})

        self.assertEqual(factory.records, [("INFO", "started", {"symbol": "BTCUSDT"})])
        self.assertEqual(factory.requested_names, ["component"])


class JsonFormatterTests(unittest.TestCase):
    def _make_logger(self) -> tuple[logging.Logger, _MemoryHandler]:
        handler = _MemoryHandler()
        handler.setFormatter(JsonFormatter())
        logger = logging.getLogger("test.json")
        logger.handlers = [handler]
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        return logger, handler

    def test_structured_output_includes_extra_fields(self) -> None:
        logger, handler = self._make_logger()
        logger.info("filled", extra={"order_id": "o1"})
        payload = json.loads(handler.lines[-1])
        self.assertEqual(payload["message"], "filled")
        self.assertEqual(payload["level"], "INFO")
        self.assertEqual(payload["order_id"], "o1")

    def test_correlation_id_is_captured(self) -> None:
        logger, handler = self._make_logger()
        with correlation_id_scope("corr-1"):
            logger.info("scoped")
        self.assertEqual(json.loads(handler.lines[-1])["correlation_id"], "corr-1")


if __name__ == "__main__":
    unittest.main()
