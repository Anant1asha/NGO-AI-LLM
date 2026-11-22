import { CSSProperties } from "react";

export interface HachiMarkProps {
  /** Pixel size (square). @default 40 */
  size?: number;
  /** "two-tone" full mascot, or "knockout" one-colour silhouette in currentColor. @default "two-tone" */
  variant?: "two-tone" | "knockout";
  style?: CSSProperties;
}

/** The Hachi mascot mark, inline. Never recolour the two-tone version. */
export function HachiMark(props: HachiMarkProps): JSX.Element;
