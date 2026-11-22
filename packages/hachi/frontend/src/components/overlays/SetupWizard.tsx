// ============================================================
// SetupWizard — 5-step onboarding modal + edit-provider mode
// Prototype markup: Hachi Web App.dc.html lines 1337–1426
// Logic: lines 2139–2158 (setup actions), 2434–2449 (setup renderVals)
// ============================================================

import React, { CSSProperties, useCallback, useEffect, useRef, useState } from 'react';
import { useStore } from '../../lib/store/store';
import { HachiMark } from '../brand/HachiMark';
import { Icon } from '../icons/Icon';
import { ConnectorLogo } from '../icons/ConnectorLogo';
import { Switch } from '../ui/Switch';
import { loadSetup, applySetup, validateKey, type KeyValidationResult } from '../../lib/data/domains/setup';
import { useFocusTrap } from '../../lib/hooks/useFocusTrap';

/**
 * Start the OAuth flow for an integration.
 * Delegates to startIntegrationOAuth from domains/integrations when available
 * (another agent is adding that function). Falls back gracefully if not yet shipped.
 */
async function startIntegrationOAuth(id: string): Promise<void> {
  try {
    // Dynamic import so this compiles even before the other agent adds the export.
    const mod = await import('../../lib/data/domains/integrations') as Record<string, unknown>;
    const fn = mod['startIntegrationOAuth'];
    if (typeof fn === 'function') {
      await (fn as (id: string) => Promise<void>)(id);
    } else {
      // Function not yet implemented — open integrations tab as fallback.
      throw new Error(`startIntegrationOAuth not yet exported from integrations.ts (id=${id})`);
    }
  } catch (err: unknown) {
    throw err;
  }
}

const KEY_STEP = 1;

const SAFETY_LEVELS = [
  {
    k: 'guarded' as const,
    name: 'Guarded',
    desc: 'Hachi asks before almost everything. Best while you\'re getting to know it.',
  },
  {
    k: 'standard' as const,
    name: 'Standard',
    desc: 'Hachi handles routine, safe work on its own and asks before anything that leaves your machine or deletes things.',
  },
  {
    k: 'open' as const,
    name: 'Open',
    desc: 'Hachi acts without asking. For trusted, sandboxed work only.',
  },
];

