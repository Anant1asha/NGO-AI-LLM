// ============================================================
// Route: / — Home ("Today")
// Prototype markup: Hachi Web App.dc.html lines 87–211
// Logic: lines 2189–2201 (renderVals home section)
// ============================================================

import React, { useState, FormEvent } from 'react';
import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useStore } from '../lib/store/store';
import { Icon } from '../components/icons/Icon';
import { HachiMark } from '../components/brand/HachiMark';
import { LeashPrompt } from '../components/brand/LeashPrompt';
import { useCountdown } from '../lib/hooks/useCountdown';
import type { Integration } from '../lib/data/types';
import { statusMeta } from '../lib/ui/status';
import { fmtUSD } from '../lib/ui/format';

type RiskKey = 'low' | 'medium' | 'high';

interface RiskMeta {
  label: string;
  fg: string;
  bg: string;
}

function riskMeta(r: RiskKey | string): RiskMeta {
  const map: Record<string, RiskMeta> = {
    low: { label: 'low risk', fg: 'var(--hachi-success-fg)', bg: 'var(--hachi-success-tint)' },
    medium: { label: 'needs care', fg: 'var(--hachi-working-fg)', bg: 'var(--hachi-working-tint)' },
    high: { label: 'high risk', fg: 'var(--hachi-danger-fg)', bg: 'var(--hachi-danger-tint)' },
  };
  return map[r] || map['medium'];
}

// ---- Approval card (needs live countdown per card) ----

interface ApprovalCardProps {
  approval: {
    id: number;
    icon: string;
    request: string;
    why: string;
    risk: string;
    expiresAt: number;
  };
  onAllow: () => void;
  onDecline: () => void;
}

export function ApprovalCard({ approval, onAllow, onDecline }: ApprovalCardProps) {
  const { label: countdownLabel } = useCountdown(approval.expiresAt);
  const rm = riskMeta(approval.risk);

  return (
    <LeashPrompt
      request={approval.request}
      why={approval.why}
      riskPill={rm}
      countdown={approval.expiresAt > 0 ? countdownLabel : null}
      onAllowOnce={onAllow}
      onAlwaysAllow={() => {}}
      onDecline={onDecline}
      headerTestId="approval-header"
      actionsTestId="approval-actions"
    />
  );
}

// ---- DoingNow run card ----

interface RunCardHomeProps {
  title: string;
  status: string;
  progress: number;
  meta?: string;
  spent: number;
  budget: number;
  onClick: () => void;
}

function RunCardHome({ title, status, progress, meta, spent, budget, onClick }: RunCardHomeProps) {
  const sm = statusMeta(status);
  const pct = Math.round(progress * 100);

  return (
    <div
      className="hachi-runcard-home"
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(); } }}
      style={{
        background: 'var(--hachi-surface)',
        border: '0.5px solid var(--hachi-line)',
        borderRadius: '16px',
        padding: '18px',
        display: 'flex',
        flexDirection: 'column',
        gap: '13px',
        cursor: 'pointer',
        transition: 'border-color var(--dur-fast) var(--ease)',
      }}
    >
      {/* title + status pill */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
        <span style={{ fontWeight: 500, fontSize: '15px' }}>{title}</span>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '7px',
            padding: '5px 11px',
            borderRadius: '999px',
            background: sm.bg,
            color: sm.fg,
            fontSize: '12px',
            fontWeight: 500,
          }}
        >
          <span
            style={{
              width: '7px',
              height: '7px',
              borderRadius: '50%',
              background: sm.dot,
            }}
          />
          {sm.text}
        </span>
      </div>

      {/* progress bar */}
      <div
        style={{
          height: '4px',
          borderRadius: '999px',
          background: 'var(--hachi-line)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            background: 'var(--hachi-brand)',
            borderRadius: '999px',
            transition: 'width var(--dur-slow) var(--ease)',
          }}
        />
      </div>

      {/* meta + cost */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '13px',
          color: 'var(--hachi-muted)',
        }}
      >
        <span>{meta}</span>
        <span style={{ fontVariantNumeric: 'tabular-nums' }}>
          spent {fmtUSD(spent)} of {fmtUSD(budget)}
        </span>
      </div>
    </div>
  );
}

