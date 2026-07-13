"""Service-layer and model tests for the ledger app.

Covers `TradeExecutionService`'s ACID guarantees (fund/position checks,
idempotent replay, stale-price rejection) and `Trade`'s immutability
enforcement, using `FakePriceCacheService` to avoid a live Redis dependency.
"""

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from ledger.exceptions import (
    InsufficientFundsError,
    InsufficientPositionError,
    PriceUnavailableError,
)
from ledger.models import Portfolio, Position, Trade
from ledger.services.price_service import PriceCacheService
from ledger.services.trade_service import TradeExecutionService

User = get_user_model()


class FakePriceCacheService(PriceCacheService):
    """Test double avoiding a live Redis dependency."""

    def __init__(self, price: Decimal | None = Decimal("100.0000")):
        self._price = price  # skip PriceCacheService.__init__ / real redis client

    def get_live_price(self, ticker: str) -> Decimal:
        """Return the configured fake price, or raise if configured as unavailable."""
        if self._price is None:
            raise PriceUnavailableError(f"No live price available for '{ticker}'.")
        return self._price


class TradeExecutionServiceTests(TestCase):
    """Exercises `TradeExecutionService`'s business rules and ACID guarantees."""

    def setUp(self):
        """Create a test user with a $1000 portfolio."""
        self.user = User.objects.create_user(username="trader", password="pw")
        self.portfolio = Portfolio.objects.create(
            user=self.user, cash_balance=Decimal("1000.0000")
        )

    def _service(self, price=Decimal("100.0000")):
        """Build a TradeExecutionService wired to a fake, Redis-free price feed."""
        return TradeExecutionService(price_service=FakePriceCacheService(price))

    def test_buy_debits_cash_and_creates_position(self):
        """A BUY should debit cash by quantity*price and create/increase the position."""
        service = self._service()
        result = service.execute_trade(
            portfolio_id=self.portfolio.id,
            ticker="aapl",
            trade_type=Trade.TradeType.BUY,
            quantity=Decimal("2"),
            idempotency_key=uuid.uuid4(),
        )

        self.portfolio.refresh_from_db()
        position = Position.objects.get(portfolio=self.portfolio, ticker="AAPL")

        self.assertFalse(result.is_replay)
        self.assertEqual(self.portfolio.cash_balance, Decimal("800.0000"))
        self.assertEqual(position.quantity, Decimal("2.0000"))
        self.assertEqual(result.trade.total_value, Decimal("200.0000"))

    def test_buy_insufficient_funds_raises_and_rolls_back(self):
        """A BUY exceeding cash_balance should raise and leave the portfolio untouched."""
        service = self._service(price=Decimal("10000.0000"))
        with self.assertRaises(InsufficientFundsError):
            service.execute_trade(
                portfolio_id=self.portfolio.id,
                ticker="AAPL",
                trade_type=Trade.TradeType.BUY,
                quantity=Decimal("1"),
                idempotency_key=uuid.uuid4(),
            )

        self.portfolio.refresh_from_db()
        self.assertEqual(self.portfolio.cash_balance, Decimal("1000.0000"))
        self.assertEqual(Trade.objects.count(), 0)

    def test_sell_insufficient_position_raises(self):
        """A SELL exceeding (or with no) held quantity should raise."""
        service = self._service()
        with self.assertRaises(InsufficientPositionError):
            service.execute_trade(
                portfolio_id=self.portfolio.id,
                ticker="AAPL",
                trade_type=Trade.TradeType.SELL,
                quantity=Decimal("1"),
                idempotency_key=uuid.uuid4(),
            )

    def test_idempotent_replay_returns_existing_trade_without_double_charging(self):
        """Resubmitting the same idempotency_key must return the original trade, not charge twice."""
        service = self._service()
        key = uuid.uuid4()

        first = service.execute_trade(
            portfolio_id=self.portfolio.id,
            ticker="AAPL",
            trade_type=Trade.TradeType.BUY,
            quantity=Decimal("1"),
            idempotency_key=key,
        )
        second = service.execute_trade(
            portfolio_id=self.portfolio.id,
            ticker="AAPL",
            trade_type=Trade.TradeType.BUY,
            quantity=Decimal("1"),
            idempotency_key=key,
        )

        self.portfolio.refresh_from_db()
        self.assertFalse(first.is_replay)
        self.assertTrue(second.is_replay)
        self.assertEqual(first.trade.id, second.trade.id)
        self.assertEqual(Trade.objects.count(), 1)
        self.assertEqual(self.portfolio.cash_balance, Decimal("900.0000"))

    def test_stale_price_rejects_trade(self):
        """No live price available (simulated missing/expired Redis key) must reject the trade."""
        service = self._service(price=None)
        with self.assertRaises(PriceUnavailableError):
            service.execute_trade(
                portfolio_id=self.portfolio.id,
                ticker="AAPL",
                trade_type=Trade.TradeType.BUY,
                quantity=Decimal("1"),
                idempotency_key=uuid.uuid4(),
            )


class TradeModelTests(TestCase):
    """Exercises `Trade`'s model-level immutability enforcement."""

    def setUp(self):
        """Create a test user with a default (zero-balance) portfolio."""
        self.user = User.objects.create_user(username="trader2", password="pw")
        self.portfolio = Portfolio.objects.create(user=self.user)

    def test_trade_is_immutable(self):
        """Modifying and re-saving an existing Trade row must raise ValueError."""
        trade = Trade.objects.create(
            portfolio=self.portfolio,
            ticker="AAPL",
            trade_type=Trade.TradeType.BUY,
            quantity=Decimal("1.0000"),
            price=Decimal("100.0000"),
            total_value=Decimal("100.0000"),
        )
        trade.price = Decimal("200.0000")
        with self.assertRaises(ValueError):
            trade.save()
