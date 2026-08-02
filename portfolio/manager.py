"""Portfolio manager.

:class:`DefaultPortfolioManager` owns the portfolio update workflow: accounting →
holdings → cash → valuation → allocation → performance → snapshot. It computes a
complete new portfolio state atomically under a lock (so partial updates never
leave the portfolio inconsistent), then publishes events and returns a
:class:`PortfolioResult`. Internal failures are translated to framework
exceptions and never escape. The individual components stay independent.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from threading import Lock

from core.logging import LoggerFactory
from events.base import Event
from events.bus import EventBus
from models import OrderSide
from portfolio.context import PortfolioContext
from portfolio.events import (
    AllocationUpdated,
    CashUpdated,
    HoldingsUpdated,
    PerformanceUpdated,
    PortfolioClosed,
    PortfolioCreated,
    PortfolioErrorOccurred,
    PortfolioSnapshotCreated,
    PortfolioUpdated,
    PortfolioValuationCompleted,
)
from portfolio.exceptions import PortfolioClosedError, PortfolioError
from portfolio.interfaces import (
    AccountingService,
    AllocationService,
    CashManager,
    HoldingsManager,
    PerformanceService,
    PortfolioRegistry,
    ValuationService,
)
from portfolio.models import (
    LedgerEntry,
    Portfolio,
    PortfolioCash,
    PortfolioPosition,
    PortfolioResult,
    PortfolioResultStatus,
    PortfolioSnapshot,
    PortfolioValue,
)
from portfolio.state import PortfolioState

__all__ = ["DefaultPortfolioManager"]


def _realized_delta(entry: LedgerEntry, position: PortfolioPosition | None) -> Decimal:
    """Realized P&L booked by this fill (non-zero only on a sell of a held lot)."""
    if entry.side is OrderSide.SELL and position is not None:
        return entry.quantity * (entry.price - position.average_cost)
    return Decimal("0")


class DefaultPortfolioManager:
    """Coordinates the portfolio update pipeline."""

    def __init__(
        self,
        bus: EventBus,
        registry: PortfolioRegistry,
        accounting: AccountingService,
        holdings: HoldingsManager,
        cash: CashManager,
        valuation: ValuationService,
        allocation: AllocationService,
        performance: PerformanceService,
        logger: LoggerFactory | None = None,
    ) -> None:
        self._bus = bus
        self._registry = registry
        self._accounting = accounting
        self._holdings = holdings
        self._cash = cash
        self._valuation = valuation
        self._allocation = allocation
        self._performance = performance
        self._log = logger.get_logger("portfolio.manager") if logger else None
        self._prev_value: dict[str, PortfolioValue] = {}
        self._lock = Lock()

    async def update(self, context: PortfolioContext) -> PortfolioResult:
        """Apply the execution in ``context`` and return a :class:`PortfolioResult`."""
        pid = context.portfolio_id
        events: list[Event] = []
        try:
            result = self._compute(context, events)
        except PortfolioError as exc:
            self._error(pid, str(exc))
            await self._bus.publish(
                PortfolioErrorOccurred(portfolio_id=pid, message=str(exc))
            )
            existing = self._registry.get(pid) if self._registry.exists(pid) else None
            return PortfolioResult(
                status=PortfolioResultStatus.FAILED,
                portfolio=existing,
                errors=(str(exc),),
            )

        for event in events:  # publish only after a fully consistent update
            await self._bus.publish(event)
        return result

    def _compute(
        self, context: PortfolioContext, events: list[Event]
    ) -> PortfolioResult:
        """Build the new portfolio state atomically (no awaits inside the lock)."""
        pid = context.portfolio_id
        now = datetime.now(UTC)
        with self._lock:
            created = not self._registry.exists(pid)
            if created:
                portfolio = Portfolio(
                    id=pid,
                    state=PortfolioState.EMPTY,
                    cash=PortfolioCash(available=context.initial_cash),
                )
                events.append(PortfolioCreated(portfolio_id=pid))
            else:
                portfolio = self._registry.get(pid)

            if portfolio.state is PortfolioState.CLOSED:
                raise PortfolioClosedError(f"portfolio {pid!r} is closed")

            entry = self._accounting.entry(context)
            old_position = portfolio.position(entry.symbol)
            realized_delta = _realized_delta(entry, old_position)
            new_position = self._holdings.apply(
                old_position,
                entry.symbol,
                entry.side,
                entry.quantity,
                entry.price,
            )
            positions = tuple(
                p for p in portfolio.positions if p.symbol != entry.symbol
            )
            if new_position is not None:
                positions = positions + (new_position,)

            new_cash = self._cash.apply(
                portfolio.cash, entry.side, entry.quantity, entry.price
            )

            updated = Portfolio(
                id=pid,
                state=PortfolioState.ACTIVE,
                positions=positions,
                cash=new_cash,
                ledger=portfolio.ledger + (entry,),
                realized_pnl=portfolio.realized_pnl + realized_delta,
                updated_at=now,
            )

            value = self._valuation.value(updated, context.prices)
            allocation = self._allocation.allocate(updated, value)
            performance = self._performance.measure(value, self._prev_value.get(pid))
            snapshot = PortfolioSnapshot(
                portfolio=updated,
                value=value,
                allocation=allocation,
                performance=performance,
                timestamp=now,
            )

            self._registry.update(updated)
            self._prev_value[pid] = value

        events.extend(
            [
                HoldingsUpdated(portfolio_id=pid, symbol=entry.symbol),
                CashUpdated(portfolio_id=pid),
                PortfolioValuationCompleted(portfolio_id=pid),
                AllocationUpdated(portfolio_id=pid),
                PerformanceUpdated(portfolio_id=pid),
                PortfolioSnapshotCreated(portfolio_id=pid),
                PortfolioUpdated(portfolio_id=pid),
            ]
        )
        self._info("Portfolio updated", pid)
        return PortfolioResult(
            status=PortfolioResultStatus.SUCCESS, portfolio=updated, snapshot=snapshot
        )

    async def close(self, portfolio_id: str) -> PortfolioResult:
        """Close a portfolio and publish :class:`PortfolioClosed`."""
        with self._lock:
            portfolio = self._registry.get(portfolio_id)
            closed = Portfolio(
                id=portfolio.id,
                state=PortfolioState.CLOSED,
                positions=portfolio.positions,
                cash=portfolio.cash,
                ledger=portfolio.ledger,
                updated_at=datetime.now(UTC),
            )
            self._registry.update(closed)
        await self._bus.publish(PortfolioClosed(portfolio_id=portfolio_id))
        return PortfolioResult(status=PortfolioResultStatus.SUCCESS, portfolio=closed)

    def _info(self, message: str, pid: str) -> None:
        if self._log is not None:
            self._log.info(message, extra={"portfolio_id": pid})

    def _error(self, pid: str, message: str) -> None:
        if self._log is not None:
            self._log.error(
                "Portfolio error", extra={"portfolio_id": pid, "error": message}
            )