// ============================================================
// Home component
// ============================================================

function Home() {
  const navigate = useNavigate();

  // store slices
  const homeInput = useStore((s) => s.homeInput);
  const setHomeInput = useStore((s) => s.setHomeInput);
  const startTask = useStore((s) => s.startTask);
  const approvals = useStore((s) => s.approvals);
  const allowApproval = useStore((s) => s.allowApproval);
  const declineApproval = useStore((s) => s.declineApproval);
  const runs = useStore((s) => s.runs);
  const routines = useStore((s) => s.routines);
  const finished = useStore((s) => s.finished);
  const streaming = useStore((s) => s.streaming);
  const spent = useStore((s) => s.spent);
  const budget = useStore((s) => s.budget);
  const openRun = useStore((s) => s.openRun);
  const sessions = useStore((s) => s.sessions);
  const integrations = useStore((s) => s.integrations);
  const openSetup = useStore((s) => s.openSetup);

  // computed
  const working = runs.some((r) => r.status === 'working') || streaming;
  const hachiText = working ? 'Hachi is working' : 'Hachi is on watch';

  // first-run: no sessions yet
  const isFirstRun = sessions.length === 0;

  // connected integration ids for filtering starters (LOW-005)
  const connectedIntegrationIds = new Set<string>(
    integrations
      .filter((i: Integration) => i.status === 'connected' || i.status === 'degraded')
      .map((i: Integration) => i.id)
  );

  const today = new Date().toLocaleDateString('en-GB', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  });

  const pendingCount = approvals.length;
  const hasPending = pendingCount > 0;
  const pendingCountStr =
    pendingCount === 1 ? '1 thing' : `${pendingCount} things`;

  const hasDoing = runs.length > 0;
  const noDoing = !hasDoing;

  // home starters — requiredIntegration: null means always show
  const allStarters = [
    {
      label: 'Summarise my inbox',
      icon: 'mail',
      requiredIntegration: 'i1', // Google (Gmail)
      go: () => {
        startTask('Summarise my inbox and flag anything urgent');
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        navigate({ to: '/conversation' as any });
      },
    },
    {
      label: 'Set up a morning briefing',
      icon: 'calendar',
      requiredIntegration: 'i1', // Google (Calendar)
      go: () => {
        startTask('Every weekday at 8, summarise my inbox and message me the urgent ones');
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        navigate({ to: '/conversation' as any });
      },
    },
    {
      label: "Check this week's PRs",
      icon: 'git-branch',
      requiredIntegration: null, // no specific integration required
      go: () => {
        startTask("Summarise this week's pull requests");
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        navigate({ to: '/conversation' as any });
      },
    },
  ];

  // LOW-005: only show starters whose integration is connected (or has no requirement)
  const starters = allStarters.filter(
    (s) => s.requiredIntegration === null || connectedIntegrationIds.has(s.requiredIntegration)
  );

  function handleHomeSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!homeInput.trim()) return;
    startTask(homeInput);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    navigate({ to: '/conversation' as any });
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* header */}
      <div
        className="hachi-home-header"
        style={{
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          padding: '0 32px',
          height: '68px',
          flexShrink: 0,
          borderBottom: '0.5px solid var(--hachi-line)',
        }}
      >
        <h1
          style={{
            margin: 0,
            fontFamily: 'var(--font-display)',
            fontWeight: 500,
            fontSize: '22px',
            lineHeight: '26px',
          }}
        >
          Today
        </h1>
        <span
          style={{
            position: 'absolute',
            left: '50%',
            transform: 'translateX(-50%)',
            fontSize: '13px',
            color: 'var(--hachi-muted)',
            pointerEvents: 'none',
          }}
        >
          {hachiText}
        </span>
      </div>

      {/* scrollable body */}
      <div
        className="hachi-scroll hachi-home-body"
        style={{ flex: 1, overflow: 'auto', padding: '28px 32px 64px' }}
      >
        <div
          style={{
            maxWidth: '940px',
            margin: '0 auto',
            display: 'flex',
            flexDirection: 'column',
            gap: '30px',
          }}
        >
          {/* ---- Start something ---- */}
          <div
            style={{
              background: 'var(--hachi-surface)',
              border: '0.5px solid var(--hachi-line)',
              borderRadius: '16px',
              padding: '22px',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                marginBottom: '14px',
              }}
            >
              <HachiMark size={26} />
              <span
                style={{
                  fontFamily: 'var(--font-display)',
                  fontWeight: 500,
                  fontSize: '18px',
                }}
              >
                Start something
              </span>
            </div>

            <form
              onSubmit={handleHomeSubmit}
              className="hachi-home-ask-form"
              style={{ display: 'flex', gap: '10px', alignItems: 'stretch' }}
            >
              <input
                value={homeInput}
                onChange={(e) => setHomeInput(e.target.value)}
                placeholder="Ask Hachi to do something…"
                className="hachi-home-ask-input"
                style={{
                  flex: 1,
                  minWidth: 0,
                  height: '46px',
                  padding: '0 16px',
                  borderRadius: '10px',
                  border: '0.5px solid var(--hachi-line)',
                  background: 'var(--hachi-canvas)',
                  font: 'inherit',
                  fontSize: '15px',
                  color: 'var(--hachi-ink)',
                  outline: 'none',
                }}
              />
              <button
                type="submit"
                className="hachi-ask-hachi-btn"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  height: '46px',
                  padding: '0 20px',
                  borderRadius: '10px',
                  border: '0.5px solid transparent',
                  background: 'var(--hachi-brand-hover)',
                  color: 'var(--hachi-canvas)',
                  font: '500 14px var(--font-body)',
                  cursor: 'pointer',
                  transition: 'background var(--dur-fast) var(--ease)',
                }}
              >
                <Icon name="arrow-up" size={16} />
                Ask Hachi
              </button>
            </form>

            {/* starter chips */}
            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: '8px',
                marginTop: '14px',
              }}
            >
              {starters.map((s) => (
                <button
                  key={s.label}
                  className="hachi-starter-chip"
                  onClick={s.go}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '7px',
                    minHeight: '44px',
                    padding: '7px 13px',
                    borderRadius: '999px',
                    border: '0.5px solid var(--hachi-line)',
                    background: 'var(--hachi-canvas)',
                    color: 'var(--hachi-ink)',
                    font: 'inherit',
                    fontSize: '13px',
                    cursor: 'pointer',
                    transition: 'background var(--dur-fast) var(--ease)',
                  }}
                >
                  <span
                    style={{ color: 'var(--hachi-muted)', display: 'inline-flex' }}
                  >
                    <Icon name={s.icon} size={14} />
                  </span>
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* ---- What needs you ---- */}
          {hasPending && (
            <div>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '9px',
                  marginBottom: '14px',
                }}
              >
                <span
                  style={{ color: 'var(--hachi-brand)', display: 'inline-flex' }}
                >
                  <Icon name="leash" size={17} />
                </span>
                <h2
                  style={{
                    margin: 0,
                    fontFamily: 'var(--font-display)',
                    fontWeight: 500,
                    fontSize: '16px',
                  }}
                >
                  What needs you
                </h2>
                <span style={{ fontSize: '13px', color: 'var(--hachi-muted)' }}>
                  {pendingCountStr} waiting on the leash
                </span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {approvals.slice(0, 3).map((a) => (
                  <ApprovalCard
                    key={a.id}
                    approval={a}
                    onAllow={() => allowApproval(a.id)}
                    onDecline={() => declineApproval(a.id)}
                  />
                ))}
                {approvals.length > 3 && (
                  <button
                    type="button"
                    className="hachi-more-approvals-link"
                    onClick={() => navigate({ to: '/approvals' as any })}
                  >
                    + {approvals.length - 3} more waiting on the leash →
                  </button>
                )}
              </div>
            </div>
          )}

          {/* ---- Doing now ---- */}
          <div>
            <h2
              style={{
                margin: '0 0 14px',
                fontFamily: 'var(--font-display)',
                fontWeight: 500,
                fontSize: '16px',
              }}
            >
              What Hachi is doing now
            </h2>

            {hasDoing && (
              <div
                className="hachi-run-grid"
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(min(420px, 100%), 1fr))',
                  gap: '14px',
                }}
              >
                {runs.map((r) => (
                  <RunCardHome
                    key={r.id}
                    title={r.title}
                    status={r.status}
                    progress={r.progress}
                    meta={r.meta}
                    spent={r.spent}
                    budget={r.budget}
                    onClick={() => {
                      openRun(r.id, 'home');
                      // eslint-disable-next-line @typescript-eslint/no-explicit-any
                      navigate({ to: '/run' as any });
                    }}
                  />
                ))}
              </div>
            )}

            {noDoing && !isFirstRun && (
              <div style={{ fontSize: '14px', color: 'var(--hachi-muted)' }}>
                Nothing running right now.
              </div>
            )}

            {/* HIGH-019: first-run guidance panel */}
            {noDoing && isFirstRun && (
              <FirstRunPanel onSetup={openSetup} onStart={() => {
                startTask('Give me a quick tour of what you can do');
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                navigate({ to: '/conversation' as any });
              }} />
            )}
          </div>

          {/* ---- On watch + Finished recently : two columns ---- */}
          <div
            className="hachi-two-col"
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '24px',
            }}
          >
            {/* On watch */}
            <div>
              <h2
                style={{
                  margin: '0 0 14px',
                  fontFamily: 'var(--font-display)',
                  fontWeight: 500,
                  fontSize: '16px',
                }}
              >
                On watch
              </h2>
              <div
                style={{
                  background: 'var(--hachi-surface)',
                  border: '0.5px solid var(--hachi-line)',
                  borderRadius: '16px',
                  overflow: 'hidden',
                }}
              >
                {routines.length === 0 ? (
                  <div
                    style={{
                      padding: '14px 16px',
                      fontSize: '13px',
                      color: 'var(--hachi-muted)',
                    }}
                  >
                    No routines on watch yet.
                  </div>
                ) : (
                  routines.map((w) => (
                    <RoutineRow key={w.id} routine={w} />
                  ))
                )}
                <button
                  className="hachi-ghost-icon-btn-bg"
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  onClick={() => navigate({ to: '/work' as any })}
                  style={{
                    width: '100%',
                    padding: '13px',
                    paddingLeft: '16px',
                    border: 'none',
                    color: 'var(--hachi-trust)',
                    font: '500 13px var(--font-body)',
                    cursor: 'pointer',
                    textAlign: 'left',
                    transition: 'background var(--dur-fast) var(--ease)',
                  }}
                >
                  Manage routines →
                </button>
              </div>
            </div>

            {/* Finished recently */}
            <div>
              <h2
                style={{
                  margin: '0 0 14px',
                  fontFamily: 'var(--font-display)',
                  fontWeight: 500,
                  fontSize: '16px',
                }}
              >
                Finished recently
              </h2>
              <div
                style={{
                  background: 'var(--hachi-surface)',
                  border: '0.5px solid var(--hachi-line)',
                  borderRadius: '16px',
                  overflow: 'hidden',
                }}
              >
                {finished.length === 0 ? (
                  <div
                    style={{
                      padding: '14px 16px',
                      fontSize: '13px',
                      color: 'var(--hachi-muted)',
                    }}
                  >
                    Nothing finished yet today.
                  </div>
                ) : (
                  finished.map((f) => (
                    <FinishedRow key={f.id} item={f} />
                  ))
                )}
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}

