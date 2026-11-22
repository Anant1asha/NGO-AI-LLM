// ============================================================
// Work screen — /work
// Prototype markup: Hachi Web App.dc.html lines 448–667
// Logic:           Hachi Web App.dc.html lines 2233–2313
// ============================================================
import React, { useState, useEffect } from 'react'
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useStore } from '../lib/store/store'
import { Icon } from '../components/icons/Icon'
import type { Run, Routine, FinishedTask, FailedTask, RunStep, RoutineRun } from '../lib/data/types'
import {
  loadWork,
  pauseRoutineLive,
  deleteRoutineLive,
  isDurableRun,
  wakeDurableRunLive,
  cancelDurableRunLive,
  runRoutineNowLive,
} from '../lib/data/domains/work'
import { loadSpend } from '../lib/data/domains/spend'
import { loadOperator } from '../lib/data/domains/operator'
import { useFocusTrap } from '../lib/hooks/useFocusTrap'
import { PendingCard } from '../components/ui/PendingCard'
import { statusMeta } from '../lib/ui/status'
import { fmtUSD } from '../lib/ui/format'

function stepMeta(state: string): { icon: string; color: string } {
  const m: Record<string, { icon: string; color: string }> = {
    done: { icon: 'circle-check', color: 'var(--hachi-success)' },
    working: { icon: 'play', color: 'var(--hachi-working)' },
    failed: { icon: 'x', color: 'var(--hachi-danger)' },
    pending: { icon: 'minus', color: 'var(--hachi-muted)' },
  }
  return m[state] ?? m.pending
}

// ---- work item type (union projected from multiple sources) -----
interface WorkItem {
  id: number
  title: string
  owner?: string
  when?: string
  cost: number
  status: string
  icon: string
  kind: 'task' | 'routine' | 'finished' | 'failed'
  // task/run
  steps?: RunStep[]
  progress?: number
  budget?: number
  spent?: number
  meta?: string
  // routine
  schedule?: string
  next?: string
  last?: string
  paused?: boolean
  runHistory?: RoutineRun[]
  // finished
  note?: string
  result?: string
  // failed
  error?: string
  waitingOn?: string
}

// ---- StatusPill inline (matches contract shape, avoids import cycle) ----
function Pill({ status }: { status: string }) {
  const sm = statusMeta(status)
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '6px',
      padding: '5px 11px',
      borderRadius: '999px',
      background: sm.bg,
      color: sm.fg,
      fontSize: '12px',
      fontWeight: 500,
    }}>
      <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: sm.dot }} />
      {sm.text}
    </span>
  )
}

// ---- spend helpers ------------------------------------------
function computeSpend(
  spendTurns: { n: number; inT: number; out: number; cost: number }[],
  spendTidies: { ts: string; before: number; after: number }[],
  spendModels: { name: string; tokens: number; cost: number; color: string }[],
) {
  const barMax = spendTurns.length ? Math.max(...spendTurns.map(t => t.inT + t.out)) : 0
  const spendBars = spendTurns.map(t => ({
    n: t.n,
    inPct: barMax > 0 ? (t.inT / barMax) * 100 : 0,
    outPct: barMax > 0 ? (t.out / barMax) * 100 : 0,
  }))

  const costs = spendTurns.map(t => t.cost)
  const cum: number[] = []
  costs.reduce((a, c) => { const v = a + c; cum.push(v); return v }, 0)
  const maxCum = cum.length ? cum[cum.length - 1] : 0
  const lineDenom = cum.length > 1 ? cum.length - 1 : 1
  const linePts = cum.map((v, i) =>
    ((i / lineDenom) * 100).toFixed(2) + ',' + (100 - (maxCum > 0 ? v / maxCum : 0) * 88 - 6).toFixed(2)
  ).join(' ')
  const areaPts = '0,100 ' + linePts + ' 100,100'

  const tokensSession = spendTurns.reduce((a, t) => a + t.inT + t.out, 0)
  const costSession = costs.reduce((a, c) => a + c, 0)
  const reclaimed = spendTidies.reduce((a, c) => a + (c.before - c.after), 0)
  const effective = spendTidies[spendTidies.length - 1]?.after ?? 0

  const tidiesRows = spendTidies.map(c => ({
    ts: c.ts,
    afterPct: c.before > 0 ? (c.after / c.before) * 100 : 0,
    reclaimedK: ((c.before - c.after) / 1000).toFixed(0) + 'K',
    beforeK: (c.before / 1000).toFixed(0) + 'K',
    afterK: (c.after / 1000).toFixed(0) + 'K',
  }))

  const reclaimedTotalK = (reclaimed / 1000).toFixed(0) + 'K'

  const totalTok = spendModels.reduce((a, mm) => a + mm.tokens, 0)
  const circ = 339.29
  let accFrac = 0
  const donut = spendModels.map(mm => {
    const frac = totalTok > 0 ? mm.tokens / totalTok : 0
    const seg = {
      color: mm.color,
      dash: (frac * circ).toFixed(2) + ' ' + ((1 - frac) * circ).toFixed(2),
      offset: (-accFrac * circ).toFixed(2),
    }
    accFrac += frac
    return seg
  })
  const modelRows = spendModels.map(mm => ({
    name: mm.name,
    color: mm.color,
    costStr: mm.cost ? fmtUSD(mm.cost) : 'free',
    costColor: mm.cost ? 'var(--hachi-ink)' : 'var(--hachi-success)',
  }))
  const spendTotalCost = fmtUSD(spendModels.reduce((a, mm) => a + mm.cost, 0))

  return {
    spendBars,
    linePts,
    areaPts,
    cumLast: fmtUSD(maxCum),
    stats: {
      tokens: tokensSession.toLocaleString(),
      cost: fmtUSD(costSession),
      reclaimed: (reclaimed / 1000).toFixed(0) + 'K',
      effective: (effective / 1000).toFixed(1) + 'K',
    },
    tidiesRows,
    reclaimedTotalK,
    donut,
    modelRows,
    spendTotalCost,
  }
}

