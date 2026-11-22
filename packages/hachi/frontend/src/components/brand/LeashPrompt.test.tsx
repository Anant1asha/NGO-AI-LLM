import { describe, it, expect, afterEach, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'

// LeashPrompt reads localStorage on mount — stub it so tests are hermetic.
vi.stubGlobal('localStorage', {
  getItem: vi.fn(() => null),
  setItem: vi.fn(),
  removeItem: vi.fn(),
})

import { LeashPrompt } from './LeashPrompt'

const BASE_PROPS = {
  request: 'Hachi wants to run a command',
  why: 'part of your scheduled task',
  onAllowOnce: vi.fn(),
  onAlwaysAllow: vi.fn(),
  onDecline: vi.fn(),
}

const RISK_MEDIUM = { label: 'needs care', fg: 'var(--hachi-working-fg)', bg: 'var(--hachi-working-tint)' }
const RISK_HIGH   = { label: 'high risk',  fg: 'var(--hachi-danger-fg)',  bg: 'var(--hachi-danger-tint)'  }

describe('LeashPrompt — button weighting (T10 / BB-85)', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('medium risk: neither Decline nor Allow once has the high-risk solid class', () => {
    render(<LeashPrompt {...BASE_PROPS} riskPill={RISK_MEDIUM} />)
    const decline = screen.getByRole('button', { name: 'Decline' })
    const allow   = screen.getByRole('button', { name: 'Allow once' })
    expect(decline.className).not.toContain('hachi-leash-decline-high-btn')
    expect(allow.className).not.toContain('high')
  })

  it('high risk: Decline carries the solid-trust class', () => {
    render(<LeashPrompt {...BASE_PROPS} riskPill={RISK_HIGH} />)
    const decline = screen.getByRole('button', { name: 'Decline' })
    expect(decline.className).toContain('hachi-leash-decline-high-btn')
  })

  it('high risk: Allow once stays outlined (no high class)', () => {
    render(<LeashPrompt {...BASE_PROPS} riskPill={RISK_HIGH} />)
    const allow = screen.getByRole('button', { name: 'Allow once' })
    expect(allow.className).not.toContain('high')
  })

  it('riskPill renders a badge with the pill label', () => {
    render(<LeashPrompt {...BASE_PROPS} riskPill={RISK_MEDIUM} />)
    expect(screen.getByText('needs care')).toBeTruthy()
  })

  it('countdown null → "no auto-decline" copy shown', () => {
    render(<LeashPrompt {...BASE_PROPS} countdown={null} />)
    expect(screen.getByText(/no auto-decline/i)).toBeTruthy()
  })

  it('countdown string → "auto-declines in" copy shown', () => {
    render(<LeashPrompt {...BASE_PROPS} countdown="1m 30s" />)
    expect(screen.getByText(/auto-declines in 1m 30s/i)).toBeTruthy()
  })

  it('touches list renders file chips', () => {
    render(<LeashPrompt {...BASE_PROPS} touches={['src/foo.ts', 'README.md']} />)
    expect(screen.getByText('src/foo.ts')).toBeTruthy()
    expect(screen.getByText('README.md')).toBeTruthy()
  })
})