// ---- Sub-components (no entrance animation per contract §2) ----

interface RoutineRowProps {
  routine: {
    id: number;
    title: string;
    schedule: string;
    next: string;
    cost: number;
  };
}

function RoutineRow({ routine: w }: RoutineRowProps) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        padding: '14px 16px',
        borderBottom: '0.5px solid var(--hachi-line)',
      }}
    >
      <span
        style={{ color: 'var(--hachi-trust)', display: 'inline-flex' }}
      >
        <Icon name="repeat" size={17} />
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 500, fontSize: '14px' }}>{w.title}</div>
        <div style={{ fontSize: '12px', color: 'var(--hachi-muted)', marginTop: '2px' }}>
          {w.schedule} · next {w.next}
        </div>
      </div>
      <span
        style={{
          fontSize: '12px',
          color: 'var(--hachi-muted)',
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {fmtUSD(w.cost)}/run
      </span>
    </div>
  );
}

interface FinishedRowProps {
  item: {
    id: number;
    title: string;
    note: string;
    when: string;
    cost: number;
  };
}

function FinishedRow({ item: f }: FinishedRowProps) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        padding: '14px 16px',
        borderBottom: '0.5px solid var(--hachi-line)',
      }}
    >
      <span
        style={{ color: 'var(--hachi-success)', display: 'inline-flex' }}
      >
        <Icon name="circle-check" size={17} />
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 500, fontSize: '14px' }}>{f.title}</div>
        <div style={{ fontSize: '12px', color: 'var(--hachi-muted)', marginTop: '2px' }}>
          {f.note} · {f.when}
        </div>
      </div>
      <span
        style={{
          fontSize: '12px',
          color: 'var(--hachi-muted)',
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {fmtUSD(f.cost)}
      </span>
    </div>
  );
}

