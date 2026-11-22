import { describe, it, expect, afterEach } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { ApprovalCard } from './index'

// Regression guard for the confirmed mobile layout bug: the Home "What needs you"
// approval card wrapped its title one word per line ("Hachi / wants / to / send…")
// because the Decline/Allow-once buttons lived as a flexShrink:0 sibling of the
// title in the SAME horizontal flex row, squeezing the title's flex:1 minWidth:0
// column down to almost nothing on narrow viewports. /approvals already puts its
// action buttons in a separate full-width row below the header — Home's card didn't.
// This test asserts that structural invariant directly: the action buttons must not
// live inside the header row alongside the icon/title.
describe('Home ApprovalCard — action row layout', () => {
  afterEach(cleanup)

  const approval = {
    id: 1,
    icon: 'mail',
    request: 'Hachi wants to send an email to alice@example.com about the Q3 report',
    why: 'drafted from your last approved template',
    risk: 'high',
    expiresAt: Date.now() + 60_000,
  }

  it('renders the action buttons outside the header row (not squeezed alongside the title)', () => {
    render(<ApprovalCard approval={approval} onAllow={() => {}} onDecline={() => {}} />)

    const header = screen.getByTestId('approval-header')
    const actions = screen.getByTestId('approval-actions')

    // The actions block must be a sibling of the header, not nested inside it.
    expect(header.contains(actions)).toBe(false)

    const declineBtn = screen.getByRole('button', { name: 'Decline' })
    const allowBtn = screen.getByRole('button', { name: 'Allow once' })
    expect(header.contains(declineBtn)).toBe(false)
    expect(header.contains(allowBtn)).toBe(false)
    expect(actions.contains(declineBtn)).toBe(true)
    expect(actions.contains(allowBtn)).toBe(true)
  })
})