// ---- Work detail slide-over ---------------------------------
interface DetailItem extends WorkItem {
  _raw?: WorkItem
}

interface WorkDetailProps {
  item: DetailItem
  packRoster: {
    role: string
    task: string
    status: string
    outcome: string
    tokens: number
  }[]
  onClose: () => void
  onRetry: (id: number) => void
  onCancelRun: (id: number) => void
  onRunNow: (id: number) => void
  onTogglePause: (id: number) => void
  onDelete: (id: number) => void
  onWatchLive: (id: number) => void
  canCancelRun: boolean
}

function WorkDetail({ item, packRoster, onClose, onRetry, onCancelRun, onRunNow, onTogglePause, onDelete, onWatchLive, canCancelRun }: WorkDetailProps) {
  const sm = statusMeta(item.status)
  const isFailed = item.kind === 'failed'
  const isRoutine = item.kind === 'routine'
  const isTask = item.kind === 'task'
  const hasPack = item.kind === 'task' || item.kind === 'finished'

  // Delete confirmation state
  const [confirmDelete, setConfirmDelete] = useState(false)

  // MED-013: focus trap (Tab cycling + return-focus) via shared hook.
  // Escape-to-close is wired separately so it doesn't duplicate the hook.
  const panelRef = useFocusTrap<HTMLDivElement>(true)

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        onClose()
      }
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [onClose])

  const packStatusMeta = (s: string) =>
    s === 'done'
      ? { dot: 'var(--hachi-success)', text: 'done', fg: 'var(--hachi-success-fg)' }
      : s === 'working'
      ? { dot: 'var(--hachi-working)', text: 'on it', fg: 'var(--hachi-working-fg)' }
      : { dot: 'var(--hachi-muted)', text: 'queued', fg: 'var(--hachi-muted)' }

  return (
    <>
      {/* backdrop */}
      <div
        onClick={onClose}
        aria-hidden="true"
        style={{
          position: 'absolute',
          inset: 0,
          background: 'rgba(28,26,32,.18)',
          zIndex: 20,
        }}
      />
      {/* panel */}
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={item.title || undefined}
        className="hachi-scroll"
        style={{
          position: 'absolute',
          top: 0,
          right: 0,
          bottom: 0,
          width: '440px',
          maxWidth: '92%',
          background: 'var(--hachi-surface)',
          borderLeft: '0.5px solid var(--hachi-line)',
          zIndex: 21,
          overflowY: 'auto',
          padding: '24px',
        }}
      >
        {/* header */}
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', marginBottom: '20px' }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
              <h3 style={{ margin: 0, fontFamily: 'var(--font-display)', fontWeight: 500, fontSize: '19px' }}>
                {item.title}
              </h3>
              <Pill status={item.status} />
            </div>
            <div style={{ fontSize: '13px', color: 'var(--hachi-muted)', marginTop: '5px' }}>
              {item.owner} · {item.when} · spent {fmtUSD(item.cost ?? 0)}
            </div>
          </div>
          <button
            type="button"
            className="hachi-ghost-icon-btn-bg"
            onClick={onClose}
            aria-label="Close detail panel"
            style={{
              border: 'none',
              color: 'var(--hachi-muted)',
              cursor: 'pointer',
              display: 'inline-flex',
              padding: '5px',
              borderRadius: '8px',
            }}
          >
            <Icon name="x" size={18} />
          </button>
        </div>

        {/* failed: error block */}
        {isFailed && (
          <div style={{ marginBottom: '18px' }}>
            <div style={{ fontSize: '12px', color: 'var(--hachi-muted)', marginBottom: '7px' }}>What went wrong</div>
            <div style={{
              background: 'var(--hachi-danger-tint)',
              border: '0.5px solid var(--hachi-line)',
              borderRadius: '10px',
              padding: '13px',
              fontFamily: 'var(--font-mono)',
              fontSize: '12px',
              lineHeight: '20px',
              color: 'var(--hachi-danger-fg)',
              whiteSpace: 'pre-wrap',
            }}>
              {item.error}
            </div>
            {item.waitingOn && (
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', fontSize: '13px', color: 'var(--hachi-muted)', marginTop: '10px' }}>
                <Icon name="clock" size={14} />
                <span>waiting on: {item.waitingOn}</span>
              </div>
            )}
          </div>
        )}

        {/* finished: result */}
        {item.result && (
          <div style={{
            background: 'var(--hachi-cream)',
            border: '0.5px solid var(--hachi-line)',
            borderRadius: '10px',
            padding: '13px',
            fontSize: '14px',
            lineHeight: '21px',
            marginBottom: '18px',
          }}>
            {item.result}
          </div>
        )}

        {/* steps — only render header+list when there are steps */}
        {(item.steps ?? []).length > 0 && (
          <>
            <div style={{ fontSize: '12px', color: 'var(--hachi-muted)', marginBottom: '6px' }}>Steps</div>
            <div style={{ display: 'flex', flexDirection: 'column', marginBottom: '20px' }}>
              {(item.steps ?? []).map((stp, i) => {
                const meta = stepMeta(stp.state)
                return (
                  <div
                    key={i}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '11px',
                      padding: '9px 0',
                      borderBottom: '0.5px solid var(--hachi-line)',
                    }}
                  >
                    <span style={{ color: meta.color, display: 'inline-flex' }}>
                      <Icon name={meta.icon} size={16} />
                    </span>
                    <span style={{ fontSize: '14px' }}>{stp.label}</span>
                  </div>
                )
              })}
            </div>
          </>
        )}

        {/* the pack */}
        {hasPack && packRoster.length > 0 && (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: '7px', marginBottom: '8px' }}>
              <span style={{ color: 'var(--hachi-trust)', display: 'inline-flex' }}>
                <Icon name="paw" size={14} />
              </span>
              <span style={{ fontSize: '12px', color: 'var(--hachi-muted)' }}>The pack — who helped</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '20px' }}>
              {packRoster.map((p, i) => {
                const pm = packStatusMeta(p.status)
                return (
                  <div
                    key={i}
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '10px',
                      background: 'var(--hachi-canvas)',
                      border: '0.5px solid var(--hachi-line)',
                      borderRadius: '12px',
                      padding: '11px 13px',
                    }}
                  >
                    <span style={{
                      width: '8px',
                      height: '8px',
                      borderRadius: '50%',
                      background: pm.dot,
                      marginTop: '5px',
                      flexShrink: 0,
                    }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', color: 'var(--hachi-ink)' }}>
                          {p.role}
                        </span>
                        <span style={{ fontSize: '11px', color: 'var(--hachi-muted)', fontVariantNumeric: 'tabular-nums' }}>
                          {p.tokens.toLocaleString()} tok
                        </span>
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--hachi-muted)', marginTop: '2px' }}>{p.task}</div>
                      {p.outcome && p.outcome !== '—' && (
                        <div style={{ fontSize: '12px', color: 'var(--hachi-success-fg)', marginTop: '3px' }}>→ {p.outcome}</div>
                      )}
                    </div>
                    <span style={{ fontSize: '11px', fontWeight: 500, color: pm.fg, flexShrink: 0 }}>{pm.text}</span>
                  </div>
                )
              })}
            </div>
          </>
        )}

        {/* routine: schedule + run history */}
        {isRoutine && (
          <>
            {(item.schedule || item.next) && (
              <>
                <div style={{ fontSize: '12px', color: 'var(--hachi-muted)', marginBottom: '7px' }}>Schedule</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px', marginBottom: item.last ? '8px' : '18px' }}>
                  <Icon name="repeat" size={15} />
                  {item.schedule} · next {item.next}
                </div>
                {item.last && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: 'var(--hachi-muted)', marginBottom: '18px' }}>
                    <Icon name="circle-check" size={13} />
                    last ran {item.last}
                  </div>
                )}
              </>
            )}
            {(item.runHistory ?? []).length > 0 && (
              <>
                <div style={{ fontSize: '12px', color: 'var(--hachi-muted)', marginBottom: '8px' }}>Recent runs · cost per run</div>
                <div style={{
                  background: 'var(--hachi-canvas)',
                  border: '0.5px solid var(--hachi-line)',
                  borderRadius: '10px',
                  overflow: 'hidden',
                  marginBottom: '20px',
                }}>
                  {(item.runHistory ?? []).map((h, i) => {
                    const ico = h.ok ? 'circle-check' : 'minus'
                    const col = h.ok ? 'var(--hachi-success)' : 'var(--hachi-danger)'
                    return (
                      <div
                        key={i}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '10px',
                          padding: '10px 13px',
                          borderBottom: '0.5px solid var(--hachi-line)',
                        }}
                      >
                        <span style={{ color: col, display: 'inline-flex' }}>
                          <Icon name={ico} size={15} label={h.ok ? 'Succeeded' : 'Failed'} />
                        </span>
                        <span style={{ flex: 1, fontSize: '13px' }}>{h.when}</span>
                        <span style={{ fontSize: '13px', color: 'var(--hachi-muted)', fontVariantNumeric: 'tabular-nums' }}>
                          {fmtUSD(h.cost)}
                        </span>
                      </div>
                    )
                  })}
                </div>
              </>
            )}
          </>
        )}

        {/* action buttons */}
        <div style={{ display: 'flex', gap: '9px', flexWrap: 'wrap' }}>
          {isFailed && (
            <>
              <button
                className="hachi-retry-btn"
                onClick={() => onRetry(item.id)}
                style={{
                  flex: 1,
                  height: '40px',
                  borderRadius: '10px',
                  border: '0.5px solid transparent',
                  background: 'var(--hachi-brand)',
                  color: 'var(--hachi-canvas)',
                  font: '500 14px var(--font-body)',
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '7px',
                }}
              >
                <Icon name="refresh" size={15} />
                Retry
              </button>
              {canCancelRun && (
                <button
                  className="hachi-danger-outline-btn"
                  onClick={() => onCancelRun(item.id)}
                  style={{
                    height: '40px',
                    padding: '0 14px',
                    borderRadius: '10px',
                    border: '0.5px solid var(--hachi-line)',
                    background: 'var(--hachi-canvas)',
                    color: 'var(--hachi-danger)',
                    font: '500 14px var(--font-body)',
                    cursor: 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                  }}
                >
                  <Icon name="stop" size={14} />
                  Cancel run
                </button>
              )}
            </>
          )}
          {isRoutine && (
            <>
              <button
                className="hachi-cancel-btn"
                onClick={() => onRunNow(item.id)}
                style={{
                  flex: 1,
                  height: '40px',
                  borderRadius: '10px',
                  border: '1px solid var(--hachi-trust)',
                  background: 'transparent',
                  color: 'var(--hachi-trust)',
                  font: '500 14px var(--font-body)',
                  cursor: 'pointer',
                }}
              >
                Run now
              </button>
              <button
                className="hachi-pause-resume-btn"
                onClick={() => onTogglePause(item.id)}
                style={{
                  flex: 1,
                  height: '40px',
                  borderRadius: '10px',
                  border: '0.5px solid var(--hachi-line)',
                  background: 'var(--hachi-canvas)',
                  color: 'var(--hachi-ink)',
                  font: '500 14px var(--font-body)',
                  cursor: 'pointer',
                }}
              >
                {item.paused ? 'Resume' : 'Pause'}
              </button>
              {/* Delete routine — two-step confirmation */}
              {!confirmDelete ? (
                <button
                  className="hachi-danger-outline-btn"
                  onClick={() => setConfirmDelete(true)}
                  style={{
                    height: '40px',
                    padding: '0 14px',
                    borderRadius: '10px',
                    border: '0.5px solid var(--hachi-line)',
                    background: 'var(--hachi-canvas)',
                    color: 'var(--hachi-danger)',
                    font: '500 14px var(--font-body)',
                    cursor: 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                  }}
                >
                  <Icon name="x" size={14} />
                  Delete
                </button>
              ) : (
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '8px 12px',
                  background: 'var(--hachi-danger-tint)',
                  border: '0.5px solid var(--hachi-danger)',
                  borderRadius: '10px',
                  flexShrink: 0,
                }}>
                  <span style={{ fontSize: '13px', color: 'var(--hachi-danger-fg)', whiteSpace: 'nowrap' }}>
                    Delete this routine?
                  </span>
                  <button
                    onClick={() => onDelete(item.id)}
                    style={{
                      height: '44px',
                      padding: '0 11px',
                      borderRadius: '8px',
                      border: 'none',
                      background: 'var(--hachi-danger)',
                      color: '#fff',
                      font: '500 13px var(--font-body)',
                      cursor: 'pointer',
                    }}
                  >
                    Yes, delete
                  </button>
                  <button
                    onClick={() => setConfirmDelete(false)}
                    style={{
                      height: '44px',
                      padding: '0 11px',
                      borderRadius: '8px',
                      border: '0.5px solid var(--hachi-line)',
                      background: 'var(--hachi-canvas)',
                      color: 'var(--hachi-ink)',
                      font: '500 13px var(--font-body)',
                      cursor: 'pointer',
                    }}
                  >
                    Cancel
                  </button>
                </div>
              )}
            </>
          )}
          {isTask && (
            <button
              className="hachi-retry-btn"
              onClick={() => onWatchLive(item.id)}
              style={{
                flex: 1,
                height: '40px',
                borderRadius: '10px',
                border: '0.5px solid transparent',
                background: 'var(--hachi-brand)',
                color: 'var(--hachi-canvas)',
                font: '500 14px var(--font-body)',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '7px',
              }}
            >
              <Icon name="eye" size={15} />
              Watch live
            </button>
          )}
        </div>
      </div>
    </>
  )
}

