"""Django Ninja Extra contract layer for the ledger app.

Thin by design: validate the request shape (schemas.py already did that),
enforce object-level authorization, delegate to the orchestrator, and map
domain exceptions to HTTP status codes. No business logic lives here.

Class-based via ninja_extra's `api_controller` — each HTTP action is a
method on `LedgerController` rather than a free function bound to a
function-based Router.
"""

from django.http import HttpRequest
from ninja.security import django_auth
from ninja_extra import api_controller, http_post

from ledger.api.schemas import (
    CashTransferRequestSchema,
    CashTransferResponseSchema,
    ErrorSchema,
    TradeRequestSchema,
    TradeResponseSchema,
)
from ledger.exceptions import (
    InsufficientFundsError,
    InsufficientPositionError,
    InvalidTradeRequestError,
    LedgerServiceError,
    PortfolioNotFoundError,
    PriceUnavailableError,
)
from ledger.services.authorization import get_owned_portfolio_or_none
from ledger.services.main_service import LedgerOrchestratorService


@api_controller("/ledger", tags=["ledger"], auth=django_auth)
class LedgerController:
    """Class-based REST controller for the ledger app's HTTP endpoints.

    Requires Django session authentication (`django_auth`) on every action.
    Each method follows the same shape: authorize, delegate to
    `LedgerOrchestratorService`, map domain exceptions to HTTP status codes.
    """

    def __init__(self) -> None:
        """Initialize the controller with its own orchestrator instance."""
        self._orchestrator = LedgerOrchestratorService()

    @http_post(
        "/trade/",
        response={
            201: TradeResponseSchema,
            200: TradeResponseSchema,
            409: ErrorSchema,
            403: ErrorSchema,
            404: ErrorSchema,
        },
    )
    def submit_trade(self, request: HttpRequest, payload: TradeRequestSchema):
        """Submit a BUY/SELL trade for the authenticated user's portfolio.

        Returns 201 for a newly committed trade, 200 for an idempotent
        replay, 403 if the caller doesn't own the portfolio, 404 if the
        portfolio doesn't exist, or 409 for a business-rule violation
        (insufficient funds/position, stale price, invalid request).
        """
        # Object-level authorization: a user may only trade on their own
        # portfolio (OWASP A01 — broken access control).
        portfolio = get_owned_portfolio_or_none(request.user, payload.portfolio_id)
        if portfolio is None:
            return 403, ErrorSchema(detail="You do not have access to this portfolio.")

        try:
            result = self._orchestrator.submit_trade(
                portfolio_id=payload.portfolio_id,
                ticker=payload.ticker,
                trade_type=payload.trade_type,
                quantity=payload.quantity,
                idempotency_key=payload.idempotency_key,
            )
        except PortfolioNotFoundError as exc:
            return 404, ErrorSchema(detail=str(exc))
        except (InsufficientFundsError, InsufficientPositionError, PriceUnavailableError) as exc:
            return 409, ErrorSchema(detail=str(exc))
        except InvalidTradeRequestError as exc:
            return 409, ErrorSchema(detail=str(exc))
        except LedgerServiceError as exc:
            return 409, ErrorSchema(detail=str(exc))

        trade = result.trade
        response = TradeResponseSchema(
            trade_id=trade.id,
            portfolio_id=trade.portfolio_id,
            ticker=trade.ticker,
            trade_type=trade.trade_type,
            quantity=trade.quantity,
            price=trade.price,
            total_value=trade.total_value,
            idempotency_key=trade.idempotency_key,
            is_replay=result.is_replay,
        )
        status_code = 200 if result.is_replay else 201
        return status_code, response

    @http_post(
        "/cash-transfer/",
        response={
            201: CashTransferResponseSchema,
            200: CashTransferResponseSchema,
            409: ErrorSchema,
            403: ErrorSchema,
            404: ErrorSchema,
        },
    )
    def transfer_cash(self, request: HttpRequest, payload: CashTransferRequestSchema):
        """Submit a CREDIT (deposit) or DEBIT (withdrawal) for the authenticated user's portfolio.

        Returns 201 for a newly committed transfer, 200 for an idempotent
        replay, 403 if the caller doesn't own the portfolio, 404 if the
        portfolio doesn't exist, or 409 for a business-rule violation
        (insufficient funds for a DEBIT, invalid request).
        """
        portfolio = get_owned_portfolio_or_none(request.user, payload.portfolio_id)
        if portfolio is None:
            return 403, ErrorSchema(detail="You do not have access to this portfolio.")

        try:
            result = self._orchestrator.submit_cash_transfer(
                portfolio_id=payload.portfolio_id,
                direction=payload.direction,
                amount=payload.amount,
                idempotency_key=payload.idempotency_key,
            )
        except PortfolioNotFoundError as exc:
            return 404, ErrorSchema(detail=str(exc))
        except InsufficientFundsError as exc:
            return 409, ErrorSchema(detail=str(exc))
        except InvalidTradeRequestError as exc:
            return 409, ErrorSchema(detail=str(exc))
        except LedgerServiceError as exc:
            return 409, ErrorSchema(detail=str(exc))

        cash_transaction = result.transaction
        response = CashTransferResponseSchema(
            transaction_id=cash_transaction.id,
            portfolio_id=cash_transaction.portfolio_id,
            direction=cash_transaction.direction,
            amount=cash_transaction.amount,
            resulting_balance=cash_transaction.resulting_balance,
            idempotency_key=cash_transaction.idempotency_key,
            is_replay=result.is_replay,
        )
        status_code = 200 if result.is_replay else 201
        return status_code, response
