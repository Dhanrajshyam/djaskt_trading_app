import { useCallback, useState } from 'react'

const STORAGE_KEY = 'djaskt_favorite_tickers'

function loadFavorites(): Set<string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return new Set()
    const parsed: unknown = JSON.parse(raw)
    return Array.isArray(parsed) ? new Set(parsed) : new Set()
  } catch {
    return new Set()
  }
}

function saveFavorites(favorites: Set<string>): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...favorites]))
}

/**
 * Favorited tickers for the market data card, persisted in localStorage.
 *
 * This is device-local only (not synced to the backend) — appropriate for
 * now since the market data it's favoriting is itself still simulated,
 * client-only data (see useMarketStream.ts). Worth revisiting once a real
 * market-data service and per-user preferences exist server-side.
 */
export function useFavoriteTickers() {
  const [favorites, setFavorites] = useState<Set<string>>(loadFavorites)

  const toggleFavorite = useCallback((ticker: string) => {
    setFavorites((current) => {
      const next = new Set(current)
      if (next.has(ticker)) {
        next.delete(ticker)
      } else {
        next.add(ticker)
      }
      saveFavorites(next)
      return next
    })
  }, [])

  const isFavorite = useCallback((ticker: string) => favorites.has(ticker), [favorites])

  return { favorites, toggleFavorite, isFavorite }
}
