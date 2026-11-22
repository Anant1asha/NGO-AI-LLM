import { ReactNode, CSSProperties } from "react";

/**
 * @startingPoint section="Core" subtitle="Primary / secondary / ghost / danger actions" viewport="700x140"
 */
export interface ButtonProps {
  /** Visual style. Torii red only on `primary`. @default "primary" */
  variant?: "primary" | "secondary" | "ghost" | "danger";
  /** @default "md" */
  size?: "sm" | "md";
  /** Optional leading icon (e.g. a Lucide <svg>). */
  icon?: ReactNode;
  disabled?: boolean;
  type?: "button" | "submit" | "reset";
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
  children?: ReactNode;
  style?: CSSProperties;
}

/** Primary action button. Sentence case labels only. */
export function Button(props: ButtonProps): JSX.Element;
