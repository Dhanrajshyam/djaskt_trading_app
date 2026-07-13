"""Django admin registrations for the ledger app's models.

Trade and CashTransaction admins disable change/delete permissions to
mirror the models' own `save()`-level immutability enforcement, so backoffice
staff can inspect the ledger but never edit history through the admin UI.
"""

from django.contrib import admin

from ledger.models import CashTransaction, Portfolio, Position, Trade


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    """Admin list/search view for user portfolios."""

    list_display = ("id", "user", "cash_balance", "updated_at")
    search_fields = ("user__username", "user__email")


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    """Admin list/search view for per-ticker holdings within a portfolio."""

    list_display = ("id", "portfolio", "ticker", "quantity", "last_updated")
    list_filter = ("ticker",)
    search_fields = ("ticker", "portfolio__user__username")


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
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

    def has_change_permission(self, request, obj=None):
        """Disallow editing trades — the model already enforces immutability
        at the ORM level; mirror it in the admin UI."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Disallow deleting trades — the ledger is append-only."""
        return False


@admin.register(CashTransaction)
class CashTransactionAdmin(admin.ModelAdmin):
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

    def has_change_permission(self, request, obj=None):
        """Disallow editing cash transactions — mirrors the model-level
        immutability enforcement in the admin UI."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Disallow deleting cash transactions — the ledger is append-only."""
        return False
