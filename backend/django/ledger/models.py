"""Data layer for the ledger app: Portfolio, Position, Trade, and
CashTransaction.

All currency and quantity fields use `DecimalField(max_digits=19,
decimal_places=4)` — never float — for strict mathematical precision
appropriate to a financial system of record. `Trade` and `CashTransaction`
are immutable, append-only ledger entries (enforced via `save()` overrides)
so the portfolio's state is always reconstructible from history.
"""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.db import models

if TYPE_CHECKING:
    from accounts.models import User


class PortfolioQuerySet(models.QuerySet["Portfolio"]):
    """Scoping helpers so data-isolation lives in one place, not per-view."""

    def for_user(self, user: User) -> PortfolioQuerySet:
        """Return only the Portfolio(s) belonging to `user`.

        Centralizes per-user data isolation (OWASP A01 — broken access
        control) so every portfolio-scoped lookup across the app — REST
        views, WebSocket consumers, admin, future code — filters through
        the same choke point instead of repeating `filter(user=...)` ad hoc.
        """
        return self.filter(user=user)


class Portfolio(models.Model):
    """Top-level account holding cash and linking to positions."""

    id: models.UUIDField = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    user: models.OneToOneField = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="portfolio"
    )
    # DecimalField for strict mathematical precision — never use float for money.
    cash_balance: models.DecimalField = models.DecimalField(
        max_digits=19, decimal_places=4, default=Decimal("0.0000")
    )
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    objects = PortfolioQuerySet.as_manager()

    def __str__(self) -> str:
        """Human-readable label used in the Django admin and shell."""
        return f"{self.user}'s Portfolio - Balance: ${self.cash_balance}"


class Position(models.Model):
    """Aggregate quantity of a specific ticker held in a portfolio."""

    id: models.UUIDField = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    portfolio: models.ForeignKey = models.ForeignKey(
        Portfolio, on_delete=models.CASCADE, related_name="positions"
    )
    ticker: models.CharField = models.CharField(max_length=10, db_index=True)
    quantity: models.DecimalField = models.DecimalField(
        max_digits=19, decimal_places=4, default=Decimal("0.0000")
    )
    last_updated: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["portfolio", "ticker"], name="unique_portfolio_ticker"
            )
        ]

    def __str__(self) -> str:
        """Human-readable label used in the Django admin and shell."""
        return f"{self.ticker}: {self.quantity} shares"


class Trade(models.Model):
    """Immutable ledger entry. Once written, a Trade is never updated or deleted."""

    class TradeType(models.TextChoices):
        """Direction of a security trade: buying or selling a position."""

        BUY = "BUY", "Buy"
        SELL = "SELL", "Sell"

    id: models.UUIDField = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )

    # Client-provided (or server-generated) key used to make trade submission
    # idempotent. Distinct from `id`: this is the caller's dedup token, not
    # the row identity.
    idempotency_key: models.UUIDField = models.UUIDField(
        unique=True, default=uuid.uuid4, editable=False
    )

    portfolio: models.ForeignKey = models.ForeignKey(
        Portfolio, on_delete=models.PROTECT, related_name="trades"
    )
    ticker: models.CharField = models.CharField(max_length=10, db_index=True)
    trade_type: models.CharField = models.CharField(
        max_length=4, choices=TradeType.choices
    )

    quantity: models.DecimalField = models.DecimalField(max_digits=19, decimal_places=4)
    price: models.DecimalField = models.DecimalField(max_digits=19, decimal_places=4)
    total_value: models.DecimalField = models.DecimalField(
        max_digits=19, decimal_places=4
    )

    timestamp: models.DateTimeField = models.DateTimeField(
        auto_now_add=True, db_index=True
    )

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(
                fields=["portfolio", "timestamp"], name="trade_portfolio_ts_idx"
            ),
        ]

    def __str__(self) -> str:
        """Human-readable label used in the Django admin and shell."""
        return f"{self.trade_type} {self.quantity} {self.ticker} @ {self.price}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Persist the trade, rejecting any attempt to modify an existing row.

        Lightweight application-layer enforcement of immutability — a Trade
        may only ever be inserted, never updated, so the ledger's audit
        trail can be trusted without relying solely on DB-level permissions.

        Checks `self._state.adding` rather than `self.pk is not None`: `id`
        is a client-generated `UUIDField(default=uuid.uuid4)`, so `self.pk`
        is already set on a brand-new, never-saved instance — `pk is not
        None` would incorrectly reject every insert. `_state.adding` is
        Django's own signal for "this instance hasn't been saved yet,
        regardless of whether its PK was assigned client-side or by the DB.
        """
        if not self._state.adding:
            raise ValueError(
                "Ledger entries (Trades) are immutable and cannot be modified."
            )
        super().save(*args, **kwargs)


class CashTransaction(models.Model):
    """Immutable ledger entry for cash movement (deposit/withdrawal) not tied
    to a security trade. Mirrors Trade's audit-trail/immutability guarantees
    so cash_balance is always reconstructable from history.
    """

    class Direction(models.TextChoices):
        """Direction of cash movement: deposit (CREDIT) or withdrawal (DEBIT)."""

        CREDIT = "CREDIT", "Credit"
        DEBIT = "DEBIT", "Debit"

    id: models.UUIDField = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )

    # Client-provided (or server-generated) key used to make transfer
    # submission idempotent.
    idempotency_key: models.UUIDField = models.UUIDField(
        unique=True, default=uuid.uuid4, editable=False
    )

    portfolio: models.ForeignKey = models.ForeignKey(
        Portfolio, on_delete=models.PROTECT, related_name="cash_transactions"
    )
    direction: models.CharField = models.CharField(
        max_length=6, choices=Direction.choices
    )
    amount: models.DecimalField = models.DecimalField(max_digits=19, decimal_places=4)
    # Snapshot of cash_balance immediately after this entry was applied.
    resulting_balance: models.DecimalField = models.DecimalField(
        max_digits=19, decimal_places=4
    )

    timestamp: models.DateTimeField = models.DateTimeField(
        auto_now_add=True, db_index=True
    )

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(
                fields=["portfolio", "timestamp"], name="cashtxn_portfolio_ts_idx"
            ),
        ]

    def __str__(self) -> str:
        """Human-readable label used in the Django admin and shell."""
        return f"{self.direction} {self.amount} -> balance {self.resulting_balance}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Persist the transaction, rejecting any attempt to modify an existing row.

        Mirrors `Trade.save()`'s immutability enforcement (including the
        `_state.adding` check, not `pk is not None` — see that method's
        docstring for why) so cash movement history is as trustworthy an
        audit trail as the trade ledger.
        """
        if not self._state.adding:
            raise ValueError("Cash transactions are immutable and cannot be modified.")
        super().save(*args, **kwargs)
