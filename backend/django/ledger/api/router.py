"""Django Ninja Extra contract layer for the ledger app.

Thin by design: validate the request shape (schemas.py already did that),
enforce object-level authorization, delegate to the orchestrator, and map
domain exceptions to HTTP status codes. No business logic lives here.

Class-based via ninja_extra's `api_controller` — each HTTP action is a
method on `LedgerController` rather than a free function bound to a
function-based Router.
"""

from django.http import HttpRequest
from ninja_extra import api_controller, http_get, http_post
from ninja_extra.pagination import LimitOffsetPagination, NinjaPaginationResponseSchema, paginate

from ledger.api.auth import DenylistCheckingJWTAuth
from ledger.api.schemas import (
    CashTransferRequestSchema,
    CashTransferResponseSchema,
    ErrorSchema,
    PortfolioResponseSchema,
    PositionSchema,
    TradeHistoryItemSchema,
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
from ledger.models import Trade
from ledger.services.authorization import get_portfolio_for_user
from ledger.services.main_service import LedgerOrchestratorService


@api_controller("/ledger", tags=["ledger"], auth=DenylistCheckingJWTAuth())
class LedgerController:
    """Class-based REST controller for the ledger app's HTTP endpoints.

    Requires a valid, non-revoked JWT access token (`DenylistCheckingJWTAuth`)
    on every action. Each method follows the same shape: resolve the
    caller's own portfolio, delegate to `LedgerOrchestratorService`, map
    domain exceptions to HTTP status codes.
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
            404: ErrorSchema,
        },
    )
    def submit_trade(self, request: HttpRequest, payload: TradeRequestSchema):
        """Submit a BUY/SELL trade for the authenticated user's portfolio.

        Returns 201 for a newly committed trade, 200 for an idempotent
        replay, 404 if the caller has no portfolio, or 409 for a
        business-rule violation (insufficient funds/position, stale price,
        invalid request).
        """
        # Portfolio.user is a strict one-to-one relationship — no client-
        # supplied ID to check ownership of, only "does this user have a
        # portfolio at all".
        portfolio = get_portfolio_for_user(request.user)
        if portfolio is None:
            return 404, ErrorSchema(detail="No portfolio found for this account.")

        try:
            result = self._orchestrator.submit_trade(
                portfolio_id=portfolio.id,
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

    @http_get(
        "/portfolio/",
        response={200: PortfolioResponseSchema, 404: ErrorSchema},
    )
    def get_portfolio(self, request: HttpRequest):
        """Return the authenticated user's cash balance and current holdings."""
        portfolio = get_portfolio_for_user(request.user)
        if portfolio is None:
            return 404, ErrorSchema(detail="No portfolio found for this account.")

        positions = [
            PositionSchema(ticker=p.ticker, quantity=p.quantity)
            for p in portfolio.positions.all()
        ]
        return 200, PortfolioResponseSchema(
            portfolio_id=portfolio.id,
            cash_balance=portfolio.cash_balance,
            positions=positions,
        )

    @http_get(
        "/trades/",
        response={200: NinjaPaginationResponseSchema[TradeHistoryItemSchema]},
    )
    @paginate(LimitOffsetPagination)
    def list_trades(self, request: HttpRequest):
        """Return the authenticated user's trade history, newest first.

        Paginated via `?limit=&offset=` (django-ninja-extra's built-in
        `LimitOffsetPagination` — see `ninja_extra.pagination`), rather
        than hand-rolled, per the app's existing latency/API conventions.
        Response is wrapped as `{"items": [...], "count": N}` by the
        pagination decorator.
        """
        portfolio = get_portfolio_for_user(request.user)
        if portfolio is None:
            return Trade.objects.none()
        # Trade.Meta.ordering is already "-timestamp"; explicit here for
        # clarity at the call site (matches the WebSocket consumer's
        # equivalent query in ledger/realtime/consumers.py).
        return Trade.objects.filter(portfolio=portfolio).order_by("-timestamp")

    @http_post(
        "/cash-transfer/",
        response={
            201: CashTransferResponseSchema,
            200: CashTransferResponseSchema,
            409: ErrorSchema,
            404: ErrorSchema,
        },
    )
    def transfer_cash(self, request: HttpRequest, payload: CashTransferRequestSchema):
        """Submit a CREDIT (deposit) or DEBIT (withdrawal) for the authenticated user's portfolio.

        Returns 201 for a newly committed transfer, 200 for an idempotent
        replay, 404 if the caller has no portfolio, or 409 for a
        business-rule violation (insufficient funds for a DEBIT, invalid
        request).
        """
        portfolio = get_portfolio_for_user(request.user)
        if portfolio is None:
            return 404, ErrorSchema(detail="No portfolio found for this account.")

        try:
            result = self._orchestrator.submit_cash_transfer(
                portfolio_id=portfolio.id,
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
