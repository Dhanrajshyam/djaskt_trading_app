import { useState } from 'react'
import { useTradeExecution } from './useTradeExecution'
import { Button } from '../../components/ui/Button'
import { ApiError } from '../../lib/apiClient'
import { SIMULATED_TICKERS } from '../market-data/useMarketStream'
import { formatMoneyNumber } from '../../lib/format'
import type { TradeType } from '../../lib/types'

interface TradeFormProps {
  onTraded?: () => void
  /** Simulated live prices, keyed by ticker (from useMarketStream) — used
   * only to show a rough "Estimated Total" for the user's convenience.
   * Optional so this form still works standalone (e.g. if ever reused
   * somewhere without a market stream in scope). */
  livePrices?: Record<string, number>
}

/**
 * Trade submission form. The "Estimated Total" shown here is a rough,
 * client-side-only estimate for the user's convenience — it uses whatever
 * price the simulated market ticker last showed, purely for display. The
 * actual execution price and total are decided by the Django backend
 * against the real (or, once built, live) price feed; this estimate is
 * never sent to the server.
 */
export function TradeForm({ onTraded, livePrices }: TradeFormProps) {
  const [ticker, setTicker] = useState<(typeof SIMULATED_TICKERS)[number]>(SIMULATED_TICKERS[0])
  const [quantity, setQuantity] = useState('1')
  const [feedback, setFeedback] = useState<{ tone: 'success' | 'error'; message: string } | null>(
    null,
  )

  const { tradeMutation } = useTradeExecution()
  const isSubmitting = tradeMutation.isPending

  async function handleTrade(tradeType: TradeType) {
    setFeedback(null)
    const qty = Number(quantity)
    if (!Number.isFinite(qty) || qty <= 0) {
      setFeedback({ tone: 'error', message: 'Enter a quantity greater than zero.' })
      return
    }

    try {
      const result = await tradeMutation.mutateAsync({ ticker, tradeType, quantity })
      setFeedback({
        tone: 'success',
        message: `${result.trade_type} ${result.quantity} ${result.ticker} @ ₹${result.price} — ${
          result.is_replay ? 'already recorded' : 'trade committed'
        }.`,
      })
      onTraded?.()
    } catch (err) {
      setFeedback({
        tone: 'error',
        message: err instanceof ApiError ? err.message : 'Trade failed. Please try again.',
      })
    }
  }

  return (
    <div className="bg-slate-950 p-4 rounded-lg border border-slate-800">
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <label className="block text-xs text-slate-400 mb-1" htmlFor="ticker">
            Ticker
          </label>
          <select
            id="ticker"
            value={ticker}
            onChange={(e) => setTicker(e.target.value as (typeof SIMULATED_TICKERS)[number])}
            className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-white outline-none focus:border-indigo-500 transition-colors"
          >
            {SIMULATED_TICKERS.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-400 mb-1" htmlFor="quantity">
            Quantity
          </label>
          <input
            id="quantity"
            type="number"
            min="1"
            step="1"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-white outline-none focus:border-indigo-500 transition-colors"
          />
        </div>
      </div>

      {livePrices?.[ticker] !== undefined && (
        <div className="flex justify-between items-end mb-4 bg-slate-900 p-3 rounded">
          <div>
            <div className="text-xs text-slate-400 mb-1">Estimated Total (simulated price)</div>
            <div className="text-lg font-mono text-white">
              {formatMoneyNumber((Number(quantity) || 0) * livePrices[ticker])}
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs text-slate-400 mb-1">Current Price</div>
            <div className="font-mono text-emerald-400">{formatMoneyNumber(livePrices[ticker])}</div>
          </div>
        </div>
      )}

      {feedback && (
        <div
          className={`text-sm rounded p-2 mb-4 ${
            feedback.tone === 'success'
              ? 'bg-emerald-400/10 text-emerald-300 border border-emerald-400/30'
              : 'bg-rose-400/10 text-rose-300 border border-rose-400/30'
          }`}
        >
          {feedback.message}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        <Button variant="buy" disabled={isSubmitting} onClick={() => handleTrade('BUY')}>
          {isSubmitting ? 'Submitting…' : `BUY ${ticker}`}
        </Button>
        <Button variant="sell" disabled={isSubmitting} onClick={() => handleTrade('SELL')}>
          {isSubmitting ? 'Submitting…' : `SELL ${ticker}`}
        </Button>
      </div>
    </div>
  )
}
