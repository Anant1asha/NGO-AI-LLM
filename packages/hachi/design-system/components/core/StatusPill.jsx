import React from "react";

/**
 * StatusPill — the four Hachi status states. Tinted bg + dark same-family text + dot.
 */
export function StatusPill({ status = "working", label, style = {}, ...rest }) {
  const map = {
    working: { bg: "var(--hachi-working-tint)", fg: "#A8651A", dot: "var(--hachi-working)", text: "working" },
    "on-watch": { bg: "var(--hachi-trust-tint)", fg: "var(--hachi-trust)", dot: "var(--hachi-trust)", text: "on watch" },
    done: { bg: "var(--hachi-success-tint)", fg: "#2C7A50", dot: "var(--hachi-success)", text: "done" },
    blocked: { bg: "var(--hachi-danger-tint)", fg: "#9E2D21", dot: "var(--hachi-danger)", text: "blocked" },
  };
  const s = map[status] || map.working;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        padding: "5px 12px",
        borderRadius: "var(--radius-pill)",
        background: s.bg,
        color: s.fg,
        fontFamily: "var(--font-body)",
        fontWeight: 500,
        fontSize: 13,
        lineHeight: 1,
        ...style,
      }}
      {...rest}
    >
      <span style={{ width: 7, height: 7, borderRadius: "50%", background: s.dot }} />
      {label || s.text}
    </span>
  );
}
