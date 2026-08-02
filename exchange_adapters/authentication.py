"""Authentication abstraction.

:class:`DefaultExchangeAuthentication` defines the authentication *workflow* only
— it holds no API keys, secrets, signatures, OAuth, or JWT. The default simply
reports ``AUTHENTICATED`` so the pipeline flows; a future broker adapter provides
a real implementation of the :class:`~exchange_adapters.interfaces.ExchangeAuthentication`
protocol. It is stateless.
"""

from __future__ import annotations

from exchange_adapters.context import ExchangeContext
from exchange_adapters.state import AuthenticationState

__all__ = ["DefaultExchangeAuthentication"]


class DefaultExchangeAuthentication:
    """Framework-level authentication (no real credentials)."""

    async def authenticate(self, context: ExchangeContext) -> AuthenticationState:
        """Return the resulting authentication state.

        The default performs no credential handling and reports authenticated;
        real brokers override this behind the same interface.
        """
        return AuthenticationState.AUTHENTICATED
