import { ReactNode, CSSProperties } from "react";

export interface BadgeProps {
  /** @default "neutral" */
  tone?: "neutral" | "brand" | "navy";
  children?: ReactNode;
  style?: CSSProperties;
}

/** Small count/meta chip — cream by default. */
export function Badge(props: BadgeProps): JSX.Element;
