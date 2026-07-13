"""Request and response schemas for the ledger REST API.

Pydantic-backed Django Ninja `Schema` classes used by `ledger.api.router`
to validate incoming payloads and serialize outgoing responses. Validators
here enforce structural correctness only (e.g. positive amounts, known
enum values) — business-rule validation (insufficient funds, stale prices,
etc.) belongs in the service layer, not here.
"""

from decimal import Decimal
from typing import Literal
from uuid import UUID

from ninja import Schema
from pydantic import field_validator


class TradeRequestSchema(Schema):
    """Payload for `POST /api/v1/ledger/trade/`.

    No `portfolio_id` — `Portfolio.user` is a strict one-to-one
    relationship, so the caller's portfolio is always resolved from
    `request.user` server-side (see `ledger.services.authorization
    .get_portfolio_for_user`), never trusted from the request body.
    """

    ticker: str
    trade_type: Literal["BUY", "SELL"]
    quantity: Decimal
    idempotency_key: UUID

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        """Uppercase and length-validate the ticker symbol."""
        value = value.strip().upper()
        if not value or len(value) > 10:
            raise ValueError("ticker must be 1-10 characters")
        return value

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, value: Decimal) -> Decimal:
        """Reject non-positive trade quantities before they reach the service layer."""
        if value <= 0:
            raise ValueError("quantity must be strictly positive")
        return value


class TradeResponseSchema(Schema):
    """Response body for a successful or replayed trade submission."""

    trade_id: UUID
    portfolio_id: UUID
    ticker: str
    trade_type: str
    quantity: Decimal
    price: Decimal
    total_value: Decimal
    idempotency_key: UUID
    is_replay: bool


class CashTransferRequestSchema(Schema):
    """Payload for `POST /api/v1/ledger/cash-transfer/`.

    No `portfolio_id` — see `TradeRequestSchema`'s docstring; the same
    reasoning applies here.
    """

    direction: Literal["CREDIT", "DEBIT"]
    amount: Decimal
    idempotency_key: UUID

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, value: Decimal) -> Decimal:
        """Reject non-positive transfer amounts before they reach the service layer."""
        if value <= 0:
            raise ValueError("amount must be strictly positive")
        return value


class CashTransferResponseSchema(Schema):
    """Response body for a successful or replayed cash transfer submission."""

    transaction_id: UUID
    portfolio_id: UUID
    direction: str
    amount: Decimal
    resulting_balance: Decimal
    idempotency_key: UUID
    is_replay: bool


class PositionSchema(Schema):
    """A single holding within a portfolio, as returned by `GET /portfolio/`."""

    ticker: str
    quantity: Decimal


class PortfolioResponseSchema(Schema):
    """Response body for `GET /api/v1/ledger/portfolio/`."""

    portfolio_id: UUID
    cash_balance: Decimal
    positions: list[PositionSchema]


class TradeHistoryItemSchema(Schema):
    """A single trade entry, as returned by `GET /trades/`.

    Serialized directly from `Trade` model instances (Ninja's ORM-object
    mode); `trade_id` doesn't match the model's `id` field name, so it's
    resolved explicitly rather than relying on attribute auto-mapping.
    """

    trade_id: UUID
    ticker: str
    trade_type: str
    quantity: Decimal
    price: Decimal
    total_value: Decimal
    timestamp: str

    @staticmethod
    def resolve_trade_id(obj) -> UUID:
        """Map the model's `id` field to this schema's `trade_id`."""
        return obj.id

    @staticmethod
    def resolve_timestamp(obj) -> str:
        """Serialize the model's `datetime` timestamp as ISO-8601."""
        return obj.timestamp.isoformat()


class ErrorSchema(Schema):
    """Generic error response body used across all ledger endpoints."""

    detail: str
