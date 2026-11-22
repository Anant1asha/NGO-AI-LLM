// SpendSection — per-task and daily spend caps + today's spend bar + breakdown.
// Caps persist live on commit (Enter / blur) via PUT /config/limits.
// FIX 4: breakdown section fetches /spend and /spend/daily for per-model,
// per-modality, per-session, and cumulative data (C-SPEND).

import { useState, useEffect, useRef, useId } from 'react';
import { useStore } from '../../../lib/store/store';
import { Icon } from '../../icons/Icon';
import { setLimitsLive } from '../../../lib/data/domains/config';
import { cardStyle, sectionHeadingStyle, PanelHeader } from '../shared';
import { apiGet } from '../../../lib/data/client';

// ---- C-SPEND contract shapes (backend may not expose all fields yet) ----

interface CSpendModel {
  model: string;
  cost_usd: number;
  input_tokens?: number;
  output_tokens?: number;
}

interface CSpendModalities {
  text?: number;
  voice?: number;
  [key: string]: number | undefined;
}

interface CSpendSession {
  session_id?: string;
  cost_usd?: number;
  turns?: number;
}

interface FeatureCostEntry {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
  call_count: number;
}

interface CSpendResponse {
  // per-model breakdown (C-SPEND)
  models?: CSpendModel[];
  // per-feature breakdown (R10)
  by_feature?: Record<string, FeatureCostEntry>;
  // per-modality breakdown (C-SPEND)
  modalities?: CSpendModalities;
  // per-session
  session?: CSpendSession;
  // cumulative all-time
  cumulative_usd?: number;
  // legacy fields still present (don't break existing loading)
  turns?: unknown[];
  tidies?: unknown[];
}

// ---- SpendCapInput ----

interface SpendCapInputProps {
  label: string;
  value: number;
  onCommit: (v: number) => void;
}

function SpendCapInput({ label, value, onCommit }: SpendCapInputProps) {
  const [editing, setEditing] = useState(false);
  const [localVal, setLocalVal] = useState(String(value.toFixed(2)));
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const inputId = useId();
  const errorId = `${inputId}-error`;

  useEffect(() => {
    if (editing) {
      setLocalVal(String(value.toFixed(2)));
      setError(null);
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editing, value]);

  function commit() {
    const parsed = parseFloat(localVal);
    if (isNaN(parsed) || parsed <= 0) {
      setError('Enter a number greater than $0');
      return;
    }
    setError(null);
    if (parsed !== value) {
      onCommit(parsed);
    }
    setEditing(false);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      e.preventDefault();
      commit();
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      setEditing(false);
    }
  }

  return (
    <div style={{ flex: 1 }}>
      <label htmlFor={inputId} style={{ display: 'block', fontSize: 12, color: 'var(--hachi-muted)', marginBottom: 6 }}>
        {label}
      </label>
      {editing ? (
        <>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 15, color: 'var(--hachi-muted)' }}>
              $
            </span>
            <input
              id={inputId}
              ref={inputRef}
              type="number"
              min="0.01"
              step="0.01"
              value={localVal}
              onChange={(e) => setLocalVal(e.target.value)}
              onKeyDown={handleKeyDown}
              onBlur={commit}
              required
              aria-invalid={error != null}
              aria-describedby={error ? errorId : undefined}
              style={{
                flex: 1,
                height: 42,
                padding: '0 14px',
                borderRadius: 10,
                border: error ? '0.5px solid var(--hachi-danger)' : '0.5px solid var(--hachi-trust)',
                background: 'var(--hachi-canvas)',
                fontFamily: 'var(--font-mono)',
                fontSize: 15,
                color: 'var(--hachi-ink)',
                outline: 'none',
              }}
            />
          </div>
          {error && (
            <div id={errorId} role="alert" style={{ fontSize: 11.5, color: 'var(--hachi-danger)', marginTop: 4 }}>
              {error}
            </div>
          )}
        </>
      ) : (
        <button
          type="button"
          className="hachi-spend-cap-display-btn"
          id={inputId}
          onClick={() => setEditing(true)}
          title="Click to edit"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            width: '100%',
            height: 42,
            padding: '0 14px',
            borderRadius: 10,
            border: '0.5px solid var(--hachi-line)',
            background: 'var(--hachi-canvas)',
            fontFamily: 'var(--font-mono)',
            fontSize: 15,
            color: 'var(--hachi-ink)',
            cursor: 'pointer',
            textAlign: 'left',
          }}
        >
          ${value.toFixed(2)}
          <span style={{ color: 'var(--hachi-muted)', fontSize: 12 }}>
            <Icon name="pencil" size={13} />
          </span>
        </button>
      )}
    </div>
  );
}

// ---- SpendBreakdown ----

interface SpendBreakdownProps {
  data: CSpendResponse | null;
  loading: boolean;
}

