"""Request and response schemas for the brokerage REST API.

Pydantic-backed Django Ninja `Schema` classes, matching `ledger.api.schemas`'s
convention: validators enforce structural correctness only (e.g. a known
brokerage name); business-rule validation (broker rejects the login, no
link exists, etc.) belongs in the service layer, not here.
"""

from typing import Any
from uuid import UUID

from ninja import Schema
from pydantic import field_validator

from brokerage.strategies.registry import BROKER_STRATEGIES


def _validate_known_brokerage(value: str) -> str:
    """Shared validator body: reject any brokerage name with no registered strategy."""
    if value not in BROKER_STRATEGIES:
        raise ValueError(f"Unknown brokerage: {value!r}")
    return value


class UserBrokerageLinkCreateSchema(Schema):
    """Payload for `POST /api/v1/brokerage/links/`.

    `user_brokerage_data` holds semi-stable identifiers (client_id, api_key)
    set up once — never a password or TOTP, which are submitted fresh at
    login time (see `BrokerLoginRequestSchema`) and never stored.
    """

    brokerage_name: str
    user_brokerage_data: dict[str, Any]

    @field_validator("brokerage_name")
    @classmethod
    def brokerage_must_be_known(cls, value: str) -> str:
        """Reject a brokerage name with no registered strategy."""
        return _validate_known_brokerage(value)


class UserBrokerageLinkResponseSchema(Schema):
    """Response body for a user's brokerage link.

    `is_connected` reflects whether a session is currently cached in Redis
    for this user+brokerage (`BrokerSessionCache.get()`), not anything
    stored on the `UserBrokerageLink` row itself — a link can exist while
    disconnected (never logged in, or the IST-midnight TTL expired).
    """

    id: UUID
    brokerage_name: str
    user_brokerage_data: dict[str, Any]
    is_connected: bool


class BrokerLoginRequestSchema(Schema):
    """Payload for `POST /api/v1/brokerage/login/`.

    Common envelope, opaque per-broker secrets: `brokerage_name` is explicit
    and typed (the controller/orchestrator need it to pick a strategy);
    `user_credentials` is a flexible dict, mirroring
    `UserBrokerageLinkCreateSchema.user_brokerage_data`. Not every broker's
    login takes the same fields (password+TOTP for Angel One, but another
    broker might need an MPIN, a client secret, etc.) — the schema stays
    generic here, and each strategy's `_validate_credentials` is the one
    place that knows and enforces the field set a specific broker needs.
    """

    brokerage_name: str
    user_credentials: dict[str, Any]

    @field_validator("brokerage_name")
    @classmethod
    def brokerage_must_be_known(cls, value: str) -> str:
        """Reject a brokerage name with no registered strategy."""
        return _validate_known_brokerage(value)


class BrokerLoginResponseSchema(Schema):
    """Response body for a successful broker login.

    Deliberately omits `jwt_token`/`feed_token` — those are live broker
    session credentials cached in Redis for a future FastAPI daemon to
    read, and must never round-trip through this response to the browser.
    """

    brokerage_name: str
    client_id: str
    expires_in_seconds: int


class BrokerLogoutRequestSchema(Schema):
    """Payload for `POST /api/v1/brokerage/logout/`."""

    brokerage_name: str

    @field_validator("brokerage_name")
    @classmethod
    def brokerage_must_be_known(cls, value: str) -> str:
        """Reject a brokerage name with no registered strategy."""
        return _validate_known_brokerage(value)


class BrokerLogoutResponseSchema(Schema):
    """Response body for a broker logout — always 200, never an error for a
    broker-side failure (see `BrokerAuthOrchestrator.logout_and_clear`)."""

    brokerage_name: str
    disconnected: bool
    message: str


class ErrorSchema(Schema):
    """Generic error response body used across all brokerage endpoints."""

    detail: str