export function SetupWizard() {
  const setup            = useStore((s) => s.setup);
  const integrations     = useStore((s) => s.integrations);
  const closeSetup       = useStore((s) => s.closeSetup);
  const setupBack        = useStore((s) => s.setupBack);
  const setupNext        = useStore((s) => s.setupNext);
  const setSetupKey      = useStore((s) => s.setSetupKey);
  const toggleSetupRoutine  = useStore((s) => s.toggleSetupRoutine);
  const setSetupField    = useStore((s) => s.setSetupField);

  // Transient validation state — local only, not in store.
  const [keyValidation, setKeyValidation] = useState<KeyValidationResult>({ status: 'idle' });
  // Track which key value was last validated so we can reset to idle on change.
  const lastValidatedKey = useRef<string>('');

  // Focus trap: keeps focus inside the modal while open; restores on close.
  const trapRef = useFocusTrap<HTMLDivElement>(setup.open);

  // Load real onboarding state only when the wizard is open.
  // SetupWizard is always mounted in GlobalOverlays, so an unconditional effect
  // would fire even while closed. Gating on setup.open avoids redundant fetches;
  // the dedupe("setup") wrapper in loadSetup handles concurrent callers.
  useEffect(() => {
    if (!setup.open) return;
    void loadSetup();
  }, [setup.open]);

  // Close on Escape.
  useEffect(() => {
    if (!setup.open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeSetup();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [setup.open, closeSetup]);

  // When the key changes, reset validation state to idle (unless it matches what was validated).
  const handleKeyChange = useCallback((v: string) => {
    setSetupKey(v);
    if (v !== lastValidatedKey.current) {
      setKeyValidation({ status: 'idle' });
    }
  }, [setSetupKey]);

  // Called on input blur OR on "Validate" click: run format check + real round-trip.
  const handleValidateKey = useCallback(async () => {
    const key = setup.key.trim();
    if (!key) return; // nothing to validate yet
    setKeyValidation({ status: 'checking' });
    const result = await validateKey(key);
    lastValidatedKey.current = setup.key;
    setKeyValidation(result);
  }, [setup.key]);

  if (!setup.open) return null;

  const isEditProvider = setup.mode === 'edit-provider';
  const step = setup.step;

  // Key border colour derived from validation state.
  const keyBorder = (() => {
    switch (keyValidation.status) {
      case 'valid':        return 'var(--hachi-success)';
      case 'format-error':
      case 'invalid':      return 'var(--hachi-danger)';
      default:             return 'var(--hachi-line)';
    }
  })();

  // In onboard mode: show 5 progress dots. In edit-provider: just one dot.
  const setupDots = isEditProvider
    ? ['var(--hachi-brand)']
    : [0, 1, 2, 3, 4].map((i) =>
        i === step
          ? 'var(--hachi-brand)'
          : i < step
          ? 'var(--hachi-brand-tint)'
          : 'var(--hachi-line)'
      );

  // A key is "ok" when the user already has one configured server-side, or
  // when they typed a new key and it passed validation this session.
  const keyOk = setup.keyAlreadySet || keyValidation.status === 'valid';

  const nextLabel = isEditProvider ? 'Save' : step >= 4 ? 'Finish' : step === 0 ? 'Get started' : 'Next';
  // Skip is hidden on the key step unless the user already has a key — they can
  // skip past without re-entering it. On all other steps Skip advances normally.
  const showSkip = !isEditProvider && step < 4 && !(step === KEY_STEP && !setup.keyAlreadySet);
  // "Set up later" is a soft-exit only on the key step in onboard mode.
  const showSetUpLater = !isEditProvider && step === KEY_STEP;
  const canBack   = !isEditProvider && step > 0;

  // On the final step, also fire the live gateway apply call (additive to the
  // existing optimistic store flow in setupNext which closes the wizard).
  const handleNext = () => {
    if (!isEditProvider && step >= 4) {
      // Fire-and-forget: errors are handled inside applySetup (setReconnecting).
      void applySetup({
        key:     setup.key,
        safety:  setup.safety,
        routine: setup.routine,
        google:  setup.google,
        channel: setup.channel,
      });
    }
    setupNext();
  };

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
    width: 540,
    maxWidth: '96vw',
    maxHeight: 'min(88vh, 720px)',
    display: 'flex',
    flexDirection: 'column',
    background: 'var(--hachi-surface)',
    border: '0.5px solid var(--hachi-line)',
    borderRadius: 18,
    overflow: 'hidden',
    boxShadow: '0 24px 60px rgba(28,26,32,.24)',
  };

  const headerStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '18px 22px',
    borderBottom: '0.5px solid var(--hachi-line)',
  };

  const bodyStyle: CSSProperties = {
    padding: '26px 22px',
    minHeight: 230,
    flex: 1,
    overflowY: 'auto',
  };

  const footerStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '16px 22px',
    borderTop: '0.5px solid var(--hachi-line)',
    flexShrink: 0,
  };

  return (
    <div className="hachi-setup-backdrop" style={backdropStyle} aria-hidden="false">
      <div
        ref={trapRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="setup-wizard-title"
        className="hachi-setup-panel"
        style={panelStyle}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={headerStyle}>
          <HachiMark size={26} />
          <span id="setup-wizard-title" style={{ fontFamily: 'var(--font-display)', fontWeight: 500, fontSize: 18, flex: 1 }}>
            {isEditProvider ? 'Change provider' : 'Set up Hachi'}
          </span>
          <div style={{ display: 'flex', gap: 5 }}>
            {setupDots.map((color, i) => (
              <span
                key={i}
                style={{ width: 7, height: 7, borderRadius: '50%', background: color }}
              />
            ))}
          </div>
          <CloseBtn onClick={closeSetup} />
        </div>

        {/* Body — step-specific content */}
        <div className="hachi-setup-body" style={bodyStyle}>
          {isEditProvider ? (
            /* Edit-provider mode: always show only the provider/key step */
            <Step1
              setupKey={setup.key}
              keyBorder={keyBorder}
              keyValidation={keyValidation}
              onKeyChange={handleKeyChange}
              onValidate={() => { void handleValidateKey(); }}
              keyAlreadySet={setup.keyAlreadySet}
            />
          ) : (
            <>
              {step === 0 && <Step0 />}
              {step === 1 && (
                <Step1
                  setupKey={setup.key}
                  keyBorder={keyBorder}
                  keyValidation={keyValidation}
                  onKeyChange={handleKeyChange}
                  onValidate={() => { void handleValidateKey(); }}
                  keyAlreadySet={setup.keyAlreadySet}
                />
              )}
              {step === 2 && <Step2 currentSafety={setup.safety} onPick={(v) => setSetupField('safety', v)} />}
              {step === 3 && <Step3 integrations={integrations} />}
              {step === 4 && <Step4 routine={setup.routine} onToggle={toggleSetupRoutine} />}
            </>
          )}
        </div>

        {/* Footer */}
        <div style={footerStyle}>
          {canBack && (
            <GhostBtn onClick={setupBack}>Back</GhostBtn>
          )}
          <div style={{ flex: 1 }} />
          {showSetUpLater && (
            <GhostBtn onClick={closeSetup}>Set up later</GhostBtn>
          )}
          {showSkip && (
            <GhostBtn onClick={setupNext}>Skip</GhostBtn>
          )}
          <PrimaryBtn
            onClick={handleNext}
            disabled={!isEditProvider && step === KEY_STEP && !keyOk}
          >
            {nextLabel}
          </PrimaryBtn>
        </div>
      </div>
    </div>
  );
}

