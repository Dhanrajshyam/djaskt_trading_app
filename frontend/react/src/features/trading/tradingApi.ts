import { apiFetch } from '../../lib/apiClient'
import type {
  CashTransferRequest,
  CashTransferResponse,
  PaginatedTradeHistory,
  PortfolioResponse,
  TradeRequest,
  TradeResponse,
} from '../../lib/types'

export function fetchPortfolio(): Promise<PortfolioResponse> {
  return apiFetch<PortfolioResponse>('/ledger/portfolio/')
}

export function fetchTradeHistory(limit = 20, offset = 0): Promise<PaginatedTradeHistory> {
  return apiFetch<PaginatedTradeHistory>(`/ledger/trades/?limit=${limit}&offset=${offset}`)
}

export function submitTrade(payload: TradeRequest): Promise<TradeResponse> {
  return apiFetch<TradeResponse>('/ledger/trade/', { method: 'POST', body: payload })
}

export function submitCashTransfer(payload: CashTransferRequest): Promise<CashTransferResponse> {
  return apiFetch<CashTransferResponse>('/ledger/cash-transfer/', {
    method: 'POST',
    body: payload,
  })
}
