import React, { CSSProperties } from 'react'

export interface HachiMarkProps {
  /** Pixel size (square). @default 24 */
  size?: number
  /** "default" full two-tone mark, or "knockout" one-colour silhouette in currentColor. @default "default" */
  variant?: 'default' | 'knockout'
  style?: CSSProperties
  className?: string
}

/**
 * HachiMark — the two-tone dog mark as inline SVG.
 * Never recolour the two-tone version: it is always Torii red + cream + ink.
 * `variant="knockout"` gives a one-colour silhouette in `currentColor` (16px-safe).
 *
 * Ported from design-system/components/hachi/HachiMark.jsx.
 */
export function HachiMark({
  size = 24,
  variant = 'default',
  style,
  className,
}: HachiMarkProps) {
  if (variant === 'knockout') {
    return (
      <svg
        viewBox="0 0 100 100"
        width={size}
        height={size}
        role="img"
        aria-label="Hachi"
        style={style}
        className={className}
      >
        <g transform="translate(50,52)" fill="currentColor" fillRule="evenodd">
          <path
            fillRule="evenodd"
            d="M -26 -14 C -30 4 -22 22 -9 28 C -3 32 3 32 9 28 C 22 22 30 4 26 -14 L 23 -44 L 8 -23 L -8 -23 L -23 -44 Z M -11 -7 C -8.9 -7 -7.2 -4.8 -7.2 -2 C -7.2 0.8 -8.9 3 -11 3 C -13.1 3 -14.8 0.8 -14.8 -2 C -14.8 -4.8 -13.1 -7 -11 -7 Z M 11 -7 C 13.1 -7 14.8 -4.8 14.8 -2 C 14.8 0.8 13.1 3 11 3 C 8.9 3 7.2 0.8 7.2 -2 C 7.2 -4.8 8.9 -7 11 -7 Z M -4 0 L 4 0 L 0 6 Z"
          />
        </g>
      </svg>
    )
  }

  return (
    <svg
      viewBox="0 0 100 100"
      width={size}
      height={size}
      role="img"
      aria-label="Hachi"
      style={style}
      className={className}
    >
      <g transform="translate(50,52)">
        {/* body — Torii red */}
        <path
          d="M -26 -14 C -30 4 -22 22 -9 28 C -3 32 3 32 9 28 C 22 22 30 4 26 -14 L 23 -44 L 8 -23 L -8 -23 L -23 -44 Z"
          fill="#D64933"
        />
        {/* ear inner — cream */}
        <path d="M -21 -40 L -11 -23 L -18 -23 Z" fill="#F3E9D2" />
        <path d="M 21 -40 L 11 -23 L 18 -23 Z" fill="#F3E9D2" />
        {/* face / muzzle — cream */}
        <path
          d="M -17 1 C -17 21 -7 28 0 28 C 7 28 17 21 17 1 C 9 -5 5 -8 0 -8 C -5 -8 -9 -5 -17 1 Z"
          fill="#F3E9D2"
        />
        {/* blaze (forehead stripe) — cream */}
        <path d="M -3 -8 L -2 -24 Q 0 -27 2 -24 L 3 -8 Z" fill="#F3E9D2" />
        {/* brow spots — cream */}
        <circle cx="-11" cy="-13" r="2.3" fill="#F3E9D2" />
        <circle cx="11" cy="-13" r="2.3" fill="#F3E9D2" />
        {/* eyes — ink */}
        <ellipse cx="-11" cy="-2" rx="3.8" ry="5" fill="#1C1A20" />
        <ellipse cx="11" cy="-2" rx="3.8" ry="5" fill="#1C1A20" />
        {/* nose — ink */}
        <path d="M -4 0 L 4 0 L 0 6 Z" fill="#1C1A20" />
      </g>
    </svg>
  )
}
