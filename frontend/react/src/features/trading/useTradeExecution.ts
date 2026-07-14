import { useMutation, useQueryClient } from '@tanstack/react-query'
import { submitCashTransfer, submitTrade } from './tradingApi'
import { portfolioQueryKey, tradeHistoryQueryKey } from './usePortfolio'
import type { CashDirection, TradeType } from '../../lib/types'

/**
 * Trade/cash-transfer submission, with the two guarantees the backend
 * expects of a well-behaved client:
 *
 * 1. A fresh `crypto.randomUUID()` idempotency key on every submission, so
 *    a retried request (e.g. the user's connection blips right as they
 *    click) never double-executes — the backend recognizes a repeated key
 *    and returns the original result instead of a new trade.
 * 2. `isPending` (from TanStack Query's mutation state) is meant to be
 *    wired to the submit button's `disabled` prop by the caller, so a
 *    double-click can't fire two separate requests with two different
 *    keys while the first is still in flight.
 */
export function useTradeExecution() {
  const queryClient = useQueryClient()

  const tradeMutation = useMutation({
    mutationFn: (input: { ticker: string; tradeType: TradeType; quantity: string }) =>
      submitTrade({
        ticker: input.ticker,
        trade_type: input.tradeType,
        quantity: input.quantity,
        idempotency_key: crypto.randomUUID(),
      }),
    onSuccess: () => {
      // The WebSocket broadcast (usePortfolioStream) will also push the new
      // balance/position, but invalidating here means the trade history
      // list and portfolio numbers update immediately even if the socket
      // is briefly disconnected.
      queryClient.invalidateQueries({ queryKey: portfolioQueryKey })
      queryClient.invalidateQueries({ queryKey: tradeHistoryQueryKey })
    },
  })

  const cashTransferMutation = useMutation({
    mutationFn: (input: { direction: CashDirection; amount: string }) =>
      submitCashTransfer({
        direction: input.direction,
        amount: input.amount,
        idempotency_key: crypto.randomUUID(),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: portfolioQueryKey })
    },
  })

  return { tradeMutation, cashTransferMutation }
}
