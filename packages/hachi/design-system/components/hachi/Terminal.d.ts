import { CSSProperties } from "react";

export interface TerminalLine {
  text: string;
  /** Tints the line. @default "default" */
  tone?: "default" | "muted" | "brand" | "working" | "success" | "danger";
}

/**
 * @startingPoint section="Hachi" subtitle="Terminal surface — the hachi ▸ prompt" viewport="700x260"
 */
export interface TerminalProps {
  lines?: TerminalLine[];
  /** Text shown after the red "hachi ▸" prompt. */
  prompt?: string;
  style?: CSSProperties;
}

/** Dark mono terminal surface with the red "hachi ▸" prompt and blinking caret. */
export function Terminal(props: TerminalProps): JSX.Element;
