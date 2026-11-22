import React from "react";

/**
 * LoyalLoop — the loading spinner. A figure-8 / infinity in Torii red.
 * 8 = ∞ = always on; "hachi" means eight.
 */
export function LoyalLoop({ size = 48, color = "var(--hachi-brand)", speed = 1.4, style = {} }) {
  const w = size;
  const h = size * 0.6;
  return (
    <svg viewBox="0 0 100 56" width={w} height={h} role="img" aria-label="Loading" style={style}>
      <path
        d="M 39 28 C 39 16 23 16 23 28 C 23 40 39 40 49 28 C 59 16 75 16 75 28 C 75 40 59 40 49 28 Z"
        fill="none"
        stroke={color}
        strokeWidth="9"
        strokeLinecap="round"
        strokeDasharray="60 180"
        style={{ animation: `hachi-loop-dash ${speed}s linear infinite` }}
      />
    </svg>
  );
}
