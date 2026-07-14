import { TrendingDown, TrendingUp, Zap } from 'lucide-react'
import { Card } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import { useMarketStream } from './useMarketStream'

export function MarketTicker() {
  const { prices, previousPrices } = useMarketStream()

  return (
    <Card>
      <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-2">
        <div className="flex items-center gap-2">
          <Zap className="w-5 h-5 text-yellow-400" />
          <h2 className="font-semibold text-white">Live Market</h2>
        </div>
        <Badge tone="warning">Simulated data</Badge>
      </div>

      <div className="space-y-3">
        {Object.entries(prices).map(([ticker, price]) => {
          const prevPrice = previousPrices[ticker] ?? price
          const isUp = price >= prevPrice
          const color = isUp ? 'text-emerald-400' : 'text-rose-400'

          return (
            <div key={ticker} className="flex justify-between items-center p-2 rounded">
              <span className="font-bold text-lg">{ticker}</span>
              <div className="text-right">
                <div className={`font-mono font-bold ${color}`}>${price.toFixed(2)}</div>
                <div className={`text-xs flex items-center justify-end gap-1 ${color}`}>
                  {isUp ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                  {Math.abs(price - prevPrice).toFixed(2)}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      <p className="text-xs text-slate-500 mt-4 border-t border-slate-800 pt-3">
        Live feed coming soon — this will connect to the FastAPI market-data service once it's built.
      </p>
    </Card>
  )
}
