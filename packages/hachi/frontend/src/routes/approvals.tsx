// ============================================================
// The leash — /approvals
// Pending approvals queue with countdown + history + operator audit log.
// ============================================================

import React, { useState, useEffect, useRef } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useStore } from "../lib/store/store";
import { useCountdown } from "../lib/hooks/useCountdown";
import { Icon } from "../components/icons/Icon";
import { HachiMark } from "../components/brand/HachiMark";
import { LeashPrompt } from "../components/brand/LeashPrompt";
import type { Approval, HistoryItem, AuditEntry } from "../lib/data/types";
import { fmtRelative } from "../lib/ui/format";
import { PendingCard } from "../components/ui/PendingCard";

// localStorage key for dismissing the "What is the leash?" info band
const LEASH_INFO_KEY = "hachi.leash-info-dismissed";
import {
  loadApprovals,
  approve,
  allowAlways,
  decline,
  declineAll as declineAllMutation,
} from "../lib/data/domains/approvals";

// ============================================================
// LeashInfoBand — "What is the leash?" dismissible info band
// Shown once on first visit; suppressed after dismiss via localStorage.
// ============================================================
function LeashInfoBand() {
  const [visible, setVisible] = useState<boolean>(
    () => localStorage.getItem(LEASH_INFO_KEY) !== "1"
  );

  const dismiss = () => {
    try {
      localStorage.setItem(LEASH_INFO_KEY, "1");
    } catch {
      // Storage unavailable (e.g. private browsing quota) — still hide the band.
    }
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div
      role="status"
      aria-label="What is the leash?"
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: 12,
        padding: "13px 16px",
        background: "var(--hachi-trust-tint)",
        border: "0.5px solid var(--hachi-line)",
        borderRadius: 12,
        marginBottom: 4,
      }}
    >
      <span
        style={{
          color: "var(--hachi-trust)",
          display: "inline-flex",
          flexShrink: 0,
          marginTop: 2,
        }}
      >
        <Icon name="shield" size={16} />
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontFamily: "var(--font-body)",
            fontWeight: 500,
            fontSize: 13,
            color: "var(--hachi-ink)",
            marginBottom: 3,
          }}
        >
          What is the leash?
        </div>
        <div style={{ fontSize: 13, color: "var(--hachi-muted)", lineHeight: "20px" }}>
          The leash is how you stay in control — before Hachi runs anything risky or
          irreversible, it pauses here and asks. You decide: allow once, always allow,
          or decline. Hachi never acts without your say-so on gated actions.
        </div>
      </div>
      <button
        type="button"
        aria-label="Dismiss: What is the leash?"
        onClick={dismiss}
        style={{
          flexShrink: 0,
          border: "none",
          background: "transparent",
          color: "var(--hachi-muted)",
          cursor: "pointer",
          padding: "2px 4px",
          display: "inline-flex",
          alignItems: "center",
          borderRadius: 6,
          font: "16px/1 var(--font-body)",
        }}
      >
        ×
      </button>
    </div>
  );
}

// ---- risk metadata (mirrors dc.html riskMeta) ----
function riskMeta(r: string): {
  label: string;
  fg: string;
  bg: string;
  cd: string;
} {
  const map: Record<string, { label: string; fg: string; bg: string; cd: string }> = {
    low: {
      label: "low risk",
      fg: "var(--hachi-success-fg)",
      bg: "var(--hachi-success-tint)",
      cd: "var(--hachi-success)",
    },
    medium: {
      label: "needs care",
      fg: "var(--hachi-working-fg)",
      bg: "var(--hachi-working-tint)",
      cd: "var(--hachi-working)",
    },
    high: {
      label: "high risk",
      fg: "var(--hachi-danger-fg)",
      bg: "var(--hachi-danger-tint)",
      cd: "var(--hachi-danger)",
    },
  };
  return map[r] ?? map.medium;
}

// ---- audit decision color map ----
const auditDColor: Record<string, string> = {
  allowed: "var(--hachi-success)",
  "allowed once": "var(--hachi-trust)",
  declined: "var(--hachi-danger)",
  automatic: "var(--hachi-muted)",
};

