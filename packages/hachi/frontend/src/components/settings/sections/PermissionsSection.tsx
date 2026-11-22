// PermissionsSection — the leash (safety level), "Ask before…" rules, and the
// operator-only folders / commands / tools reach. Carried over from the previous
// single-scroll Settings page. Safety changes still persist live via the gateway;
// the flicker guard (pendingSafety) is preserved.

import { useState, useEffect, useRef } from 'react';
import { useStore } from '../../../lib/store/store';
import { Icon } from '../../icons/Icon';
import { Switch } from '../../ui/Switch';
import type { SafetyLevel } from '../../../lib/data/types';
import {
  setSafetyLive,
  setAskRuleLive,
  addFolderLive,
  addCommandLive,
  removeFolderLive,
  removeCommandLive,
  toggleOpToolLive,
} from '../../../lib/data/domains/config';
import { cardStyle, sectionHeadingStyle, PanelHeader } from '../shared';

const SAFETY_LEVELS: { k: SafetyLevel; name: string; desc: string }[] = [
  {
    k: 'guarded',
    name: 'Guarded',
    desc: "Hachi asks before almost everything. Best while you're getting to know it.",
  },
  {
    k: 'standard',
    name: 'Standard',
    desc: 'Hachi handles routine, safe work on its own and asks before anything that leaves your machine or deletes things.',
  },
  {
    k: 'open',
    name: 'Open',
    desc: 'Hachi acts without asking. For trusted, sandboxed work only.',
  },
];

interface InlineInputProps {
  placeholder: string;
  onConfirm: (value: string) => void;
  onCancel: () => void;
}

function InlineInput({ placeholder, onConfirm, onCancel }: InlineInputProps) {
  const [value, setValue] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (value.trim()) onConfirm(value.trim());
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      onCancel();
    }
  }

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        style={{
          height: 30,
          padding: '0 10px',
          borderRadius: 8,
          border: '0.5px solid var(--hachi-trust)',
          background: 'var(--hachi-canvas)',
          fontFamily: 'var(--font-mono)',
          fontSize: 12,
          color: 'var(--hachi-ink)',
          outline: 'none',
          width: 160,
        }}
      />
      <button
        type="button"
        onClick={() => {
          if (value.trim()) onConfirm(value.trim());
        }}
        disabled={!value.trim()}
        style={{
          height: 30,
          padding: '0 10px',
          borderRadius: 8,
          border: 'none',
          background: 'var(--hachi-trust)',
          color: '#fff',
          font: '500 12px var(--font-body)',
          cursor: value.trim() ? 'pointer' : 'default',
          opacity: value.trim() ? 1 : 0.5,
        }}
      >
        Add
      </button>
      <button
        type="button"
        onClick={onCancel}
        style={{
          height: 30,
          padding: '0 8px',
          borderRadius: 8,
          border: '0.5px solid var(--hachi-line)',
          background: 'transparent',
          color: 'var(--hachi-muted)',
          font: '500 12px var(--font-body)',
          cursor: 'pointer',
        }}
      >
        Cancel
      </button>
    </span>
  );
}

function Chip({
  value,
  onRemove,
}: {
  value: string;
  onRemove: (v: string) => void;
}) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 7,
        padding: '6px 10px',
        borderRadius: 8,
        background: 'var(--hachi-cream)',
        fontFamily: 'var(--font-mono)',
        fontSize: 12,
        color: 'var(--hachi-ink)',
      }}
    >
      {value}
      <button
        className="hachi-chip-remove-btn"
        onClick={() => onRemove(value)}
        style={{
          border: 'none',
          background: 'transparent',
          color: 'var(--hachi-muted)',
          cursor: 'pointer',
          display: 'inline-flex',
          padding: 0,
          transition: 'color var(--dur-fast) var(--ease)',
        }}
        aria-label={`Remove ${value}`}
      >
        <Icon name="minus" size={13} />
      </button>
    </span>
  );
}

function AddChipButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        padding: '6px 10px',
        borderRadius: 8,
        border: '0.5px dashed var(--hachi-line)',
        background: 'transparent',
        color: 'var(--hachi-trust)',
        font: '500 12px var(--font-body)',
        cursor: 'pointer',
      }}
    >
      <Icon name="plus" size={13} />
      {label}
    </button>
  );
}

