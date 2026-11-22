// T14: Safety radiogroup must commit only on activation (Space/Enter/click), not on arrow navigation.

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

const mockSetSafetyLive = vi.fn((_level: unknown) => Promise.resolve())
vi.mock('../../../lib/data/domains/config', async (importOriginal) => {
  const orig = await importOriginal<typeof import('../../../lib/data/domains/config')>()
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return { ...orig, setSafetyLive: (level: any) => mockSetSafetyLive(level) }
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  useStore.setState({ safety: 'standard', configLoaded: false, askRules: [], allowedFolders: [], allowedCommands: [], opTools: [], operator: false })
})

describe('PermissionsSection safety radiogroup — WAI-ARIA commit on activation (T14)', () => {
  async function setup() {
    useStore.setState({ safety: 'guarded', configLoaded: true, askRules: [], allowedFolders: [], allowedCommands: [], opTools: [] })
    const { default: PermissionsSection } = await import('./PermissionsSection')
    render(<PermissionsSection />)
    return screen.getByRole('radiogroup', { name: 'Safety level' })
  }

  it('does not call setSafetyLive when arrow keys move the cursor', async () => {
    const group = await setup()
    fireEvent.keyDown(group, { key: 'ArrowDown' })
    fireEvent.keyDown(group, { key: 'ArrowDown' })
    expect(mockSetSafetyLive).not.toHaveBeenCalled()
  })

  it('calls setSafetyLive exactly once with the final value after ArrowDown×2 + Enter', async () => {
    const group = await setup()
    fireEvent.keyDown(group, { key: 'ArrowDown' })
    fireEvent.keyDown(group, { key: 'ArrowDown' })
    fireEvent.keyDown(group, { key: 'Enter' })
    expect(mockSetSafetyLive).toHaveBeenCalledTimes(1)
    expect(mockSetSafetyLive).toHaveBeenCalledWith('open')
  })

  it('commits immediately on click without requiring Enter', async () => {
    await setup()
    fireEvent.click(screen.getByRole('radio', { name: /Standard/i }))
    expect(mockSetSafetyLive).toHaveBeenCalledTimes(1)
    expect(mockSetSafetyLive).toHaveBeenCalledWith('standard')
  })
})
