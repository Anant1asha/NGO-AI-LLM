// ProviderSettings — the "AI & models" settings panel.
//
// Providers are shown as a card gallery with at-a-glance status; adding one
// opens a guided dialog (AddProviderDialog). Routing is presented task-first:
// a single default model, then plain-language per-capability overrides.
//
// Data: GET/POST/PUT/DELETE /config/providers, GET/PUT /config/routing,
// GET /config/models/all. UI-only redesign — the gateway contract is unchanged.

import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  getProviders,
  removeProvider,
  testConnection,
  getRouting,
  setRouting,
  listAllModels,
  addProvider,
  updateProvider,
  type ProviderEntry,
  type ProviderSpec,
  type CapabilityRow,
} from '../../lib/data/domains/providers';
import { useStore } from '../../lib/store/store';
import { Icon } from '../icons/Icon';
import { cardStyle, sectionHeadingStyle, labelStyle, PanelHeader, Banner } from './shared';
import { AddProviderDialog, providerVisual, type ProviderFormInitial } from './AddProviderDialog';

const NO_KEY_KINDS = new Set(['ollama']);

/**
 * Capability slots that have no router implementation yet (FIX 5 — Issue 11).
 * These are rendered as disabled rows with a "not configurable yet" hint
 * rather than as functional model selects.
 */
const STUB_CAPABILITIES = new Set([
  'embeddings',
  'speech_to_text',
  'text_to_speech',
  'web_search',
  'realtime',
]);

// Best-effort icon + hint for a routing capability, matched on its name. Falls
// back to a neutral chip icon for capabilities we don't recognise.
function capMeta(name: string): { icon: string; desc?: string } {
  const n = name.toLowerCase();
  if (/(reason|think|deep|plan|complex)/.test(n)) return { icon: 'brain', desc: 'hard, multi-step problems' };
  if (/(cod|program|dev|engineer)/.test(n)) return { icon: 'terminal', desc: 'writing & editing code' };
  if (/(vision|image|ocr|screenshot|see)/.test(n)) return { icon: 'image', desc: 'images & screenshots' };
  if (/(fast|quick|chat|cheap|small|light|simple)/.test(n)) return { icon: 'zap', desc: 'short, fast turns' };
  if (/(embed|search|retriev|rank)/.test(n)) return { icon: 'search', desc: 'embeddings & retrieval' };
  if (/(summar|extract|write|draft|format)/.test(n)) return { icon: 'file-text' };
  return { icon: 'cpu' };
}

const selectStyleSm: React.CSSProperties = {
  width: '100%',
  height: 36,
  padding: '0 10px',
  borderRadius: 9,
  border: '0.5px solid var(--hachi-line)',
  background: 'var(--hachi-canvas)',
  fontFamily: 'var(--font-body)',
  fontWeight: 500,
  fontSize: 13,
  color: 'var(--hachi-ink)',
  outline: 'none',
  cursor: 'pointer',
  boxSizing: 'border-box',
};

function ModelSelect({
  value,
  onChange,
  allModels,
  placeholder,
  style,
}: {
  value: string;
  onChange: (v: string) => void;
  allModels: Record<string, string[]>;
  placeholder: string;
  style?: React.CSSProperties;
}) {
  const grouped = Object.entries(allModels).filter(([, m]) => m && m.length > 0);
  const known = new Set(grouped.flatMap(([, m]) => m));
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} style={{ ...selectStyleSm, ...style }}>
      <option value="">{placeholder}</option>
      {value && !known.has(value) && <option value={value}>{value}</option>}
      {grouped.map(([prov, models]) => (
        <optgroup key={prov} label={prov}>
          {Array.from(new Set(models)).sort().map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </optgroup>
      ))}
    </select>
  );
}

// ---- Provider card ----

