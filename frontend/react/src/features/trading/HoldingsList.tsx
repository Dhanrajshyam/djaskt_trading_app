import type { Position } from '../../lib/types'
import { formatQuantity, formatMoneyNumber } from '../../lib/format'

interface HoldingsListProps {
  positions: Position[]
  /** Simulated live prices, keyed by ticker (from useMarketStream).
   * Optional: when omitted (e.g. PortfolioPage's plain usage), only
   * ticker/quantity are shown — current price/value are real-backend-data
   * adjacent numbers this component won't fabricate without a price to
   * multiply by. */
  livePrices?: Record<string, number>
}

export function HoldingsList({ positions, livePrices }: HoldingsListProps) {
  if (positions.length === 0) {
    return <p className="text-sm text-slate-500 py-4 text-center">No active positions.</p>
  }

  return (
    <div className="space-y-3">
      {positions.map((position) => {
        const price = livePrices?.[position.ticker]
        const currentValue = price !== undefined ? Number(position.quantity) * price : undefined

        return (
          <div
            key={position.ticker}
            className="flex justify-between items-center p-3 bg-slate-800/50 rounded border border-slate-700/50"
          >
            <div>
              <div className="font-bold text-white text-lg">{position.ticker}</div>
              <div className="text-xs text-slate-400">{formatQuantity(position.quantity)} shares</div>
            </div>
            {livePrices && (
              <div className="text-right">
                <div className="font-mono text-white">
                  {currentValue !== undefined ? formatMoneyNumber(currentValue) : '—'}
                </div>
                <div className="text-xs text-slate-500 font-mono">
                  {price !== undefined ? `@ ${formatMoneyNumber(price)}` : 'price unavailable'}
                </div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
