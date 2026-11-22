import { describe, it, expect } from 'vitest'
import { fuzzyScore } from './CommandPalette'

describe('fuzzyScore', () => {
  it('returns -1 when query is not a subsequence', () => {
    expect(fuzzyScore('xyz', 'Conversation')).toBe(-1)
  })

  it('"cnv" matches "Go to Conversation"', () => {
    expect(fuzzyScore('cnv', 'Go to Conversation')).toBeGreaterThan(0)
  })

  it('exact prefix scores highest', () => {
    const full = fuzzyScore('conv', 'Conversation')
    const spread = fuzzyScore('cnv', 'Conversation')
    expect(full).toBeGreaterThan(spread)
  })

  it('word-start match scores higher than mid-word', () => {
    // 'c' at start of "Conversation" vs mid-word
    const start = fuzzyScore('c', 'Conversation')
    const mid = fuzzyScore('v', 'Conversation')
    expect(start).toBeGreaterThan(mid)
  })

  it('empty query always scores 0 (show all)', () => {
    expect(fuzzyScore('', 'anything')).toBe(0)
  })

  it('case-insensitive', () => {
    expect(fuzzyScore('CONV', 'conversation')).toBeGreaterThan(0)
  })
})