// ---- step sub-components ----

function Step0() {
  return (
    <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16, padding: '14px 0' }}>
      <HachiMark size={64} />
      <div>
        <div style={{ fontFamily: 'var(--font-display)', fontWeight: 500, fontSize: 24, marginBottom: 6 }}>
          A good dog, on your machine
        </div>
        <div style={{ fontSize: 15, color: 'var(--hachi-muted)', lineHeight: '23px', maxWidth: 400 }}>
          Hachi does long, autonomous work locally — and asks before anything risky. You hold the leash. This takes about three minutes.
        </div>
      </div>
    </div>
  );
}

function Step1({
  setupKey,
  keyBorder,
  keyValidation,
  onKeyChange,
  onValidate,
  keyAlreadySet,
}: {
  setupKey: string;
  keyBorder: string;
  keyValidation: KeyValidationResult;
  onKeyChange: (v: string) => void;
  onValidate: () => void;
  keyAlreadySet: boolean;
}) {
  const isChecking = keyValidation.status === 'checking';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ fontFamily: 'var(--font-display)', fontWeight: 500, fontSize: 18 }}>Connect an AI provider</div>
      <div style={{ fontSize: 13, color: 'var(--hachi-muted)' }}>Hachi uses your own key. It is stored securely and never shown back to you.</div>
      <div>
        <div style={{ fontSize: 13, color: 'var(--hachi-muted)', marginBottom: 6 }}>Provider</div>
        <div style={{ display: 'flex', alignItems: 'center', height: 44, padding: '0 14px', borderRadius: 10, border: '0.5px solid var(--hachi-line)', background: 'var(--hachi-canvas)', fontSize: 14 }}>
          Anthropic · Claude
        </div>
      </div>
      <div>
        <div style={{ fontSize: 13, color: 'var(--hachi-muted)', marginBottom: 6 }}>API key</div>
        {/* Show a "key already configured" indicator when the env boolean is true and user hasn't started typing */}
        {keyAlreadySet && !setupKey && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            height: 44,
            padding: '0 14px',
            borderRadius: 10,
            border: '0.5px solid var(--hachi-success)',
            background: 'var(--hachi-success-tint)',
            fontSize: 14,
            color: 'var(--hachi-muted)',
            marginBottom: 6,
          }}>
            <Icon name="check" size={15} />
            <span>••••••••  (key configured — stored securely)</span>
          </div>
        )}
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            value={setupKey}
            onChange={(e) => onKeyChange(e.target.value)}
            onBlur={onValidate}
            type="password"
            placeholder={keyAlreadySet ? 'Enter a new key to replace the existing one' : 'Paste your API key here'}
            disabled={isChecking}
            style={{
              flex: 1,
              height: 44,
              padding: '0 14px',
              borderRadius: 10,
              border: `0.5px solid ${keyBorder}`,
              background: 'var(--hachi-canvas)',
              font: 'inherit',
              fontFamily: 'var(--font-mono)',
              fontSize: 14,
              color: 'var(--hachi-ink)',
              outline: 'none',
              boxSizing: 'border-box',
              opacity: isChecking ? 0.6 : 1,
            }}
          />
          {/* Validate button — visible once the user has typed something */}
          {setupKey.trim().length > 0 && (
            <button
              type="button"
              onClick={onValidate}
              disabled={isChecking}
              style={{
                height: 44,
                padding: '0 14px',
                borderRadius: 10,
                border: '0.5px solid var(--hachi-line)',
                background: 'var(--hachi-canvas)',
                color: 'var(--hachi-trust)',
                font: '500 13px var(--font-body)',
                cursor: isChecking ? 'default' : 'pointer',
                flexShrink: 0,
                opacity: isChecking ? 0.5 : 1,
                transition: 'opacity var(--dur-fast) var(--ease)',
              }}
            >
              {isChecking ? 'Checking…' : 'Validate'}
            </button>
          )}
        </div>

        {/* Validation feedback */}
        {keyValidation.status === 'checking' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 13, color: 'var(--hachi-muted)', marginTop: 8 }}>
            <Icon name="clock" size={15} />
            Checking with the gateway…
          </div>
        )}
        {keyValidation.status === 'valid' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 13, color: 'var(--hachi-success-fg)', marginTop: 8 }}>
            <Icon name="check" size={15} />
            Gateway confirmed — key is valid.
          </div>
        )}
        {keyValidation.status === 'format-error' && (
          <div role="alert" style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 13, color: 'var(--hachi-danger)', marginTop: 8 }}>
            <Icon name="alert" size={15} />
            {keyValidation.message}
          </div>
        )}
        {keyValidation.status === 'invalid' && (
          <div role="alert" style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 13, color: 'var(--hachi-danger)', marginTop: 8 }}>
            <Icon name="alert" size={15} />
            {keyValidation.message}
          </div>
        )}
        {keyValidation.status === 'network-error' && (
          <div role="alert" style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 13, color: 'var(--hachi-muted)', marginTop: 8 }}>
            <Icon name="alert" size={15} />
            {keyValidation.message}
          </div>
        )}
      </div>
    </div>
  );
}

