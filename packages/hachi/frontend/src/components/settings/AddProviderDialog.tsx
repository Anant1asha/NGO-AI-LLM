// AddProviderDialog — guided add/edit flow for an AI provider.
//
// Add mode: pick a service from a tile grid, then only the fields it needs are
// shown. Known providers get their API base URL pre-filled. A "Test connection"
// button probes the gateway (which calls the provider server-side) to verify the
// key AND fetch the real model list, so the default-model field becomes a picker
// instead of a guess that 404s. Allowed-models and custom headers live under
// "Advanced". Edit mode: kind + name are locked; Test reuses the stored key.
//
// Submit delegates to the parent via onSave(name, spec) — the same contract the
// previous inline form used.

import React, { useState, useRef } from 'react';
import { Icon } from '../icons/Icon';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { probeProvider, type ProviderSpec } from '../../lib/data/domains/providers';
import { inputStyle, labelStyle } from './shared';

interface ProviderKind {
  value: string;
  label: string;
  monogram: string;
  brand: string;
  needsBase: boolean;
  needsKey: boolean;
  headers: boolean;
  modelPlaceholder: string;
  defaultBaseUrl: string;
}

export const PROVIDER_KINDS: ProviderKind[] = [
  { value: 'anthropic', label: 'Anthropic', monogram: 'A', brand: '#D97757', needsBase: false, needsKey: true, headers: false, modelPlaceholder: 'claude-haiku-4-5', defaultBaseUrl: '' },
  { value: 'openai-compatible', label: 'OpenAI / compatible', monogram: 'AI', brand: '#10A37F', needsBase: true, needsKey: true, headers: true, modelPlaceholder: 'gpt-4o-mini', defaultBaseUrl: 'https://api.openai.com/v1' },
  { value: 'openrouter', label: 'OpenRouter', monogram: 'OR', brand: '#6467F2', needsBase: false, needsKey: true, headers: true, modelPlaceholder: 'anthropic/claude-3.5-sonnet', defaultBaseUrl: '' },
  { value: 'groq', label: 'Groq', monogram: 'G', brand: '#F55036', needsBase: false, needsKey: true, headers: true, modelPlaceholder: 'llama-3.1-70b-versatile', defaultBaseUrl: '' },
  { value: 'together', label: 'Together AI', monogram: 'T', brand: '#1C66FF', needsBase: false, needsKey: true, headers: true, modelPlaceholder: 'meta-llama/Llama-3-70b', defaultBaseUrl: '' },
  { value: 'deepseek', label: 'DeepSeek', monogram: 'DS', brand: '#4D6BFE', needsBase: false, needsKey: true, headers: true, modelPlaceholder: 'deepseek-chat', defaultBaseUrl: '' },
  { value: 'ollama', label: 'Ollama (local)', monogram: 'OL', brand: '#475569', needsBase: true, needsKey: false, headers: false, modelPlaceholder: 'llama3.1:8b', defaultBaseUrl: 'http://localhost:11434' },
];

function kindOf(value: string): ProviderKind {
  return PROVIDER_KINDS.find((k) => k.value === value) ?? PROVIDER_KINDS[0];
}

/** Brand-coloured logo tile for a provider kind — shared by the dialog + cards. */
export function providerVisual(kind: string): { monogram: string; bg: string; fg: string } {
  const pk = PROVIDER_KINDS.find((k) => k.value === kind);
  if (pk) return { monogram: pk.monogram, bg: pk.brand, fg: '#fff' };
  return { monogram: kind.slice(0, 2).toUpperCase(), bg: 'var(--hachi-cream)', fg: 'var(--hachi-muted)' };
}

interface HeaderRow {
  id: string;
  key: string;
  value: string;
}

export interface ProviderFormInitial {
  name?: string;
  kind?: string;
  model?: string;
  base_url?: string;
  allowed_models_raw?: string;
  headers?: HeaderRow[];
}

const selectStyle: React.CSSProperties = { ...inputStyle, cursor: 'pointer', font: '14px var(--font-body)' };

