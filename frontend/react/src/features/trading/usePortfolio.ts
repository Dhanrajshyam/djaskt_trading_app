import { useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchPortfolio, fetchTradeHistory } from './tradingApi'
import type { PortfolioResponse } from '../../lib/types'

/** Query keys centralized here so useTradeExecution/usePortfolioStream can
 * invalidate/update the same cache entries this hook reads from. */
export const portfolioQueryKey = ['portfolio'] as const
export const tradeHistoryQueryKey = ['tradeHistory'] as const

export function usePortfolio() {
  return useQuery({
    queryKey: portfolioQueryKey,
    queryFn: fetchPortfolio,
  })
}

export function useTradeHistory() {
  return useQuery({
    queryKey: tradeHistoryQueryKey,
    queryFn: () => fetchTradeHistory(),
  })
}

/** Returns a stable function that overwrites the cached portfolio — used by
 * usePortfolioStream to merge in live WebSocket updates without a refetch.
 * Wrapped in useCallback (with the also-stable queryClient as its only
 * dependency) so usePortfolioStream's effect can safely depend on it
 * without reconnecting the WebSocket on every render. */
export function useSetPortfolioCache() {
  const queryClient = useQueryClient()
  return useCallback(
    (portfolio: PortfolioResponse) => {
      queryClient.setQueryData(portfolioQueryKey, portfolio)
    },
    [queryClient],
  )
}
