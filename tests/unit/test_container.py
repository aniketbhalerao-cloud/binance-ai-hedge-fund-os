"""Unit tests for the DI container, focused on constructor injection."""

from __future__ import annotations

import unittest

from core.container import ServiceContainer


class Engine:
    """A leaf dependency with no constructor arguments."""


class Service:
    """A dependency that requires an :class:`Engine` via its constructor."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine


class ConstructorInjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.container = ServiceContainer()

    def test_register_class_injects_constructor_dependencies(self) -> None:
        self.container.register_class(Engine)
        self.container.register_class(Service)

        service = self.container.resolve(Service)

        self.assertIsInstance(service, Service)
        self.assertIsInstance(service.engine, Engine)

    def test_singleton_dependency_is_shared(self) -> None:
        self.container.register_class(Engine)
        self.container.register_class(Service)

        service = self.container.resolve(Service)
        same = self.container.resolve(Service)

        self.assertIs(service, same)
        self.assertIs(service.engine, self.container.resolve(Engine))

    def test_create_builds_without_registering(self) -> None:
        self.container.register_class(Engine)

        service = self.container.create(Service)

        self.assertIsInstance(service.engine, Engine)
        self.assertFalse(self.container.has(Service))

    def test_unregistered_dependency_raises_keyerror(self) -> None:
        self.container.register_class(Service)  # Engine intentionally missing
        with self.assertRaises(KeyError):
            self.container.resolve(Service)

    def test_register_instance_returns_same_object(self) -> None:
        engine = Engine()
        self.container.register_instance(Engine, engine)
        self.assertIs(self.container.resolve(Engine), engine)


if __name__ == "__main__":
    unittest.main()
