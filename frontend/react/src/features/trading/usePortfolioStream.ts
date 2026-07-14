import { useEffect, useRef, useState } from 'react'
import { useAuthStore } from '../auth/authStore'
import { useSetPortfolioCache } from './usePortfolio'
import type { PortfolioSocketMessage } from '../../lib/types'

const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL

// Exponential backoff schedule for reconnection: 1s, 2s, 4s, 8s, then holds
// at 8s. Matches the resiliency requirement from the project's original
// spec (gemini/prompt_react) so a dropped connection doesn't hammer the
// server with instant reconnect attempts.
const RECONNECT_DELAYS_MS = [1000, 2000, 4000, 8000]

export type ConnectionStatus = 'connecting' | 'open' | 'closed'

/**
 * Opens the portfolio WebSocket and keeps the shared portfolio cache
 * (TanStack Query) up to date with live `portfolio.update` broadcasts.
 *
 * Authenticates via "first message": connects with a plain URL (no token
 * in it — see backend ledger/realtime/auth.py for why), then immediately
 * sends `{"type": "auth", "access_token": "<jwt>"}` as the very first
 * message once the socket opens. The server only starts sending data
 * after that message validates.
 */
export function usePortfolioStream(portfolioId: string | undefined) {
  const accessToken = useAuthStore((state) => state.accessToken)
  const setPortfolioCache = useSetPortfolioCache()
  const [status, setStatus] = useState<ConnectionStatus>('connecting')

  // Refs (not state) for anything the reconnect loop needs to read/mutate
  // without triggering a re-render or being captured stale in a closure.
  const socketRef = useRef<WebSocket | null>(null)
  const reconnectAttemptRef = useRef(0)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const isUnmountedRef = useRef(false)

  useEffect(() => {
    if (!portfolioId || !accessToken) {
      return
    }

    isUnmountedRef.current = false

    function connect() {
      setStatus('connecting')
      const socket = new WebSocket(`${WS_BASE_URL}/ws/v1/ledger/portfolio/${portfolioId}/`)
      socketRef.current = socket

      socket.onopen = () => {
        // First message must be the auth payload — see module docstring.
        socket.send(JSON.stringify({ type: 'auth', access_token: accessToken }))
      }

      socket.onmessage = (event: MessageEvent<string>) => {
        setStatus('open')
        reconnectAttemptRef.current = 0 // Reset backoff after any successful message.

        const message: PortfolioSocketMessage = JSON.parse(event.data)

        // The two message shapes are told apart by which fields are
        // present, not a shared discriminant: the initial snapshot has
        // `type: "trade_history"`, while a live portfolio.update broadcast
        // has `portfolio_id` and no `type` at all (see
        // ledger/services/main_service.py's payload construction on the
        // backend — it's a plain dict, not a Pydantic schema).
        if ('portfolio_id' in message) {
          setPortfolioCache({
            portfolio_id: message.portfolio_id,
            cash_balance: message.cash_balance,
            positions: message.positions,
          })
        }
        // Else: the initial trade_history snapshot. The Portfolio page's
        // own TanStack Query fetch already loads trade history over REST,
        // so this snapshot is informational only — nothing to do with it here.
      }

      socket.onclose = () => {
        setStatus('closed')
        if (isUnmountedRef.current) return

        const attempt = reconnectAttemptRef.current
        const delay = RECONNECT_DELAYS_MS[Math.min(attempt, RECONNECT_DELAYS_MS.length - 1)]
        reconnectAttemptRef.current += 1
        reconnectTimeoutRef.current = setTimeout(connect, delay)
      }

      socket.onerror = () => {
        // onclose always fires after onerror for a WebSocket, so the
        // reconnect logic above handles this too — nothing extra needed
        // here beyond letting the browser's own close event follow.
      }
    }

    connect()

    return () => {
      isUnmountedRef.current = true
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current)
      socketRef.current?.close()
    }
  }, [portfolioId, accessToken, setPortfolioCache])

  return { status }
}
