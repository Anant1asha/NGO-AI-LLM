// Tests for FIX 1 (adaptMcpServer status mapping) and FIX 4 (SpendBreakdown).
// These are pure unit tests — no DOM / React rendering needed.

import { describe, it, expect } from 'vitest'

import { adaptMcpServer, extractMcpSecrets, looksLikeMcpSecretKey } from './integrations'

// ---- BB-16: real-function regression lock for status mapping ----
// adaptMcpServer is now exported, so test it directly instead of a replica.
// The key regression: backend "pending_restart"/"stopped" (registered but not
// running this session) must NOT render as "starting" (a boot that never ends).
describe('adaptMcpServer — real mapping (BB-16)', () => {
  const map = (status: string) => adaptMcpServer({ name: 'x', status }).status

  it('maps "pending_restart" → pending (NOT starting)', () => {
    expect(map('pending_restart')).toBe('pending')
  })
  it('maps "stopped" → pending (NOT starting)', () => {
    expect(map('stopped')).toBe('pending')
  })
  it('maps "ready" → connected', () => {
    expect(map('ready')).toBe('connected')
  })
  it('maps "failed" → blocked', () => {
    expect(map('failed')).toBe('blocked')
  })
  it('maps unknown status → starting (fallback unchanged)', () => {
    expect(map('something_weird')).toBe('starting')
  })
})

// ---- FIX 1: adaptMcpServer mapping (replica kept for the broader matrix) ----
// Mirrors adaptMcpServer's statusMap. Kept in sync with the real function above.

type McpStatus = 'connected' | 'starting' | 'blocked' | 'loading' | 'pending'

/** Mirrors adaptMcpServer's statusMap exactly (integrations.ts). */
function mapStatus(rawStatus: string): McpStatus {
  const s = (rawStatus ?? '').toLowerCase()
  const map: Record<string, McpStatus> = {
    connected: 'connected',
    ready: 'connected',
    running: 'connected',
    starting: 'starting',
    loading: 'loading',
    initialising: 'loading',
    initializing: 'loading',
    pending_restart: 'pending',
    stopped: 'pending',
    pending: 'pending',
    blocked: 'blocked',
    failed: 'blocked',
    error: 'blocked',
  }
  return map[s] ?? 'starting'
}

describe('adaptMcpServer — status mapping', () => {
  // ---- connected variants ----
  it('maps "ready" → connected', () => {
    expect(mapStatus('ready')).toBe('connected')
  })
  it('maps "running" → connected', () => {
    expect(mapStatus('running')).toBe('connected')
  })
  it('maps "connected" → connected', () => {
    expect(mapStatus('connected')).toBe('connected')
  })

  // ---- loading variants (FIX 1 — transient state) ----
  it('maps "loading" → loading', () => {
    expect(mapStatus('loading')).toBe('loading')
  })
  it('maps "initialising" → loading', () => {
    expect(mapStatus('initialising')).toBe('loading')
  })
  it('maps "initializing" → loading', () => {
    expect(mapStatus('initializing')).toBe('loading')
  })
  it('maps "pending" → pending', () => {
    expect(mapStatus('pending')).toBe('pending')
  })

  // ---- blocked/error variants (FIX 1 — err chip) ----
  it('maps "failed" → blocked (error chip)', () => {
    expect(mapStatus('failed')).toBe('blocked')
  })
  it('maps "error" → blocked', () => {
    expect(mapStatus('error')).toBe('blocked')
  })
  it('maps "blocked" → blocked', () => {
    expect(mapStatus('blocked')).toBe('blocked')
  })

  // ---- starting fallback ----
  it('maps "starting" → starting', () => {
    expect(mapStatus('starting')).toBe('starting')
  })
  it('maps unknown string → starting (fallback)', () => {
    expect(mapStatus('something_weird')).toBe('starting')
  })
  it('maps empty string → starting (fallback)', () => {
    expect(mapStatus('')).toBe('starting')
  })

  // ---- case insensitivity ----
  it('handles mixed case "READY"', () => {
    expect(mapStatus('READY')).toBe('connected')
  })
  it('handles mixed case "FAILED"', () => {
    expect(mapStatus('FAILED')).toBe('blocked')
  })
  it('handles mixed case "Loading"', () => {
    expect(mapStatus('Loading')).toBe('loading')
  })
})

// ---- FIX 4: C-SPEND payload rendering logic ----
// We test the pure helper functions that the SpendBreakdown component uses
// (usd formatter, tok formatter) and the data shape contracts.

/** Mirrors SpendSection's usd() helper. */
function usd(v: number | undefined): string {
  if (v == null) return '—'
  return `$${v.toFixed(4)}`
}

