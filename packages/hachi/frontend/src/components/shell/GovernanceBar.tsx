// ============================================================
// GovernanceBar — persistent status strip shown on every route.
// Shows: safety posture · spent / budget (spent-first) · connection status
// ============================================================

import { useNavigate } from "@tanstack/react-router";
import { useStore } from "../../lib/store/store";
import { fmtUSD } from "../../lib/ui/format";
import type { SafetyLevel } from "../../lib/data/types";

interface PostureMeta { label: string; dot: string; fg: string }

function postureMeta(level: SafetyLevel): PostureMeta {
  const map: Record<SafetyLevel, PostureMeta> = {
    guarded:  { label: "guarded",  dot: "var(--hachi-success)", fg: "var(--hachi-success)" },
    standard: { label: "standard", dot: "var(--hachi-trust)",   fg: "var(--hachi-trust)"   },
    open:     { label: "open",     dot: "var(--hachi-working)", fg: "var(--hachi-working)"  },
  };
  return map[level] ?? map.standard;
}

export function GovernanceBar() {
  const safety       = useStore((s) => s.safety);
  const spent        = useStore((s) => s.spent);
  const budget       = useStore((s) => s.budget);
  const reconnecting = useStore((s) => s.reconnecting);
  const operator     = useStore((s) => s.operator);
  const setWorkFilter = useStore((s) => s.setWorkFilter);
  const navigate     = useNavigate();

  const pm         = postureMeta(safety);
  const pct        = budget > 0 ? Math.min(100, (spent / budget) * 100) : 0;
  const overBudget = budget > 0 && spent > budget;

  const handleCostClick = () => {
    setWorkFilter("spend");
    void navigate({ to: "/work" as never });
  };

  return (
    <div
      className="hachi-governance-bar"
      style={{
        flexShrink: 0, height: "28px", background: "var(--hachi-canvas)",
        borderTop: "0.5px solid var(--hachi-line)", display: "flex",
        alignItems: "center", gap: "16px", padding: "0 16px",
        fontFamily: "var(--font-mono)", fontSize: "12px", color: "var(--hachi-muted)",
        userSelect: "none",
      }}
    >
      {/* Governance posture */}
      <span style={{ display: "inline-flex", alignItems: "center", gap: "5px", flexShrink: 0 }}>
        <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: pm.dot, flexShrink: 0 }} />
        <span style={{ color: pm.fg, fontWeight: 500 }}>{pm.label}</span>
      </span>

      <span style={{ width: "1px", height: "12px", background: "var(--hachi-line)", flexShrink: 0 }} />

      {/* Live cost readout — spent-first, links to Work→Spend */}
      <button
        type="button"
        onClick={handleCostClick}
        title="View spend details"
        style={{
          display: "inline-flex", alignItems: "center", gap: "6px",
          flexShrink: 0, border: "none", background: "transparent",
          cursor: "pointer", fontFamily: "var(--font-mono)", fontSize: "12px",
          padding: 0, color: "inherit",
        }}
      >
        <span
          style={{
            color: overBudget ? "var(--hachi-danger)" : "var(--hachi-ink)",
            fontWeight: 500,
            userSelect: "text",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {fmtUSD(spent)}
        </span>
        {budget > 0 && (
          <>
            <span style={{ color: "var(--hachi-muted)" }}>/ {fmtUSD(budget)} today</span>
            <span
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(pct)}
              aria-label={`Budget: ${pct.toFixed(0)}% used`}
              style={{
                display: "inline-block", width: "48px", height: "3px",
                borderRadius: "999px", background: "var(--hachi-line)",
                overflow: "hidden", flexShrink: 0,
              }}
            >
              <span
                style={{
                  display: "block", width: `${pct}%`, height: "100%",
                  background: overBudget ? "var(--hachi-danger)" : "var(--hachi-brand)",
                  borderRadius: "999px", transition: "width 0.3s ease",
                }}
              />
            </span>
          </>
        )}
      </button>

      {operator && (
        <>
          <span style={{ width: "1px", height: "12px", background: "var(--hachi-line)", flexShrink: 0 }} />
          <span style={{ color: "var(--hachi-muted)", flexShrink: 0 }}>operator</span>
        </>
      )}

      <span style={{ flex: 1 }} />

      {/* Connection status */}
      <span style={{ display: "inline-flex", alignItems: "center", gap: "5px", flexShrink: 0 }}>
        {reconnecting ? (
          <>
            <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "var(--hachi-working)", flexShrink: 0, animation: "hachi-pulse 1.2s ease-in-out infinite" }} />
            <span style={{ color: "var(--hachi-working)" }}>reconnecting</span>
          </>
        ) : (
          <>
            <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "var(--hachi-success)", flexShrink: 0 }} />
            <span>connected</span>
          </>
        )}
      </span>
    </div>
  );
}