function Step2({
  currentSafety,
  onPick,
}: {
  currentSafety: string;
  onPick: (v: string) => void;
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ fontFamily: 'var(--font-display)', fontWeight: 500, fontSize: 18 }}>Choose a safety level</div>
      <div style={{ fontSize: 13, color: 'var(--hachi-muted)' }}>You can change this any time. Hachi always shows what it's doing.</div>
      <div
        role="radiogroup"
        aria-label="Safety level"
        style={{ display: 'flex', flexDirection: 'column', gap: 9 }}
        onKeyDown={(e) => {
          if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
          e.preventDefault();
          const idx = SAFETY_LEVELS.findIndex((lvl) => lvl.k === currentSafety);
          const dir = e.key === 'ArrowDown' ? 1 : -1;
          const next = SAFETY_LEVELS[(idx + dir + SAFETY_LEVELS.length) % SAFETY_LEVELS.length];
          onPick(next.k);
          requestAnimationFrame(() => {
            (e.currentTarget.querySelector(`[data-safety-level="${next.k}"]`) as HTMLElement | null)?.focus();
          });
        }}
      >
        {SAFETY_LEVELS.map((lvl) => {
          const sel = currentSafety === lvl.k;
          return (
            <SafetyOption
              key={lvl.k}
              dataKey={lvl.k}
              name={lvl.name}
              desc={lvl.desc}
              selected={sel}
              onClick={() => onPick(lvl.k)}
            />
          );
        })}
      </div>
    </div>
  );
}

