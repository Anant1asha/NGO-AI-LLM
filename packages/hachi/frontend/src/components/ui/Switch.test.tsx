// T18: Switch rebuilds with native <input type="checkbox" role="switch">
// so label is labelable and label-click toggles.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, fireEvent } from '@testing-library/react'
import { Switch } from './Switch'

afterEach(cleanup)

describe('Switch (T18)', () => {
  it('is findable by role+name via label prop', () => {
    render(<Switch checked={false} onChange={() => {}} label="Operator mode" />)
    expect(screen.getByRole('switch', { name: 'Operator mode' })).toBeTruthy()
  })

  it('is findable by role+name via ariaLabel prop', () => {
    render(<Switch checked={false} onChange={() => {}} ariaLabel="Dark mode" />)
    expect(screen.getByRole('switch', { name: 'Dark mode' })).toBeTruthy()
  })

  it('calls onChange when label text is clicked', () => {
    const onChange = vi.fn()
    render(<Switch checked={false} onChange={onChange} label="Operator mode" />)
    fireEvent.click(screen.getByText('Operator mode'))
    expect(onChange).toHaveBeenCalledWith(true)
  })

  it('does not call onChange when disabled', () => {
    const onChange = vi.fn()
    render(<Switch checked={false} onChange={onChange} label="Operator mode" disabled />)
    const input = screen.getByRole('switch', { name: 'Operator mode' })
    fireEvent.click(input)
    expect(onChange).not.toHaveBeenCalled()
  })
})
