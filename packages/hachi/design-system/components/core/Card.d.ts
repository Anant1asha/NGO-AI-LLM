import { ReactNode, CSSProperties } from "react";

export interface CardProps {
  /** Inner padding in px. @default 24 */
  padding?: number;
  children?: ReactNode;
  style?: CSSProperties;
}

/** Flat surface container — hairline border, radius 16, no shadow. */
export function Card(props: CardProps): JSX.Element;