function SafetyOption({ dataKey, name, desc, selected, onClick }: {
  dataKey: string; name: string; desc: string; selected: boolean; onClick: () => void;
}) {
  const bg     = selected ? 'var(--hachi-brand-tint)' : 'var(--hachi-canvas)';
  const dotBorder = selected ? 'var(--hachi-brand)' : 'var(--hachi-line)';
  const dotBg     = selected ? 'var(--hachi-brand)' : 'transparent';

  return (
    <button
      type="button"
      className="hachi-safety-option"
      data-safety-level={dataKey}
      role="radio"
      aria-checked={selected}
      tabIndex={selected ? 0 : -1}
      onClick={onClick}
      style={{
        display: 'flex',
        gap: 12,
        alignItems: 'flex-start',
        textAlign: 'left',
        padding: 14,
        borderRadius: 12,
        border: selected ? '1px solid var(--hachi-brand)' : undefined,
        background: bg,
        cursor: 'pointer',
        font: 'inherit',
        transition: 'border-color var(--dur-fast) var(--ease)',
      }}
    >
      <span aria-hidden="true" style={{
        flexShrink: 0,
        width: 18,
        height: 18,
        borderRadius: '50%',
        border: `2px solid ${dotBorder}`,
        background: dotBg,
        marginTop: 1,
        transition: 'border-color var(--dur-fast) var(--ease), background var(--dur-fast) var(--ease)',
      }} />
      <div>
        <div style={{ fontWeight: 500, fontSize: 14 }}>{name}</div>
        <div style={{ fontSize: 13, color: 'var(--hachi-muted)', marginTop: 2 }}>{desc}</div>
      </div>
    </button>
  );
}

// ---- Step 3: Connect accounts (real OAuth via integrations list) ----

function Step3({ integrations }: { integrations: { id: string; icon: string; name: string; can: string; status: string }[] }) {
  const showToast = useStore((s) => s.showToast);

  // Track per-integration in-flight OAuth state locally.
  const [pending, setPending] = useState<Set<string>>(new Set());

  // Filter to integrations that make sense to connect during onboarding.
  // Show all configured/available integrations from the backend, not a hardcoded list.
  // If integrations list is empty (not yet loaded or backend returned none), show a note.
  const connectables = integrations.filter((i) => i.status !== undefined);

  async function handleConnect(id: string) {
    if (pending.has(id)) return;
    setPending((prev) => new Set([...prev, id]));
    try {
      await startIntegrationOAuth(id);
      // startIntegrationOAuth opens the provider OAuth flow and refreshes status;
      // the integrations store will update when the flow completes.
    } catch {
      showToast(`Could not start OAuth for ${id} — try again in Integrations`, 'blocked');
    } finally {
      setPending((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ fontFamily: 'var(--font-display)', fontWeight: 500, fontSize: 18 }}>Connect your accounts</div>
      <div style={{ fontSize: 13, color: 'var(--hachi-muted)' }}>
        Optional — you can do this any time in Integrations. Hachi only ever uses what you connect.
      </div>

      {connectables.length === 0 ? (
        <div style={{
          padding: 16,
          borderRadius: 12,
          border: '0.5px solid var(--hachi-line)',
          background: 'var(--hachi-canvas)',
          fontSize: 13,
          color: 'var(--hachi-muted)',
        }}>
          No integrations available yet — configure them any time in the Integrations tab.
        </div>
      ) : (
        connectables.map((integration) => {
          const isConnected = integration.status === 'connected';
          const isPending = pending.has(integration.id);
          return (
            <ConnectRow
              key={integration.id}
              id={integration.id}
              title={integration.name}
              sub={integration.can}
              connected={isConnected}
              pending={isPending}
              onConnect={() => void handleConnect(integration.id)}
            />
          );
        })
      )}
    </div>
  );
}

function ConnectRow({
  id, title, sub, connected, pending, onConnect,
}: {
  id: string; title: string; sub: string; connected: boolean; pending: boolean; onConnect: () => void;
}) {
  const bg = connected ? 'var(--hachi-success-tint)' : 'var(--hachi-canvas)';

  return (
    <div
      className="hachi-connect-row"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 13,
        textAlign: 'left',
        padding: 14,
        borderRadius: 12,
        border: connected ? '1px solid var(--hachi-success)' : undefined,
        background: bg,
        transition: 'border-color var(--dur-fast) var(--ease), background var(--dur-fast) var(--ease)',
      }}
    >
      <div style={{
        width: 40,
        height: 40,
        borderRadius: 10,
        background: 'var(--hachi-cream)',
        display: 'grid',
        placeItems: 'center',
        flexShrink: 0,
      }}>
        <ConnectorLogo id={id} size={22} />
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 500, fontSize: 14 }}>{title}</div>
        <div style={{ fontSize: 13, color: 'var(--hachi-muted)', marginTop: 1 }}>{sub}</div>
      </div>
      {connected ? (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--hachi-success-fg)', fontWeight: 500 }}>
          <Icon name="check" size={15} />
          connected
        </span>
      ) : (
        <button
          type="button"
          onClick={onConnect}
          disabled={pending}
          style={{
            height: 32,
            padding: '0 12px',
            borderRadius: 8,
            border: '0.5px solid var(--hachi-trust)',
            background: 'transparent',
            color: 'var(--hachi-trust)',
            font: '500 12px var(--font-body)',
            cursor: pending ? 'default' : 'pointer',
            opacity: pending ? 0.6 : 1,
            flexShrink: 0,
          }}
        >
          {pending ? 'Opening…' : 'Connect'}
        </button>
      )}
    </div>
  );
}

