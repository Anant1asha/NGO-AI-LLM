import { CSSProperties, useId } from 'react';

const VISUALLY_HIDDEN: CSSProperties = {
  position: 'absolute',
  width: 1,
  height: 1,
  margin: -1,
  padding: 0,
  overflow: 'hidden',
  clip: 'rect(0,0,0,0)',
  whiteSpace: 'nowrap',
  border: 0,
};

export interface SwitchProps {
  checked: boolean;
  onChange: (v: boolean) => void;
  label?: string;
  /** Accessible name when no visible label is provided. */
  ariaLabel?: string;
  disabled?: boolean;
}

export function Switch({ checked, onChange, label, ariaLabel, disabled = false }: SwitchProps) {
  const id = useId();

  const hitAreaStyle: CSSProperties = {
    position: 'relative',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '44px',
    height: '44px',
    margin: '-10px -2px',
    flexShrink: 0,
  };

  const trackStyle: CSSProperties = {
    position: 'relative',
    display: 'inline-block',
    width: '40px',
    height: '24px',
    borderRadius: 'var(--radius-pill)',
    background: checked ? 'var(--hachi-brand)' : 'var(--hachi-line)',
    transition: `background var(--dur-fast) var(--ease)`,
    opacity: disabled ? 0.45 : 1,
    border: '0.5px solid transparent',
    pointerEvents: 'none',
  };

  const thumbStyle: CSSProperties = {
    position: 'absolute',
    top: '3px',
    left: checked ? '19px' : '3px',
    width: '16px',
    height: '16px',
    borderRadius: '50%',
    background: 'white',
    transition: `left var(--dur-fast) var(--ease)`,
    pointerEvents: 'none',
  };

  const wrapStyle: CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 'var(--space-2)',
    cursor: disabled ? 'not-allowed' : 'pointer',
    userSelect: 'none',
  };

  const labelStyle: CSSProperties = {
    fontFamily: 'var(--font-body)',
    fontSize: 'var(--type-body-size)',
    color: disabled ? 'var(--text-muted)' : 'var(--text-default)',
  };

  return (
    <label htmlFor={id} style={wrapStyle}>
      <input
        id={id}
        type="checkbox"
        role="switch"
        checked={checked}
        onChange={(e) => !disabled && onChange(e.target.checked)}
        disabled={disabled}
        aria-label={!label ? ariaLabel : undefined}
        style={VISUALLY_HIDDEN}
      />
      <span style={hitAreaStyle} aria-hidden="true">
        <span style={trackStyle}>
          <span style={thumbStyle} />
        </span>
      </span>
      {label && <span style={labelStyle}>{label}</span>}
    </label>
  );
}
