"""Dependency-injection wiring for the Binance Spot adapter.

Registers every Binance component (config, signer, authentication, transports,
REST/WebSocket clients, connection, translator, parser, validator, adapter) as
singletons in the existing container, and optionally registers the adapter into
the Exchange Adapter Framework's registry so the framework can route to it.
Transports are injectable so tests never touch the network.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from adapters.binance.adapter import BinanceSpotAdapter
from adapters.binance.authentication import BinanceAuthentication
from adapters.binance.client import (
    HttpTransport,
    NullStreamTransport,
    StreamTransport,
    UrllibHttpTransport,
)
from adapters.binance.config import BinanceConfig
from adapters.binance.connection import BinanceConnection
from adapters.binance.converters import BinanceRequestTranslator
from adapters.binance.parser import BinanceResponseParser
from adapters.binance.requests import BinanceRequestValidator
from adapters.binance.rest import BinanceRESTClient
from adapters.binance.signer import BinanceSigner
from adapters.binance.websocket import BinanceWebSocketClient
from core.logging import LoggerFactory
from events.bus import EventBus
from exchange_adapters.interfaces import ExchangeRegistry

if TYPE_CHECKING:
    from core.interfaces import Container, Resolver

__all__ = ["register_binance_adapter"]


def _logger(resolver: Resolver) -> LoggerFactory | None:
    return resolver.resolve(LoggerFactory) if resolver.has(LoggerFactory) else None


def register_binance_adapter(
    container: Container,
    config: BinanceConfig,
    *,
    transport: HttpTransport | None = None,
    stream_transport: StreamTransport | None = None,
    register_in_framework: bool = True,
) -> None:
    """Register the Binance Spot adapter and its components.

    Args:
        container: The DI container to register into.
        config: The immutable Binance configuration (credentials, URLs, …).
        transport: Optional HTTP transport; defaults to the stdlib transport.
        stream_transport: Optional stream transport; defaults to the stub.
        register_in_framework: When ``True`` and an
            :class:`~exchange_adapters.interfaces.ExchangeRegistry` is registered,
            the adapter is added to it so the framework can route to it.
    """
    if not container.has(EventBus):
        container.register_class(EventBus)

    container.register_instance(BinanceConfig, config)
    container.register_class(BinanceSigner)
    container.register_class(BinanceRequestTranslator)
    container.register_class(BinanceResponseParser)
    container.register_class(BinanceRequestValidator)

    if transport is not None:
        container.register_instance(HttpTransport, transport)
    else:
        container.register_class(HttpTransport, UrllibHttpTransport)
    if stream_transport is not None:
        container.register_instance(StreamTransport, stream_transport)
    else:
        container.register_class(StreamTransport, NullStreamTransport)

    container.register_singleton(
        BinanceAuthentication,
        lambda r: BinanceAuthentication(
            r.resolve(BinanceConfig), r.resolve(BinanceSigner)
        ),
    )
    container.register_singleton(
        BinanceConnection,
        lambda r: BinanceConnection(r.resolve(EventBus), logger=_logger(r)),
    )
    container.register_singleton(
        BinanceRESTClient,
        lambda r: BinanceRESTClient(
            r.resolve(HttpTransport),
            r.resolve(BinanceConfig),
            r.resolve(BinanceAuthentication),
            r.resolve(EventBus),
            logger=_logger(r),
        ),
    )
    container.register_singleton(
        BinanceWebSocketClient,
        lambda r: BinanceWebSocketClient(
            r.resolve(StreamTransport),
            r.resolve(BinanceConfig),
            r.resolve(EventBus),
            logger=_logger(r),
        ),
    )
    container.register_singleton(
        BinanceSpotAdapter,
        lambda r: BinanceSpotAdapter(
            r.resolve(BinanceAuthentication),
            r.resolve(BinanceConnection),
            r.resolve(BinanceRESTClient),
            r.resolve(BinanceRequestTranslator),
            r.resolve(BinanceRequestValidator),
            r.resolve(BinanceResponseParser),
            r.resolve(EventBus),
            r.resolve(BinanceConfig),
            logger=_logger(r),
        ),
    )

    if register_in_framework and container.has(ExchangeRegistry):
        container.resolve(ExchangeRegistry).register(
            container.resolve(BinanceSpotAdapter)
        )
