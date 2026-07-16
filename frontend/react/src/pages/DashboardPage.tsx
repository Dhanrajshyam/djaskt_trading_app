import { Briefcase, IndianRupee, Server } from 'lucide-react'
import { usePortfolio } from '../features/trading/usePortfolio'
import { usePortfolioStream } from '../features/trading/usePortfolioStream'
import { useMarketStream } from '../features/market-data/useMarketStream'
import { formatMoney, formatMoneyNumber } from '../lib/format'
import { Card } from '../components/ui/Card'
import { StatTile } from '../components/ui/StatTile'
import { Badge } from '../components/ui/Badge'
import { MarketTicker } from '../features/market-data/MarketTicker'
import { AnalyticsPanel } from '../features/analytics/AnalyticsPanel'
import { TradeForm } from '../features/trading/TradeForm'
import { TradeHistoryList } from '../features/trading/TradeHistoryList'
import { HoldingsList } from '../features/trading/HoldingsList'

/**
 * The trading desk: 4 cards mirroring gemini/dashboard_look.png —
 * top-left live market data, top-middle trade execution, top-right live
 * portfolio, bottom-left analytics.
 */
export default function DashboardPage() {
  const { data: portfolio, isLoading, isError } = usePortfolio()
  const { status: wsStatus } = usePortfolioStream(portfolio?.portfolio_id)
  const { prices: livePrices } = useMarketStream()

  // Sum of quantity × simulated live price across positions that have a
  // matching simulated ticker. This is deliberately an estimate, not a
  // backend figure — see HoldingsList/StatTile captions below, which both
  // label it as such. Positions with no matching simulated ticker are
  // excluded from the sum (not treated as zero), so this number is never
  // silently wrong, just possibly incomplete.
  const holdingsValue = portfolio?.positions.reduce((sum, position) => {
    const price = livePrices[position.ticker]
    return price !== undefined ? sum + Number(position.quantity) * price : sum
  }, 0)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-sm text-slate-400">Your trading desk at a glance.</p>
      </div>

      {isLoading && <p className="text-sm text-slate-500">Loading portfolio…</p>}
      {isError && <p className="text-sm text-rose-400">Couldn't load your portfolio.</p>}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* TOP-LEFT: live market data (simulated) */}
        <div className="lg:col-span-3">
          <MarketTicker />
        </div>

        {/* TOP-MIDDLE: trade execution (real Django REST) */}
        <Card className="lg:col-span-5">
          <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-2">
            <div className="flex items-center gap-2">
              <Server className="w-5 h-5 text-indigo-400" />
              <h2 className="font-semibold text-white">Trade Execution (Django REST)</h2>
            </div>
            <Badge tone="success">Connected</Badge>
          </div>
          <TradeForm livePrices={livePrices} />

          <div className="mt-6">
            <h3 className="text-sm font-semibold text-slate-400 mb-3 uppercase tracking-wider">
              Recent Trades
            </h3>
            <TradeHistoryList />
          </div>
        </Card>

        {/* TOP-RIGHT: live portfolio (real Django Channels) */}
        <Card className="lg:col-span-4">
          <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-2">
            <div className="flex items-center gap-2">
              <Briefcase className="w-5 h-5 text-purple-400" />
              <h2 className="font-semibold text-white">Live Portfolio (Django Channels WS)</h2>
            </div>
            <LiveStatusBadge status={wsStatus} />
          </div>

          {portfolio && (
            <>
              <div className="grid grid-cols-1 gap-3 mb-4">
                <StatTile
                  label="Available Cash"
                  value={formatMoney(portfolio.cash_balance)}
                  icon={<IndianRupee className="w-5 h-5 text-emerald-400" />}
                />
                <StatTile
                  label="Holdings Value (simulated prices)"
                  value={holdingsValue !== undefined ? formatMoneyNumber(holdingsValue) : '—'}
                  valueClassName="text-slate-300"
                />
              </div>

              <h3 className="text-sm font-semibold text-slate-400 mb-3 uppercase tracking-wider">
                Holdings
              </h3>
              <HoldingsList positions={portfolio.positions} livePrices={livePrices} />
            </>
          )}
        </Card>

        {/* BOTTOM-LEFT: analytics (simulated Flask) */}
        <div className="lg:col-span-3">
          <AnalyticsPanel />
        </div>
      </div>
    </div>
  )
}

function LiveStatusBadge({ status }: { status: 'connecting' | 'open' | 'closed' }) {
  if (status === 'open') return <Badge tone="success">Connected</Badge>
  if (status === 'connecting') return <Badge tone="neutral">Connecting…</Badge>
  return <Badge tone="warning">Disconnected</Badge>
}