// ---- unchecked actions per safety level ----
// Backend has no canonical list; these are typical for each level.
const UNCHECKED_BY_LEVEL: Record<string, string[]> = {
  guarded: [
    "Reading files inside your project folder",
  ],
  standard: [
    "Reading files inside your project folder",
    "Searching the web to answer a question",
    "Reading your calendar and inbox (not sending)",
  ],
  open: [
    "Reading files inside your project folder",
    "Searching the web to answer a question",
    "Reading your calendar and inbox (not sending)",
    "Running shell commands in folders you approved",
    "Sending drafts you pre-approved",
  ],
};
function uncheckedActionsFor(level: string): string[] {
  return UNCHECKED_BY_LEVEL[level] ?? UNCHECKED_BY_LEVEL.standard;
}

// ============================================================
// ApprovalCard — renders one pending approval with live countdown
// ============================================================
interface ApprovalCardProps {
  approval: Approval;
  onAllowOnce: () => void;
  onAlwaysAllow: () => void;
  onDecline: () => void;
}

function ApprovalCard({
  approval,
  onAllowOnce,
  onAlwaysAllow,
  onDecline,
}: ApprovalCardProps) {
  const { ms, label: countdownLabel } = useCountdown(approval.expiresAt);
  const rm = riskMeta(approval.risk);
  const cdPct = Math.max(0, Math.min(100, (ms / approval.totalMs) * 100));

  // Aria-live announcement — fires only at 30s and 10s thresholds (never per-second).
  const lastAnnounced = useRef<number | null>(null);
  const [announcement, setAnnouncement] = useState('');
  useEffect(() => {
    const secs = Math.ceil(ms / 1000);
    if (secs <= 10 && lastAnnounced.current !== 10) {
      lastAnnounced.current = 10;
      setAnnouncement('Approval auto-declines in 10 seconds');
    } else if (secs <= 30 && secs > 10 && lastAnnounced.current !== 30) {
      lastAnnounced.current = 30;
      setAnnouncement('Approval auto-declines in 30 seconds');
    }
  }, [ms]);

  return (
    <>
      <span
        aria-live="polite"
        style={{ position: 'absolute', width: 1, height: 1, overflow: 'hidden', clip: 'rect(0,0,0,0)', whiteSpace: 'nowrap' }}
      >
        {announcement}
      </span>
      <LeashPrompt
      request={approval.request}
      why={approval.why}
      action={approval.action}
      riskPill={rm}
      touches={approval.touches}
      countdown={approval.totalMs > 0 ? countdownLabel : null}
      countdownBar={approval.totalMs > 0 ? { pct: cdPct, color: rm.cd } : undefined}
      onAllowOnce={onAllowOnce}
      onAlwaysAllow={onAlwaysAllow}
      onDecline={onDecline}
    />
    </>
  );
}

// ============================================================
// HistoryRow
// ============================================================
function HistoryRow({ item }: { item: HistoryItem }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "13px 16px",
        borderBottom: "0.5px solid var(--hachi-line)",
      }}
    >
      <span style={{ color: item.color, display: "inline-flex" }}>
        <Icon name={item.icon} size={16} />
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14 }}>{item.request}</div>
        <div
          style={{
            fontSize: 12,
            color: "var(--hachi-muted)",
            marginTop: 2,
          }}
        >
          {item.decision} · {item.ts !== undefined ? fmtRelative(item.ts) : item.when}
        </div>
      </div>
    </div>
  );
}

// ============================================================
// AuditRow (operator-only)
// ============================================================
function AuditRow({ entry }: { entry: AuditEntry }) {
  const dColor = auditDColor[entry.decision] ?? "var(--hachi-muted)";
  return (
    <div
      role="row"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 13,
        padding: "11px 16px",
        borderBottom: "0.5px solid var(--hachi-line)",
        fontSize: 13,
      }}
    >
      <span
        role="cell"
        aria-label={`Time: ${entry.ts}`}
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 12,
          color: "var(--hachi-muted)",
          flexShrink: 0,
        }}
      >
        {entry.ts}
      </span>
      <span
        role="cell"
        aria-label={`Operation: ${entry.op}`}
        style={{
          color: "var(--hachi-ink)",
          minWidth: 110,
          flexShrink: 0,
        }}
      >
        {entry.op}
      </span>
      <span
        role="cell"
        aria-label={`Target: ${entry.target}`}
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 12,
          color: "var(--hachi-muted)",
          flex: 1,
          minWidth: 0,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {entry.target}
      </span>
      <span
        role="cell"
        aria-label={`Policy: ${entry.policy}`}
        style={{
          fontSize: 12,
          color: "var(--hachi-muted)",
          flexShrink: 0,
        }}
      >
        {entry.policy}
      </span>
      <span
        role="cell"
        aria-label={`Decision: ${entry.decision}`}
        style={{
          fontSize: 12,
          fontWeight: 500,
          color: dColor,
          flexShrink: 0,
          minWidth: 78,
          textAlign: "right",
        }}
      >
        {entry.decision}
      </span>
    </div>
  );
}

