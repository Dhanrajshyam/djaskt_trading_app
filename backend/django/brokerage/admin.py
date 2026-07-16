"""Django admin registrations for the brokerage app's models.

`Brokerage`/`BrokerageEndpoint` are operator-configured, rare-to-change
platform configuration (set up once per broker) — managed here rather than
via dedicated REST CRUD endpoints. `UserBrokerageLink` is intentionally not
registered: it's user-facing data managed through the REST API
(`brokerage.api.router.BrokerageController`), scoped to each user's own
links, which the Django admin's staff-wide visibility isn't a fit for.
"""

from django.contrib import admin

from brokerage.models import Brokerage, BrokerageEndpoint


@admin.register(Brokerage)
class BrokerageAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    # django-stubs types ModelAdmin as Generic for static checking, but
    # Django's actual runtime class has no __class_getitem__ — subscripting
    # it would raise TypeError at admin.autodiscover() time. See
    # ledger.admin.PortfolioAdmin's identical comment for the same pattern.
    """Admin list/search view for supported brokerages."""

    list_display = ("name", "display_name", "is_active", "created_at")
    search_fields = ("name", "display_name")


@admin.register(BrokerageEndpoint)
class BrokerageEndpointAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Admin list/search view for each brokerage's API endpoint configuration."""

    list_display = ("brokerage", "purpose", "url", "http_method", "payload_type")
    list_filter = ("purpose", "http_method")
    search_fields = ("brokerage__name", "url")