// ---- FirstRunPanel — shown when sessions.length === 0 (HIGH-019) ----

interface FirstRunPanelProps {
  onStart: () => void;
  onSetup: () => void;
}

function FirstRunPanel({ onStart, onSetup }: FirstRunPanelProps) {
  return (
    <div
      style={{
        background: 'var(--hachi-surface)',
        border: '0.5px solid var(--hachi-line)',
        borderRadius: '16px',
        padding: '28px 24px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '18px',
        textAlign: 'center',
      }}
    >
      <HachiMark size={40} />
      <div>
        <div
          style={{
            fontFamily: 'var(--font-display)',
            fontWeight: 500,
            fontSize: '18px',
            marginBottom: '8px',
          }}
        >
          Welcome — Hachi is ready
        </div>
        <div style={{ fontSize: '14px', color: 'var(--hachi-muted)', maxWidth: '380px' }}>
          Give Hachi a task and watch it work. Connect integrations to unlock more capabilities.
        </div>
      </div>

      <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', justifyContent: 'center' }}>
        <button
          className="hachi-mcp-submit-btn"
          onClick={onStart}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            height: '42px',
            padding: '0 20px',
            borderRadius: '10px',
            border: '0.5px solid transparent',
            background: 'var(--hachi-brand-hover)',
            color: 'var(--hachi-canvas)',
            font: '500 14px var(--font-body)',
            cursor: 'pointer',
            transition: 'background var(--dur-fast) var(--ease)',
          }}
        >
          <Icon name="arrow-up" size={15} />
          Start your first task
        </button>
        <button
          className="hachi-ghost-icon-btn-bg"
          onClick={onSetup}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            height: '42px',
            padding: '0 20px',
            borderRadius: '10px',
            border: '0.5px solid var(--hachi-line)',
            background: 'var(--hachi-canvas)',
            color: 'var(--hachi-ink)',
            font: '500 14px var(--font-body)',
            cursor: 'pointer',
            transition: 'background var(--dur-fast) var(--ease)',
          }}
        >
          <Icon name="settings" size={15} />
          Connect integrations
        </button>
      </div>
    </div>
  );
}

// ============================================================
// Route export (TanStack Router file-based routing)
// ============================================================

export const Route = createFileRoute('/')({
  component: Home,
});
