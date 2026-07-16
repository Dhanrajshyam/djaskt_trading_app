import { Activity, Landmark, LogOut } from 'lucide-react'
import { NavLink, useNavigate } from 'react-router'
import { useAuthStore } from '../../features/auth/authStore'
import { logout as logoutRequest } from '../../features/auth/authApi'

const NAV_LINK_CLASSES = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
    isActive ? 'bg-slate-800 text-white' : 'text-slate-400 hover:text-white'
  }`

export function Header() {
  const navigate = useNavigate()
  const { email, refreshToken, accessToken, clearTokens } = useAuthStore()

  async function handleLogout() {
    // Best-effort: tell the backend to revoke these tokens. Log the user
    // out locally regardless of whether this call succeeds — an
    // unreachable server shouldn't trap the user in a logged-in UI.
    try {
      if (accessToken || refreshToken) {
        await logoutRequest({ access: accessToken ?? undefined, refresh: refreshToken ?? undefined })
      }
    } catch {
      // Ignored — see comment above.
    } finally {
      clearTokens()
      navigate('/login')
    }
  }

  return (
    <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-10">
      <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-indigo-600 rounded-lg">
            <Activity className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-base font-bold text-white leading-tight">Djaskt Trading</h1>
            <p className="text-xs text-slate-500 leading-tight">Paper Trading Terminal</p>
          </div>
        </div>

        <nav className="flex items-center gap-1">
          {email && (
            <>
              <NavLink to="/dashboard" className={NAV_LINK_CLASSES}>
                Dashboard
              </NavLink>
              <NavLink to="/portfolio" className={NAV_LINK_CLASSES}>
                Portfolio
              </NavLink>
            </>
          )}
          {/* Public showcase page — visible whether or not the user is
              logged in, unlike the trading-feature links above. */}
          <NavLink to="/design" className={NAV_LINK_CLASSES}>
            Design
          </NavLink>
        </nav>

        <div className="flex items-center gap-3">
          {email && (
            <>
              <NavLink
                to="/brokerage-setup"
                className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-white bg-slate-900 hover:bg-slate-800 border border-slate-800 px-3 py-1.5 rounded-full transition-colors"
              >
                <Landmark className="w-3.5 h-3.5" />
                Brokerage Setup
              </NavLink>
              <span className="text-sm text-slate-400 hidden sm:inline">{email}</span>
              <button
                onClick={handleLogout}
                className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-white bg-slate-900 hover:bg-slate-800 border border-slate-800 px-3 py-1.5 rounded-full transition-colors"
              >
                <LogOut className="w-3.5 h-3.5" />
                Logout
              </button>
            </>
          )}
        </div>
      </div>
    </header>
  )
}
