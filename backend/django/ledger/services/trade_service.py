"""Trade execution: the ACID-critical core of the ledger.

Isolated from the API/routing layer and from the realtime broadcast concern —
this module's only job is to apply a trade to a Portfolio/Position pair with
strict correctness guarantees under concurrency.
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from django.db import transaction

from ledger.exceptions import (
    InsufficientFundsError,
    InsufficientPositionError,
    InvalidTradeRequestError,
    PortfolioNotFoundError,
)
from ledger.models import Portfolio, Position, Trade
from ledger.services.price_service import PriceCacheService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TradeResult:
    """Outcome of a trade submission.

    `is_replay` distinguishes a freshly committed trade from an idempotent
    replay (same `idempotency_key` as a prior request), so callers such as
    the API layer can map the result to the correct HTTP status code (201
    vs 200) without re-deriving that distinction themselves.
    """

    trade: Trade
    is_replay: bool


class TradeExecutionService:
    """Executes BUY/SELL trades with pessimistic locking and idempotency.

    Depends on a `PriceCacheService` instance (constructor-injected) rather
    than instantiating one internally, so tests can supply a fake without
    touching Redis.
    """

    def __init__(self, price_service: PriceCacheService | None = None) -> None:
        """Initialize the service, optionally injecting a `PriceCacheService`.

        Constructor injection (rather than instantiating one internally)
        lets tests supply a fake price service without touching Redis.
        """
        self._price_service = price_service or PriceCacheService()

    def execute_trade(
        self,
        *,
        portfolio_id: UUID,
        ticker: str,
        trade_type: str,
        quantity: Decimal,
        idempotency_key: UUID,
    ) -> TradeResult:
        """Execute a BUY or SELL trade against a portfolio.

        Applies strict ACID guarantees via `select_for_update()` (locking
        Portfolio before Position, in that fixed order, to avoid deadlocks
        between concurrent trades) inside a `transaction.atomic()` block, so
        concurrent trades against the same portfolio can never double-spend
        cash or oversell a position. Idempotent: replaying the same
        `idempotency_key` returns the original trade without re-executing
        any locks or mutations.

        Raises `InvalidTradeRequestError` for structurally invalid input,
        `PortfolioNotFoundError` if the portfolio doesn't exist,
        `InsufficientFundsError`/`InsufficientPositionError` if the trade
        would violate a business rule, and `PriceUnavailableError` (via the
        injected price service) if no fresh live price exists for `ticker`.
        """
        if trade_type not in Trade.TradeType.values:
            raise InvalidTradeRequestError(f"Invalid trade type: {trade_type!r}")
        if quantity <= 0:
            raise InvalidTradeRequestError("Quantity must be strictly positive.")

        # Idempotency check happens outside any lock: a replayed request must
        # never contend for the same row locks as a fresh trade.
        existing_trade = Trade.objects.filter(idempotency_key=idempotency_key).first()
        if existing_trade is not None:
            logger.info(
                "Idempotent trade replay detected; returning existing trade.",
                extra={
                    "portfolio_id": str(portfolio_id),
                    "ticker": ticker,
                    "idempotency_key": str(idempotency_key),
                },
            )
            return TradeResult(trade=existing_trade, is_replay=True)

        # Fetch the live price before opening the transaction — no DB lock
        # should ever be held while waiting on an external Redis call.
        price = self._price_service.get_live_price(ticker)
        ticker = ticker.upper()
        total_value = quantity * price

        with transaction.atomic():
            # Lock ordering is always Portfolio then Position, to avoid
            # deadlocks between concurrent trades touching the same pair.
            try:
                portfolio = Portfolio.objects.select_for_update().get(id=portfolio_id)
            except Portfolio.DoesNotExist as exc:
                logger.warning(
                    "Trade rejected: portfolio not found.",
                    extra={"portfolio_id": str(portfolio_id), "ticker": ticker},
                )
                raise PortfolioNotFoundError(
                    f"Portfolio {portfolio_id} does not exist."
                ) from exc

            position: Position | None
            if trade_type == Trade.TradeType.BUY:
                if portfolio.cash_balance < total_value:
                    logger.warning(
                        "Trade rejected: insufficient funds.",
                        extra={
                            "portfolio_id": str(portfolio_id),
                            "ticker": ticker,
                            "cash_balance": str(portfolio.cash_balance),
                            "total_value": str(total_value),
                        },
                    )
                    raise InsufficientFundsError(
                        "Insufficient funds to execute buy order."
                    )

                portfolio.cash_balance -= total_value

                position, _ = Position.objects.select_for_update().get_or_create(
                    portfolio=portfolio,
                    ticker=ticker,
                    defaults={"quantity": Decimal("0.0000")},
                )
                position.quantity += quantity
                position.save()

            else:  # SELL
                position = (
                    Position.objects.select_for_update()
                    .filter(portfolio=portfolio, ticker=ticker)
                    .first()
                )
                if position is None or position.quantity < quantity:
                    logger.warning(
                        "Trade rejected: insufficient position.",
                        extra={
                            "portfolio_id": str(portfolio_id),
                            "ticker": ticker,
                            "held_quantity": str(
                                position.quantity if position else Decimal("0")
                            ),
                            "requested_quantity": str(quantity),
                        },
                    )
                    raise InsufficientPositionError(
                        f"Insufficient quantity of {ticker} to sell."
                    )

                position.quantity -= quantity
                portfolio.cash_balance += total_value
                position.save()

            portfolio.save()

            trade = Trade.objects.create(
                portfolio=portfolio,
                ticker=ticker,
                trade_type=trade_type,
                quantity=quantity,
                price=price,
                total_value=total_value,
                idempotency_key=idempotency_key,
            )

        logger.info(
            "Trade committed.",
            extra={
                "trade_id": str(trade.id),
                "portfolio_id": str(portfolio_id),
                "ticker": ticker,
                "trade_type": trade_type,
                "quantity": str(quantity),
                "price": str(price),
                "total_value": str(total_value),
            },
        )
        return TradeResult(trade=trade, is_replay=False)
