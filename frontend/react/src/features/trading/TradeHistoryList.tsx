import { useTradeHistory } from './usePortfolio'
import { formatMoney, formatQuantity, formatTimestamp } from '../../lib/format'

export function TradeHistoryList() {
  const { data, isLoading, isError } = useTradeHistory()

  if (isLoading) return <p className="text-sm text-slate-500 py-8 text-center">Loading trade history…</p>
  if (isError) return <p className="text-sm text-rose-400 py-8 text-center">Couldn't load trade history.</p>
  if (!data || data.items.length === 0) {
    return <p className="text-sm text-slate-500 py-8 text-center">No trades executed yet.</p>
  }

  return (
    <div className="space-y-2 overflow-y-auto max-h-[400px] pr-1">
      {data.items.map((trade) => (
        <div
          key={trade.trade_id}
          className="bg-slate-950 p-3 rounded border border-slate-800 flex justify-between items-center text-sm"
        >
          <div>
            <div className="flex items-center gap-2">
              <span className={`font-bold ${trade.trade_type === 'BUY' ? 'text-emerald-400' : 'text-rose-400'}`}>
                {trade.trade_type}
              </span>
              <span className="font-bold text-white">
                {formatQuantity(trade.quantity)} {trade.ticker}
              </span>
            </div>
            <div className="text-xs text-slate-500 font-mono mt-1">
              {formatTimestamp(trade.timestamp)}
            </div>
          </div>
          <div className="text-right">
            <div className="font-mono text-white">{formatMoney(trade.total_value)}</div>
            <div className="text-xs text-slate-500">@ {formatMoney(trade.price)}</div>
          </div>
        </div>
      ))}
    </div>
  )
}
