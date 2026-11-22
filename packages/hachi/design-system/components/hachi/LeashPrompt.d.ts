import { CSSProperties } from "react";

/**
 * @startingPoint section="Hachi" subtitle="The signature leash permission prompt" viewport="700x360"
 */
export interface LeashPromptProps {
  /** Plain-language request headline. @default "Hachi wants to run a command" */
  request?: string;
  /** The exact action, shown verbatim in mono. */
  action?: string;
  /** One-line reason, rendered after "why:". */
  why?: string;
  onDeny?: () => void;
  onAllowOnce?: () => void;
  onAlwaysAllow?: () => void;
  style?: CSSProperties;
}

/** Hachi's signature permission prompt — calm, plain-language, never an error. */
export function LeashPrompt(props: LeashPromptProps): JSX.Element;