function usd(v: number | undefined): string {
  if (v == null) return '—';
  return `$${v.toFixed(4)}`;
}

function tok(v: number | undefined): string {
  if (v == null) return '—';
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
  return String(v);
}

const tableHeadStyle: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 500,
  color: 'var(--hachi-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
  padding: '6px 0',
  borderBottom: '0.5px solid var(--hachi-line)',
};

const tableCellStyle: React.CSSProperties = {
  fontSize: 12.5,
  padding: '7px 0',
  borderBottom: '0.5px solid var(--hachi-line)',
  fontFamily: 'var(--font-mono)',
  color: 'var(--hachi-ink)',
};

const tableLastCellStyle: React.CSSProperties = {
  ...tableCellStyle,
  borderBottom: 'none',
};

function SpendBreakdown({ data, loading }: SpendBreakdownProps) {
  if (loading) {
    return (
      <div style={{ fontSize: 12, color: 'var(--hachi-muted)', padding: '8px 0' }}>
        Loading breakdown…
      </div>
    );
  }

  const hasModels = Array.isArray(data?.models) && data!.models!.length > 0;
  const modalities = data?.modalities ?? null;
  const hasModalities = modalities != null && Object.keys(modalities).length > 0;
  const hasCumulative = typeof data?.cumulative_usd === 'number';
  const hasSession = data?.session != null;

  if (!hasModels && !hasModalities && !hasCumulative && !hasSession) {
    return (
      <div style={{ fontSize: 12, color: 'var(--hachi-muted)', fontStyle: 'italic' }}>
        No breakdown data yet — start a conversation to see per-model costs.
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* Per-model */}
      {hasModels && (
        <div>
          <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--hachi-muted)', marginBottom: 6 }}>
            Per model (today)
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={{ ...tableHeadStyle, textAlign: 'left' }}>Model</th>
                <th style={{ ...tableHeadStyle, textAlign: 'right' }}>In</th>
                <th style={{ ...tableHeadStyle, textAlign: 'right' }}>Out</th>
                <th style={{ ...tableHeadStyle, textAlign: 'right' }}>Cost</th>
              </tr>
            </thead>
            <tbody>
              {data!.models!.map((row, idx) => {
                const isLast = idx === data!.models!.length - 1;
                const cell: React.CSSProperties = isLast ? tableLastCellStyle : tableCellStyle;
                return (
                  <tr key={row.model}>
                    <td style={{ ...cell, fontFamily: 'var(--font-body)', fontWeight: 500, maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {row.model}
                    </td>
                    <td style={{ ...cell, textAlign: 'right', color: 'var(--hachi-muted)' }}>{tok(row.input_tokens)}</td>
                    <td style={{ ...cell, textAlign: 'right', color: 'var(--hachi-muted)' }}>{tok(row.output_tokens)}</td>
                    <td style={{ ...cell, textAlign: 'right' }}>{usd(row.cost_usd)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Per-feature (R10) */}
      {data?.by_feature && Object.keys(data.by_feature).length > 0 && (
        <div>
          <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--hachi-muted)', marginBottom: 6 }}>
            By feature (this session)
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={{ ...tableHeadStyle, textAlign: 'left' }}>Feature</th>
                <th style={{ ...tableHeadStyle, textAlign: 'right' }}>Tokens</th>
                <th style={{ ...tableHeadStyle, textAlign: 'right' }}>Calls</th>
                <th style={{ ...tableHeadStyle, textAlign: 'right' }}>Cost</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(data.by_feature).map(([feature, entry], idx, arr) => {
                const isLast = idx === arr.length - 1;
                const cell: React.CSSProperties = isLast ? tableLastCellStyle : tableCellStyle;
                return (
                  <tr key={feature}>
                    <td style={{ ...cell, fontFamily: 'var(--font-body)', fontWeight: 500, textTransform: 'capitalize' }}>
                      {feature}
                    </td>
                    <td style={{ ...cell, textAlign: 'right', color: 'var(--hachi-muted)' }}>{tok(entry.total_tokens)}</td>
                    <td style={{ ...cell, textAlign: 'right', color: 'var(--hachi-muted)' }}>{entry.call_count}</td>
                    <td style={{ ...cell, textAlign: 'right' }}>{usd(entry.estimated_cost_usd)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Per-modality */}
      {hasModalities && (
        <div>
          <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--hachi-muted)', marginBottom: 6 }}>
            By modality (today)
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            {Object.entries(modalities!).map(([key, val]) => (
              val != null && (
                <div
                  key={key}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 2,
                    background: 'var(--hachi-canvas)',
                    border: '0.5px solid var(--hachi-line)',
                    borderRadius: 9,
                    padding: '7px 14px',
                    minWidth: 80,
                  }}
                >
                  <span style={{ fontSize: 11, color: 'var(--hachi-muted)', textTransform: 'capitalize' }}>
                    {key}
                  </span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 500 }}>
                    {usd(val)}
                  </span>
                </div>
              )
            ))}
          </div>
        </div>
      )}

      {/* Session + cumulative */}
      {(hasSession || hasCumulative) && (
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {hasSession && typeof data!.session!.cost_usd === 'number' && (
            <div
              style={{
                display: 'flex', flexDirection: 'column', gap: 2,
                background: 'var(--hachi-canvas)', border: '0.5px solid var(--hachi-line)',
                borderRadius: 9, padding: '7px 14px', minWidth: 110,
              }}
            >
              <span style={{ fontSize: 11, color: 'var(--hachi-muted)' }}>This session</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 500 }}>
                {usd(data!.session!.cost_usd)}
              </span>
              {typeof data!.session!.turns === 'number' && (
                <span style={{ fontSize: 11, color: 'var(--hachi-muted)' }}>
                  {data!.session!.turns} turn{data!.session!.turns !== 1 ? 's' : ''}
                </span>
              )}
            </div>
          )}
          {hasCumulative && (
            <div
              style={{
                display: 'flex', flexDirection: 'column', gap: 2,
                background: 'var(--hachi-canvas)', border: '0.5px solid var(--hachi-line)',
                borderRadius: 9, padding: '7px 14px', minWidth: 110,
              }}
            >
              <span style={{ fontSize: 11, color: 'var(--hachi-muted)' }}>All time</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 500 }}>
                {usd(data!.cumulative_usd)}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---- Main component ----

export default function SpendSection() {
  const spent = useStore((s) => s.spent);
  const budget = useStore((s) => s.budget);
  const taskCap = useStore((s) => s.taskCap);
  const dailyCap = useStore((s) => s.dailyCap);
  const setTaskCap = useStore((s) => s.setTaskCap);
  const setDailyCap = useStore((s) => s.setDailyCap);
  const showToast = useStore((s) => s.showToast);

  // C-SPEND breakdown data fetched locally (not in store).
  const [breakdownData, setBreakdownData] = useState<CSpendResponse | null>(null);
  const [breakdownLoading, setBreakdownLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setBreakdownLoading(true);
    apiGet<CSpendResponse>('/spend')
      .then((data) => {
        if (!cancelled) setBreakdownData(data ?? null);
      })
      .catch(() => {
        if (!cancelled) setBreakdownData(null);
      })
      .finally(() => {
        if (!cancelled) setBreakdownLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  async function persistLimits() {
    const s = useStore.getState();
    try {
      await setLimitsLive(s.taskCap, s.dailyCap);
      showToast('Spend limits saved', 'success');
    } catch {
      showToast('Could not save limits — please try again', 'blocked');
    }
  }

  function handleTaskCap(v: number) {
    setTaskCap(v);
    void persistLimits();
  }
  function handleDailyCap(v: number) {
    setDailyCap(v);
    void persistLimits();
  }

  const spentStr = '$' + Number(spent).toFixed(2);
  const pct = budget > 0 ? Math.min(100, Math.round((spent / budget) * 100)) : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <PanelHeader title="Spend" subtitle="Caps and today's running cost." />

      <div style={cardStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 16 }}>
          <span style={{ color: 'var(--hachi-ink)', display: 'inline-flex' }}>
            <Icon name="dollar" size={18} />
          </span>
          <h3 style={sectionHeadingStyle}>Spend &amp; limits</h3>
        </div>

        <div
          className="hachi-spend-cap-row"
          style={{ display: 'flex', gap: 14, marginBottom: 18 }}
        >
          <SpendCapInput label="Per-task cap" value={taskCap} onCommit={handleTaskCap} />
          <SpendCapInput label="Daily cap" value={dailyCap} onCommit={handleDailyCap} />
        </div>

        <div style={{ fontSize: 12, color: 'var(--hachi-muted)', marginBottom: 8 }}>
          Today, against ${dailyCap.toFixed(2)}
        </div>
        <div
          style={{
            height: 6,
            borderRadius: 999,
            background: 'var(--hachi-line)',
            overflow: 'hidden',
            marginBottom: 8,
          }}
        >
          <div
            style={{
              width: `${pct}%`,
              height: '100%',
              background: 'var(--hachi-brand)',
              borderRadius: 999,
              transition: 'width var(--dur) var(--ease)',
            }}
          />
        </div>
        <div style={{ fontSize: 13, color: 'var(--hachi-muted)' }}>
          What's costing money: model calls {spentStr} · tools $0.00
        </div>
      </div>

      {/* C-SPEND breakdown */}
      <div style={cardStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 14 }}>
          <span style={{ color: 'var(--hachi-ink)', display: 'inline-flex' }}>
            <Icon name="bar-chart" size={17} />
          </span>
          <h3 style={sectionHeadingStyle}>Breakdown</h3>
        </div>
        <SpendBreakdown data={breakdownData} loading={breakdownLoading} />
      </div>
    </div>
  );
}
