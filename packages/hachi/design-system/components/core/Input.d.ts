import { CSSProperties, InputHTMLAttributes } from "react";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  /** Render value in JetBrains Mono (paths, commands). @default false */
  mono?: boolean;
  style?: CSSProperties;
}

/** Text input — cream-white surface, hairline border, Torii-red focus ring. */
export function Input(props: InputProps): JSX.Element;