// ---- Spend lens ---------------------------------------------
function SpendLens() {
  const spendTurns = useStore(s => s.spendTurns)
  const spendTidies = useStore(s => s.spendTidies)
  const spendModels = useStore(s => s.spendModels)

  if (spendTurns.length === 0 && spendModels.length === 0 && spendTidies.length === 0) {
    return (
      <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '48px 0' }}>
        <div
          style={{
            background: 'var(--hachi-surface)',
            border: '0.5px solid var(--hachi-line)',
            borderRadius: '16px',
            padding: '40px',
            textAlign: 'center',
            color: 'var(--hachi-muted)',
            fontSize: '14px',
            lineHeight: '22px',
          }}
        >
          No spend yet. Run a task and Hachi will show exactly what it cost — token burn,
          tidy-ups, and where the money went — right here.
        </div>
      </div>
    )
  }

  const {
    spendBars,
    linePts,
    areaPts,
    cumLast,
    stats,
    tidiesRows,
    reclaimedTotalK,
    donut,
    modelRows,
    spendTotalCost,
  } = computeSpend(spendTurns, spendTidies, spendModels)

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={{ fontSize: '14px', color: 'var(--hachi-muted)', lineHeight: '22px', maxWidth: '680px' }}>
        Cost is a feature here, never hidden — what Hachi spent, what it reclaimed by tidying its own memory, and where the money went.
      </div>

      {/* stat cards */}
      <div className="hachi-spend-stat-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: '12px' }}>
        <div style={{ background: 'var(--hachi-surface)', border: '0.5px solid var(--hachi-line)', borderRadius: '14px', padding: '15px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '7px', fontSize: '12px', color: 'var(--hachi-muted)', marginBottom: '9px' }}>
            <Icon name="hash" size={14} />
            Tokens this session
          </div>
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 500, fontSize: '23px', fontVariantNumeric: 'tabular-nums' }}>
            {stats.tokens}
          </div>
        </div>
        <div style={{ background: 'var(--hachi-surface)', border: '0.5px solid var(--hachi-line)', borderRadius: '14px', padding: '15px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '7px', fontSize: '12px', color: 'var(--hachi-muted)', marginBottom: '9px' }}>
            <Icon name="dollar" size={14} />
            Cost this session
          </div>
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 500, fontSize: '23px', color: 'var(--hachi-ink)', fontVariantNumeric: 'tabular-nums' }}>
            {stats.cost}
          </div>
        </div>
        <div style={{ background: 'var(--hachi-surface)', border: '0.5px solid var(--hachi-line)', borderRadius: '14px', padding: '15px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '7px', fontSize: '12px', color: 'var(--hachi-muted)', marginBottom: '9px' }}>
            <Icon name="refresh" size={14} />
            Reclaimed by tidying
          </div>
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 500, fontSize: '23px', color: 'var(--hachi-success)', fontVariantNumeric: 'tabular-nums' }}>
            {stats.reclaimed}
          </div>
        </div>
        <div style={{ background: 'var(--hachi-surface)', border: '0.5px solid var(--hachi-line)', borderRadius: '14px', padding: '15px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '7px', fontSize: '12px', color: 'var(--hachi-muted)', marginBottom: '9px' }}>
            <Icon name="cpu" size={14} />
            Effective memory
          </div>
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 500, fontSize: '23px', fontVariantNumeric: 'tabular-nums' }}>
            {stats.effective}<span style={{ fontSize: '13px', color: 'var(--hachi-muted)', fontWeight: 400 }}> of 200K</span>
          </div>
        </div>
      </div>

      {/* burn bars + cumulative line */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ flex: '1 1 400px', minWidth: 0, background: 'var(--hachi-surface)', border: '0.5px solid var(--hachi-line)', borderRadius: '16px', padding: '18px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <span style={{ fontWeight: 500, fontSize: '14px' }}>Token burn by turn</span>
            {spendBars.length > 0 && (
              <span style={{ display: 'flex', gap: '12px', fontSize: '11.5px', color: 'var(--hachi-muted)' }}>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                  <span style={{ width: '9px', height: '9px', borderRadius: '2px', background: 'var(--hachi-trust)' }} />
                  in
                </span>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                  <span style={{ width: '9px', height: '9px', borderRadius: '2px', background: 'var(--hachi-trust)', opacity: 0.4 }} />
                  out
                </span>
              </span>
            )}
          </div>
          {/* HACHI-018: show placeholder when there are no turns yet */}
          {spendBars.length === 0 ? (
            <div style={{
              height: '150px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--hachi-muted)',
              fontSize: '13px',
              fontStyle: 'italic',
            }}>
              No spend yet this session
            </div>
          ) : (
            <>
              <div
                role="img"
                aria-label={`Token burn by turn: ${spendBars.length} turns, ${stats.tokens} tokens total this session (input and output per turn)`}
                style={{ display: 'flex', alignItems: 'flex-end', gap: '10px', height: '150px' }}
              >
                {spendBars.map(b => (
                  <div key={b.n} style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', gap: '2px', height: '100%' }}>
                    <div style={{ height: b.outPct + '%', background: 'var(--hachi-trust)', opacity: 0.4, borderRadius: '3px 3px 0 0', minHeight: '2px' }} />
                    <div style={{ height: b.inPct + '%', background: 'var(--hachi-trust)', borderRadius: '0 0 3px 3px', minHeight: '2px' }} />
                  </div>
                ))}
              </div>
              <div style={{ display: 'flex', gap: '10px', marginTop: '8px' }}>
                {spendBars.map(b => (
                  <span key={b.n} style={{ flex: 1, textAlign: 'center', fontFamily: 'var(--font-mono)', fontSize: '10.5px', color: 'var(--hachi-muted)' }}>
                    #{b.n}
                  </span>
                ))}
              </div>
            </>
          )}
        </div>

        <div style={{ flex: '1 1 320px', minWidth: 0, background: 'var(--hachi-surface)', border: '0.5px solid var(--hachi-line)', borderRadius: '16px', padding: '18px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <span style={{ fontWeight: 500, fontSize: '14px' }}>Cost so far</span>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--hachi-trust)' }}>{cumLast}</span>
          </div>
          <svg
            role="img"
            aria-label={`Cumulative cost so far: rising to ${cumLast} over ${spendBars.length} turn${spendBars.length === 1 ? '' : 's'}`}
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
            style={{ width: '100%', height: '150px', display: 'block' }}
          >
            <polygon points={areaPts} fill="var(--hachi-trust-tint)" />
            <polyline points={linePts} fill="none" stroke="var(--hachi-trust)" strokeWidth="1.6" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
          </svg>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: '10.5px', color: 'var(--hachi-muted)', marginTop: '8px' }}>
            <span>turn {spendBars.length > 0 ? spendBars[0].n : 1}</span>
            <span>turn {spendBars.length > 0 ? spendBars[spendBars.length - 1].n : 1}</span>
          </div>
        </div>
      </div>

      {/* tidy-ups + donut */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ flex: '2 1 400px', minWidth: 0, background: 'var(--hachi-surface)', border: '0.5px solid var(--hachi-line)', borderRadius: '16px', padding: '18px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '9px', marginBottom: '16px' }}>
            <span style={{ color: 'var(--hachi-muted)', display: 'inline-flex' }}><Icon name="refresh" size={16} /></span>
            <span style={{ fontWeight: 500, fontSize: '14px' }}>Tidy-ups — what Hachi reclaimed</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {tidiesRows.map((c, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--hachi-muted)', width: '42px', flexShrink: 0 }}>{c.ts}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', height: '22px', borderRadius: '5px', overflow: 'hidden', background: 'var(--hachi-line)' }}>
                    <div style={{ width: c.afterPct + '%', background: 'var(--hachi-trust)', minWidth: '3px' }} />
                    <div style={{ flex: 1, background: 'var(--hachi-success-tint)', display: 'flex', alignItems: 'center', paddingLeft: '10px' }}>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--hachi-success-fg)' }}>−{c.reclaimedK} reclaimed</span>
                    </div>
                  </div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--hachi-muted)', marginTop: '5px' }}>
                    {c.beforeK} → {c.afterK} tokens
                  </div>
                </div>
              </div>
            ))}
          </div>
          <div style={{ marginTop: '16px', paddingTop: '14px', borderTop: '0.5px solid var(--hachi-line)', display: 'flex', alignItems: 'center', gap: '9px' }}>
            <span style={{ color: 'var(--hachi-success)', display: 'inline-flex' }}><Icon name="sparkles" size={15} /></span>
            <span style={{ fontSize: '13px', color: 'var(--hachi-muted)' }}>
              Tidying reclaimed{' '}
              <b style={{ color: 'var(--hachi-ink)', fontFamily: 'var(--font-mono)' }}>{reclaimedTotalK}</b>
              {' '}tokens this session — Hachi spends, then cleans up after itself.
            </span>
          </div>
        </div>

        <div style={{ flex: '1 1 240px', minWidth: 0, background: 'var(--hachi-surface)', border: '0.5px solid var(--hachi-line)', borderRadius: '16px', padding: '18px' }}>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: '8px', marginBottom: '14px' }}>
            <span style={{ fontWeight: 500, fontSize: '14px' }}>Where it went</span>
            <span style={{ fontSize: '11px', color: 'var(--hachi-muted)' }}>this session</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '16px', position: 'relative' }}>
            <svg
              role="img"
              aria-label={`Where it went: total ${spendTotalCost} — ${modelRows.map(r => `${r.name} ${r.costStr}`).join(', ')}`}
              viewBox="0 0 128 128"
              style={{ width: '140px', height: '140px', display: 'block' }}
            >
              <g transform="rotate(-90 64 64)">
                <circle cx="64" cy="64" r="54" fill="none" stroke="var(--hachi-line)" strokeWidth="16" />
                {donut.map((seg, i) => (
                  <circle
                    key={i}
                    cx="64" cy="64" r="54"
                    fill="none"
                    stroke={seg.color}
                    strokeWidth="16"
                    strokeDasharray={seg.dash}
                    strokeDashoffset={seg.offset}
                  />
                ))}
              </g>
              <text x="64" y="60" textAnchor="middle" style={{ fontFamily: 'var(--font-display)', fontWeight: 500, fontSize: '17px', fill: 'var(--hachi-ink)' }}>
                {spendTotalCost}
              </text>
              <text x="64" y="76" textAnchor="middle" style={{ fontFamily: 'var(--font-body)', fontSize: '9px', fill: 'var(--hachi-muted)' }}>
                total
              </text>
            </svg>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {modelRows.map((mm, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '9px', fontSize: '12.5px' }}>
                <span style={{ width: '9px', height: '9px', borderRadius: '3px', background: mm.color, flexShrink: 0 }} />
                <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--hachi-muted)' }}>{mm.name}</span>
                <span style={{ fontFamily: 'var(--font-mono)', color: mm.costColor }}>{mm.costStr}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

