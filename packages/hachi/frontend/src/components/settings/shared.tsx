// Shared style tokens and small presentational helpers for the Settings area.
// Keeps the sectioned Settings panels visually consistent (card / heading /
// input / select / label) without each file re-declaring the same objects.

import React from 'react';

export const cardStyle: React.CSSProperties = {
  background: 'var(--hachi-surface)',
  border: '0.5px solid var(--hachi-line)',
  borderRadius: 16,
  padding: 22,
};

/** h3-level heading used on individual cards inside a section panel. */
export const sectionHeadingStyle: React.CSSProperties = {
  margin: 0,
  fontFamily: 'var(--font-display)',
  fontWeight: 500,
  fontSize: 17,
};

export const inputStyle: React.CSSProperties = {
  width: '100%',
  height: 40,
  padding: '0 12px',
  borderRadius: 10,
  border: '0.5px solid var(--hachi-line)',
  background: 'var(--hachi-canvas)',
  font: '14px var(--font-mono)',
  color: 'var(--hachi-ink)',
  outline: 'none',
  boxSizing: 'border-box',
};

export const selectStyle: React.CSSProperties = {
  ...inputStyle,
  cursor: 'pointer',
  font: '14px var(--font-body)',
};

export const labelStyle: React.CSSProperties = {
  fontSize: 12,
  color: 'var(--hachi-muted)',
  marginBottom: 6,
  display: 'block',
};

/**
 * Panel header shown at the top of each Settings section.
 * Renders as an <h2> (the shell owns the single <h1> "Settings").
 */
export function PanelHeader({
  title,
  subtitle,
  right,
}: {
  title: string;
  subtitle?: string;
  right?: React.ReactNode;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 18 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <h2
          style={{
            margin: 0,
            fontFamily: 'var(--font-display)',
            fontWeight: 500,
            fontSize: 20,
            lineHeight: '26px',
          }}
        >
          {title}
        </h2>
        {subtitle && (
          <div style={{ fontSize: 13, color: 'var(--hachi-muted)', marginTop: 4 }}>{subtitle}</div>
        )}
      </div>
      {right && <div style={{ flexShrink: 0 }}>{right}</div>}
    </div>
  );
}

/** Inline toast/banner used inside section panels (errors and confirmations). */
export function Banner({ message, type }: { message: string; type: 'success' | 'error' }) {
  return (
    <div
      style={{
        padding: '10px 14px',
        borderRadius: 10,
        background: type === 'success' ? 'var(--hachi-trust-tint)' : 'var(--hachi-danger-tint)',
        color: type === 'success' ? 'var(--hachi-trust)' : 'var(--hachi-danger)',
        fontSize: 13,
        marginTop: 12,
      }}
    >
      {message}
    </div>
  );
}
