import { CSSProperties } from 'react';

export interface LoyalLoopProps {
  size?: number;
  /** Accessible label for the spinner. Defaults to "Hachi is working". */
  label?: string;
}

/**
 * The Hachi figure-8 / infinity loyalty spinner.
 * Path traces the "8 = ∞ = always on" motif in Torii red.
 * Animates stroke-dashoffset via the `hachi-loop-dash` keyframe from motion.css.
 * Respects prefers-reduced-motion.
 */
export function LoyalLoop({ size = 48, label = 'Hachi is working' }: LoyalLoopProps) {
  // The path follows the hachi-loop.svg geometry (viewBox 0 0 100 56, translated +11,0)
  // Stroke length ~240 (matching the keyframe `to { stroke-dashoffset: -240 }`)
  const strokeWidth = 9;
  const pathD = 'M 39 28 C 39 16 23 16 23 28 C 23 40 39 40 49 28 C 59 16 75 16 75 28 C 75 40 59 40 49 28 Z';

  const svgStyle: CSSProperties = {
    display: 'block',
    overflow: 'visible',
  };

  // The animation uses CSS keyframe `hachi-loop-dash` defined in motion.css
  // dasharray ~240, dashoffset animates from 0 to -240
  const pathStyle: CSSProperties = {
    strokeDasharray: 240,
    strokeDashoffset: 0,
    // Reduced-motion: animation paused via media query utility class on parent, or inline:
    animation: 'hachi-loop-dash 1.6s linear infinite',
  };

  // Scale the 100x56 viewBox to requested size
  // Maintain aspect ratio: 100/56 ≈ 1.786
  const width = size * (100 / 56);
  const height = size;

  return (
    <svg
      viewBox="0 0 100 56"
      width={width}
      height={height}
      role="img"
      aria-label={label}
      style={svgStyle}
    >
      <style>{`
        @media (prefers-reduced-motion: reduce) {
          .hachi-loop-path { animation: none !important; }
        }
      `}</style>
      <path
        className="hachi-loop-path"
        d={pathD}
        fill="none"
        stroke="var(--hachi-brand)"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        style={pathStyle}
      />
    </svg>
  );
}
