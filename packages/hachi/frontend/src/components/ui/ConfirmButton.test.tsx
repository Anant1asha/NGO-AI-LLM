// T8b / BB-83: ConfirmButton arm-then-confirm semantics.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, act, fireEvent } from '@testing-library/react';
import { ConfirmButton } from './ConfirmButton';

vi.mock('../icons/Icon', () => ({
  Icon: ({ name }: { name: string }) => <span data-icon={name} />,
}));

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe('ConfirmButton — arm-then-confirm (BB-83)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  it('does not fire onConfirm on first click (arms instead)', () => {
    const onConfirm = vi.fn();
    render(<ConfirmButton label="Delete" confirmLabel="Delete?" onConfirm={onConfirm} />);
    fireEvent.click(screen.getByRole('button'));
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it('does not fire onConfirm on immediate second click within cooldownMs', () => {
    const onConfirm = vi.fn();
    render(<ConfirmButton label="Delete" confirmLabel="Delete?" onConfirm={onConfirm} cooldownMs={400} />);
    const btn = screen.getByRole('button');
    fireEvent.click(btn);  // arm
    // Advance time by less than cooldown — should still be ignored
    act(() => { vi.advanceTimersByTime(10); });
    fireEvent.click(btn);  // within cooldown → ignored
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it('fires onConfirm on second click after cooldownMs', () => {
    const onConfirm = vi.fn();
    render(<ConfirmButton label="Delete" confirmLabel="Delete?" onConfirm={onConfirm} cooldownMs={400} armWindowMs={4000} />);
    const btn = screen.getByRole('button');
    fireEvent.click(btn);  // arm
    act(() => { vi.advanceTimersByTime(401); });  // past cooldown, before auto-disarm
    fireEvent.click(btn);  // confirm
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('auto-disarms after armWindowMs without a second click', () => {
    const onConfirm = vi.fn();
    render(<ConfirmButton label="Delete" confirmLabel="Delete?" onConfirm={onConfirm} armWindowMs={4000} cooldownMs={400} />);
    const btn = screen.getByRole('button');
    fireEvent.click(btn);  // arm
    act(() => { vi.advanceTimersByTime(4001); });  // disarm fires
    // Next click arms again, not confirms
    fireEvent.click(btn);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it('shows confirmLabel when armed', () => {
    render(<ConfirmButton label="Delete" confirmLabel="Delete?" onConfirm={() => {}} />);
    const btn = screen.getByRole('button');
    expect(btn.textContent).not.toContain('Delete?');
    fireEvent.click(btn);
    expect(btn.textContent).toContain('Delete?');
  });
});
