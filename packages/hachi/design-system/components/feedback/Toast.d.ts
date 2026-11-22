import { CSSProperties } from "react";

export interface ToastProps {
  /** Message in Hachi's voice. @default "Task complete — Hachi is resting" */
  message?: string;
  /** @default "success" */
  tone?: "success" | "working" | "blocked";
  style?: CSSProperties;
}

/** Pill notification in Hachi's voice — success check by default. */
export function Toast(props: ToastProps): JSX.Element;