function Step4({
  routine,
  onToggle,
}: {
  routine: boolean;
  onToggle: () => void;
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ fontFamily: 'var(--font-display)', fontWeight: 500, fontSize: 18 }}>Your first routine</div>
      <div style={{ fontSize: 13, color: 'var(--hachi-muted)' }}>A suggestion to get value on day one. You can edit or skip it.</div>
      <div style={{
        background: 'var(--hachi-cream)',
        border: '0.5px solid var(--hachi-line)',
        borderRadius: 12,
        padding: 16,
        display: 'flex',
        gap: 13,
        alignItems: 'flex-start',
      }}>
        <div style={{
          width: 40,
          height: 40,
          borderRadius: 10,
          background: 'var(--hachi-surface)',
          display: 'grid',
          placeItems: 'center',
          color: 'var(--hachi-trust)',
        }}>
          <Icon name="calendar" size={20} />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 500, fontSize: 15 }}>Morning briefing</div>
          <div style={{ fontSize: 13, color: 'var(--hachi-muted)', marginTop: 3, lineHeight: '20px' }}>
            Every weekday at 8:00, Hachi summarises your inbox and calendar and flags anything urgent. ≈ $0.04 per run.
          </div>
        </div>
      </div>
      <Switch
        checked={routine}
        onChange={onToggle}
        label="Set up this routine and keep it on watch"
      />
    </div>
  );
}

// ---- shared small components ----

function CloseBtn({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      className="hachi-ghost-icon-btn-bg"
      onClick={onClick}
      aria-label="Close setup wizard"
      style={{
        border: 'none',
        color: 'var(--hachi-muted)',
        cursor: 'pointer',
        display: 'inline-flex',
        padding: 4,
        borderRadius: 6,
        transition: 'background var(--dur-fast) var(--ease)',
      }}
    >
      <Icon name="x" size={18} />
    </button>
  );
}

function GhostBtn({ onClick, children }: { onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      className="hachi-ghost-icon-btn-bg"
      onClick={onClick}
      style={{
        height: 40,
        padding: '0 16px',
        borderRadius: 10,
        border: 'none',
        color: 'var(--hachi-muted)',
        font: '500 14px var(--font-body)',
        cursor: 'pointer',
        transition: 'background var(--dur-fast) var(--ease)',
      }}
    >
      {children}
    </button>
  );
}

function PrimaryBtn({ onClick, children, disabled }: { onClick: () => void; children: React.ReactNode; disabled?: boolean }) {
  return (
    <button
      type="button"
      className="hachi-mcp-submit-btn"
      onClick={onClick}
      disabled={disabled}
      style={{
        height: 40,
        padding: '0 22px',
        borderRadius: 10,
        border: '0.5px solid transparent',
        background: disabled ? 'var(--hachi-line)' : 'var(--hachi-brand-hover)',
        color: disabled ? 'var(--hachi-muted)' : 'var(--hachi-canvas)',
        font: '500 14px var(--font-body)',
        cursor: disabled ? 'not-allowed' : 'pointer',
        transition: 'background var(--dur-fast) var(--ease)',
      }}
    >
      {children}
    </button>
  );
}