// ---- Activity lens (operator only) --------------------------
function ActivityLens() {
  const events = useStore(s => s.events)
  const toolCalls = useStore(s => s.toolCalls)

  const evColor: Record<string, string> = {
    ok: 'var(--hachi-success)',
    info: 'var(--hachi-trust)',
    warn: 'var(--hachi-working)',
    error: 'var(--hachi-danger)',
    muted: 'var(--hachi-muted)',
  }

  return (
    <div style={{ maxWidth: '920px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={{ fontSize: '14px', color: 'var(--hachi-muted)', lineHeight: '22px', maxWidth: '680px' }}>
        Everything Hachi did, in order — the event stream and every tool call. Shown because you're in operator view.
      </div>

      {/* events */}
      <div
        role="table"
        aria-label="Recent events"
        style={{ background: 'var(--hachi-surface)', border: '0.5px solid var(--hachi-line)', borderRadius: '16px', overflow: 'hidden' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '9px', padding: '14px 16px', borderBottom: '0.5px solid var(--hachi-line)' }}>
          <span style={{ color: 'var(--hachi-muted)', display: 'inline-flex' }}><Icon name="work" size={15} /></span>
          <span style={{ fontWeight: 500, fontSize: '14px' }}>Recent events</span>
        </div>
        <div role="rowgroup">
          {events.map((e, i) => (
            <div
              key={i}
              role="row"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '13px',
                padding: '10px 16px',
                borderBottom: '0.5px solid var(--hachi-line)',
                fontSize: '13px',
              }}
            >
              <span role="cell" aria-label={`Time: ${e.t}`} style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--hachi-muted)', flexShrink: 0 }}>{e.t}</span>
              <span aria-hidden="true" style={{ width: '7px', height: '7px', borderRadius: '2px', background: evColor[e.lvl] ?? 'var(--hachi-muted)', flexShrink: 0 }} />
              <span role="cell" aria-label={`Event: ${e.type}, level ${e.lvl}`} style={{ color: 'var(--hachi-ink)', minWidth: '150px', flexShrink: 0 }}>{e.type}</span>
              <span role="cell" aria-label={`Detail: ${e.d}`} style={{ color: 'var(--hachi-muted)', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.d}</span>
            </div>
          ))}
        </div>
      </div>

      {/* tool calls */}
      <div
        role="table"
        aria-label="Tool calls"
        style={{ background: 'var(--hachi-surface)', border: '0.5px solid var(--hachi-line)', borderRadius: '16px', overflow: 'hidden' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '9px', padding: '14px 16px', borderBottom: '0.5px solid var(--hachi-line)' }}>
          <span style={{ color: 'var(--hachi-muted)', display: 'inline-flex' }}><Icon name="terminal" size={15} /></span>
          <span style={{ fontWeight: 500, fontSize: '14px' }}>Tool calls</span>
        </div>
        <div role="rowgroup">
          {toolCalls.map((t, i) => (
            <div
              key={i}
              role="row"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '13px',
                padding: '11px 16px',
                borderBottom: '0.5px solid var(--hachi-line)',
                fontFamily: 'var(--font-mono)',
                fontSize: '12.5px',
              }}
            >
              <span role="cell" aria-label={`Tool: ${t.tool}`} style={{ color: 'var(--hachi-ink)', minWidth: '160px', flexShrink: 0 }}>{t.tool}</span>
              <span role="cell" aria-label={`Input: ${t.inp}`} style={{ color: 'var(--hachi-muted)', flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.inp}</span>
              <span role="cell" aria-label={`Output: ${t.out}`} style={{ color: 'var(--hachi-trust)', flexShrink: 0 }}>{t.out}</span>
              <span role="cell" aria-label={`Duration: ${t.dur}`} style={{ color: 'var(--hachi-muted)', flexShrink: 0, width: '42px', textAlign: 'right' }}>{t.dur}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ---- Main Work component ------------------------------------
function Work() {
  const navigate = useNavigate()

  // store state
  const operator = useStore(s => s.operator)
  const dataMode = useStore(s => s.dataMode)
  const workFilter = useStore(s => s.workFilter)
  const runs = useStore(s => s.runs)
  const routines = useStore(s => s.routines)
  const finished = useStore(s => s.finished)
  const failed = useStore(s => s.failed)
  const packRoster = useStore(s => s.packRoster)
  const selectedWork = useStore(s => s.selectedWork) as WorkItem | null
  const loadedWork = useStore(s => s.loaded.work)

  // store actions
  const setWorkFilter = useStore(s => s.setWorkFilter)
  const openWork = useStore(s => s.openWork)
  const closeWork = useStore(s => s.closeWork)
  const retryFailed = useStore(s => s.retryFailed)
  const openRun = useStore(s => s.openRun)
  const showToast = useStore(s => s.showToast)

  // load live data on mount, then poll at 6 s intervals.
  // HACHI-021: pause polling when the tab is hidden to avoid wasting bandwidth.
  useEffect(() => {
    void loadWork()
    void loadSpend()
    void loadOperator()

    const POLL_INTERVAL = 6000

    let intervalId: ReturnType<typeof setInterval> | null = null

    function startPolling() {
      if (intervalId !== null) return // already running
      intervalId = setInterval(() => {
        void loadWork()
        void loadSpend()
      }, POLL_INTERVAL)
    }

    function stopPolling() {
      if (intervalId !== null) {
        clearInterval(intervalId)
        intervalId = null
      }
    }

    function handleVisibilityChange() {
      if (document.hidden) {
        stopPolling()
      } else {
        // Resume immediately so users see fresh data on tab-switch
        void loadWork()
        void loadSpend()
        startPolling()
      }
    }

    // Only start polling if the tab is visible on mount
    if (!document.hidden) {
      startPolling()
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)

    return () => {
      stopPolling()
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [])

  // navigate to conversation to start a new task
  const goChat = () => {
    navigate({ to: '/conversation' })
  }

  // build tab definitions
  const tabsDef: { k: string; label: string }[] = [
    { k: 'active', label: 'Active' },
    { k: 'routines', label: 'Routines' },
    { k: 'history', label: 'History' },
    { k: 'needs', label: 'Needs attention' },
    { k: 'spend', label: 'Spend' },
  ]
  if (operator) tabsDef.push({ k: 'activity', label: 'Activity' })

  const tabCounts: Record<string, number | null> = {
    active: runs.length,
    routines: routines.length,
    history: finished.length,
    needs: failed.length,
    spend: null,
    activity: null,
  }

  // build work items list
  const buildWorkItems = (): WorkItem[] => {
    if (workFilter === 'active') {
      return runs.map((r: Run): WorkItem => ({
        id: r.id,
        title: r.title,
        owner: r.owner ?? 'this conversation',
        when: r.when ?? 'running',
        cost: r.spent ?? 0,
        status: r.status,
        icon: 'work',
        kind: 'task',
        steps: r.steps,
        progress: r.progress,
        budget: r.budget,
        spent: r.spent,
        meta: r.meta,
      }))
    }
    if (workFilter === 'routines') {
      return routines.map((r: Routine): WorkItem => ({
        id: r.id,
        title: r.title,
        owner: 'routine',
        when: r.paused ? 'paused' : (r.schedule + ' · next ' + r.next),
        cost: r.cost,
        status: r.paused ? 'blocked' : 'on-watch',
        icon: 'repeat',
        kind: 'routine',
        steps: r.steps,
        schedule: r.schedule,
        next: r.next,
        last: r.last,
        paused: r.paused,
        runHistory: r.runHistory,
      }))
    }
    if (workFilter === 'history') {
      return finished.map((f: FinishedTask): WorkItem => ({
        id: f.id,
        title: f.title,
        owner: 'task',
        when: f.when,
        cost: f.cost,
        status: 'done',
        icon: 'circle-check',
        kind: 'finished',
        steps: f.steps,
        result: f.result,
        note: f.note,
      }))
    }
    // needs attention
    return failed.map((f: FailedTask): WorkItem => ({
      id: f.id,
      title: f.title,
      owner: f.owner ?? 'a routine',
      when: f.when,
      cost: f.cost,
      status: f.status as string,
      icon: 'alert',
      kind: 'failed',
      steps: f.steps,
      error: f.error,
      waitingOn: f.waitingOn,
    }))
  }

  const workItems = buildWorkItems()
  const showList = ['active', 'routines', 'history', 'needs'].includes(workFilter)
  const showSpend = workFilter === 'spend'
  const showActivity = workFilter === 'activity'
  const workEmpty = workItems.length === 0

  const handleOpenWork = (item: WorkItem) => {
    openWork(item)
  }

  const handleTogglePause = (id: number) => {
    void pauseRoutineLive(id) // calls pauseRoutine optimistically + gateway PUT
    // close the detail panel so the updated paused state is visible in the list
    closeWork()
  }

  const handleDelete = (id: number) => {
    void deleteRoutineLive(id) // optimistic removal + DELETE /schedules/{id}
    closeWork()
    void loadWork() // refresh the list after deletion
  }

  const handleWatchLive = (id: number) => {
    closeWork()
    openRun(id, 'work')
    navigate({ to: '/run' })
  }

  const handleRetry = (id: number) => {
    if (dataMode !== 'live' || !isDurableRun(id)) {
      retryFailed(id)
      return
    }

    void (async () => {
      const woke = await wakeDurableRunLive(id)
      if (woke) {
        showToast('Waking durable run — resuming in background', 'working')
        closeWork()
        void loadWork()
        return
      }
      showToast('Run is not in waiting state — cannot wake', 'blocked')
    })()
  }

  const handleCancelRun = (id: number) => {
    if (dataMode !== 'live' || !isDurableRun(id)) {
      showToast('Only durable runs can be cancelled from here', 'blocked')
      return
    }

    void (async () => {
      const cancelled = await cancelDurableRunLive(id)
      if (cancelled) {
        showToast('Run cancelled', 'success')
        closeWork()
        void loadWork()
        return
      }
      showToast('Could not cancel run — please try again', 'blocked')
    })()
  }

  const handleRunNow = (id: number) => {
    // runRoutineNowLive always applies the optimistic store update (closes the
    // panel + toast) itself; here we only need to react to whether the
    // gateway actually dispatched the run in live mode.
    void (async () => {
      const dispatched = await runRoutineNowLive(id)
      if (dataMode === 'live' && dispatched) {
        void loadWork()
      }
    })()
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        position: 'relative',
      }}
    >
      {/* header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '16px',
        padding: '0 32px',
        height: '68px',
        flexShrink: 0,
        borderBottom: '0.5px solid var(--hachi-line)',
      }}>
        <h1 style={{ margin: 0, fontFamily: 'var(--font-display)', fontWeight: 500, fontSize: '22px', lineHeight: '26px' }}>
          Work
        </h1>
        <div style={{ flex: 1 }} />
        <button
          className="hachi-retry-btn"
          onClick={goChat}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '7px',
            height: '38px',
            padding: '0 14px',
            borderRadius: '10px',
            border: '0.5px solid transparent',
            background: 'var(--hachi-brand)',
            color: 'var(--hachi-canvas)',
            font: '500 13px var(--font-body)',
            cursor: 'pointer',
          }}
        >
          <Icon name="plus" size={15} />
          New task
        </button>
      </div>

      {/* tabs — HACHI-008: overflow-x scroll so all tabs are reachable at 375px */}
      <div
        role="tablist"
        aria-label="Work filters"
        style={{
          display: 'flex',
          gap: '4px',
          padding: '14px 32px 0',
          borderBottom: '0.5px solid var(--hachi-line)',
          overflowX: 'auto',
          flexWrap: 'nowrap',
          WebkitOverflowScrolling: 'touch',
          /* hide scrollbar while keeping scrollability */
          scrollbarWidth: 'none',
          msOverflowStyle: 'none',
        }}
        onKeyDown={(e) => {
          if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return
          e.preventDefault()
          const idx = tabsDef.findIndex(t => t.k === workFilter)
          const dir = e.key === 'ArrowRight' ? 1 : -1
          const next = tabsDef[(idx + dir + tabsDef.length) % tabsDef.length]
          setWorkFilter(next.k)
          requestAnimationFrame(() => {
            (e.currentTarget.querySelector(`#work-tab-${next.k}`) as HTMLElement | null)?.focus()
          })
        }}
      >
        {tabsDef.map(t => {
          const active = workFilter === t.k
          const count = tabCounts[t.k]
          return (
            <button
              key={t.k}
              id={`work-tab-${t.k}`}
              role="tab"
              aria-selected={active}
              aria-controls="work-tabpanel"
              tabIndex={active ? 0 : -1}
              onClick={() => setWorkFilter(t.k)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '7px',
                padding: '9px 14px',
                border: 'none',
                background: 'transparent',
                borderBottom: active ? '2px solid var(--hachi-brand)' : '2px solid transparent',
                color: active ? 'var(--hachi-ink)' : 'var(--hachi-muted)',
                font: '500 14px var(--font-body)',
                cursor: 'pointer',
                marginBottom: '-0.5px',
                flexShrink: 0,
                whiteSpace: 'nowrap',
              }}
            >
              {t.label}
              {count !== null && count > 0 && (
                <span style={{ fontSize: '12px', color: 'var(--hachi-muted)' }}>{count}</span>
              )}
            </button>
          )
        })}
      </div>

      {/* scrollable body */}
      <div
        className="hachi-scroll"
        role="tabpanel"
        id="work-tabpanel"
        aria-labelledby={`work-tab-${workFilter}`}
        tabIndex={0}
        style={{ flex: 1, overflow: 'auto', padding: '24px 32px 64px' }}
      >
        {/* list views */}
        {showList && (
          <div style={{ maxWidth: '900px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {workItems.map(w => {
              const sm = statusMeta(w.status)
              return (
                <div
                  key={w.id}
                  className="hachi-runcard-home"
                  role="button"
                  tabIndex={0}
                  onClick={() => handleOpenWork(w)}
                  onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleOpenWork(w); } }}
                  style={{
                    background: 'var(--hachi-surface)',
                    border: '0.5px solid var(--hachi-line)',
                    borderRadius: '14px',
                    padding: '16px 18px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '14px',
                    cursor: 'pointer',
                  }}
                >
                  <span style={{ color: 'var(--hachi-muted)', display: 'inline-flex' }}>
                    <Icon name={w.icon} size={18} />
                  </span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 500, fontSize: '15px' }}>{w.title}</div>
                    <div style={{ fontSize: '12px', color: 'var(--hachi-muted)', marginTop: '2px' }}>
                      {w.owner} · {w.when}
                    </div>
                  </div>
                  <span style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '5px 11px',
                    borderRadius: '999px',
                    background: sm.bg,
                    color: sm.fg,
                    fontSize: '12px',
                    fontWeight: 500,
                  }}>
                    <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: sm.dot }} />
                    {sm.text}
                  </span>
                  <span style={{
                    fontSize: '13px',
                    color: 'var(--hachi-muted)',
                    fontVariantNumeric: 'tabular-nums',
                    minWidth: '54px',
                    textAlign: 'right',
                  }}>
                    {fmtUSD(w.cost)}
                  </span>
                  <span style={{ color: 'var(--hachi-muted)', display: 'inline-flex' }}>
                    <Icon name="chevron-right" size={16} />
                  </span>
                </div>
              )
            })}

            {!loadedWork ? (
              <PendingCard label="Loading work…" />
            ) : workEmpty ? (
              <div style={{
                textAlign: 'center',
                padding: '48px 0',
                color: 'var(--hachi-muted)',
                fontSize: '14px',
                lineHeight: '22px',
              }}>
                Nothing here yet.{' '}
                <button
                  onClick={goChat}
                  style={{
                    border: 'none',
                    background: 'transparent',
                    color: 'var(--hachi-trust)',
                    font: '500 14px var(--font-body)',
                    cursor: 'pointer',
                    padding: 0,
                  }}
                >
                  Start a task
                </button>
                {' '}or set up a routine.
              </div>
            ) : null}
          </div>
        )}

        {/* spend lens */}
        {showSpend && <SpendLens />}

        {/* activity lens (operator) */}
        {showActivity && <ActivityLens />}
      </div>

      {/* work detail slide-over */}
      {selectedWork !== null && (
        <WorkDetail
          item={selectedWork as WorkItem}
          packRoster={packRoster}
          onClose={closeWork}
          onRetry={handleRetry}
          onCancelRun={handleCancelRun}
          onRunNow={handleRunNow}
          onTogglePause={handleTogglePause}
          onDelete={handleDelete}
          onWatchLive={handleWatchLive}
          canCancelRun={isDurableRun((selectedWork as WorkItem).id)}
        />
      )}
    </div>
  )
}

export const Route = createFileRoute('/work')({
  component: Work,
})
