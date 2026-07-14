import { Briefcase, DollarSign, Wallet } from 'lucide-react'
import { usePortfolio } from '../features/trading/usePortfolio'
import { usePortfolioStream } from '../features/trading/usePortfolioStream'
import { formatMoney } from '../lib/format'
import { Card } from '../components/ui/Card'
import { StatTile } from '../components/ui/StatTile'
import { Badge } from '../components/ui/Badge'
import { TradeForm } from '../features/trading/TradeForm'
import { CashTransferForm } from '../features/trading/CashTransferForm'
import { TradeHistoryList } from '../features/trading/TradeHistoryList'
import { HoldingsList } from '../features/trading/HoldingsList'

export default function PortfolioPage() {
  const { data: portfolio, isLoading, isError } = usePortfolio()
  const { status: wsStatus } = usePortfolioStream(portfolio?.portfolio_id)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Portfolio</h1>
          <p className="text-sm text-slate-400">Cash, holdings, and trade execution.</p>
        </div>
        <LiveStatusBadge status={wsStatus} />
      </div>

      {isLoading && <p className="text-sm text-slate-500">Loading portfolio…</p>}
      {isError && <p className="text-sm text-rose-400">Couldn't load your portfolio.</p>}

      {portfolio && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* LEFT: cash + holdings */}
          <div className="lg:col-span-4 space-y-6">
            <Card>
              <StatTile
                label="Available Cash"
                value={formatMoney(portfolio.cash_balance)}
                icon={<DollarSign className="w-5 h-5 text-emerald-400" />}
              />
            </Card>

            <Card>
              <div className="flex items-center gap-2 mb-4 border-b border-slate-800 pb-2">
                <Wallet className="w-5 h-5 text-purple-400" />
                <h2 className="font-semibold text-white">Deposit / Withdraw</h2>
              </div>
              <CashTransferForm />
            </Card>

            <Card>
              <div className="flex items-center gap-2 mb-4 border-b border-slate-800 pb-2">
                <Briefcase className="w-5 h-5 text-purple-400" />
                <h2 className="font-semibold text-white">Holdings</h2>
              </div>
              <HoldingsList positions={portfolio.positions} />
            </Card>
          </div>

          {/* MIDDLE: trade execution */}
          <Card className="lg:col-span-4">
            <h2 className="font-semibold text-white mb-4 border-b border-slate-800 pb-2">
              Trade Execution
            </h2>
            <TradeForm />
          </Card>

          {/* RIGHT: trade history */}
          <Card className="lg:col-span-4">
            <h2 className="font-semibold text-white mb-4 border-b border-slate-800 pb-2">
              Trade History
            </h2>
            <TradeHistoryList />
          </Card>
        </div>
      )}
    </div>
  )
}

function LiveStatusBadge({ status }: { status: 'connecting' | 'open' | 'closed' }) {
  if (status === 'open') return <Badge tone="success">Live updates connected</Badge>
  if (status === 'connecting') return <Badge tone="neutral">Connecting…</Badge>
  return <Badge tone="warning">Reconnecting…</Badge>
}
