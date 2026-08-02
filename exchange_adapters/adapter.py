"""Abstract exchange adapter.

:class:`BaseExchangeAdapter` is the abstract base every future broker adapter
(Binance, Zerodha, Interactive Brokers, paper, backtest, …) inherits from. It
defines the adapter contract — accept a translated request, produce a
standardized response, and track adapter lifecycle — with **no** broker SDK,
REST, or WebSocket logic. Concrete adapters are not implemented in this task.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from exchange_adapters.models import ExchangeRequest, ExchangeResponse
from exchange_adapters.state import AdapterState

__all__ = ["BaseExchangeAdapter"]


class BaseExchangeAdapter(ABC):
    """Base class implementing the ``ExchangeAdapter`` contract.

    Subclasses implement :meth:`submit` with real broker behaviour. The base
    tracks a coarse lifecycle state and never performs I/O.
    """

    def __init__(self, name: str) -> None:
        self._name = name
        self._state = AdapterState.REGISTERED

    @property
    def name(self) -> str:
        """Return this adapter's unique name."""
        return self._name

    @property
    def state(self) -> AdapterState:
        """Return this adapter's lifecycle state."""
        return self._state

    async def on_start(self) -> None:
        """Lifecycle hook: mark the adapter ready. Override for real setup."""
        self._state = AdapterState.READY

    async def on_stop(self) -> None:
        """Lifecycle hook: mark the adapter stopped. Override for real teardown."""
        self._state = AdapterState.STOPPED

    @abstractmethod
    async def submit(self, request: ExchangeRequest) -> ExchangeResponse:
        """Accept a translated request and produce a standardized response."""