/** Mirrors SpendSection's tok() helper. */
function tok(v: number | undefined): string {
  if (v == null) return '—'
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`
  return String(v)
}

interface CSpendModel {
  model: string
  cost_usd: number
  input_tokens?: number
  output_tokens?: number
}

interface CSpendModalities {
  text?: number
  voice?: number
  [key: string]: number | undefined
}

interface CSpendResponse {
  models?: CSpendModel[]
  modalities?: CSpendModalities
  cumulative_usd?: number
  session?: { session_id?: string; cost_usd?: number; turns?: number }
}

describe('SpendBreakdown — C-SPEND payload', () => {
  const samplePayload: CSpendResponse = {
    models: [
      { model: 'claude-haiku-4-5', cost_usd: 0.0015, input_tokens: 1200, output_tokens: 300 },
      { model: 'claude-sonnet-4-6', cost_usd: 0.024, input_tokens: 8000, output_tokens: 2000 },
    ],
    modalities: { text: 0.0255, voice: 0.003 },
    session: { session_id: 'abc123', cost_usd: 0.028, turns: 5 },
    cumulative_usd: 1.425,
  }

  it('sample payload has models array with 2 entries', () => {
    expect(Array.isArray(samplePayload.models)).toBe(true)
    expect(samplePayload.models!.length).toBe(2)
  })

  it('usd() formats correctly', () => {
    expect(usd(0.0015)).toBe('$0.0015')
    expect(usd(0.024)).toBe('$0.0240')
    expect(usd(undefined)).toBe('—')
  })

  it('tok() formats tokens with K/M suffix', () => {
    expect(tok(300)).toBe('300')
    expect(tok(1200)).toBe('1.2K')
    expect(tok(8000)).toBe('8.0K')
    expect(tok(1_500_000)).toBe('1.5M')
    expect(tok(undefined)).toBe('—')
  })

  it('has text and voice modalities', () => {
    expect(samplePayload.modalities?.text).toBe(0.0255)
    expect(samplePayload.modalities?.voice).toBe(0.003)
  })

  it('session data is accessible', () => {
    expect(samplePayload.session?.cost_usd).toBe(0.028)
    expect(samplePayload.session?.turns).toBe(5)
  })

  it('cumulative is accessible', () => {
    expect(samplePayload.cumulative_usd).toBe(1.425)
    expect(usd(samplePayload.cumulative_usd)).toBe('$1.4250')
  })

  it('defensive: empty payload has no models or modalities', () => {
    const empty: CSpendResponse = {}
    expect(Array.isArray(empty.models)).toBe(false)
    expect(empty.modalities).toBeUndefined()
    expect(empty.cumulative_usd).toBeUndefined()
  })

  it('defensive: models array may be missing individual optional fields', () => {
    const minimal: CSpendModel = { model: 'x', cost_usd: 0.001 }
    // input_tokens and output_tokens are optional — should fall back to "—"
    expect(tok(minimal.input_tokens)).toBe('—')
    expect(tok(minimal.output_tokens)).toBe('—')
    expect(usd(minimal.cost_usd)).toBe('$0.0010')
  })
})

// ---- BB-18: transparent MCP secret extraction ----
describe('extractMcpSecrets — transparent secret handling', () => {
  it('detects secret-looking keys', () => {
    expect(looksLikeMcpSecretKey('CONTEXT7_API_KEY')).toBe(true)
    expect(looksLikeMcpSecretKey('Authorization')).toBe(true)
    expect(looksLikeMcpSecretKey('X-API-Token')).toBe(true)
    expect(looksLikeMcpSecretKey('REGION')).toBe(false)
    expect(looksLikeMcpSecretKey('BASE_URL')).toBe(false)
  })

  it('rewrites a secret-looking raw value to a secret:<name> ref + queues the secret', () => {
    const { sanitized, secrets } = extractMcpSecrets('context7', 'env', {
      CONTEXT7_API_KEY: 'ctx7-raw-value',
    })
    expect(sanitized.CONTEXT7_API_KEY).toBe('secret:mcp_context7_env_CONTEXT7_API_KEY')
    expect(secrets).toEqual([
      { name: 'mcp_context7_env_CONTEXT7_API_KEY', value: 'ctx7-raw-value' },
    ])
  })

  it('sanitizes header keys into the gateway secret-name charset', () => {
    const { sanitized, secrets } = extractMcpSecrets('ctx', 'header', {
      'X-Api-Key': 'abc',
    })
    // The "-" in the header key must be coerced to match ^[\w.\-]+$.
    expect(secrets[0].name).toMatch(/^[\w.\-]+$/)
    expect(sanitized['X-Api-Key']).toBe(`secret:${secrets[0].name}`)
  })

  it('passes non-secret keys through untouched', () => {
    const { sanitized, secrets } = extractMcpSecrets('s', 'env', { REGION: 'us-east-1' })
    expect(sanitized).toEqual({ REGION: 'us-east-1' })
    expect(secrets).toEqual([])
  })

  it('leaves an existing secret:<name> reference untouched', () => {
    const { sanitized, secrets } = extractMcpSecrets('s', 'env', {
      API_KEY: 'secret:my_existing_cred',
    })
    expect(sanitized.API_KEY).toBe('secret:my_existing_cred')
    expect(secrets).toEqual([])
  })

  it('does not store an empty value', () => {
    const { sanitized, secrets } = extractMcpSecrets('s', 'env', { API_KEY: '' })
    expect(secrets).toEqual([])
    expect(sanitized.API_KEY).toBe('')
  })
})
