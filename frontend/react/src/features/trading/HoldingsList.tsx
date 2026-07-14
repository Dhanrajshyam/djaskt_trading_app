import type { Position } from '../../lib/types'
import { formatQuantity } from '../../lib/format'

export function HoldingsList({ positions }: { positions: Position[] }) {
  if (positions.length === 0) {
    return <p className="text-sm text-slate-500 py-4 text-center">No active positions.</p>
  }

  return (
    <div className="space-y-3">
      {positions.map((position) => (
        <div
          key={position.ticker}
          className="flex justify-between items-center p-3 bg-slate-800/50 rounded border border-slate-700/50"
        >
          <div>
            <div className="font-bold text-white text-lg">{position.ticker}</div>
            <div className="text-xs text-slate-400">{formatQuantity(position.quantity)} shares</div>
          </div>
        </div>
      ))}
    </div>
  )
}