export default function PermissionsSection() {
  const configLoaded = useStore((s) => s.configLoaded);
  const safety = useStore((s) => s.safety);
  const askRules = useStore((s) => s.askRules);
  const allowedFolders = useStore((s) => s.allowedFolders);
  const allowedCommands = useStore((s) => s.allowedCommands);
  const opTools = useStore((s) => s.opTools);
  const operator = useStore((s) => s.operator);
  // Use Live functions so removals are persisted to the gateway (T2 / BB-78).

  // Hold the user's chosen value until setSafetyLive's full round-trip
  // (PUT + re-read) settles. Previously cleared as soon as the optimistic
  // store update matched pendingSafety — before the PUT response arrived —
  // which let a concurrent loadConfig() overwrite the UI mid-flight.
  const [pendingSafety, setPendingSafety] = useState<SafetyLevel | null>(null);
  // Keyboard cursor: set on arrow-key navigation, cleared on commit or blur-out.
  const [highlighted, setHighlighted] = useState<SafetyLevel | null>(null);

  const [addingFolder, setAddingFolder] = useState(false);
  const [addingCommand, setAddingCommand] = useState(false);

  function handleSetSafety(v: SafetyLevel) {
    setPendingSafety(v);
    void setSafetyLive(v).finally(() => setPendingSafety(null));
  }
  function handleAddFolder(path: string) {
    setAddingFolder(false);
    void addFolderLive(path);
  }
  function handleAddCommand(cmd: string) {
    setAddingCommand(false);
    void addCommandLive(cmd);
  }

  const effectiveSafety = pendingSafety ?? safety;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <PanelHeader title="Permissions" subtitle="How much Hachi can do before it asks you." />

      {/* The leash */}
      <div style={cardStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 6 }}>
          <span style={{ color: 'var(--hachi-brand)', display: 'inline-flex' }}>
            <Icon name="leash" size={18} />
          </span>
          <h3 style={sectionHeadingStyle}>Permissions &amp; safety — the leash</h3>
        </div>
        <div style={{ fontSize: 13, color: 'var(--hachi-muted)', marginBottom: 16 }}>
          How much Hachi can do before it asks you.
        </div>

        {!configLoaded ? (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              fontSize: 13,
              color: 'var(--hachi-muted)',
              padding: 14,
              borderRadius: 12,
              border: '0.5px solid var(--hachi-line)',
              background: 'var(--hachi-canvas)',
            }}
          >
            <Icon name="clock" size={14} />
            Loading…
          </div>
        ) : (
          <div
            role="radiogroup"
            aria-label="Safety level"
            style={{ display: 'flex', flexDirection: 'column', gap: 9 }}
            onKeyDown={(e) => {
              const ARROW = new Set(['ArrowDown', 'ArrowUp', 'ArrowRight', 'ArrowLeft', 'Home', 'End']);
              if (ARROW.has(e.key)) {
                e.preventDefault();
                const current = highlighted ?? effectiveSafety;
                const idx = SAFETY_LEVELS.findIndex((lvl) => lvl.k === current);
                let nextIdx: number;
                if (e.key === 'Home') nextIdx = 0;
                else if (e.key === 'End') nextIdx = SAFETY_LEVELS.length - 1;
                else {
                  const dir = (e.key === 'ArrowDown' || e.key === 'ArrowRight') ? 1 : -1;
                  nextIdx = (idx + dir + SAFETY_LEVELS.length) % SAFETY_LEVELS.length;
                }
                const next = SAFETY_LEVELS[nextIdx];
                const container = e.currentTarget;
                setHighlighted(next.k);
                requestAnimationFrame(() => {
                  (container?.querySelector(`[data-safety-level="${next.k}"]`) as HTMLElement | null)?.focus();
                });
              } else if ((e.key === 'Enter' || e.key === ' ') && highlighted !== null) {
                e.preventDefault();
                handleSetSafety(highlighted);
                setHighlighted(null);
              }
            }}
            onBlur={(e) => {
              if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
                setHighlighted(null);
              }
            }}
          >
            {SAFETY_LEVELS.map((lvl) => {
              const committed = effectiveSafety === lvl.k;
              const isFocused = highlighted === lvl.k;
              return (
                <button
                  key={lvl.k}
                  data-safety-level={lvl.k}
                  role="radio"
                  aria-checked={committed}
                  tabIndex={highlighted !== null ? (isFocused ? 0 : -1) : (committed ? 0 : -1)}
                  onClick={() => { handleSetSafety(lvl.k); setHighlighted(null); }}
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
                    <div style={{ fontWeight: 500, fontSize: 14 }}>{lvl.name}</div>
                    <div style={{ fontSize: 13, color: 'var(--hachi-muted)', marginTop: 2 }}>
                      {lvl.desc}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )}

        {effectiveSafety === 'open' && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              fontSize: 13,
              color: 'var(--hachi-danger)',
              background: 'var(--hachi-danger-tint)',
              padding: '10px 12px',
              borderRadius: 10,
              marginTop: 12,
            }}
          >
            <Icon name="alert" size={15} />
            Open lets Hachi act without asking. Reserve it for trusted, sandboxed work.
          </div>
        )}

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            fontSize: 12,
            color: 'var(--hachi-muted)',
            marginTop: 14,
          }}
        >
          <Icon name="clock" size={13} />
          Some changes apply next time Hachi starts.
        </div>
      </div>

      {/* Ask before… */}
      <div style={cardStyle}>
        <h3 style={{ ...sectionHeadingStyle, marginBottom: 16 }}>Ask before…</h3>
        {askRules.length === 0 ? (
          <div style={{ fontSize: 13, color: 'var(--hachi-muted)' }}>No rules loaded.</div>
        ) : (
          askRules.map((rule, idx) => (
            <div
              key={rule.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 14,
                padding: '11px 0',
                borderBottom:
                  idx < askRules.length - 1 ? '0.5px solid var(--hachi-line)' : 'none',
              }}
            >
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14 }}>{rule.label}</div>
              </div>
              <Switch
                checked={rule.on}
                onChange={() => void setAskRuleLive(rule.id, !rule.on)}
                ariaLabel={rule.label}
              />
            </div>
          ))
        )}
      </div>

      {/* Operator: folders, commands & tools */}
      {operator && (
        <div style={cardStyle}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 6 }}>
            <span style={{ color: 'var(--hachi-trust)', display: 'inline-flex' }}>
              <Icon name="cpu" size={18} />
            </span>
            <h3 style={sectionHeadingStyle}>Folders, commands &amp; tools</h3>
            <span
              style={{
                fontSize: 11,
                fontWeight: 500,
                color: 'var(--hachi-trust)',
                background: 'var(--hachi-trust-tint)',
                padding: '3px 9px',
                borderRadius: 999,
              }}
            >
              operator
            </span>
          </div>
          <div style={{ fontSize: 13, color: 'var(--hachi-muted)', marginBottom: 16 }}>
            The exact reach you've granted Hachi. Narrow it any time.
          </div>

          <div style={{ fontSize: 12, color: 'var(--hachi-muted)', marginBottom: 8 }}>
            Folders Hachi may use
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 18 }}>
            {allowedFolders.map((folder) => (
              <Chip key={folder} value={folder} onRemove={(f) => void removeFolderLive(f)} />
            ))}
            {addingFolder ? (
              <InlineInput
                placeholder="~/path/to/folder"
                onConfirm={handleAddFolder}
                onCancel={() => setAddingFolder(false)}
              />
            ) : (
              <AddChipButton label="folder" onClick={() => setAddingFolder(true)} />
            )}
          </div>

          <div style={{ fontSize: 12, color: 'var(--hachi-muted)', marginBottom: 8 }}>
            Commands allowed
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 18 }}>
            {allowedCommands.map((cmd) => (
              <Chip key={cmd} value={cmd} onRemove={(c) => void removeCommandLive(c)} />
            ))}
            {addingCommand ? (
              <InlineInput
                placeholder="command name"
                onConfirm={handleAddCommand}
                onCancel={() => setAddingCommand(false)}
              />
            ) : (
              <AddChipButton label="command" onClick={() => setAddingCommand(true)} />
            )}
          </div>

          <div style={{ fontSize: 12, color: 'var(--hachi-muted)', marginBottom: 4 }}>Tools</div>
          {opTools.map((tool, idx) => (
            <div
              key={tool.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 14,
                padding: '11px 0',
                borderBottom:
                  idx < opTools.length - 1 ? '0.5px solid var(--hachi-line)' : 'none',
              }}
            >
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14 }}>{tool.label}</div>
                <div
                  style={{
                    fontSize: 12,
                    color: 'var(--hachi-muted)',
                    fontFamily: 'var(--font-mono)',
                    marginTop: 1,
                  }}
                >
                  {tool.scope}
                </div>
              </div>
              <Switch checked={tool.on} onChange={() => void toggleOpToolLive(tool.id)} ariaLabel={tool.label} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
