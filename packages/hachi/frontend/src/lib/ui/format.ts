/**
 * App-wide formatting utilities.
 *
 * Single source of truth for money, tokens, dates, and relative time.
 * T20 migrates all call sites to these functions.
 */

const USD_FMT = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

/** Format a USD amount. Sub-cent positive amounts render as "<$0.01". */
export function fmtUSD(n: number): string {
  if (n > 0 && n < 0.01) return '<$0.01'
  return USD_FMT.format(n)
}

const COMMA_FMT = new Intl.NumberFormat('en-US')

/**
 * Format a token count.
 * 0 → "0"; < 10 000 → comma-separated ("1,234"); ≥ 10 000 → K ("12.3K"); ≥ 1M → M ("1.2M").
 */
export function fmtTokens(n: number): string {
  if (n === 0) return '0'
  if (n < 10_000) return COMMA_FMT.format(n)
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M'
  const k = n / 1000
  return k.toFixed(1).replace(/\.0$/, '') + 'K'
}

const DATE_FMT = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
})

/** Format a unix-ms timestamp as "12 Jul 2026". One format, app-wide. */
export function fmtDate(ts: number): string {
  return DATE_FMT.format(new Date(ts))
}

/**
 * Format a unix-ms timestamp as a relative human label.
 * < 60s → "just now"; < 1h → "Nm ago"; < 24h → "Nh ago"; older → fmtDate.
 */
export function fmtRelative(ts: number): string {
  const diff = Date.now() - ts
  const secs = Math.floor(diff / 1000)
  if (secs < 60) return 'just now'
  const mins = Math.floor(diff / 60_000)
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(diff / 3_600_000)
  if (hours < 24) return `${hours}h ago`
  return fmtDate(ts)
}
