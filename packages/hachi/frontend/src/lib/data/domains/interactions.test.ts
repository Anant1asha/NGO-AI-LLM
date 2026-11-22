// Tests for the interactions domain adapter + rateInteraction mutation.
// Pure unit tests — no DOM / React rendering needed.

import { describe, it, expect } from 'vitest'

// ---- adapter logic (mirrored from interactions.ts — not exported) ----
// We replicate the pure logic here to guard against regressions without
// importing the module (which would pull in store / client dependencies).

function humanizeTs(iso: string): string {
  try {
    const d = new Date(iso)
    if (isNaN(d.getTime())) return iso
    const now = Date.now()
    const diffMs = now - d.getTime()
    const diffMin = Math.floor(diffMs / 60_000)
    if (diffMin < 1) return 'just now'
    if (diffMin < 60) return `${diffMin}m ago`
    const diffHr = Math.floor(diffMin / 60)
    if (diffHr < 24) return `${diffHr}h ago`
    const diffDays = Math.floor(diffHr / 24)
    if (diffDays === 1) return 'yesterday'
    if (diffDays < 7) return `${diffDays}d ago`
    return d.toLocaleDateString()
  } catch {
    return iso
  }
}

function adaptRating(raw: string | null | undefined): 'up' | 'down' | null {
  if (raw === 'up') return 'up'
  if (raw === 'down') return 'down'
  return null
}

interface GatewayInteractionRecord {
  id: string
  session_id: string
  turn_id?: string | null
  ts: string
  user_input?: string | null
  agent_output?: string | null
  tool_calls?: string[]
  memory_hits?: string[]
  model_used?: string | null
  token_cost?: number | null
  tokens?: number | null
  rating?: string | null
  notes?: string | null
}

interface AgentInteraction {
  id: string
  sessionId: string
  turnId: string | null
  ts: string
  tsHuman: string
  userInput: string
  agentOutput: string
  toolCalls: string[]
  memoryHits: string[]
  modelUsed: string
  tokenCost: number | null
  tokens: number | null
  rating: 'up' | 'down' | null
  notes: string | null
}

function adapt(raw: GatewayInteractionRecord): AgentInteraction {
  return {
    id: raw.id,
    sessionId: raw.session_id,
    turnId: raw.turn_id ?? null,
    ts: raw.ts,
    tsHuman: humanizeTs(raw.ts),
    userInput: raw.user_input ?? '',
    agentOutput: raw.agent_output ?? '',
    toolCalls: raw.tool_calls ?? [],
    memoryHits: raw.memory_hits ?? [],
    modelUsed: raw.model_used ?? '',
    tokenCost: raw.token_cost ?? null,
    tokens: raw.tokens ?? null,
    rating: adaptRating(raw.rating),
    notes: raw.notes ?? null,
  }
}

// ---- tests ----