export function AddProviderDialog({
  isEditing,
  initial,
  onSave,
  onClose,
}: {
  isEditing: boolean;
  initial?: ProviderFormInitial;
  onSave: (name: string, spec: ProviderSpec) => Promise<void>;
  onClose: () => void;
}) {
  const headerIdRef = useRef(0);

  const [name, setName] = useState(initial?.name ?? 'anthropic');
  const [kind, setKind] = useState(initial?.kind ?? 'anthropic');
  const [model, setModel] = useState(initial?.model ?? '');
  const [baseUrl, setBaseUrl] = useState(initial?.base_url ?? '');
  const [apiKey, setApiKey] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);
  const [allowedRaw, setAllowedRaw] = useState(initial?.allowed_models_raw ?? '');
  const [headers, setHeaders] = useState<HeaderRow[]>(initial?.headers ?? []);
  const [nameAuto, setNameAuto] = useState(!isEditing); // name tracks kind until edited
  const [baseAuto, setBaseAuto] = useState(!isEditing); // base url tracks kind until edited
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  // Probe (test connection + model listing) state
  const [probing, setProbing] = useState(false);
  const [probeResult, setProbeResult] = useState<{ ok: boolean; detail: string } | null>(null);
  const [models, setModels] = useState<string[]>([]);
  const [manualModel, setManualModel] = useState(false);

  const meta = kindOf(kind);

  function selectKind(value: string) {
    const next = kindOf(value);
    setKind(value);
    if (nameAuto) setName(value);
    if (baseAuto) setBaseUrl(next.defaultBaseUrl);
    // Target changed — any earlier probe result no longer applies.
    setModels([]);
    setProbeResult(null);
    setManualModel(false);
    setError('');
  }

  function buildHeaderMap(): Record<string, string> {
    const map: Record<string, string> = {};
    for (const row of headers) if (row.key.trim()) map[row.key.trim()] = row.value;
    return map;
  }

  function addHeader() {
    headerIdRef.current += 1;
    setHeaders((h) => [...h, { id: String(headerIdRef.current), key: '', value: '' }]);
  }
  function setHeader(id: string, field: 'key' | 'value', val: string) {
    setHeaders((h) => h.map((r) => (r.id === id ? { ...r, [field]: val } : r)));
  }
  function removeHeader(id: string) {
    setHeaders((h) => h.filter((r) => r.id !== id));
  }

  async function handleTest() {
    setProbing(true);
    setProbeResult(null);
    const res = await probeProvider({
      name: name.trim() || undefined,
      kind,
      base_url: baseUrl.trim() || null,
      api_key: apiKey || undefined,
      headers: buildHeaderMap(),
    });
    setProbing(false);
    setProbeResult({ ok: res.ok, detail: res.detail });
    if (res.models.length > 0) {
      setModels(res.models);
      setManualModel(false);
    }
  }

  async function handleSubmit() {
    if (!name.trim()) return setError('Give this connection a name.');
    if (meta.needsBase && !baseUrl.trim()) return setError('This provider needs a base URL.');

    const spec: ProviderSpec = {
      kind,
      model: model.trim(),
      base_url: baseUrl.trim() || null,
      allowed_models: allowedRaw.split(',').map((s) => s.trim()).filter(Boolean),
      headers: buildHeaderMap(),
      api_key: apiKey || undefined,
    };

    setSaving(true);
    setError('');
    try {
      await onSave(name.trim(), spec);
      onClose();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Could not save this provider.');
    } finally {
      setSaving(false);
    }
  }

  const showModelSelect = models.length > 0 && !manualModel;

  const linkBtn: React.CSSProperties = {
    alignSelf: 'flex-start',
    background: 'transparent',
    border: 'none',
    color: 'var(--hachi-trust)',
    cursor: 'pointer',
    font: '500 12px var(--font-body)',
    padding: 0,
    marginTop: 6,
  };

  return (
    <Modal onClose={onClose} titleId="add-provider-title" dirtyGuard={!!apiKey} width={500}>
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: '20px 22px 16px',
            borderBottom: '0.5px solid var(--hachi-line)',
            flexShrink: 0,
          }}
        >
          <div>
            <h2
              id="add-provider-title"
              style={{ margin: 0, fontFamily: 'var(--font-display)', fontWeight: 500, fontSize: 18 }}
            >
              {isEditing ? `Edit ${name}` : 'Add a provider'}
            </h2>
            {!isEditing && (
              <div style={{ fontSize: 12, color: 'var(--hachi-muted)', marginTop: 2 }}>
                Pick a service — Hachi only asks for what it needs.
              </div>
            )}
          </div>
          <div style={{ flex: 1 }} />
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            style={{
              border: 'none',
              background: 'transparent',
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

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '18px 22px' }}>
          {!isEditing && (
            <div style={{ marginBottom: 18 }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
                {PROVIDER_KINDS.map((pk) => {
                  const sel = pk.value === kind;
                  return (
                    <button
                      key={pk.value}
                      type="button"
                      onClick={() => selectKind(pk.value)}
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        gap: 6,
                        padding: '10px 4px',
                        borderRadius: 10,
                        border: `1px solid ${sel ? 'var(--hachi-brand)' : 'var(--hachi-line)'}`,
                        background: sel ? 'var(--hachi-brand-tint)' : 'var(--hachi-canvas)',
                        cursor: 'pointer',
                      }}
                    >
                      <span
                        style={{
                          width: 24,
                          height: 24,
                          borderRadius: 6,
                          background: pk.brand,
                          color: '#fff',
                          display: 'grid',
                          placeItems: 'center',
                          fontSize: pk.monogram.length > 1 ? 10 : 12,
                          fontWeight: 600,
                          fontFamily: 'var(--font-mono)',
                        }}
                      >
                        {pk.monogram}
                      </span>
                      <span
                        style={{
                          fontSize: 11,
                          color: sel ? 'var(--hachi-brand)' : 'var(--hachi-ink)',
                          textAlign: 'center',
                          lineHeight: 1.2,
                        }}
                      >
                        {pk.label}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {/* Name */}
            <div>
              <label style={labelStyle} htmlFor="provider-name">Name</label>
              <input
                id="provider-name"
                style={{ ...inputStyle, opacity: isEditing ? 0.6 : 1 }}
                value={name}
                disabled={isEditing}
                onChange={(e) => {
                  setName(e.target.value);
                  setNameAuto(false);
                }}
                placeholder="e.g. my-openrouter"
              />
            </div>

            {/* Base URL */}
            {meta.needsBase && (
              <div>
                <label style={labelStyle} htmlFor="provider-base-url">Base URL</label>
                <input
                  id="provider-base-url"
                  style={inputStyle}
                  value={baseUrl}
                  onChange={(e) => {
                    setBaseUrl(e.target.value);
                    setBaseAuto(false);
                  }}
                  placeholder={meta.defaultBaseUrl}
                />
              </div>
            )}

            {/* API key */}
            {meta.needsKey && (
              <div>
                <label style={labelStyle} htmlFor="provider-api-key">
                  API key{isEditing ? ' (leave blank to keep existing)' : ''}
                </label>
                <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                  <input
                    id="provider-api-key"
                    type={showApiKey ? 'text' : 'password'}
                    style={{ ...inputStyle, paddingRight: 38 }}
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder={isEditing ? '••••••••' : 'sk-…'}
                    autoComplete="new-password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowApiKey((v) => !v)}
                    aria-label={showApiKey ? 'Hide API key' : 'Show API key'}
                    style={{
                      position: 'absolute', right: 8, border: 'none',
                      background: 'transparent', color: 'var(--hachi-muted)',
                      cursor: 'pointer', padding: '2px 4px', borderRadius: 4, lineHeight: 1,
                    }}
                  >
                    <Icon name={showApiKey ? 'eye-off' : 'eye'} size={14} />
                  </button>
                </div>
                <div style={{ fontSize: 11, color: 'var(--hachi-muted)', marginTop: 4 }}>
                  Stored securely, never shown again.
                </div>
              </div>
            )}

            {/* Test connection */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={() => void handleTest()}
                disabled={probing}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  height: 36,
                  padding: '0 14px',
                  borderRadius: 10,
                  border: '1px solid var(--hachi-trust)',
                  background: 'transparent',
                  color: 'var(--hachi-trust)',
                  font: '500 13px var(--font-body)',
                  cursor: probing ? 'default' : 'pointer',
                  opacity: probing ? 0.6 : 1,
                }}
              >
                <Icon name="zap" size={14} />
                {probing ? 'Testing…' : 'Test connection'}
              </button>
              {probeResult && (
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    fontSize: 12.5,
                    color: probeResult.ok ? 'var(--hachi-success)' : 'var(--hachi-danger)',
                  }}
                >
                  <Icon name={probeResult.ok ? 'circle-check' : 'circle-alert'} size={14} />
                  {probeResult.detail}
                </span>
              )}
            </div>

            {/* Model */}
            <div>
              <label style={labelStyle} htmlFor="provider-model">
                Default model <span style={{ opacity: 0.8 }}>(optional)</span>
              </label>
              {showModelSelect ? (
                <>
                  <select
                    id="provider-model"
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    style={selectStyle}
                  >
                    <option value="">Provider default</option>
                    {models.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                  <button type="button" style={linkBtn} onClick={() => setManualModel(true)}>
                    Enter a model id manually
                  </button>
                </>
              ) : (
                <>
                  <input
                    id="provider-model"
                    style={inputStyle}
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    placeholder={meta.modelPlaceholder}
                  />
                  {models.length > 0 ? (
                    <button type="button" style={linkBtn} onClick={() => setManualModel(false)}>
                      Pick from {models.length} available models
                    </button>
                  ) : (
                    <div style={{ fontSize: 11, color: 'var(--hachi-muted)', marginTop: 4 }}>
                      Leave blank to use the provider's default, or Test connection to pick from a list.
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Advanced */}
            <button
              type="button"
              onClick={() => setAdvancedOpen((v) => !v)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                alignSelf: 'flex-start',
                background: 'transparent',
                border: 'none',
                color: 'var(--hachi-trust)',
                cursor: 'pointer',
                font: '500 12px var(--font-body)',
                padding: 0,
              }}
            >
              <Icon name={advancedOpen ? 'chevron-down' : 'chevron-right'} size={14} />
              Advanced
            </button>

            {advancedOpen && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div>
                  <label style={labelStyle} htmlFor="provider-allowed-models">Allowed models (comma-separated, blank = all)</label>
                  <input
                    id="provider-allowed-models"
                    style={inputStyle}
                    value={allowedRaw}
                    onChange={(e) => setAllowedRaw(e.target.value)}
                    placeholder="e.g. claude-haiku-4-5, claude-sonnet-4-6"
                  />
                </div>

                {meta.headers && (
                  <div>
                    <span style={labelStyle}>Custom HTTP headers (optional)</span>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {headers.map((row) => (
                        <div key={row.id} style={{ display: 'flex', gap: 8 }}>
                          <input
                            style={{ ...inputStyle, flex: 1 }}
                            value={row.key}
                            onChange={(e) => setHeader(row.id, 'key', e.target.value)}
                            placeholder="Header name"
                            aria-label="Header name"
                          />
                          <input
                            style={{ ...inputStyle, flex: 2 }}
                            value={row.value}
                            onChange={(e) => setHeader(row.id, 'value', e.target.value)}
                            placeholder="Value"
                            aria-label="Header value"
                          />
                          <button
                            type="button"
                            onClick={() => removeHeader(row.id)}
                            aria-label="Remove header"
                            style={{
                              height: 40,
                              width: 40,
                              borderRadius: 10,
                              border: '0.5px solid var(--hachi-line)',
                              background: 'transparent',
                              color: 'var(--hachi-muted)',
                              cursor: 'pointer',
                              fontSize: 16,
                              flexShrink: 0,
                            }}
                          >
                            ×
                          </button>
                        </div>
                      ))}
                      <button
                        type="button"
                        onClick={addHeader}
                        style={{
                          alignSelf: 'flex-start',
                          height: 32,
                          padding: '0 12px',
                          borderRadius: 8,
                          border: '0.5px solid var(--hachi-line)',
                          background: 'transparent',
                          color: 'var(--hachi-muted)',
                          fontSize: 13,
                          cursor: 'pointer',
                        }}
                      >
                        + Add header
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {error && (
              <div
                style={{
                  padding: '10px 14px',
                  borderRadius: 10,
                  background: 'var(--hachi-danger-tint)',
                  color: 'var(--hachi-danger)',
                  fontSize: 13,
                }}
              >
                {error}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div
          style={{
            display: 'flex',
            gap: 10,
            padding: '14px 22px',
            borderTop: '0.5px solid var(--hachi-line)',
            flexShrink: 0,
          }}
        >
          <Button
            variant="secondary"
            onClick={onClose}
            style={{ flex: 1, height: 42 }}
          >
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={() => void handleSubmit()}
            loading={saving}
            style={{ flex: 1, height: 42 }}
          >
            {isEditing ? 'Save changes' : 'Add provider'}
          </Button>
        </div>
    </Modal>
  );
}
