import { Briefcase, DollarSign } from 'lucide-react'
import { Link } from 'react-router'
import { usePortfolio } from '../features/trading/usePortfolio'
import { formatMoney } from '../lib/format'
import { Card } from '../components/ui/Card'
import { StatTile } from '../components/ui/StatTile'
import { Button } from '../components/ui/Button'
import { MarketTicker } from '../features/market-data/MarketTicker'
import { AnalyticsPanel } from '../features/analytics/AnalyticsPanel'

export default function DashboardPage() {
  const { data: portfolio, isLoading, isError } = usePortfolio()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-sm text-slate-400">Your account at a glance.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Real data: portfolio summary from Django */}
        <Card className="lg:col-span-2">
          <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-2">
            <div className="flex items-center gap-2">
              <Briefcase className="w-5 h-5 text-purple-400" />
              <h2 className="font-semibold text-white">Account Summary</h2>
            </div>
            <Link to="/portfolio">
              <Button variant="ghost" className="text-xs py-1.5 px-3">
                View portfolio
              </Button>
            </Link>
          </div>

          {isLoading && <p className="text-sm text-slate-500">Loading portfolio…</p>}
          {isError && (
            <p className="text-sm text-rose-400">Couldn't load your portfolio. Try refreshing.</p>
          )}
          {portfolio && (
            <div className="grid grid-cols-2 gap-4">
              <StatTile
                label="Available Cash"
                value={formatMoney(portfolio.cash_balance)}
                icon={<DollarSign className="w-5 h-5 text-emerald-400" />}
              />
              <StatTile label="Open Positions" value={String(portfolio.positions.length)} />
            </div>
          )}
        </Card>

        {/* Simulated data: market ticker (future FastAPI service) */}
        <MarketTicker />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Simulated data: analytics/reporting (future Flask service) */}
        <AnalyticsPanel />
      </div>
    </div>
  )
}
