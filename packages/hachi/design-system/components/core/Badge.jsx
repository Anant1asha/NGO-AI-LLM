import React from "react";

/** Badge — small count / meta chip. Subtle by default; `tone` for emphasis. */
export function Badge({ tone = "neutral", style = {}, children, ...rest }) {
  const tones = {
    neutral: { bg: "var(--hachi-cream)", fg: "var(--text-muted)" },
    brand: { bg: "var(--hachi-brand-tint)", fg: "var(--hachi-brand-hover)" },
    navy: { bg: "var(--hachi-trust-tint)", fg: "var(--hachi-trust)" },
  };
  const t = tones[tone] || tones.neutral;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        padding: "2px 8px",
        borderRadius: "var(--radius-sm)",
        background: t.bg,
        color: t.fg,
        fontFamily: "var(--font-body)",
        fontWeight: 500,
        fontSize: 12,
        lineHeight: 1.5,
        ...style,
      }}
      {...rest}
    >
      {children}
    </span>
  );
}
