import { CSSProperties } from "react";

/**
 * @startingPoint section="Hachi" subtitle="Task run card with live budget" viewport="700x180"
 */
export interface RunCardProps {
  title?: string;
  status?: "working" | "on-watch" | "done" | "blocked";
  /** 0..1 progress for the thin red bar. @default 0.4 */
  progress?: number;
  /** Dollars spent so far. @default 0.02 */
  spent?: number;
  /** Budget cap in dollars. @default 1.0 */
  budget?: number;
  /** Override the left meta line (defaults to "{pct}% complete"). */
  meta?: string;
  onClick?: () => void;
  style?: CSSProperties;
}

/** A running task — status pill, thin red progress bar, always-visible budget. */
export function RunCard(props: RunCardProps): JSX.Element;
