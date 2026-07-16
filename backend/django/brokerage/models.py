"""Data layer for the brokerage app: Brokerage, BrokerageEndpoint, and
UserBrokerageLink.

Three-table split (identity / API shape / user linkage) rather than one wide
model, matching `ledger.models`'s relational style. Notably absent: nowhere
in this app is a user's broker password or TOTP ever persisted — those are
submitted fresh on every login (see `brokerage.api.schemas.BrokerLoginRequestSchema`)
and used transiently within a single request, never written to a row here.
"""

import uuid
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models

if TYPE_CHECKING:
    from accounts.models import User


class Brokerage(models.Model):
    """A brokerage the platform supports (Angel One, Zerodha, Dhan, ...).

    One row per broker, not per user — `name` is the stable slug used as the
    strategy-registry lookup key and as the Redis session key's brokerage
    component, so it stays valid even if this row is ever deleted and
    recreated (e.g. to fix a misconfigured endpoint).
    """

    id: models.UUIDField = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    name: models.CharField = models.CharField(max_length=50, unique=True)
    display_name: models.CharField = models.CharField(max_length=100)
    is_active: models.BooleanField = models.BooleanField(default=True)
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        """Human-readable label used in the Django admin and shell."""
        return f"{self.display_name}"


class BrokerageEndpoint(models.Model):
    """How to call a brokerage's API for a given purpose (login, ...).

    `success_response_structure`/`error_response_structure` are reference
    documentation for admins editing this row — what shape a maintainer
    should expect the broker's response to have — not a template the code
    parses generically at runtime. Actual response parsing happens as
    explicit code in each broker's strategy class
    (`brokerage.strategies.base.BaseBrokerAuthStrategy._parse_response`).
    """

    class HttpMethod(models.TextChoices):
        """HTTP method used to call this endpoint."""

        GET = "GET", "GET"
        POST = "POST", "POST"

    class PayloadType(models.TextChoices):
        """Request body encoding used to call this endpoint."""

        JSON = "JSON", "application/json"
        FORM = "FORM", "application/x-www-form-urlencoded"

    id: models.UUIDField = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    brokerage: models.ForeignKey = models.ForeignKey(
        Brokerage, on_delete=models.CASCADE, related_name="endpoints"
    )
    # Room for "logout"/"refresh" endpoints later; only "login" is used by
    # this pass's authentication flow.
    purpose: models.CharField = models.CharField(max_length=20, default="login")
    url: models.URLField = models.URLField()
    http_method: models.CharField = models.CharField(
        max_length=10, choices=HttpMethod.choices, default=HttpMethod.POST
    )
    payload_type: models.CharField = models.CharField(
        max_length=10, choices=PayloadType.choices, default=PayloadType.JSON
    )
    default_headers: models.JSONField = models.JSONField(default=dict, blank=True)
    success_response_structure: models.JSONField = models.JSONField(
        default=dict, blank=True
    )
    error_response_structure: models.JSONField = models.JSONField(
        default=dict, blank=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["brokerage", "purpose"],
                name="unique_brokerage_endpoint_purpose",
            )
        ]

    def __str__(self) -> str:
        """Human-readable label used in the Django admin and shell."""
        return f"{self.brokerage.name}:{self.purpose}"


class UserBrokerageLinkQuerySet(models.QuerySet["UserBrokerageLink"]):
    """Scoping helpers so data-isolation lives in one place, not per-view."""

    def for_user(self, user: User) -> UserBrokerageLinkQuerySet:
        """Return only the UserBrokerageLink(s) belonging to `user`.

        Mirrors `ledger.models.PortfolioQuerySet.for_user` — centralizes
        per-user data isolation (OWASP A01 — broken access control) so every
        link-scoped lookup filters through the same choke point.
        """
        return self.filter(user=user)


class UserBrokerageLink(models.Model):
    """Links a user to a brokerage, storing their broker-specific identifiers.

    `user_brokerage_data` holds semi-stable identifiers a user sets up once
    (e.g. `client_id`, `api_key`) — never a password or TOTP, which are
    submitted fresh at login time and never persisted (see module docstring).
    """

    id: models.UUIDField = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    user: models.ForeignKey = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="brokerage_links",
    )
    brokerage: models.ForeignKey = models.ForeignKey(
        Brokerage, on_delete=models.CASCADE, related_name="user_links"
    )
    user_brokerage_data: models.JSONField = models.JSONField(default=dict)
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    objects = UserBrokerageLinkQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "brokerage"], name="unique_user_brokerage_link"
            )
        ]

    def __str__(self) -> str:
        """Human-readable label used in the Django admin and shell."""
        return f"{self.user}'s link to {self.brokerage.name}"
