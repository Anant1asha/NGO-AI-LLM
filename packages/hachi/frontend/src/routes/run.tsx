// ============================================================
// Live run — /run
// Prototype markup: Hachi Web App.dc.html lines 1239–1310
// Logic: lines 1927–2012, 2452–2471 (openRun, runTick, runAllowLeash,
//         runDenyLeash, stopRun, closeRun, _finishRun, renderVals run block)
//
// HIGH-007: live-run streaming wired.
// RunSurface is the shared presentational layer, driven from the store run
// slice in both mock and live modes.  MockRunSimulation keeps its mock-only
// bootstrapping useEffects.  LiveRun renders RunSurface when runView is set
// (populated by startTaskLive → driveRunSlice in chat.ts), or an honest
// empty-state card otherwise.
// ============================================================

import { memo, useEffect, useRef } from "react";
import type { CSSProperties } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useStore } from "../lib/store/store";
import { Icon } from "../components/icons/Icon";
import { Terminal } from "../components/ui/Terminal";
import { LeashPrompt } from "../components/brand/LeashPrompt";
import { useFocusTrap } from "../lib/hooks/useFocusTrap";
import { statusMeta } from "../lib/ui/status";
import { fmtUSD } from "../lib/ui/format";

// Mirror prototype stepMeta — icon + color per step state.
function stepMeta(state: string): { icon: string; color: string } {
  const map: Record<string, { icon: string; color: string }> = {
    done: { icon: "circle-check", color: "var(--hachi-success)" },
    working: { icon: "play", color: "var(--hachi-working)" },
    failed: { icon: "circle-alert", color: "var(--hachi-danger)" },
    pending: { icon: "minus", color: "var(--hachi-muted)" },
  };
  return map[state] ?? map.pending;
}

// Mirror prototype packMeta — dot/text/fg per pack member status.
function packMeta(status: string): { dot: string; text: string; fg: string } {
  if (status === "done") {
    return { dot: "var(--hachi-success)", text: "done", fg: "var(--hachi-success-fg)" };
  }
  if (status === "working") {
    return { dot: "var(--hachi-working)", text: "on it", fg: "var(--hachi-working-fg)" };
  }
  return { dot: "var(--hachi-line)", text: "queued", fg: "var(--hachi-muted)" };
}

// ============================================================
// Shared presentational surface — reads from the store run slice.
// Used by both MockRunSimulation and the live RunSurface.
// ============================================================

interface RunSurfaceProps {
  /** Called by the back-button click handler */
  onBack: () => void;
}

