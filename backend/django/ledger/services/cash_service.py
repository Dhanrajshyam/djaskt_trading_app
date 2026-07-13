"""Cash transfer execution: deposits/withdrawals against a Portfolio's
cash_balance, independent of security trades.

Isolated from the trade execution path — cash transfers never touch
Position rows — but follows the identical ACID pattern: idempotency check
outside any lock, then select_for_update() + atomic() around the mutation
and the immutable ledger write.
"""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from django.db import transaction

from ledger.exceptions import (
    InsufficientFundsError,
    InvalidTradeRequestError,
    PortfolioNotFoundError,
)
from ledger.models import CashTransaction, Portfolio


@dataclass(frozen=True)
class CashTransferResult:
    """Outcome of a cash transfer submission.

    `is_replay` distinguishes a freshly committed transfer from an
    idempotent replay (same `idempotency_key` as a prior request), mirroring
    `TradeResult`'s role for trade submissions.
    """

    transaction: CashTransaction
    is_replay: bool


class CashTransferService:
    """Executes CREDIT/DEBIT cash transfers with pessimistic locking and idempotency."""

    def apply_transfer(
        self,
        *,
        portfolio_id: UUID,
        direction: str,
        amount: Decimal,
        idempotency_key,
    ) -> CashTransferResult:
        """Apply a CREDIT (deposit) or DEBIT (withdrawal) to a portfolio's cash balance.

        Follows the same ACID pattern as `TradeExecutionService.execute_trade`:
        an idempotency check outside any lock, then `select_for_update()` on
        the `Portfolio` row inside `transaction.atomic()` around both the
        balance mutation and the immutable `CashTransaction` write, so
        concurrent transfers against the same portfolio can never race.

        Raises `InvalidTradeRequestError` for structurally invalid input,
        `PortfolioNotFoundError` if the portfolio doesn't exist, and
        `InsufficientFundsError` if a DEBIT would overdraw the balance.
        """
        if direction not in CashTransaction.Direction.values:
            raise InvalidTradeRequestError(f"Invalid transfer direction: {direction!r}")
        if amount <= 0:
            raise InvalidTradeRequestError("Amount must be strictly positive.")

        # Idempotency check happens outside any lock, matching TradeExecutionService.
        existing = CashTransaction.objects.filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            return CashTransferResult(transaction=existing, is_replay=True)

        with transaction.atomic():
            try:
                portfolio = Portfolio.objects.select_for_update().get(id=portfolio_id)
            except Portfolio.DoesNotExist as exc:
                raise PortfolioNotFoundError(
                    f"Portfolio {portfolio_id} does not exist."
                ) from exc

            if direction == CashTransaction.Direction.CREDIT:
                portfolio.cash_balance += amount
            else:  # DEBIT
                if portfolio.cash_balance < amount:
                    raise InsufficientFundsError(
                        "Insufficient funds to complete withdrawal."
                    )
                portfolio.cash_balance -= amount

            portfolio.save()

            cash_transaction = CashTransaction.objects.create(
                portfolio=portfolio,
                direction=direction,
                amount=amount,
                resulting_balance=portfolio.cash_balance,
                idempotency_key=idempotency_key,
            )

        return CashTransferResult(transaction=cash_transaction, is_replay=False)
