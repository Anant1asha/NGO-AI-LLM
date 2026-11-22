// GeneralSection — Mode (operator) + Appearance & account (theme, re-run setup).
// Carried over from the previous single-scroll Settings page; behaviour is
// unchanged, just grouped under the "General" panel.

import { useState, useEffect } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { useStore } from '../../../lib/store/store';
import { Icon } from '../../icons/Icon';
import { Switch } from '../../ui/Switch';
import { setTierLive, type WizardTier } from '../../../lib/data/domains/setup';
import { cardStyle, sectionHeadingStyle, PanelHeader } from '../shared';

const TIER_OPTIONS: { k: WizardTier; name: string; desc: string }[] = [
  { k: 'lightning', name: 'Lightning', desc: 'Fastest start — just provider and safety.' },
  { k: 'recommended', name: 'Recommended', desc: 'Adds memory so Hachi remembers across sessions.' },
  { k: 'enhanced', name: 'Enhanced', desc: 'Adds integrations — connect Google, Slack and more.' },
  { k: 'power', name: 'Power', desc: 'Everything, including advanced operator controls.' },
];

function SetupButton({ onClick, children }: { onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      className="hachi-setup-btn"
      onClick={onClick}
      style={{
        height: 34,
        padding: '0 14px',
        borderRadius: 10,
        border: '0.5px solid var(--hachi-line)',
        background: 'var(--hachi-canvas)',
        color: 'var(--hachi-ink)',
        font: '500 13px var(--font-body)',
        cursor: 'pointer',
        transition: 'background var(--dur-fast) var(--ease)',
      }}
    >
      {children}
    </button>
  );
}