function RunSurface({ onBack }: RunSurfaceProps) {
  // Store slices
  const runView = useStore((s) => s.runView);
  const runDone = useStore((s) => s.runDone);
  const runLeash = useStore((s) => s.runLeash);
  const runSpent = useStore((s) => s.runSpent);
  const runPack = useStore((s) => s.runPack);
  const runSteps = useStore((s) => s.runSteps);

  // Store actions
  const stopRun = useStore((s) => s.stopRun);
  const runAllowLeash = useStore((s) => s.runAllowLeash);
  const runAlwaysAllow = useStore((s) => s.runAlwaysAllow);
  const runDenyLeash = useStore((s) => s.runDenyLeash);

  // ---- derived renderVals (mirror dc.html lines 2452–2471) ----
  const runPhase: "working" | "done" | "blocked" = runDone
    ? "done"
    : runLeash
    ? "blocked"
    : "working";

  const rsm = statusMeta(runPhase);

  const statusText = runDone
    ? "Hachi is resting"
    : runLeash
    ? "Hachi is blocked — needs you"
    : "Hachi is working";

  const spentStr = fmtUSD(runSpent);
  const budgetStr = fmtUSD(runView?.budget ?? 1.0);

  const canStop = !runDone && !runLeash;

  const onit = runPack.filter((p) => p.status === "working").length;
  const packLabel = runDone
    ? runPack.length + " rested"
    : onit > 0
    ? onit + " on it"
    : "spinning up";

  const title = runView?.title ?? "Live run";

  const steps = runSteps.map((stp) => {
    const mm = stepMeta(stp.state);
    return {
      label: stp.label,
      icon: mm.icon,
      color: mm.color,
      textColor:
        stp.state === "pending"
          ? "var(--hachi-muted)"
          : "var(--hachi-ink)",
    };
  });

  const pack = runPack.map((p) => {
    const m = packMeta(p.status);
    return {
      id: p.id,
      name: p.name,
      task: p.task,
      dot: m.dot,
      statusText: m.text,
      statusFg: m.fg,
      tokens: (p.tokens ?? 0).toLocaleString(),
      hasTokens: (p.tokens ?? 0) > 0,
    };
  });

  const hasLeash = !!runLeash;
  const leashTrapRef = useFocusTrap<HTMLDivElement>(hasLeash);
  // Hide the Plan section when no steps exist (live mode emits no plan events)
  const hasPlan = steps.length > 0;

  // ---- styles ----
  const headerStyle: CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: 14,
    padding: "0 32px",
    height: 68,
    flexShrink: 0,
    borderBottom: "0.5px solid var(--hachi-line)",
  };

  const backBtnStyle: CSSProperties = {
    border: "none",
    color: "var(--hachi-muted)",
    cursor: "pointer",
    display: "inline-flex",
    padding: 6,
    borderRadius: 8,
    marginLeft: -6,
    transition: "background var(--dur-fast) var(--ease)",
  };

  const pillStyle: CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: 7,
    padding: "5px 11px",
    borderRadius: 999,
    background: rsm.bg,
    color: rsm.fg,
    fontSize: 12,
    fontWeight: 500,
  };

  const stopBtnStyle: CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: 7,
    height: 36,
    padding: "0 14px",
    borderRadius: 10,
    border: "1px solid var(--hachi-trust)",
    background: "transparent",
    color: "var(--hachi-trust)",
    font: "500 13px var(--font-body)",
    cursor: "pointer",
    transition: "background var(--dur-fast) var(--ease)",
  };

  const leftPanelStyle: CSSProperties = {
    width: 312,
    flexShrink: 0,
    borderRight: "0.5px solid var(--hachi-line)",
    overflow: "auto",
    padding: "22px 22px 32px",
    display: "flex",
    flexDirection: "column",
    gap: 26,
  };

  const sectionLabelStyle: CSSProperties = {
    fontSize: 12,
    color: "var(--hachi-muted)",
    marginBottom: 10,
  };

  const packCardStyle: CSSProperties = {
    display: "flex",
    alignItems: "flex-start",
    gap: 10,
    background: "var(--hachi-surface)",
    border: "0.5px solid var(--hachi-line)",
    borderRadius: 12,
    padding: "11px 13px",
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* ---- header ---- */}
      <div className="hachi-run-header" style={headerStyle}>
        {/* back button */}
        <button
          className="hachi-ghost-icon-btn-bg"
          onClick={onBack}
          style={backBtnStyle}
          aria-label="Back"
        >
          <Icon name="chevron-left" size={18} />
        </button>

        {/* title */}
        <h1
          style={{
            margin: 0,
            fontFamily: "var(--font-display)",
            fontWeight: 500,
            fontSize: 20,
            lineHeight: "24px",
            color: "var(--hachi-ink)",
          }}
        >
          {title}
        </h1>

        {/* status pill */}
        <span style={pillStyle}>
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: rsm.dot,
            }}
          />
          {rsm.text}
        </span>

        {/* status text */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            fontSize: 13,
            color: "var(--hachi-muted)",
          }}
        >
          <span>{statusText}</span>
        </div>

        <div style={{ flex: 1 }} />

        {/* budget */}
        <span
          style={{
            fontSize: 13,
            color: "var(--hachi-muted)",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          spent {spentStr} of {budgetStr}
        </span>

        {/* stop button */}
        {canStop && (
          <button
            className="hachi-stop-run-btn"
            onClick={stopRun}
            style={stopBtnStyle}
          >
            <Icon name="stop" size={15} />
            Stop
          </button>
        )}
      </div>

      {/* ---- body ---- */}
      <div className="hachi-run-body" style={{ flex: 1, minHeight: 0, display: "flex" }}>
        {/* ==== left panel: plan + the pack ==== */}
        <div className="hachi-scroll hachi-run-left" style={leftPanelStyle}>
          {/* Plan section — hidden in live mode when no steps are emitted */}
          {hasPlan && (
            <div>
              <div style={sectionLabelStyle}>Plan</div>
              <div style={{ display: "flex", flexDirection: "column" }}>
                {steps.map((stp, i) => (
                  <div
                    key={i}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 11,
                      padding: "9px 0",
                      borderBottom: "0.5px solid var(--hachi-line)",
                    }}
                  >
                    <span
                      style={{
                        color: stp.color,
                        display: "inline-flex",
                      }}
                    >
                      <Icon name={stp.icon} size={16} />
                    </span>
                    <span
                      style={{
                        fontSize: 14,
                        color: stp.textColor,
                      }}
                    >
                      {stp.label}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* The pack section */}
          <div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 7,
                marginBottom: 11,
              }}
            >
              <span
                style={{
                  color: "var(--hachi-trust)",
                  display: "inline-flex",
                }}
              >
                <Icon name="paw" size={15} />
              </span>
              <span style={{ fontSize: 12, color: "var(--hachi-muted)" }}>
                The pack · {packLabel}
              </span>
            </div>

            <div
              style={{ display: "flex", flexDirection: "column", gap: 8 }}
            >
              {pack.map((p) => (
                <div key={p.id} style={packCardStyle}>
                  {/* status dot */}
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: "50%",
                      background: p.dot,
                      marginTop: 5,
                      flexShrink: 0,
                    }}
                  />
                  {/* name + task */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                      }}
                    >
                      <span
                        style={{
                          fontFamily: "var(--font-mono)",
                          fontSize: 13,
                          color: "var(--hachi-ink)",
                        }}
                      >
                        {p.name}
                      </span>
                      {p.hasTokens && (
                        <span
                          style={{
                            fontSize: 11,
                            color: "var(--hachi-muted)",
                            fontVariantNumeric: "tabular-nums",
                          }}
                        >
                          {p.tokens} tok
                        </span>
                      )}
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                        color: "var(--hachi-muted)",
                        marginTop: 2,
                      }}
                    >
                      {p.task}
                    </div>
                  </div>
                  {/* status label */}
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 500,
                      color: p.statusFg,
                    }}
                  >
                    {p.statusText}
                  </span>
                </div>
              ))}
            </div>

            {/* sub-agent disclaimer */}
            <div
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 7,
                marginTop: 13,
                fontSize: 12,
                color: "var(--hachi-muted)",
                lineHeight: "18px",
              }}
            >
              <Icon name="shield" size={13} />
              <span>
                Sub-agents share your leash — they ask before anything risky
                too.
              </span>
            </div>
          </div>
        </div>

        {/* ==== right panel: live output ==== */}
        <div
          style={{
            flex: 1,
            minWidth: 0,
            display: "flex",
            flexDirection: "column",
            position: "relative",
          }}
        >
          {/* output header */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "16px 24px 12px",
              flexShrink: 0,
            }}
          >
            <span
              style={{
                color: "var(--hachi-muted)",
                display: "inline-flex",
              }}
            >
              <Icon name="terminal" size={15} />
            </span>
            <span style={{ fontSize: 13, color: "var(--hachi-muted)" }}>
              Live output
            </span>
          </div>

          {/* scrollable terminal wrapper — no overflow here; Terminal manages its own scroll */}
          <div
            className="hachi-run-output"
            style={{
              flex: 1,
              minHeight: 0,
              display: "flex",
              padding: "0 24px 24px",
            }}
          >
            <RunOutputTerminal />
          </div>

          {/* leash overlay (inline, mid-run) */}
          {hasLeash && runLeash && (
            <div
              ref={leashTrapRef}
              role="alertdialog"
              aria-modal="true"
              aria-label={runLeash.request}
              style={{
                position: "absolute",
                inset: 0,
                background: "rgba(28,26,32,0.22)",
                display: "grid",
                placeItems: "center",
                padding: 24,
                zIndex: 10,
              }}
            >
              <LeashPrompt
                request={runLeash.request}
                action={runLeash.action}
                why={runLeash.why}
                onAllowOnce={runAllowLeash}
                onAlwaysAllow={runAlwaysAllow}
                onDecline={runDenyLeash}
                style={{ width: 440, maxWidth: "100%" }}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

const RunOutputTerminal = memo(function RunOutputTerminal() {
  const runLines = useStore((s) => s.runLines);
  const runDone = useStore((s) => s.runDone);
  return (
    <Terminal
      lines={runLines}
      prompt=""
      streaming={!runDone}
      style={{ height: "100%", flex: 1 }}
    />
  );
});

// ---- Mock simulation component (mock mode only) ----

function MockRunSimulation() {
  const navigate = useNavigate();

  const runView = useStore((s) => s.runView);
  const openRun = useStore((s) => s.openRun);
  const closeRun = useStore((s) => s.closeRun);

  // If there is no active run, boot one from the first available run in the
  // store (mirrors prototype behaviour when navigating to /run directly).
  useEffect(() => {
    if (!runView) {
      openRun(undefined, "run");
    }
  }, []); // run once on mount only

  // Navigate back on closeRun (runView becomes null after close).
  // We do NOT fire this on initial mount (before the useEffect above kicks in).
  const didMountRef = useRef(false);
  useEffect(() => {
    if (!didMountRef.current) {
      didMountRef.current = true;
      return;
    }
    // runView cleared by closeRun → go back
    if (!runView) {
      navigate({ to: "/" });
    }
  }, [runView]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleBack = () => {
    closeRun();
    // Navigation is handled by the runView→null effect above.
  };

  return <RunSurface onBack={handleBack} />;
}

// ---- Live mode component ----

function LiveRun() {
  const navigate = useNavigate();
  const dataMode = useStore((s) => s.dataMode);
  const runView = useStore((s) => s.runView);
  const closeRun = useStore((s) => s.closeRun);

  if (dataMode !== "live") {
    return <MockRunSimulation />;
  }

  // Live mode: show RunSurface when a run is active/recent, else empty state.
  if (runView) {
    const handleBack = () => {
      closeRun();
      void navigate({ to: "/" });
    };
    return <RunSurface onBack={handleBack} />;
  }

  // Honest empty state — no mock bootstrapping
  const containerStyle: CSSProperties = {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    height: "100%",
    padding: 32,
    gap: 0,
  };

  const cardStyle: CSSProperties = {
    background: "var(--hachi-surface)",
    border: "0.5px solid var(--hachi-line)",
    borderRadius: 16,
    padding: "36px 40px",
    maxWidth: 520,
    width: "100%",
    display: "flex",
    flexDirection: "column",
    gap: 20,
  };

  const iconRowStyle: CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: 12,
  };

  const titleStyle: CSSProperties = {
    margin: 0,
    fontFamily: "var(--font-display)",
    fontWeight: 500,
    fontSize: 20,
    color: "var(--hachi-ink)",
  };

  const bodyStyle: CSSProperties = {
    fontSize: 14,
    color: "var(--hachi-muted)",
    lineHeight: "22px",
    margin: 0,
  };

  const chatBtnStyle: CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    height: 40,
    padding: "0 18px",
    borderRadius: 10,
    background: "var(--hachi-trust)",
    color: "#fff",
    font: "500 14px var(--font-body)",
    border: "none",
    cursor: "pointer",
    alignSelf: "flex-start",
    transition: "opacity var(--dur-fast) var(--ease)",
  };

  return (
    <div style={containerStyle}>
      <div style={cardStyle}>
        <div style={iconRowStyle}>
          <span style={{ color: "var(--hachi-working)", display: "inline-flex" }}>
            <Icon name="terminal" size={22} />
          </span>
          <h1 style={titleStyle}>No active run</h1>
        </div>

        <p style={bodyStyle}>
          Start a task in the conversation and watch Hachi work here — live
          sub-agent output, the pack, and budget as it happens.
        </p>

        <button
          className="hachi-open-conversation-btn"
          style={chatBtnStyle}
          onClick={() => void navigate({ to: "/conversation" })}
        >
          <Icon name="message-square" size={15} />
          Open conversation
        </button>
      </div>
    </div>
  );
}

export const Route = createFileRoute("/run")({
  component: LiveRun,
});
