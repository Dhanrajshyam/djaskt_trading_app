"""Ledger orchestration entry point.

The API and realtime layers should only ever import `LedgerOrchestratorService`
— never `TradeExecutionService` or `PriceCacheService` directly. Today this
class is a thin coordinator over trade execution plus the post-commit
realtime broadcast, but it is the designated seam for wiring in additional
services later (e.g. compliance checks, notifications, audit logging)
without changing the contract layer.
"""

import logging
from decimal import Decimal
from typing import Any
from uuid import UUID

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from ledger.models import CashTransaction, Portfolio, Position, Trade
from ledger.realtime.consumers import portfolio_group_name
from ledger.services.cash_service import CashTransferResult, CashTransferService
from ledger.services.trade_service import TradeExecutionService, TradeResult

logger = logging.getLogger(__name__)


class LedgerOrchestratorService:
    """Single entry point for all ledger mutations (trades and cash transfers).

    Coordinates the ACID-critical execution services (`TradeExecutionService`,
    `CashTransferService`) with the post-commit realtime broadcast, so
    neither execution service needs to know Channels exists, and so a
    broadcast never fires for a mutation that could still roll back.
    """

    def __init__(
        self,
        trade_service: TradeExecutionService | None = None,
        cash_service: CashTransferService | None = None,
    ) -> None:
        """Initialize the orchestrator, optionally injecting its dependencies.

        Constructor injection lets tests supply fakes for either execution
        service without touching the database or Redis.
        """
        self._trade_service = trade_service or TradeExecutionService()
        self._cash_service = cash_service or CashTransferService()

    def submit_trade(
        self,
        *,
        portfolio_id: UUID,
        ticker: str,
        trade_type: str,
        quantity: Decimal,
        idempotency_key: UUID,
    ) -> TradeResult:
        """Execute a trade and broadcast the resulting portfolio state.

        Delegates execution to `TradeExecutionService`, then — only for a
        freshly committed (non-replay) trade — broadcasts the updated cash
        balance, positions, and trade details to the portfolio's WebSocket
        group.
        """
        result = self._trade_service.execute_trade(
            portfolio_id=portfolio_id,
            ticker=ticker,
            trade_type=trade_type,
            quantity=quantity,
            idempotency_key=idempotency_key,
        )

        # Only broadcast for a freshly committed trade — an idempotent replay
        # reflects state the client (and any subscribed sockets) already saw.
        if not result.is_replay:
            self._broadcast_portfolio_update(
                result.trade.portfolio, latest_trade=result.trade
            )

        return result

    def submit_cash_transfer(
        self,
        *,
        portfolio_id: UUID,
        direction: str,
        amount: Decimal,
        idempotency_key: UUID,
    ) -> CashTransferResult:
        """Apply a cash transfer and broadcast the resulting portfolio state.

        Delegates execution to `CashTransferService`, then — only for a
        freshly committed (non-replay) transfer — broadcasts the updated
        cash balance, positions, and transfer details to the portfolio's
        WebSocket group.
        """
        result = self._cash_service.apply_transfer(
            portfolio_id=portfolio_id,
            direction=direction,
            amount=amount,
            idempotency_key=idempotency_key,
        )

        if not result.is_replay:
            self._broadcast_portfolio_update(
                result.transaction.portfolio,
                latest_cash_transaction=result.transaction,
            )

        return result

    @staticmethod
    def _broadcast_portfolio_update(
        portfolio: Portfolio,
        *,
        latest_trade: Trade | None = None,
        latest_cash_transaction: CashTransaction | None = None,
    ) -> None:
        """Broadcast the portfolio's current state to its WebSocket group.

        Takes the already-loaded `Portfolio` instance from the calling
        service (rather than re-fetching by ID) to avoid a redundant query —
        `TradeExecutionService`/`CashTransferService` both already hold the
        row they just mutated inside the same request.

        Sends the resulting cash balance and full position list, plus
        whichever of `latest_trade`/`latest_cash_transaction` triggered this
        update (at most one is passed per call), so subscribed clients can
        prepend the new entry to their local trade/transaction history
        without a separate re-fetch. No-op if no channel layer is configured
        (e.g. in a test environment without Channels wired up).
        """
        channel_layer = get_channel_layer()
        if channel_layer is None:
            logger.warning(
                "Skipped portfolio broadcast: no channel layer configured.",
                extra={"portfolio_id": str(portfolio.id)},
            )
            return

        positions = [
            {"ticker": p.ticker, "quantity": str(p.quantity)}
            for p in Position.objects.filter(portfolio=portfolio)
        ]

        payload: dict[str, Any] = {
            "portfolio_id": str(portfolio.id),
            "cash_balance": str(portfolio.cash_balance),
            "positions": positions,
        }

        if latest_trade is not None:
            payload["latest_trade"] = {
                "trade_id": str(latest_trade.id),
                "ticker": latest_trade.ticker,
                "trade_type": latest_trade.trade_type,
                "quantity": str(latest_trade.quantity),
                "price": str(latest_trade.price),
                "total_value": str(latest_trade.total_value),
                "timestamp": latest_trade.timestamp.isoformat(),
            }

        if latest_cash_transaction is not None:
            payload["latest_cash_transaction"] = {
                "transaction_id": str(latest_cash_transaction.id),
                "direction": latest_cash_transaction.direction,
                "amount": str(latest_cash_transaction.amount),
                "resulting_balance": str(latest_cash_transaction.resulting_balance),
                "timestamp": latest_cash_transaction.timestamp.isoformat(),
            }

        async_to_sync(channel_layer.group_send)(
            portfolio_group_name(portfolio.id),
            {"type": "portfolio.update", "payload": payload},
        )
        logger.debug(
            "Broadcast portfolio update.",
            extra={"portfolio_id": str(portfolio.id)},
        )
