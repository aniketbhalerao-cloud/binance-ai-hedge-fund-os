"""Strategy factory.

:class:`DefaultStrategyFactory` isolates strategy *construction* from execution.
It builds strategy instances through the existing DI container's constructor
injection, so a strategy simply declares its dependencies as typed constructor
parameters. The factory never executes, stores, or registers strategies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from strategies.interfaces import Strategy

if TYPE_CHECKING:
    from core.container import ServiceContainer

__all__ = ["DefaultStrategyFactory"]


class DefaultStrategyFactory:
    """Creates strategies via the DI container (constructor injection).

    Args:
        container: The DI container used to build strategies. Injected — the
            factory never constructs its own dependencies.
    """

    def __init__(self, container: ServiceContainer) -> None:
        self._container = container

    def create(self, strategy_cls: type[Strategy]) -> Strategy:
        """Construct an instance of ``strategy_cls`` with its dependencies injected.

        The container resolves each annotated constructor parameter, so future
        strategies gain dependencies without the factory changing (Open/Closed).
        """
        return self._container.create(strategy_cls)
