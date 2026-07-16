import { useEffect, useRef, useState } from 'react'

/**
 * SIMULATED market data — the real FastAPI market-data microservice
 * (gemini/LLD - Fast API.docx) doesn't exist yet. This hook fakes it with
 * a `setInterval` that randomly nudges a set of hardcoded ticker prices.
 *
 * Shaped to match the *documented* future FastAPI contract exactly:
 *
 *   ws://<host>/api/v1/market/stream/
 *   -> {"type": "PRICE_UPDATE", "data": {"AAPL": 175.50, ...}, "timestamp": 1689150000}
 *
 * so that swapping this out for a real `useMarketStream` that opens an
 * actual WebSocket to that endpoint is a like-for-like replacement: same
 * return shape (`{ prices, previousPrices, status }`), same consumers
 * (components/pages using this hook don't need to change at all). `status`
 * mirrors the shape `features/trading/usePortfolioStream.ts` already
 * returns for its real WebSocket, so both "live data" indicators in the UI
 * behave consistently even though only one of them is backed by a real
 * connection today.
 */

export interface PriceUpdateMessage {
  type: 'PRICE_UPDATE'
  data: Record<string, number>
  timestamp: number
}

export type MarketStreamStatus = 'connecting' | 'connected'

// Exported so features/trading/TradeForm.tsx's ticker dropdown shows
// exactly the same universe of tickers this card streams prices for —
// one list, not two hand-maintained copies that could drift apart.
export const SIMULATED_TICKERS = [
  'AAPL',
  'MSFT',
  'GOOG',
  'AMZN',
  'NVDA',
  'META',
  'TSLA',
  'NFLX',
  'AMD',
  'INTC',
  'DIS',
  'BA',
] as const

const STARTING_PRICES: Record<string, number> = {
  AAPL: 175.5,
  MSFT: 330.1,
  GOOG: 140.05,
  AMZN: 178.25,
  NVDA: 121.4,
  META: 505.6,
  TSLA: 210.2,
  NFLX: 645.3,
  AMD: 165.75,
  INTC: 31.2,
  DIS: 112.9,
  BA: 189.45,
}

const UPDATE_INTERVAL_MS = 1500

export function useMarketStream() {
  const [prices, setPrices] = useState<Record<string, number>>(STARTING_PRICES)
  const [status, setStatus] = useState<MarketStreamStatus>('connecting')
  const previousPricesRef = useRef<Record<string, number>>(STARTING_PRICES)

  useEffect(() => {
    // A real WebSocket takes a moment to open; simulate that same brief
    // "connecting" beat so the status badge behaves like the real
    // portfolio socket's, rather than always reading "connected" instantly.
    const connectTimeout = setTimeout(() => setStatus('connected'), 400)

    const interval = setInterval(() => {
      setPrices((current) => {
        previousPricesRef.current = current
        const next = { ...current }
        for (const ticker of SIMULATED_TICKERS) {
          // ~50% chance any given ticker moves on a tick, by up to 0.5%,
          // matching the reference design's fluctuation logic — a real
          // feed would tick far more often, but this is easier to watch.
          if (Math.random() > 0.5) {
            const change = next[ticker] * (Math.random() * 0.005)
            next[ticker] = Math.random() > 0.5 ? next[ticker] + change : next[ticker] - change
          }
        }
        return next
      })
    }, UPDATE_INTERVAL_MS)

    return () => {
      clearTimeout(connectTimeout)
      clearInterval(interval)
    }
  }, [])

  return { prices, previousPrices: previousPricesRef.current, status }
}
