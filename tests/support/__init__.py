"""Reusable test support: sample-model factories and fake implementations.

This package is the shared testing framework for the project. It provides
deterministic factories for the domain models and standard-library fakes (test
doubles) for repositories, the event bus subscriber, and the logger — so unit
and integration tests never touch real exchanges, external APIs, or databases.
"""

from __future__ import annotations

from tests.support.factories import make_order, make_position, make_trade
from tests.support.fakes import (
    FakeLogger,
    FakeLoggerFactory,
    FakeOrderRepository,
    FakePositionRepository,
    FakeSubscriber,
    FakeTradeRepository,
)

__all__ = [
    "make_order",
    "make_trade",
    "make_position",
    "FakeOrderRepository",
    "FakeTradeRepository",
    "FakePositionRepository",
    "FakeSubscriber",
    "FakeLogger",
    "FakeLoggerFactory",
]
