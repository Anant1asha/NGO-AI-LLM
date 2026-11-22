// ============================================================
// KennelConsent — skill-add permission overlay
// Prototype markup: Hachi Web App.dc.html lines 1428–1451
// Logic: lines 2014–2020 (cancelKennel/confirmKennel), 2323–2325 (kennelConsent renderVals)
// Shows exactly what the skill will be allowed to do.
//
// CRIT-003: also handles kennelBrowseOpen=true to show the full kennel list
// in a browse/list mode (no specific item pre-selected).
// ============================================================

import React, { CSSProperties, useEffect, useState } from 'react';
import { useStore } from '../../lib/store/store';
import { Icon } from '../icons/Icon';
import { useFocusTrap } from '../../lib/hooks/useFocusTrap';
import type { KennelItem } from '../../lib/data/types';

// Permission sets per skill (mirrored from prototype renderVals)
const KENNEL_PERMS: Record<string, string[]> = {
  GitHub:  ['Read your repositories and issues', 'Open pull requests for you', 'Comment on issues'],
  Notion:  ['Read your workspace pages', 'Create and edit pages'],
  Slack:   ['Read channels you choose', 'Post messages as you'],
};

// ---- Browse mode: shows kennel list --------------------------------

function KennelBrowsePanel({
  kennel,
  onSelect,
  onClose,
}: {
  kennel: KennelItem[];
  onSelect: (item: KennelItem) => void;
  onClose: () => void;
}) {
  const trapRef = useFocusTrap<HTMLDivElement>(true);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const backdropStyle: CSSProperties = {
    position: 'fixed',
    inset: 0,
    background: 'rgba(28,26,32,.4)',
    display: 'grid',
    placeItems: 'center',
    padding: 24,
    zIndex: 60,
  };

  const panelStyle: CSSProperties = {
    width: 520,
    maxWidth: '96vw',
    maxHeight: '80vh',
    background: 'var(--hachi-surface)',
    border: '0.5px solid var(--hachi-line)',
    borderRadius: 18,
    overflow: 'hidden',
    boxShadow: '0 24px 60px rgba(28,26,32,.24)',
    display: 'flex',
    flexDirection: 'column',
  };

  return (
    <div style={backdropStyle} onClick={onClose}>
      <div
        ref={trapRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="kennel-browse-title"
        style={panelStyle}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '20px 22px 16px',
          borderBottom: '0.5px solid var(--hachi-line)',
          flexShrink: 0,
        }}>
          <span style={{ color: 'var(--hachi-trust)', display: 'inline-flex' }}>
            <Icon name="skills" size={20} />
          </span>
          <h2 id="kennel-browse-title" style={{
            margin: 0,
            fontFamily: 'var(--font-display)',
            fontWeight: 500,
            fontSize: 18,
            flex: 1,
          }}>
            Browse the kennel
          </h2>
          <button
            type="button"
            className="hachi-ghost-icon-btn-bg"
            onClick={onClose}
            aria-label="Close kennel browser"
            style={{
              border: 'none',
              color: 'var(--hachi-muted)',
              cursor: 'pointer',
              display: 'inline-flex',
              padding: 6,
              borderRadius: 8,
            }}
          >
            <Icon name="x" size={16} />
          </button>
        </div>

        {/* Kennel list */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '12px 22px 20px' }}>
          {kennel.length === 0 ? (
            <div style={{
              textAlign: 'center',
              padding: '32px 0',
              color: 'var(--hachi-muted)',
              fontSize: 14,
            }}>
              No skills in the kennel yet.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {kennel.map((k) => (
                <KennelBrowseRow key={k.id} item={k} onSelect={onSelect} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function KennelBrowseRow({
  item,
  onSelect,
}: {
  item: KennelItem;
  onSelect: (item: KennelItem) => void;
}) {
  return (
    <div
      className="hachi-kennel-browse-row"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '12px 14px',
        borderRadius: 12,
        border: '0.5px solid var(--hachi-line)',
        background: 'var(--hachi-canvas)',
        transition: 'background var(--dur-fast) var(--ease)',
      }}
    >
      <span style={{ color: 'var(--hachi-trust)', display: 'inline-flex', flexShrink: 0 }}>
        <Icon name={item.icon} size={18} />
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 500, fontSize: 14 }}>{item.name}</div>
        <div style={{ fontSize: 12, color: 'var(--hachi-muted)', marginTop: 2 }}>{item.desc}</div>
      </div>
      <button
        type="button"
        className="hachi-kennel-browse-add-btn"
        onClick={() => onSelect(item)}
        style={{
          height: 32,
          padding: '0 14px',
          borderRadius: 10,
          border: '0.5px solid var(--hachi-line)',
          color: 'var(--hachi-ink)',
          font: '500 13px var(--font-body)',
          cursor: 'pointer',
          flexShrink: 0,
        }}
      >
        Add
      </button>
    </div>
  );
}

// ---- Main KennelConsent (single item consent) ----------------------

export function KennelConsent() {
  const kc            = useStore((s) => s.kennelConsent);
  const kennelBrowseOpen = useStore((s) => s.kennelBrowseOpen);
  const kennel        = useStore((s) => s.kennel);
  const cancelKennel  = useStore((s) => s.cancelKennel);
  const confirmKennel = useStore((s) => s.confirmKennel);
  const askKennel     = useStore((s) => s.askKennel);

  const isOpen = kc !== null;
  const trapRef = useFocusTrap<HTMLDivElement>(isOpen);

  // Close on Escape. Hooks must run unconditionally on every render of this
  // component instance, so this is declared before the kennelBrowseOpen /
  // !kc early returns below (rules-of-hooks) — the isOpen guard inside makes
  // it a no-op while the browse panel (which has its own Escape handler) is showing.
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') cancelKennel();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isOpen, cancelKennel]);

  // CRIT-003: handle kennelBrowseOpen — show browse panel first, then
  // ask for consent when user picks an item.
  if (kennelBrowseOpen) {
    return (
      <KennelBrowsePanel
        kennel={kennel}
        onSelect={(item) => {
          // Transition from browse mode to per-item consent by calling askKennel
          askKennel(item);
        }}
        onClose={cancelKennel}
      />
    );
  }

  if (!kc) return null;

  const perms = KENNEL_PERMS[kc.name] ?? ['Use this capability within the leash'];

  const backdropStyle: CSSProperties = {
    position: 'fixed',
    inset: 0,
    background: 'rgba(28,26,32,.4)',
    display: 'grid',
    placeItems: 'center',
    padding: 24,
    zIndex: 60,
  };

  const panelStyle: CSSProperties = {
    width: 460,
    maxWidth: '96vw',
    background: 'var(--hachi-surface)',
    border: '0.5px solid var(--hachi-line)',
    borderRadius: 18,
    overflow: 'hidden',
    boxShadow: '0 24px 60px rgba(28,26,32,.24)',
  };

  return (
    <div style={backdropStyle} onClick={cancelKennel}>
      <div
        ref={trapRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="kennel-consent-title"
        style={panelStyle}
        onClick={(e) => e.stopPropagation()}
      >

        {/* Header */}
        <div style={{ padding: '22px 22px 0', display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 44,
            height: 44,
            borderRadius: 11,
            background: 'var(--hachi-cream)',
            display: 'grid',
            placeItems: 'center',
          }}>
            <Icon name={kc.icon} size={22} />
          </div>
          <div>
            <div id="kennel-consent-title" style={{ fontFamily: 'var(--font-display)', fontWeight: 500, fontSize: 18 }}>
              Add {kc.name}
            </div>
            <div style={{ fontSize: 13, color: 'var(--hachi-muted)', marginTop: 1 }}>
              {kc.desc}
            </div>
          </div>
        </div>

        {/* Permission list */}
        <div style={{ padding: '18px 22px' }}>
          <div style={{ fontSize: 13, color: 'var(--hachi-muted)', marginBottom: 10 }}>
            What it will be allowed to do
          </div>
          <div style={{
            background: 'var(--hachi-canvas)',
            border: '0.5px solid var(--hachi-line)',
            borderRadius: 12,
            overflow: 'hidden',
          }}>
            {perms.map((p, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '11px 14px',
                  borderBottom: i < perms.length - 1 ? '0.5px solid var(--hachi-line)' : 'none',
                  fontSize: 14,
                }}
              >
                <span style={{ color: 'var(--hachi-brand)', display: 'inline-flex' }}>
                  <Icon name="leash" size={15} />
                </span>
                {p}
              </div>
            ))}
          </div>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 7,
            fontSize: 12,
            color: 'var(--hachi-muted)',
            marginTop: 12,
          }}>
            <Icon name="shield" size={13} />
            You can change or remove this any time. Hachi still asks before risky actions.
          </div>
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: 10, padding: '0 22px 22px' }}>
          <CancelBtn onClick={cancelKennel} />
          <ConfirmBtn onClick={confirmKennel} />
        </div>
      </div>
    </div>
  );
}

function CancelBtn({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      className="hachi-cancel-btn"
      onClick={onClick}
      style={{
        flex: 1,
        height: 42,
        borderRadius: 10,
        border: '1px solid var(--hachi-trust)',
        color: 'var(--hachi-trust)',
        font: '500 14px var(--font-body)',
        cursor: 'pointer',
        transition: 'background var(--dur-fast) var(--ease)',
      }}
    >
      Cancel
    </button>
  );
}

function ConfirmBtn({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      className="hachi-mcp-submit-btn"
      onClick={onClick}
      style={{
        flex: 1,
        height: 42,
        borderRadius: 10,
        border: '0.5px solid transparent',
        font: '500 14px var(--font-body)',
        cursor: 'pointer',
        transition: 'background var(--dur-fast) var(--ease)',
      }}
    >
      Add and allow
    </button>
  );
}
