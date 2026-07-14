import { useEffect, useRef, useState } from 'react'

/**
 * SIMULATED market data — the real FastAPI market-data microservice
 * (gemini/LLD - Fast API.docx) doesn't exist yet. This hook fakes it with
 * a `setInterval` that randomly nudges a few hardcoded ticker prices.
 *
 * Shaped to match the *documented* future FastAPI contract exactly:
 *
 *   ws://<host>/api/v1/market/stream/
 *   -> {"type": "PRICE_UPDATE", "data": {"AAPL": 175.50, ...}, "timestamp": 1689150000}
 *
 * so that swapping this out for a real `useMarketStream` that opens an
 * actual WebSocket to that endpoint is a like-for-like replacement: same
 * return shape (`{ prices, previousPrices }`), same consumers
 * (components/pages using this hook don't need to change at all).
 */

export interface PriceUpdateMessage {
  type: 'PRICE_UPDATE'
  data: Record<string, number>
  timestamp: number
}

const SIMULATED_TICKERS = ['AAPL', 'TSLA', 'MSFT', 'GOOG'] as const

const STARTING_PRICES: Record<string, number> = {
  AAPL: 175.5,
  TSLA: 210.2,
  MSFT: 330.1,
  GOOG: 140.05,
}

const UPDATE_INTERVAL_MS = 1500

export function useMarketStream() {
  const [prices, setPrices] = useState<Record<string, number>>(STARTING_PRICES)
  const previousPricesRef = useRef<Record<string, number>>(STARTING_PRICES)

  useEffect(() => {
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

    return () => clearInterval(interval)
  }, [])

  return { prices, previousPrices: previousPricesRef.current }
}
