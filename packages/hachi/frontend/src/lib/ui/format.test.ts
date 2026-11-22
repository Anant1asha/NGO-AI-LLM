import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { fmtUSD, fmtTokens, fmtRelative, fmtDate } from './format'

// ---- fmtUSD ----------------------------------------------------------------

describe('fmtUSD', () => {
  it('zero renders as $0.00', () => {
    expect(fmtUSD(0)).toBe('$0.00')
  })

  it('sub-cent positive amount renders as <$0.01', () => {
    expect(fmtUSD(0.001)).toBe('<$0.01')
    expect(fmtUSD(0.0099)).toBe('<$0.01')
  })

  it('exact cent renders numerically', () => {
    expect(fmtUSD(0.01)).toBe('$0.01')
  })

  it('typical amount rounds to 2dp', () => {
    expect(fmtUSD(1.5)).toBe('$1.50')
    expect(fmtUSD(12.999)).toBe('$13.00')
  })

  it('negative sub-cent does NOT trigger the < guard', () => {
    expect(fmtUSD(-0.005)).toBe('-$0.01')
  })
})

// ---- fmtTokens -------------------------------------------------------------

describe('fmtTokens', () => {
  it('zero renders as "0"', () => {
    expect(fmtTokens(0)).toBe('0')
  })

  it('small counts render as plain integers', () => {
    expect(fmtTokens(1)).toBe('1')
    expect(fmtTokens(999)).toBe('999')
  })

  it('four-digit counts use comma thousands separator', () => {
    expect(fmtTokens(1_234)).toBe('1,234')
    expect(fmtTokens(9_999)).toBe('9,999')
  })

  it('10 000+ counts use K abbreviation', () => {
    expect(fmtTokens(10_000)).toBe('10K')
    expect(fmtTokens(12_345)).toBe('12.3K')
    expect(fmtTokens(128_000)).toBe('128K')
  })

  it('K abbreviation drops trailing .0', () => {
    expect(fmtTokens(20_000)).toBe('20K')
    expect(fmtTokens(15_000)).toBe('15K')
  })
})

// ---- fmtDate ---------------------------------------------------------------

describe('fmtDate', () => {
  it('formats a known date as "D Mon YYYY"', () => {
    // 2026-07-18 00:00:00 UTC
    const ts = Date.UTC(2026, 6, 18)
    // en-GB format: "18 Jul 2026"
    expect(fmtDate(ts)).toBe('18 Jul 2026')
  })

  it('handles 1-digit day without zero-padding', () => {
    const ts = Date.UTC(2026, 0, 5)
    expect(fmtDate(ts)).toBe('5 Jan 2026')
  })
})

// ---- fmtRelative -----------------------------------------------------------

describe('fmtRelative', () => {
  const BASE = Date.UTC(2026, 6, 18, 12, 0, 0)

  beforeEach(() => {
    // Pin Date.now() to a fixed point so relative diffs are deterministic.
    // @ts-ignore — vitest supports setSystemTime via fake timers
    // We avoid importing vi from vitest at top-level to keep imports tidy.
  })

  it('returns "just now" for ts within the last 59 seconds', () => {
    const now = BASE
    const ts = BASE - 30_000 // 30 seconds ago
    // Temporarily override Date.now inside the function via a small spy
    const origNow = Date.now
    Date.now = () => now
    try {
      expect(fmtRelative(ts)).toBe('just now')
    } finally {
      Date.now = origNow
    }
  })

  it('returns "Nm ago" for ts 1–59 minutes ago', () => {
    const now = BASE
    const ts = BASE - 5 * 60_000 // 5 minutes ago
    const origNow = Date.now
    Date.now = () => now
    try {
      expect(fmtRelative(ts)).toBe('5m ago')
    } finally {
      Date.now = origNow
    }
  })

  it('returns "Nh ago" for ts 1–23 hours ago', () => {
    const now = BASE
    const ts = BASE - 3 * 3_600_000 // 3 hours ago
    const origNow = Date.now
    Date.now = () => now
    try {
      expect(fmtRelative(ts)).toBe('3h ago')
    } finally {
      Date.now = origNow
    }
  })

  it('returns a fmtDate string for ts more than 24 hours ago', () => {
    const now = BASE
    const ts = Date.UTC(2026, 6, 17, 0, 0, 0) // yesterday
    const origNow = Date.now
    Date.now = () => now
    try {
      expect(fmtRelative(ts)).toBe('17 Jul 2026')
    } finally {
      Date.now = origNow
    }
  })
})
