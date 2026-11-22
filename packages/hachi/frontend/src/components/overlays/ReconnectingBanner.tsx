// ============================================================
// ReconnectingBanner — calm top status pill shown while socket
// reconnects. Auto-recovers via simulateReconnect in the store.
// Prototype markup: Hachi Web App.dc.html lines 1453–1459
// ============================================================

import React, { CSSProperties } from 'react';
import { useStore } from '../../lib/store/store';
import { LoyalLoop } from '../ui/LoyalLoop';

export function ReconnectingBanner() {
  const reconnecting = useStore((s) => s.reconnecting);

  if (!reconnecting) return null;

  const pillStyle: CSSProperties = {
    position: 'fixed',
    top: 18,
    left: '50%',
    transform: 'translateX(-50%)',
    zIndex: 80,
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    background: 'var(--hachi-working-tint)',
    border: '0.5px solid var(--hachi-line)',
    borderRadius: 999,
    padding: '9px 16px',
    boxShadow: '0 6px 20px rgba(28,26,32,.1)',
    whiteSpace: 'nowrap',
  };

  const textStyle: CSSProperties = {
    fontSize: 13,
    color: 'var(--hachi-working-fg)',
    fontWeight: 500,
  };

  return (
    <div style={pillStyle} role="status" aria-live="polite">
      <LoyalLoop size={18} />
      <span style={textStyle}>Reconnecting to Hachi on your machine…</span>
    </div>
  );
}