export default function GeneralSection() {
  const navigate = useNavigate();
  const operator = useStore((s) => s.operator);
  const toggleOperator = useStore((s) => s.toggleOperator);
  const theme = useStore((s) => s.theme);
  const toggleTheme = useStore((s) => s.toggleTheme);
  const openSetup = useStore((s) => s.openSetup);
  const tier = useStore((s) => s.setup.tier);

  // Pin the chosen tier locally so a concurrent loadSetup re-hydration can't
  // briefly revert the selection while the apply round-trip is in flight.
  const [pendingTier, setPendingTier] = useState<WizardTier | null>(null);
  // Keyboard cursor: set on arrow-key navigation, cleared on commit or blur-out.
  const [highlighted, setHighlighted] = useState<WizardTier | null>(null);
  useEffect(() => {
    if (pendingTier !== null && tier === pendingTier) setPendingTier(null);
  }, [tier, pendingTier]);
  const effectiveTier = pendingTier ?? tier;
  function handleSetTier(t: WizardTier) {
    setPendingTier(t);
    void setTierLive(t);
  }

  const systemIsDark =
    typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches;
  const isDark = theme === 'dark' || (theme === 'auto' && systemIsDark);
  const themeIcon = isDark ? 'moon' : 'sun';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <PanelHeader title="General" subtitle="How Hachi looks and behaves day to day." />

      {/* Mode */}
      <div style={cardStyle}>
        <h3 style={{ ...sectionHeadingStyle, marginBottom: 16 }}>Mode</h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '11px 0' }}>
          <span style={{ color: 'var(--hachi-trust)', display: 'inline-flex' }}>
            <Icon name="cpu" size={17} />
          </span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 14, fontWeight: 500 }}>Operator mode</div>
            <div style={{ fontSize: 13, color: 'var(--hachi-muted)', marginTop: 2 }}>
              Shows tool signatures, expanded cards, and advanced controls. For power users and
              integrators.
            </div>
          </div>
          <Switch checked={operator} onChange={toggleOperator} ariaLabel="Operator mode" />
        </div>
      </div>

      {/* Setup tier */}
      <div style={cardStyle}>
        <h3 style={{ ...sectionHeadingStyle, marginBottom: 6 }}>Setup tier</h3>
        <div style={{ fontSize: 13, color: 'var(--hachi-muted)', marginBottom: 16 }}>
          How much of Hachi is switched on. Higher tiers unlock memory, integrations, and
          advanced controls. This is separate from the safety leash in Permissions.
        </div>
        <div
          role="radiogroup"
          aria-label="Setup tier"
          style={{ display: 'flex', flexDirection: 'column', gap: 9 }}
          onKeyDown={(e) => {
            const ARROW = new Set(['ArrowDown', 'ArrowUp', 'ArrowRight', 'ArrowLeft', 'Home', 'End']);
            if (ARROW.has(e.key)) {
              e.preventDefault();
              const current = highlighted ?? effectiveTier;
              const idx = TIER_OPTIONS.findIndex((opt) => opt.k === current);
              let nextIdx: number;
              if (e.key === 'Home') nextIdx = 0;
              else if (e.key === 'End') nextIdx = TIER_OPTIONS.length - 1;
              else {
                const dir = (e.key === 'ArrowDown' || e.key === 'ArrowRight') ? 1 : -1;
                nextIdx = (idx + dir + TIER_OPTIONS.length) % TIER_OPTIONS.length;
              }
              const next = TIER_OPTIONS[nextIdx];
              const container = e.currentTarget;
              setHighlighted(next.k);
              requestAnimationFrame(() => {
                (container?.querySelector(`[data-tier="${next.k}"]`) as HTMLElement | null)?.focus();
              });
            } else if ((e.key === 'Enter' || e.key === ' ') && highlighted !== null) {
              e.preventDefault();
              handleSetTier(highlighted);
              setHighlighted(null);
            }
          }}
          onBlur={(e) => {
            if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
              setHighlighted(null);
            }
          }}
        >
          {TIER_OPTIONS.map((opt) => {
            const committed = effectiveTier === opt.k;
            const isFocused = highlighted === opt.k;
            return (
              <button
                key={opt.k}
                data-tier={opt.k}
                role="radio"
                aria-checked={committed}
                tabIndex={highlighted !== null ? (isFocused ? 0 : -1) : (committed ? 0 : -1)}
                onClick={() => { handleSetTier(opt.k); setHighlighted(null); }}
                style={{
                  display: 'flex',
                  gap: 13,
                  alignItems: 'flex-start',
                  textAlign: 'left',
                  padding: 14,
                  borderRadius: 12,
                  border: committed
                    ? '1px solid var(--hachi-brand)'
                    : '0.5px solid var(--hachi-line)',
                  background: committed
                    ? 'var(--hachi-brand-tint)'
                    : isFocused
                    ? 'var(--hachi-cream)'
                    : 'var(--hachi-canvas)',
                  cursor: 'pointer',
                  font: 'inherit',
                }}
              >
                <span
                  aria-hidden="true"
                  style={{
                    flexShrink: 0,
                    width: 18,
                    height: 18,
                    borderRadius: '50%',
                    border: `2px solid ${committed ? 'var(--hachi-brand)' : 'var(--hachi-line)'}`,
                    background: committed ? 'var(--hachi-brand)' : 'transparent',
                    marginTop: 2,
                  }}
                />
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 500, fontSize: 14 }}>{opt.name}</div>
                  <div style={{ fontSize: 13, color: 'var(--hachi-muted)', marginTop: 2 }}>
                    {opt.desc}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
        {(effectiveTier === 'enhanced' || effectiveTier === 'power') && (
          <button
            type="button"
            onClick={() => void navigate({ to: '/integrations' })}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              fontSize: 13,
              color: 'var(--hachi-trust)',
              background: 'var(--hachi-trust-tint)',
              padding: '10px 12px',
              borderRadius: 10,
              marginTop: 12,
              border: 'none',
              cursor: 'pointer',
              width: '100%',
              textAlign: 'left',
            }}
          >
            <Icon name="plug" size={15} />
            Connect Google, Slack and more in Integrations →
          </button>
        )}
      </div>

      {/* Appearance & account */}
      <div style={cardStyle}>
        <h3 style={{ ...sectionHeadingStyle, marginBottom: 16 }}>Appearance &amp; account</h3>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 14,
            padding: '11px 0',
            borderBottom: '0.5px solid var(--hachi-line)',
          }}
        >
          <span style={{ color: 'var(--hachi-muted)', display: 'inline-flex' }}>
            <Icon name={themeIcon} size={17} />
          </span>
          <div style={{ flex: 1, fontSize: 14 }}>Dark mode</div>
          <Switch checked={isDark} onChange={() => toggleTheme()} ariaLabel="Dark mode" />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '11px 0' }}>
          <span style={{ color: 'var(--hachi-muted)', display: 'inline-flex' }}>
            <Icon name="sparkles" size={17} />
          </span>
          <div style={{ flex: 1, fontSize: 14 }}>Re-run the setup wizard</div>
          <SetupButton onClick={openSetup}>Run setup</SetupButton>
        </div>
      </div>
    </div>
  );
}