function ProviderCard({
  provider,
  onEdit,
  onRemove,
}: {
  provider: ProviderEntry;
  onEdit: (p: ProviderEntry) => void;
  onRemove: (name: string) => void;
}) {
  const [status, setStatus] = useState<boolean | null>(null);
  const [detail, setDetail] = useState<string | undefined>(undefined);
  const [testing, setTesting] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const confirmTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (confirmTimerRef.current) clearTimeout(confirmTimerRef.current); }, []);

  const isPrimary = provider.name === '__primary__';
  const noKey = NO_KEY_KINDS.has(provider.kind);
  const displayName = isPrimary ? 'Primary provider' : provider.name;
  const mono = providerVisual(provider.kind);

  async function handleTest() {
    setTesting(true);
    setDetail(undefined);
    const r = await testConnection(provider.name);
    setStatus(r.ok);
    if (!r.ok) setDetail(r.detail);
    setTesting(false);
  }

  // Removing a provider is destructive with no undo — arm on first click,
  // require a second click (or Escape/blur, or a 4s timeout) to confirm.
  function handleRemoveClick() {
    if (!confirmRemove) {
      setConfirmRemove(true);
      confirmTimerRef.current = setTimeout(() => setConfirmRemove(false), 4000);
      return;
    }
    if (confirmTimerRef.current) clearTimeout(confirmTimerRef.current);
    setConfirmRemove(false);
    onRemove(provider.name);
  }
  function handleRemoveBlur() {
    setConfirmRemove(false);
  }
  function handleRemoveKeyDown(e: React.KeyboardEvent<HTMLButtonElement>) {
    if (e.key === 'Escape' && confirmRemove) {
      e.stopPropagation();
      setConfirmRemove(false);
    }
  }

  // Resolve the status line: testing → connected/failed → needs-key → idle.
  let dotColor = 'var(--hachi-line)';
  let statusText = 'Not tested';
  let statusColor = 'var(--hachi-muted)';
  if (testing) {
    dotColor = 'var(--hachi-working)';
    statusText = 'Testing…';
    statusColor = 'var(--hachi-working)';
  } else if (status === true) {
    dotColor = 'var(--hachi-success)';
    statusText = 'Connected';
    statusColor = 'var(--hachi-success)';
  } else if (status === false) {
    dotColor = 'var(--hachi-danger)';
    statusText = 'Connection failed';
    statusColor = 'var(--hachi-danger)';
  } else if (!provider.configured && !noKey) {
    dotColor = 'var(--hachi-working)';
    statusText = 'Needs API key';
    statusColor = 'var(--hachi-working)';
  } else if (noKey) {
    statusText = 'Local';
  }

  const actionBtn: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 5,
    height: 28,
    padding: '0 10px',
    borderRadius: 8,
    border: '0.5px solid var(--hachi-line)',
    background: 'var(--hachi-surface)',
    color: 'var(--hachi-ink)',
    font: '500 12px var(--font-body)',
    cursor: 'pointer',
  };

  return (
    <div
      style={{
        background: 'var(--hachi-surface)',
        border: '0.5px solid var(--hachi-line)',
        borderRadius: 13,
        padding: 14,
        display: 'flex',
        flexDirection: 'column',
        gap: 9,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
        <span
          style={{
            width: 28,
            height: 28,
            borderRadius: 8,
            background: mono.bg,
            color: mono.fg,
            display: 'grid',
            placeItems: 'center',
            fontSize: mono.monogram.length > 1 ? 11 : 13,
            fontWeight: 600,
            fontFamily: 'var(--font-mono)',
            flexShrink: 0,
          }}
        >
          {mono.monogram}
        </span>
        <span
          style={{
            flex: 1,
            minWidth: 0,
            fontSize: 14,
            fontWeight: 500,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {displayName}
        </span>
        {isPrimary ? (
          <span
            style={{
              fontSize: 11,
              fontWeight: 500,
              padding: '2px 8px',
              borderRadius: 999,
              background: 'var(--hachi-brand-tint)',
              color: 'var(--hachi-brand)',
            }}
          >
            Primary
          </span>
        ) : (
          <span
            style={{
              fontSize: 11,
              padding: '2px 7px',
              borderRadius: 6,
              fontFamily: 'var(--font-mono)',
              background: 'var(--hachi-canvas)',
              color: 'var(--hachi-muted)',
              border: '0.5px solid var(--hachi-line)',
            }}
          >
            {provider.kind}
          </span>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span
          style={{ width: 7, height: 7, borderRadius: '50%', background: dotColor, flexShrink: 0 }}
        />
        <span style={{ fontSize: 11.5, color: statusColor }}>{statusText}</span>
      </div>

      <div
        style={{
          fontSize: 12,
          color: 'var(--hachi-muted)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          display: 'flex',
          alignItems: 'center',
          gap: 5,
        }}
        title={provider.base_url ? `${provider.model} · ${provider.base_url}` : provider.model}
      >
        {provider.model && (
          <span style={{ fontFamily: 'var(--font-body)', fontWeight: 500, color: 'var(--hachi-ink)', flexShrink: 0 }}>
            {provider.model}
          </span>
        )}
        {provider.base_url && (
          <>
            {provider.model && <span style={{ opacity: 0.4 }}>·</span>}
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {provider.base_url}
            </span>
          </>
        )}
      </div>

      {status === false && detail && (
        <div
          style={{
            fontSize: 11.5,
            color: 'var(--hachi-danger)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
          title={detail}
        >
          {detail}
        </div>
      )}

      <div style={{ display: 'flex', gap: 6, marginTop: 2 }}>
        <button type="button" style={actionBtn} disabled={testing} onClick={() => void handleTest()}>
          <Icon name="zap" size={12} />
          Test
        </button>
        <button type="button" style={actionBtn} onClick={() => onEdit(provider)}>
          <Icon name="pencil" size={12} />
          Edit
        </button>
        {!isPrimary && (
          <button
            type="button"
            style={{
              ...actionBtn,
              color: 'var(--hachi-danger)',
              marginLeft: 'auto',
              background: confirmRemove ? 'var(--hachi-danger-tint)' : actionBtn.background,
              border: confirmRemove ? '0.5px solid var(--hachi-danger)' : actionBtn.border,
            }}
            aria-label={confirmRemove ? `Confirm remove ${displayName}` : `Remove ${displayName}`}
            title={confirmRemove ? 'Click again to confirm removal' : 'Remove provider'}
            onClick={handleRemoveClick}
            onBlur={handleRemoveBlur}
            onKeyDown={handleRemoveKeyDown}
          >
            <Icon name="trash" size={12} />
            {confirmRemove && <span>Remove?</span>}
          </button>
        )}
      </div>
    </div>
  );
}

// ---- Routing panel ----

function RoutingPanel({
  routing,
  allModels,
  onSave,
}: {
  routing: { default_model: string; capabilities: CapabilityRow[] };
  allModels: Record<string, string[]>;
  onSave: (defaultModel: string, caps: Record<string, string[]>) => Promise<void>;
}) {
  const [defaultModel, setDefaultModel] = useState(routing.default_model);
  const [caps, setCaps] = useState<Record<string, string[]>>(
    Object.fromEntries(routing.capabilities.map((r) => [r.name, r.models]))
  );
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' } | null>(null);

  function setCapModel(name: string, model: string) {
    setCaps((prev) => ({ ...prev, [name]: model ? [model] : [] }));
  }

  async function handleSave() {
    setSaving(true);
    setToast(null);
    try {
      await onSave(defaultModel, caps);
      setToast({ msg: 'Routing saved', type: 'success' });
    } catch (e: unknown) {
      setToast({ msg: e instanceof Error ? e.message : 'Save failed', type: 'error' });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={cardStyle}>
      <h3 style={{ ...sectionHeadingStyle, marginBottom: 14 }}>Routing</h3>

      <div
        style={{
          background: 'var(--hachi-canvas)',
          border: '0.5px solid var(--hachi-line)',
          borderRadius: 12,
          padding: 14,
          marginBottom: 16,
        }}
      >
        <label style={labelStyle}>Default model</label>
        <ModelSelect
          value={defaultModel}
          onChange={setDefaultModel}
          allModels={allModels}
          placeholder="— keep current —"
          style={{ height: 40 }}
        />
        <div style={{ fontSize: 11, color: 'var(--hachi-muted)', marginTop: 7 }}>
          Used for everything unless a task below overrides it.
        </div>
      </div>

      {routing.capabilities.length > 0 && (
        <>
          <div style={{ fontSize: 12, color: 'var(--hachi-muted)', marginBottom: 8 }}>
            Use a different model for…
          </div>
          <div
            style={{
              border: '0.5px solid var(--hachi-line)',
              borderRadius: 12,
              overflow: 'hidden',
            }}
          >
            {routing.capabilities.map((row, idx) => {
              const isStub = STUB_CAPABILITIES.has(row.name);
              const meta = capMeta(row.name);
              const isLast = idx === routing.capabilities.length - 1;
              return (
                <div
                  key={row.name}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 11,
                    padding: '11px 13px',
                    borderBottom: isLast ? undefined : '0.5px solid var(--hachi-line)',
                    opacity: isStub ? 0.5 : 1,
                  }}
                  title={isStub ? 'Not configurable yet — routing for this capability is not implemented.' : undefined}
                >
                  <span style={{ color: 'var(--hachi-muted)', display: 'inline-flex', flexShrink: 0 }}>
                    <Icon name={meta.icon} size={17} />
                  </span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500 }}>{row.label}</div>
                    {isStub ? (
                      <div style={{ fontSize: 11, color: 'var(--hachi-muted)' }}>
                        not configurable yet
                      </div>
                    ) : (
                      meta.desc && (
                        <div style={{ fontSize: 11, color: 'var(--hachi-muted)' }}>{meta.desc}</div>
                      )
                    )}
                  </div>
                  <div style={{ width: 170, flexShrink: 0 }}>
                    {isStub ? (
                      <div
                        style={{
                          height: 36,
                          borderRadius: 9,
                          border: '0.5px solid var(--hachi-line)',
                          background: 'var(--hachi-canvas)',
                          display: 'flex',
                          alignItems: 'center',
                          paddingLeft: 10,
                          fontSize: 12,
                          color: 'var(--hachi-muted)',
                          userSelect: 'none',
                        }}
                        aria-disabled="true"
                      >
                        — not available —
                      </div>
                    ) : (
                      <ModelSelect
                        value={caps[row.name]?.[0] ?? ''}
                        onChange={(m) => setCapModel(row.name, m)}
                        allModels={allModels}
                        placeholder="— use default —"
                      />
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {toast && <Banner message={toast.msg} type={toast.type} />}

      <div style={{ marginTop: 14 }}>
        <button
          type="button"
          onClick={() => void handleSave()}
          disabled={saving}
          style={{
            height: 36,
            padding: '0 16px',
            borderRadius: 10,
            border: 'none',
            background: 'var(--hachi-brand-hover)',
            color: 'var(--hachi-canvas)',
            font: '500 13px var(--font-body)',
            cursor: saving ? 'default' : 'pointer',
            opacity: saving ? 0.6 : 1,
          }}
        >
          {saving ? 'Saving…' : 'Save routing'}
        </button>
      </div>
    </div>
  );
}

// ---- Main panel ----

type DialogState = { mode: 'add' } | { mode: 'edit'; provider: ProviderEntry } | null;

export default function ProviderSettings() {
  const showToast = useStore((s) => s.showToast);
  const [providers, setProviders] = useState<ProviderEntry[]>([]);
  const [routing, setRoutingState] = useState<{
    default_model: string;
    capabilities: CapabilityRow[];
  } | null>(null);
  const [allModels, setAllModels] = useState<Record<string, string[]>>({});
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [dialog, setDialog] = useState<DialogState>(null);

  // Counter for stable header-row ids when seeding the edit form.
  const editHeaderIdRef = useRef(0);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError('');
    try {
      const [pResp, rResp, mResp] = await Promise.all([
        getProviders(),
        getRouting(),
        listAllModels(),
      ]);
      setProviders(pResp?.providers ?? []);
      setRoutingState(rResp ? { ...rResp, capabilities: rResp.capabilities ?? [] } : null);
      setAllModels(mResp ?? {});
    } catch (e: unknown) {
      setLoadError(e instanceof Error ? e.message : 'Failed to load provider config');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function refreshModels() {
    try {
      setAllModels(await listAllModels());
    } catch {
      /* non-fatal */
    }
  }

  async function handleSaveProvider(name: string, spec: ProviderSpec) {
    if (dialog?.mode === 'edit') {
      const entry = await updateProvider(name, spec);
      setProviders((prev) => prev.map((p) => (p.name === name ? entry : p)));
      showToast('Provider updated', 'success');
    } else {
      const entry = await addProvider(name, spec);
      setProviders((prev) => [...prev, entry]);
      showToast('Provider added', 'success');
    }
    void refreshModels();
  }

  async function handleRemove(name: string) {
    try {
      await removeProvider(name);
      setProviders((prev) => prev.filter((p) => p.name !== name));
      showToast('Provider removed', 'success');
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : 'Remove failed', 'blocked');
    }
  }

  async function handleSaveRouting(defaultModel: string, caps: Record<string, string[]>) {
    const resp = await setRouting(defaultModel, caps);
    setRoutingState(resp);
  }

  function providerToInitial(p: ProviderEntry): ProviderFormInitial {
    return {
      name: p.name,
      kind: p.kind,
      model: p.model,
      base_url: p.base_url ?? '',
      allowed_models_raw: (p.allowed_models ?? []).join(', '),
      headers: Object.entries(p.headers ?? {}).map(([key, value]) => {
        editHeaderIdRef.current += 1;
        return { id: String(editHeaderIdRef.current), key, value };
      }),
    };
  }

  const addCardStyle: React.CSSProperties = {
    border: '1px dashed var(--hachi-line)',
    borderRadius: 13,
    padding: 14,
    minHeight: 92,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 7,
    color: 'var(--hachi-brand)',
    background: 'transparent',
    cursor: 'pointer',
    font: '500 13px var(--font-body)',
  };

  return (
    <div>
      <PanelHeader
        title="AI & models"
        subtitle="Connect providers and pick which model handles each kind of task."
      />

      {loading ? (
        <div style={{ ...cardStyle, color: 'var(--hachi-muted)', fontSize: 14 }}>Loading…</div>
      ) : loadError ? (
        <div style={cardStyle}>
          <Banner message={loadError} type="error" />
          <div style={{ marginTop: 12 }}>
            <button
              type="button"
              onClick={() => void load()}
              style={{
                height: 34,
                padding: '0 14px',
                borderRadius: 10,
                border: '0.5px solid var(--hachi-line)',
                background: 'var(--hachi-canvas)',
                color: 'var(--hachi-ink)',
                font: '500 13px var(--font-body)',
                cursor: 'pointer',
              }}
            >
              Retry
            </button>
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {/* Providers */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <h3 style={{ ...sectionHeadingStyle, fontSize: 15 }}>Providers</h3>
              <span style={{ fontSize: 12, color: 'var(--hachi-muted)' }}>
                {providers.length} connected
              </span>
            </div>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(218px, 1fr))',
                gap: 10,
              }}
            >
              {providers.map((p) => (
                <ProviderCard
                  key={p.name}
                  provider={p}
                  onEdit={(prov) => setDialog({ mode: 'edit', provider: prov })}
                  onRemove={(name) => void handleRemove(name)}
                />
              ))}
              <button type="button" style={addCardStyle} onClick={() => setDialog({ mode: 'add' })}>
                <Icon name="plus" size={15} />
                Add provider
              </button>
            </div>
          </div>

          {/* Routing */}
          {routing && (
            <RoutingPanel routing={routing} allModels={allModels} onSave={handleSaveRouting} />
          )}
        </div>
      )}

      {dialog && (
        <AddProviderDialog
          isEditing={dialog.mode === 'edit'}
          initial={dialog.mode === 'edit' ? providerToInitial(dialog.provider) : undefined}
          onSave={handleSaveProvider}
          onClose={() => setDialog(null)}
        />
      )}
    </div>
  );
}
