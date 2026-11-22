import React from "react";

/**
 * Toast — a pill notification in Hachi's voice. Default tone "success" with a check.
 * e.g. "Task complete — Hachi is resting".
 */
export function Toast({ message = "Task complete — Hachi is resting", tone = "success", style = {} }) {
  const tones = {
    success: { dot: "var(--hachi-success)", glyph: "✓" },
    working: { dot: "var(--hachi-working)", glyph: "•" },
    blocked: { dot: "var(--hachi-danger)", glyph: "!" },
  };
  const t = tones[tone] || tones.success;
  return (
    <div style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 10,
      background: "var(--surface-card)",
      border: "0.5px solid var(--hachi-line)",
      borderRadius: "var(--radius-pill)",
      padding: "10px 18px 10px 12px",
      boxShadow: "0 4px 16px rgba(28,26,32,0.08)",
      ...style,
    }}>
      <span style={{
        width: 22, height: 22, borderRadius: "50%",
        background: t.dot, color: "#FBF7EF",
        display: "grid", placeItems: "center",
        fontSize: 13, fontWeight: 500, flexShrink: 0,
      }}>{t.glyph}</span>
      <span style={{ font: "var(--text-body)", fontSize: 14, color: "var(--text-default)" }}>{message}</span>
    </div>
  );
}
