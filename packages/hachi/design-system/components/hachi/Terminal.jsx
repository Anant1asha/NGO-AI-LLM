import React from "react";

/**
 * Terminal — the dark mono surface with the red "hachi ▸" prompt.
 * `lines` is an array of { text, tone? } where tone tints the line.
 */
export function Terminal({ lines = [], prompt = "run build --watch", style = {} }) {
  const toneColor = {
    muted: "#9C968C",
    brand: "#E25A44",
    working: "#E0922E",
    success: "#3F9D6B",
    danger: "#E05D4C",
    default: "#FBF7EF",
  };
  return (
    <div style={{
      background: "#16151A",
      borderRadius: "var(--radius-lg)",
      padding: 20,
      fontFamily: "var(--font-mono)",
      fontSize: 13,
      lineHeight: "22px",
      color: "#FBF7EF",
      ...style,
    }}>
      {lines.map((l, i) => (
        <div key={i} style={{ color: toneColor[l.tone] || toneColor.default, whiteSpace: "pre-wrap" }}>
          {l.text}
        </div>
      ))}
      <div style={{ display: "flex", gap: 8 }}>
        <span style={{ color: "#E25A44", flexShrink: 0 }}>hachi&nbsp;▸</span>
        <span style={{ color: "#FBF7EF" }}>{prompt}</span>
        <span style={{
          width: 8, height: 16, background: "#E25A44", display: "inline-block",
          animation: "hachi-caret 1s steps(1) infinite", marginLeft: 1,
        }} />
      </div>
      <style>{`@keyframes hachi-caret{50%{opacity:0}}`}</style>
    </div>
  );
}
