// T14: Tier radiogroup must commit only on activation (Space/Enter/click), not on arrow navigation.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, fireEvent } from '@testing-library/react'
import { useStore } from '../../../lib/store/store'

vi.mock('../../icons/Icon', () => ({ Icon: () => null }))
vi.mock('../../ui/Switch', () => ({ Switch: () => null }))
vi.mock('../shared', () => ({
  PanelHeader: () => null,
  cardStyle: {},
  sectionHeadingStyle: {},
}))
vi.mock('@tanstack/react-router', () => ({ useNavigate: () => vi.fn() }))

const mockSetTierLive = vi.fn((_tier: unknown) => Promise.resolve())
vi.mock('../../../lib/data/domains/setup', async (importOriginal) => {
  const orig = await importOriginal<typeof import('../../../lib/data/domains/setup')>()
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return { ...orig, setTierLive: (tier: any) => mockSetTierLive(tier) }
})

// jsdom doesn't implement matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (_q: string) => ({ matches: false, addEventListener: () => {}, removeEventListener: () => {} }),
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  useStore.setState({ setup: { open: false, step: 0, key: '', safety: 'standard', routine: true, google: false, channel: false, mode: 'onboard', keyAlreadySet: false, tier: 'lightning', completed: false } })
})

describe('GeneralSection tier radiogroup — WAI-ARIA commit on activation (T14)', () => {
  async function setup() {
    useStore.setState({ setup: { open: false, step: 0, key: '', safety: 'standard', routine: true, google: false, channel: false, mode: 'onboard', keyAlreadySet: false, tier: 'lightning', completed: false } })
    const { default: GeneralSection } = await import('./GeneralSection')
    render(<GeneralSection />)
    return screen.getByRole('radiogroup', { name: 'Setup tier' })
  }

  it('does not call setTierLive when arrow keys move the cursor', async () => {
    const group = await setup()
    fireEvent.keyDown(group, { key: 'ArrowDown' })
    fireEvent.keyDown(group, { key: 'ArrowDown' })
    expect(mockSetTierLive).not.toHaveBeenCalled()
  })

  it('calls setTierLive exactly once with the final value after ArrowDown×2 + Enter', async () => {
    const group = await setup()
    fireEvent.keyDown(group, { key: 'ArrowDown' })
    fireEvent.keyDown(group, { key: 'ArrowDown' })
    fireEvent.keyDown(group, { key: 'Enter' })
    expect(mockSetTierLive).toHaveBeenCalledTimes(1)
    expect(mockSetTierLive).toHaveBeenCalledWith('enhanced')
  })

  it('commits immediately on click without requiring Enter', async () => {
    await setup()
    fireEvent.click(screen.getByRole('radio', { name: /Recommended/i }))
    expect(mockSetTierLive).toHaveBeenCalledTimes(1)
    expect(mockSetTierLive).toHaveBeenCalledWith('recommended')
  })
})
