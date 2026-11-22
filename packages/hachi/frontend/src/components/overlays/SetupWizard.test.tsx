// T6 / BB-82: Setup wizard key gate, Skip semantics, and openSetup step preservation.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { SetupWizard } from './SetupWizard';
import { useStore } from '../../lib/store/store';

vi.mock('../../lib/data/domains/setup', () => ({
  loadSetup: vi.fn().mockResolvedValue(undefined),
  applySetup: vi.fn().mockResolvedValue(undefined),
  validateKey: vi.fn().mockResolvedValue({ status: 'idle' }),
}));

vi.mock('../../lib/data/client', () => ({
  USE_MOCKS: false,
  apiGet: vi.fn().mockResolvedValue(undefined),
  apiSend: vi.fn().mockResolvedValue(undefined),
  registerReconnectCallback: vi.fn(),
  isNetworkError: () => false,
  API_BASE: '/api',
  authHeaders: () => ({}),
  ApiError: class ApiError extends Error {},
}));

vi.mock('../../lib/data/sse', () => ({ streamSSE: vi.fn() }));

vi.mock('../../lib/notifications', () => ({
  ensureNotificationPermission: vi.fn(),
  notifyApprovalPending: vi.fn(),
}));

vi.mock('../../lib/hooks/useFocusTrap', () => ({
  useFocusTrap: () => ({ current: null }),
}));

type SetupState = {
  open: boolean;
  step: number;
  key: string;
  safety: 'guarded' | 'standard' | 'open';
  routine: boolean;
  google: boolean;
  channel: boolean;
  mode: 'onboard' | 'edit-provider';
  keyAlreadySet: boolean;
  tier: 'lightning' | 'recommended' | 'enhanced' | 'power';
  completed: boolean;
};

function setupAt(overrides: Partial<SetupState> = {}) {
  const base: SetupState = {
    open: true,
    step: 1,
    key: '',
    safety: 'standard',
    routine: true,
    google: false,
    channel: false,
    mode: 'onboard',
    keyAlreadySet: false,
    tier: 'lightning',
    completed: false,
    ...overrides,
  };
  useStore.setState({ setup: base } as Parameters<typeof useStore.setState>[0]);
}

afterEach(() => {
  cleanup();
  useStore.setState({
    setup: {
      open: false,
      step: 0,
      key: '',
      safety: 'standard',
      routine: true,
      google: false,
      channel: false,
      mode: 'onboard',
      keyAlreadySet: false,
      tier: 'lightning',
      completed: false,
    },
  } as Parameters<typeof useStore.setState>[0]);
});

// ---- T6 / BB-82: Next gate on key step ----

describe('SetupWizard — key step gate (BB-82)', () => {
  it('Next button is disabled when key is empty and no key pre-configured', () => {
    setupAt({ keyAlreadySet: false, key: '' });
    render(<SetupWizard />);
    const btn = screen.getByRole('button', { name: /^next$/i }) as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
  });

  it('Next button is enabled when keyAlreadySet=true (existing key qualifies)', () => {
    setupAt({ keyAlreadySet: true, key: '' });
    render(<SetupWizard />);
    const btn = screen.getByRole('button', { name: /^next$/i }) as HTMLButtonElement;
    expect(btn.disabled).toBe(false);
  });

  it('Next button is not disabled on non-key steps', () => {
    setupAt({ step: 2 });
    render(<SetupWizard />);
    const btn = screen.getByRole('button', { name: /^next$/i }) as HTMLButtonElement;
    expect(btn.disabled).toBe(false);
  });
});

// ---- T6 / BB-82: Skip advances a step; Set up later closes ----

describe('SetupWizard — Skip and Set-up-later (BB-82)', () => {
  it('Skip button is hidden on KEY_STEP when keyAlreadySet=false', () => {
    setupAt({ step: 1, keyAlreadySet: false });
    render(<SetupWizard />);
    expect(screen.queryByRole('button', { name: /^skip$/i })).toBeNull();
  });

  it('Skip button is visible on KEY_STEP when keyAlreadySet=true', () => {
    setupAt({ step: 1, keyAlreadySet: true });
    render(<SetupWizard />);
    expect(screen.getByRole('button', { name: /^skip$/i })).toBeTruthy();
  });

  it('"Set up later" button is present on KEY_STEP', () => {
    setupAt({ step: 1, keyAlreadySet: false });
    render(<SetupWizard />);
    expect(screen.getByRole('button', { name: /set up later/i })).toBeTruthy();
  });

  it('"Set up later" is not present on non-key steps', () => {
    setupAt({ step: 2 });
    render(<SetupWizard />);
    expect(screen.queryByRole('button', { name: /set up later/i })).toBeNull();
  });
});

// ---- T6 / BB-82: openSetup preserves step progress ----

describe('SetupWizard — openSetup step preservation (BB-82)', () => {
  beforeEach(() => {
    useStore.setState({
      setup: { open: false, step: 0, key: '', safety: 'standard', routine: true, google: false, channel: false, mode: 'onboard', keyAlreadySet: false, tier: 'lightning', completed: false },
    } as Parameters<typeof useStore.setState>[0]);
  });

  it('openSetup preserves step when wizard was partially completed (step>0, not done)', () => {
    useStore.setState({
      setup: {
        open: false, step: 2, key: '', safety: 'standard', routine: true, google: false,
        channel: false, mode: 'onboard', keyAlreadySet: false, tier: 'lightning', completed: false,
      },
    } as Parameters<typeof useStore.setState>[0]);
    useStore.getState().openSetup();
    expect(useStore.getState().setup.step).toBe(2);
    expect(useStore.getState().setup.open).toBe(true);
  });

  it('openSetup resets to step 0 when wizard was fully completed', () => {
    useStore.setState({
      setup: {
        open: false, step: 4, key: '', safety: 'standard', routine: true, google: false,
        channel: false, mode: 'onboard', keyAlreadySet: false, tier: 'lightning', completed: true,
      },
    } as Parameters<typeof useStore.setState>[0]);
    useStore.getState().openSetup();
    expect(useStore.getState().setup.step).toBe(0);
  });

  it('openSetup resets to step 0 when wizard was at step 0 and closed', () => {
    useStore.setState({
      setup: {
        open: false, step: 0, key: '', safety: 'standard', routine: true, google: false,
        channel: false, mode: 'onboard', keyAlreadySet: false, tier: 'lightning', completed: false,
      },
    } as Parameters<typeof useStore.setState>[0]);
    useStore.getState().openSetup();
    expect(useStore.getState().setup.step).toBe(0);
  });

  it('setupNext on the final step sets completed=true', () => {
    useStore.setState({
      setup: {
        open: true, step: 4, key: '', safety: 'standard', routine: false, google: false,
        channel: false, mode: 'onboard', keyAlreadySet: false, tier: 'lightning', completed: false,
      },
    } as Parameters<typeof useStore.setState>[0]);
    useStore.getState().setupNext();
    expect(useStore.getState().setup.completed).toBe(true);
    expect(useStore.getState().setup.open).toBe(false);
  });
});