// ============================================================
// Approvals screen component
// ============================================================
function Approvals() {
  const navigate = useNavigate();
  const approvals = useStore((s) => s.approvals);
  const history = useStore((s) => s.history);
  const auditLog = useStore((s) => s.auditLog);
  const operator = useStore((s) => s.operator);
  const loadedApprovals = useStore((s) => s.loaded.approvals);
  const safety = useStore((s) => s.safety);

  const queueRef = useRef<HTMLDivElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const prevLengthRef = useRef(approvals.length);

  // After a card is resolved and removed, move focus to the next card's first
  // action button; if the queue is now empty, focus the heading.
  useEffect(() => {
    if (approvals.length < prevLengthRef.current) {
      const firstBtn = queueRef.current?.querySelector<HTMLButtonElement>('button');
      if (firstBtn) {
        firstBtn.focus();
      } else {
        headingRef.current?.focus();
      }
    }
    prevLengthRef.current = approvals.length;
  }, [approvals.length]);

  // Refresh gateway data on navigate-to this screen
  useEffect(() => { void loadApprovals(); }, []);

  const pendingCount = approvals.length;
  const hasPending = pendingCount > 0;
  const noPending = pendingCount === 0;
  const manyPending = pendingCount > 1;
  const pendingCountStr =
    pendingCount === 1 ? "1 thing" : pendingCount + " things";

  const goSettings = () => navigate({ to: "/settings" });

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
      }}
    >
      {/* Header */}
      <div
        className="hachi-approvals-header"
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          padding: "0 32px",
          height: 68,
          flexShrink: 0,
          borderBottom: "0.5px solid var(--hachi-line)",
        }}
      >
        <h1
          ref={headingRef}
          tabIndex={-1}
          style={{
            margin: 0,
            fontFamily: "var(--font-display)",
            fontWeight: 500,
            fontSize: 22,
            lineHeight: "26px",
          }}
        >
          The leash
        </h1>
        <span style={{ fontSize: 13, color: "var(--hachi-muted)" }}>
          you hold it · {pendingCountStr} waiting
        </span>
        <div style={{ flex: 1 }} />
        {manyPending && (
          <button
            type="button"
            className="hachi-cancel-btn"
            onClick={() => { void declineAllMutation(); }}
            style={{
              height: 36,
              padding: "0 14px",
              borderRadius: 10,
              border: "1px solid var(--hachi-trust)",
              background: "transparent",
              color: "var(--hachi-trust)",
              font: "500 13px var(--font-body)",
              cursor: "pointer",
              transition: "background var(--dur-fast) var(--ease)",
            }}
          >
            Decline all
          </button>
        )}
      </div>

      {/* Scrollable content */}
      <div
        className="hachi-scroll hachi-approvals-body"
        style={{ flex: 1, overflow: "auto", padding: "28px 32px 64px" }}
      >
        <div
          style={{
            maxWidth: 720,
            margin: "0 auto",
            display: "flex",
            flexDirection: "column",
            gap: 28,
          }}
        >
          {/* What is the leash? — first-encounter info band */}
          <LeashInfoBand />

          {/* Pending approvals */}
          {hasPending && (
            <div ref={queueRef} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {approvals.map((a) => (
                <ApprovalCard
                  key={a.id}
                  approval={a}
                  onAllowOnce={() => { void approve(a.id); }}
                  onAlwaysAllow={() => { void allowAlways(a.id); }}
                  onDecline={() => { void decline(a.id); }}
                />
              ))}
            </div>
          )}

          {/* Loading / empty state */}
          {!loadedApprovals ? (
            <PendingCard label="Checking the queue…" />
          ) : noPending ? (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                textAlign: "center",
                gap: 14,
                padding: "40px 0",
                background: "var(--hachi-surface)",
                border: "0.5px solid var(--hachi-line)",
                borderRadius: 16,
              }}
            >
              <HachiMark size={48} />
              <div
                style={{
                  fontFamily: "var(--font-display)",
                  fontWeight: 500,
                  fontSize: 18,
                }}
              >
                Nothing pending
              </div>
              <div style={{ fontSize: 14, color: "var(--hachi-muted)" }}>
                Hachi is on watch. It will ask here before doing anything risky.
              </div>
            </div>
          ) : null}

          {/* Runs without a leash check */}
          <div>
            <h2
              style={{
                margin: "0 0 12px",
                fontFamily: "var(--font-display)",
                fontWeight: 500,
                fontSize: 16,
              }}
            >
              Runs without a leash check
            </h2>
            <div
              style={{
                background: "var(--hachi-surface)",
                border: "0.5px solid var(--hachi-line)",
                borderRadius: 16,
                padding: 18,
                fontSize: 13,
                color: "var(--hachi-muted)",
              }}
            >
              <div
                style={{
                  marginBottom: 10,
                  color: "var(--hachi-ink)",
                }}
              >
                Typical for the <strong>{safety}</strong> level — these run without asking.
              </div>
              {uncheckedActionsFor(safety).map((u, i) => (
                <div
                  key={i}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 9,
                    padding: "6px 0",
                  }}
                >
                  <span
                    style={{
                      color: "var(--hachi-success)",
                      display: "inline-flex",
                    }}
                  >
                    <Icon name="check" size={15} />
                  </span>
                  {u}
                </div>
              ))}
              <GoSettingsLink onClick={goSettings} />
            </div>
          </div>

          {/* Past decisions — always rendered; empty card when no history yet */}
          <div>
            <h2
              style={{
                margin: "0 0 12px",
                fontFamily: "var(--font-display)",
                fontWeight: 500,
                fontSize: 16,
              }}
            >
              Past decisions
            </h2>
            <div
              style={{
                background: "var(--hachi-surface)",
                border: "0.5px solid var(--hachi-line)",
                borderRadius: 16,
                overflow: "hidden",
              }}
            >
              {!loadedApprovals ? (
                <PendingCard label="Loading past decisions…" />
              ) : history.length > 0 ? (
                history.map((h) => <HistoryRow key={h.id} item={h} />)
              ) : (
                <div
                  style={{
                    padding: "24px 20px",
                    fontSize: 13.5,
                    color: "var(--hachi-muted)",
                    textAlign: "center",
                  }}
                >
                  No decisions yet — approvals you resolve will show up here.
                </div>
              )}
            </div>
          </div>

          {/* Permission audit — operator only; always rendered when operator mode is active */}
          {operator && (
            <div>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 9,
                  marginBottom: 12,
                }}
              >
                <h2
                  style={{
                    margin: 0,
                    fontFamily: "var(--font-display)",
                    fontWeight: 500,
                    fontSize: 16,
                  }}
                >
                  Permission audit
                </h2>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 500,
                    color: "var(--hachi-trust)",
                    background: "var(--hachi-trust-tint)",
                    padding: "3px 9px",
                    borderRadius: 999,
                  }}
                >
                  operator
                </span>
              </div>
              <div
                role="table"
                aria-label="Permission audit log"
                style={{
                  background: "var(--hachi-surface)",
                  border: "0.5px solid var(--hachi-line)",
                  borderRadius: 16,
                  overflow: "hidden",
                }}
              >
                {auditLog.map((a, i) => (
                  <AuditRow key={i} entry={a} />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ---- small inline link (avoids re-creating on each parent render) ----
function GoSettingsLink({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      className="hachi-go-settings-link"
      onClick={onClick}
      style={{
        marginTop: 8,
        border: "none",
        background: "transparent",
        color: "var(--hachi-trust)",
        font: "500 13px var(--font-body)",
        cursor: "pointer",
        padding: 0,
        transition: "opacity var(--dur-fast) var(--ease)",
      }}
    >
      Tighten the leash in settings →
    </button>
  );
}

// ============================================================
// Route registration
// ============================================================
export const Route = createFileRoute("/approvals")({
  component: Approvals,
});
