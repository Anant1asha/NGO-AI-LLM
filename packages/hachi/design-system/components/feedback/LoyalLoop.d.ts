import { CSSProperties } from "react";

export interface LoyalLoopProps {
  /** Width in px (height is 0.6×). @default 48 */
  size?: number;
  /** Stroke color. @default Torii red */
  color?: string;
  /** Animation duration in seconds. @default 1.4 */
  speed?: number;
  style?: CSSProperties;
}

/** The loyal loop — Hachi's infinity/figure-8 loading spinner in Torii red. */
export function LoyalLoop(props: LoyalLoopProps): JSX.Element;
