import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router'
import { LogIn, Search, Star, TrendingDown, TrendingUp, Zap } from 'lucide-react'
import { Card } from '../../components/ui/Card'
import { Badge } from '../../components/ui/Badge'
import { useMarketStream } from './useMarketStream'
import { useFavoriteTickers } from './useFavoriteTickers'
import { formatMoneyNumber } from '../../lib/format'
import { useBrokerageLinks } from '../brokerage/useBrokerageLinks'
import { BrokerLoginModal } from '../brokerage/BrokerLoginModal'

export function MarketTicker() {
  const { prices, previousPrices } = useMarketStream()
  const { isFavorite, toggleFavorite } = useFavoriteTickers()
  const { data: brokerageLinks } = useBrokerageLinks()

  const [search, setSearch] = useState('')
  const [favoritesOnly, setFavoritesOnly] = useState(false)
  const [selectedBrokerage, setSelectedBrokerage] = useState<string | null>(null)
  const [loginModalOpen, setLoginModalOpen] = useState(false)

  // Default to the first linked brokerage once links load; re-picks if the
  // previously selected one gets unlinked (e.g. "Remove link" on the Setup page).
  useEffect(() => {
    if (!brokerageLinks || brokerageLinks.length === 0) {
      setSelectedBrokerage(null)
      return
    }
    if (!brokerageLinks.some((link) => link.brokerage_name === selectedBrokerage)) {
      setSelectedBrokerage(brokerageLinks[0].brokerage_name)
    }
  }, [brokerageLinks, selectedBrokerage])

  const selectedLink = brokerageLinks?.find((link) => link.brokerage_name === selectedBrokerage)

  const visibleTickers = useMemo(() => {
    const query = search.trim().toUpperCase()
    return Object.keys(prices)
      .filter((ticker) => !query || ticker.includes(query))
      .filter((ticker) => !favoritesOnly || isFavorite(ticker))
      .sort()
  }, [prices, search, favoritesOnly, isFavorite])

  return (
    <Card>
      <div className="flex items-center gap-2 mb-3 border-b border-slate-800 pb-2">
        <Zap className="w-5 h-5 text-yellow-400" />
        <h2 className="font-semibold text-white">Live Market (FastAPI WS)</h2>
      </div>

      <div className="flex items-center justify-between mb-3">
        {brokerageLinks && brokerageLinks.length === 0 ? (
          <Link to="/brokerage-setup" className="text-xs text-indigo-400 hover:text-indigo-300">
            No brokerage linked — set one up
          </Link>
        ) : (
          <div className="flex items-center gap-2">
            <select
              value={selectedBrokerage ?? ''}
              onChange={(e) => setSelectedBrokerage(e.target.value)}
              className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-xs text-white outline-none focus:border-indigo-500 transition-colors"
            >
              {brokerageLinks?.map((link) => (
                <option key={link.brokerage_name} value={link.brokerage_name}>
                  {link.brokerage_name}
                </option>
              ))}
            </select>

            {selectedLink?.is_connected ? (
              <Badge tone="success">Connected</Badge>
            ) : (
              <>
                <Badge tone="warning">Disconnected</Badge>
                {selectedLink && (
                  <button
                    onClick={() => setLoginModalOpen(true)}
                    title="Log in"
                    className="p-1 rounded text-slate-500 hover:text-emerald-400 transition-colors"
                  >
                    <LogIn className="w-3.5 h-3.5" />
                  </button>
                )}
              </>
            )}
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 mb-3">
        <div className="relative flex-1">
          <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search ticker…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-slate-950 border border-slate-700 rounded pl-8 pr-2 py-1.5 text-sm text-white outline-none focus:border-indigo-500 transition-colors"
          />
        </div>
        <button
          onClick={() => setFavoritesOnly((v) => !v)}
          title="Show favorites only"
          className={`p-1.5 rounded border transition-colors ${
            favoritesOnly
              ? 'bg-yellow-400/10 border-yellow-400/40 text-yellow-400'
              : 'bg-slate-950 border-slate-700 text-slate-500 hover:text-yellow-400'
          }`}
        >
          <Star className="w-4 h-4" fill={favoritesOnly ? 'currentColor' : 'none'} />
        </button>
      </div>

      <div className="space-y-2 max-h-[360px] overflow-y-auto pr-1">
        {visibleTickers.length === 0 ? (
          <p className="text-sm text-slate-500 text-center py-6">No matching tickers.</p>
        ) : (
          visibleTickers.map((ticker) => {
            const price = prices[ticker]
            const prevPrice = previousPrices[ticker] ?? price
            const isUp = price >= prevPrice
            const color = isUp ? 'text-emerald-400' : 'text-rose-400'
            const favorite = isFavorite(ticker)

            return (
              <div key={ticker} className="flex justify-between items-center p-2 rounded hover:bg-slate-800/50">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => toggleFavorite(ticker)}
                    title={favorite ? 'Remove from favorites' : 'Add to favorites'}
                    className={favorite ? 'text-yellow-400' : 'text-slate-600 hover:text-yellow-400'}
                  >
                    <Star className="w-4 h-4" fill={favorite ? 'currentColor' : 'none'} />
                  </button>
                  <span className="font-bold text-lg">{ticker}</span>
                </div>
                <div className="text-right">
                  <div className={`font-mono font-bold ${color}`}>{formatMoneyNumber(price)}</div>
                  <div className={`text-xs flex items-center justify-end gap-1 ${color}`}>
                    {isUp ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                    {Math.abs(price - prevPrice).toFixed(2)}
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>

      <div className="flex items-center justify-between mt-4 border-t border-slate-800 pt-3">
        <Badge tone="warning">Simulated data</Badge>
        <p className="text-xs text-slate-500">Live feed coming soon.</p>
      </div>

      {selectedLink && (
        <BrokerLoginModal
          open={loginModalOpen}
          onClose={() => setLoginModalOpen(false)}
          brokerageName={selectedLink.brokerage_name}
          displayName={selectedLink.brokerage_name}
        />
      )}
    </Card>
  )
}
