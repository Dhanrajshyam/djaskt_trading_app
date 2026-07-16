"""Django admin registrations for the ledger app's models.

Trade and CashTransaction admins disable change/delete permissions to
mirror the models' own `save()`-level immutability enforcement, so backoffice
staff can inspect the ledger but never edit history through the admin UI.
"""

from django.contrib import admin
from django.http import HttpRequest

from ledger.models import CashTransaction, Portfolio, Position, Trade


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    # django-stubs types ModelAdmin as Generic for static checking, but
    # Django's actual runtime class has no __class_getitem__ — subscripting
    # it would raise TypeError at admin.autodiscover() time (confirmed via
    # a real django.setup() run). See accounts.admin.UserAdmin's identical
    # comment for the same pattern.
    """Admin list/search view for user portfolios."""

    list_display = ("id", "user", "cash_balance", "updated_at")
    search_fields = ("user__username", "user__email")


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Admin list/search view for per-ticker holdings within a portfolio."""

    list_display = ("id", "portfolio", "ticker", "quantity", "last_updated")
    list_filter = ("ticker",)
    search_fields = ("ticker", "portfolio__user__username")


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Read-only admin view over the immutable trade ledger."""

    list_display = (
        "id",
        "portfolio",
        "ticker",
        "trade_type",
        "quantity",
        "price",
        "total_value",
        "timestamp",
    )
    list_filter = ("trade_type", "ticker")
    search_fields = ("ticker", "idempotency_key", "portfolio__user__username")
    readonly_fields = [f.name for f in Trade._meta.fields]

    def has_change_permission(
        self, request: HttpRequest, obj: Trade | None = None
    ) -> bool:
        """Disallow editing trades — the model already enforces immutability
        at the ORM level; mirror it in the admin UI."""
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: Trade | None = None
    ) -> bool:
        """Disallow deleting trades — the ledger is append-only."""
        return False


@admin.register(CashTransaction)
class CashTransactionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Read-only admin view over the immutable cash transaction ledger."""

    list_display = (
        "id",
        "portfolio",
        "direction",
        "amount",
        "resulting_balance",
        "timestamp",
    )
    list_filter = ("direction",)
    search_fields = ("idempotency_key", "portfolio__user__username")
    readonly_fields = [f.name for f in CashTransaction._meta.fields]

    def has_change_permission(
        self, request: HttpRequest, obj: CashTransaction | None = None
    ) -> bool:
        """Disallow editing cash transactions — mirrors the model-level
        immutability enforcement in the admin UI."""
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: CashTransaction | None = None
    ) -> bool:
        """Disallow deleting cash transactions — the ledger is append-only."""
        return False