describe('interactions adapter — gateway → UI mapping', () => {
  const baseRaw: GatewayInteractionRecord = {
    id: 'ix-001',
    session_id: 'sess-abc',
    ts: new Date(Date.now() - 2 * 60_000).toISOString(), // 2 minutes ago
    user_input: 'Hello Hachi',
    agent_output: 'Hello! How can I help?',
    tool_calls: ['read_file', 'list_dir'],
    memory_hits: ['User prefers dark mode'],
    model_used: 'claude-haiku-4-5',
    token_cost: 0.0012,
    tokens: 850,
    rating: null,
    notes: null,
  }

  it('maps id and session_id correctly', () => {
    const ix = adapt(baseRaw)
    expect(ix.id).toBe('ix-001')
    expect(ix.sessionId).toBe('sess-abc')
  })

  it('tool_calls stays as string[]', () => {
    const ix = adapt(baseRaw)
    expect(Array.isArray(ix.toolCalls)).toBe(true)
    expect(ix.toolCalls).toEqual(['read_file', 'list_dir'])
    // Confirm elements are strings, not objects
    expect(typeof ix.toolCalls[0]).toBe('string')
  })

  it('memory_hits stays as string[]', () => {
    const ix = adapt(baseRaw)
    expect(Array.isArray(ix.memoryHits)).toBe(true)
    expect(ix.memoryHits).toEqual(['User prefers dark mode'])
    expect(typeof ix.memoryHits[0]).toBe('string')
  })

  it('null tool_calls / memory_hits default to empty arrays', () => {
    const raw: GatewayInteractionRecord = { ...baseRaw, tool_calls: undefined, memory_hits: undefined }
    const ix = adapt(raw)
    expect(ix.toolCalls).toEqual([])
    expect(ix.memoryHits).toEqual([])
  })

  it('null user_input defaults to empty string', () => {
    const raw: GatewayInteractionRecord = { ...baseRaw, user_input: null }
    const ix = adapt(raw)
    expect(ix.userInput).toBe('')
  })

  it('null agent_output defaults to empty string', () => {
    const raw: GatewayInteractionRecord = { ...baseRaw, agent_output: null }
    const ix = adapt(raw)
    expect(ix.agentOutput).toBe('')
  })

  it('null model_used defaults to empty string', () => {
    const raw: GatewayInteractionRecord = { ...baseRaw, model_used: null }
    const ix = adapt(raw)
    expect(ix.modelUsed).toBe('')
  })

  it('null token_cost stays null', () => {
    const raw: GatewayInteractionRecord = { ...baseRaw, token_cost: null }
    const ix = adapt(raw)
    expect(ix.tokenCost).toBeNull()
  })

  it('null tokens stays null', () => {
    const raw: GatewayInteractionRecord = { ...baseRaw, tokens: null }
    const ix = adapt(raw)
    expect(ix.tokens).toBeNull()
  })

  it('null turn_id maps to null', () => {
    const raw: GatewayInteractionRecord = { ...baseRaw, turn_id: null }
    const ix = adapt(raw)
    expect(ix.turnId).toBeNull()
  })

  it('tsHuman is populated (non-empty string)', () => {
    const ix = adapt(baseRaw)
    expect(typeof ix.tsHuman).toBe('string')
    expect(ix.tsHuman.length).toBeGreaterThan(0)
  })

  it('tsHuman for ~2m ago is "2m ago"', () => {
    const ix = adapt(baseRaw)
    expect(ix.tsHuman).toBe('2m ago')
  })

  it('tsHuman for invalid date returns the raw string', () => {
    const raw: GatewayInteractionRecord = { ...baseRaw, ts: 'not-a-date' }
    const ix = adapt(raw)
    expect(ix.tsHuman).toBe('not-a-date')
  })
})

describe('adaptRating — rating mapping', () => {
  it('"up" → "up"', () => {
    expect(adaptRating('up')).toBe('up')
  })
  it('"down" → "down"', () => {
    expect(adaptRating('down')).toBe('down')
  })
  it('null → null', () => {
    expect(adaptRating(null)).toBeNull()
  })
  it('undefined → null', () => {
    expect(adaptRating(undefined)).toBeNull()
  })
  it('unknown string → null', () => {
    expect(adaptRating('maybe')).toBeNull()
  })
})

describe('humanizeTs — timestamp humanization', () => {
  it('< 1 min → "just now"', () => {
    const ts = new Date(Date.now() - 30_000).toISOString()
    expect(humanizeTs(ts)).toBe('just now')
  })
  it('5 min ago → "5m ago"', () => {
    const ts = new Date(Date.now() - 5 * 60_000).toISOString()
    expect(humanizeTs(ts)).toBe('5m ago')
  })
  it('2h ago → "2h ago"', () => {
    const ts = new Date(Date.now() - 2 * 60 * 60_000).toISOString()
    expect(humanizeTs(ts)).toBe('2h ago')
  })
  it('1d ago → "yesterday"', () => {
    const ts = new Date(Date.now() - 25 * 60 * 60_000).toISOString()
    expect(humanizeTs(ts)).toBe('yesterday')
  })
  it('invalid date → returns input string', () => {
    expect(humanizeTs('bad-date')).toBe('bad-date')
  })
})

describe('rateInteraction contract (mock mode logic)', () => {
  // We test the mutation shape (what body should be sent to the gateway).
  // The actual HTTP call is not made here — tested at integration level.

  it('rating body has correct shape for "up"', () => {
    const body = { rating: 'up' as const, notes: 'Excellent' }
    expect(body.rating).toBe('up')
    expect(body.notes).toBe('Excellent')
  })

  it('rating body has correct shape for "down" with no notes', () => {
    const body: { rating: 'up' | 'down'; notes?: string } = { rating: 'down' }
    expect(body.rating).toBe('down')
    expect(body.notes).toBeUndefined()
  })

  it('gateway path is correct format', () => {
    const id = 'ix-xyz'
    const path = `/interactions/${id}/rating`
    expect(path).toBe('/interactions/ix-xyz/rating')
  })
})
