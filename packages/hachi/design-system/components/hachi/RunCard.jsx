import React from "react";
import { StatusPill } from "../core/StatusPill.jsx";

/**
 * RunCard — a task with status, thin red progress bar, and always-visible budget.
 * Cost is a feature, not a setting to hide.
 */
export function RunCard({
  title = "Refactor auth module",
  status = "working",
  progress = 0.4,
  spent = 0.02,
  budget = 1.0,
  meta,
  style = {},
  onClick,
}) {
  const pct = Math.max(0, Math.min(1, progress));
  const money = (n) => "$" + n.toFixed(2);
  return (
    <div
      onClick={onClick}
      style={{
        background: "var(--surface-card)",
        border: "0.5px solid var(--hachi-line)",
        borderRadius: "var(--radius-lg)",
        padding: 20,
        display: "flex",
        flexDirection: "column",
        gap: 14,
        cursor: onClick ? "pointer" : "default",
        ...style,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <div style={{ font: "var(--text-heading)", fontSize: 17, lineHeight: "22px", color: "var(--text-default)" }}>
          {title}
        </div>
        <StatusPill status={status} />
      </div>

      <div style={{ height: 4, borderRadius: 999, background: "var(--hachi-line)", overflow: "hidden" }}>
        <div style={{
          width: (pct * 100) + "%",
          height: "100%",
          background: "var(--hachi-brand)",
          borderRadius: 999,
          transition: "width var(--dur-slow) var(--ease)",
        }} />
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", font: "var(--text-small)", color: "var(--text-muted)" }}>
        <span>{meta || `${Math.round(pct * 100)}% complete`}</span>
        <span>spent {money(spent)} of {money(budget)}</span>
      </div>
    </div>
  );
}
