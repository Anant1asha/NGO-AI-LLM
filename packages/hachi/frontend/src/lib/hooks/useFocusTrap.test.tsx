// T19: useFocusTrap must restore focus on unmount, not on active-flip.
// Previously the restore effect was keyed on `active` becoming false,
// but all dialogs unmount while active=true, so restore never ran.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, fireEvent, act } from '@testing-library/react'
import { useState } from 'react'
import { useFocusTrap } from './useFocusTrap'

afterEach(cleanup)

function Dialog({ onClose }: { onClose: () => void }) {
  const trapRef = useFocusTrap<HTMLDivElement>(true)
  return (
    <div ref={trapRef} role="dialog" aria-modal="true" aria-label="Test dialog">
      <button onClick={onClose}>Close</button>
    </div>
  )
}

function Host() {
  const [open, setOpen] = useState(false)
  return (
    <div>
      <button onClick={() => setOpen(true)}>Open</button>
      {open && <Dialog onClose={() => setOpen(false)} />}
    </div>
  )
}

describe('useFocusTrap (T19)', () => {
  it('moves focus into dialog when it opens', () => {
    render(<Host />)
    act(() => { fireEvent.click(screen.getByText('Open')) })
    expect(document.activeElement?.textContent).toBe('Close')
  })

  it('restores focus to trigger on dialog unmount', () => {
    render(<Host />)
    const trigger = screen.getByText('Open')

    // jsdom does not auto-focus on click; set focus explicitly so the hook
    // captures the right prev element before the dialog mounts.
    act(() => { trigger.focus() })
    const focusSpy = vi.spyOn(trigger, 'focus')

    act(() => { fireEvent.click(trigger) })
    // Dialog is now open; close it (unmounts Dialog, cleanup restores focus)
    act(() => { fireEvent.click(screen.getByText('Close')) })

    expect(focusSpy).toHaveBeenCalled()
    focusSpy.mockRestore()
  })
})
