import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'
import { useAuthStore } from './authStore'

/**
 * Wraps a page that requires a logged-in user. Redirects to /login if
 * there's no access token, remembering the page the user was trying to
 * reach so login can send them back afterward.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const accessToken = useAuthStore((state) => state.accessToken)
  const location = useLocation()

  if (!accessToken) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return children
}
