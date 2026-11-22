/**
 * useMediaQuery — SSR-safe hook that tracks a CSS media query.
 * Returns true when the query matches, false otherwise.
 * Updates synchronously on first render and on every subsequent change.
 */
import { useState, useEffect } from 'react'

export function useMediaQuery(query: string): boolean {
  const getMatches = (): boolean => {
    if (typeof window === 'undefined') return false
    return window.matchMedia(query).matches
  }

  const [matches, setMatches] = useState<boolean>(getMatches)

  useEffect(() => {
    const mql = window.matchMedia(query)
    const handler = (e: MediaQueryListEvent) => setMatches(e.matches)

    // Use the modern addEventListener API (addEventListener is available in
    // all browsers that matter; fall back to addListener only if absent).
    if (typeof mql.addEventListener === 'function') {
      mql.addEventListener('change', handler)
      return () => mql.removeEventListener('change', handler)
    } else {
      // Safari < 14 fallback
      // eslint-disable-next-line @typescript-eslint/no-deprecated
      mql.addListener(handler)
      // eslint-disable-next-line @typescript-eslint/no-deprecated
      return () => mql.removeListener(handler)
    }
  }, [query])

  return matches
}

/** Convenience wrapper — true when viewport is phone-width (< 768px). */
export function useIsMobile(): boolean {
  return useMediaQuery('(max-width: 767px)')
}
