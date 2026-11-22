import { CSSProperties } from "react";

export interface SwitchProps {
  checked?: boolean;
  onChange?: (next: boolean) => void;
  disabled?: boolean;
  label?: string;
  style?: CSSProperties;
}

/** Flat toggle — on-state is Torii red. */
export function Switch(props: SwitchProps): JSX.Element;
