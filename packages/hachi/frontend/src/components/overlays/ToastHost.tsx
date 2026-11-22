// ============================================================
// ToastHost — renders the global transient toast stack (max 3).
// The wrapper div is ALWAYS mounted with role="status" aria-live="polite"
// so the live region is in the DOM BEFORE content changes — many screen
// readers won't announce a region that appears with text already inside it.
// Auto-dismiss runs here (not in the store) so it can pause while hovered.
// Prototype markup: Hachi Web App.dc.html lines 1461–1466
// ============================================================

import React, { CSSProperties, useEffect, useState } from 'react';
import { useStore } from '../../lib/store/store';
import { Toast } from '../ui/Toast';
import type { ToastTone } from '../ui/Toast';

const DEFAULT_DURATION_MS = 3200;
const ERROR_DURATION_MS   = 6500;
const ACTION_DURATION_MS  = 6000;

// Map store tone values to the Toast component's accepted tones.
const TONE_MAP: Record<string, ToastTone> = {
  success: 'success',
  working: 'info',
  blocked: 'blocked',
  info:    'info',
};

export function ToastHost() {
  const toasts       = useStore((s) => s.toasts);
  const dismissToast = useStore((s) => s.dismissToast);
  const [paused, setPaused] = useState(false);

  // Auto-dismiss the oldest toast after its duration.
  // Re-runs whenever the oldest toast id changes or hover state changes.
  const oldest = toasts[0];
  useEffect(() => {
    if (!oldest || paused) return;
    const duration = oldest.tone === 'blocked' ? ERROR_DURATION_MS
                   : oldest.action             ? ACTION_DURATION_MS
                   :                             DEFAULT_DURATION_MS;
    const t = setTimeout(() => dismissToast(oldest.id), duration);
    return () => clearTimeout(t);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [oldest?.id, paused, dismissToast]);

  const wrapStyle: CSSProperties = {
    position: 'fixed',
    bottom: 28,
    left: '50%',
    transform: 'translateX(-50%)',
    zIndex: 70,
    display: 'flex',
    flexDirection: 'column-reverse',
    alignItems: 'center',
    gap: 'var(--space-2)',
  };

  return (
    <div role="status" aria-live="polite" aria-atomic="false" style={wrapStyle}>
      {toasts.map((t) => (
        <Toast
          key={t.id}
          message={t.message}
          tone={TONE_MAP[t.tone ?? 'success'] ?? 'success'}
          action={t.action}
          onDismiss={() => dismissToast(t.id)}
          onMouseEnter={() => setPaused(true)}
          onMouseLeave={() => setPaused(false)}
        />
      ))}
    </div>
  );
}
