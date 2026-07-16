import { create } from 'zustand'

/**
 * Global auth state: the current user's email and JWT token pair.
 *
 * Tokens are kept in memory (this store) and mirrored to sessionStorage so
 * a page refresh doesn't immediately log the user out. sessionStorage
 * (not localStorage) is used deliberately: it clears when the browser tab
 * closes, which is a reasonable default for a demo/education app.
 *
 * Tradeoff worth knowing: storing JWTs in any form of Web Storage
 * (session or local) means they're readable by any JavaScript that runs
 * on the page, which is a real risk if this app ever loads third-party
 * scripts or has an XSS bug. The more secure alternative is httpOnly
 * cookies set by the server, which JavaScript can never read — but that
 * requires the Django backend to issue/manage cookies instead of returning
 * tokens in the JSON response body, which is a backend contract change
 * out of scope for this frontend-only pass. Worth revisiting if this app
 * ever handles real money.
 */

const STORAGE_KEY = 'djaskt_auth'

interface StoredAuth {
  email: string
  access: string
  refresh: string
}

function loadFromStorage(): StoredAuth | null {
  const raw = sessionStorage.getItem(STORAGE_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as StoredAuth
  } catch {
    return null
  }
}

function saveToStorage(auth: StoredAuth | null): void {
  if (auth) {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(auth))
  } else {
    sessionStorage.removeItem(STORAGE_KEY)
  }
}

interface AuthState {
  email: string | null
  accessToken: string | null
  refreshToken: string | null
  /** True once the store has checked sessionStorage on app startup. */
  isInitialized: boolean
  setTokens: (auth: StoredAuth) => void
  clearTokens: () => void
}

export const useAuthStore = create<AuthState>((set) => {
  const stored = loadFromStorage()

  return {
    email: stored?.email ?? null,
    accessToken: stored?.access ?? null,
    refreshToken: stored?.refresh ?? null,
    isInitialized: true,

    setTokens: (auth) => {
      saveToStorage(auth)
      set({
        email: auth.email,
        accessToken: auth.access,
        refreshToken: auth.refresh,
      })
    },

    clearTokens: () => {
      saveToStorage(null)
      set({ email: null, accessToken: null, refreshToken: null })
    },
  }
})
