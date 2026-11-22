import { CSSProperties } from "react";

/**
 * @startingPoint section="Core" subtitle="working · on watch · done · blocked" viewport="700x120"
 */
export interface StatusPillProps {
  /** @default "working" */
  status?: "working" | "on-watch" | "done" | "blocked";
  /** Override the default label text for the status. */
  label?: string;
  style?: CSSProperties;
}

/** The four Hachi status states as a tinted pill. */
export function StatusPill(props: StatusPillProps): JSX.Element;
