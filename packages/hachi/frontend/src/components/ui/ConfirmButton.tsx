// ConfirmButton — arm-then-confirm for irreversible actions.
//
// First activation arms: shows confirmLabel + armed styling. A second activation
// AFTER cooldownMs confirms (fires onConfirm). Clicks within cooldownMs of arming
// are silently ignored — this defeats accidental double-clicks. The component
// auto-disarms after armWindowMs or on blur.

import React, { CSSProperties, useEffect, useRef, useState } from 'react';
import { Icon } from '../icons/Icon';

export interface ConfirmButtonProps {
  label: string;
  confirmLabel: string;
  onConfirm: () => void;
  tone?: 'danger' | 'neutral';
  armWindowMs?: number;
  cooldownMs?: number;
  icon?: string;
  ariaLabel?: string;
  style?: CSSProperties;
  className?: string;
}

export function ConfirmButton({
  label,
  confirmLabel,
  onConfirm,
  tone = 'danger',
  armWindowMs = 4000,
  cooldownMs = 400,
  icon,
  ariaLabel,
  style,
  className,
}: ConfirmButtonProps) {
  const [armed, setArmed] = useState(false);
  const armedAtRef  = useRef<number>(0);
  const disarmTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (disarmTimer.current) clearTimeout(disarmTimer.current);
  }, []);

  const disarm = () => {
    setArmed(false);
    if (disarmTimer.current) clearTimeout(disarmTimer.current);
  };

  const handleClick = () => {
    if (!armed) {
      setArmed(true);
      armedAtRef.current = Date.now();
      disarmTimer.current = setTimeout(disarm, armWindowMs);
      return;
    }
    // Cooldown: ignore fast second clicks (defeat accidental double-tap).
    if (Date.now() - armedAtRef.current < cooldownMs) return;
    disarm();
    onConfirm();
  };

  const isDanger = tone === 'danger';

  const restingBg = 'transparent';
  const armedBg   = isDanger ? 'var(--hachi-danger-tint)' : 'var(--hachi-working-tint)';
  const armedBorder = isDanger ? 'var(--hachi-danger)' : 'var(--hachi-working)';
  const armedColor  = isDanger ? 'var(--hachi-danger-fg)' : 'var(--hachi-working-fg)';

  const btnStyle: CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: icon && !armed ? 0 : 6,
    minWidth: 24,
    minHeight: 24,
    padding: icon && !armed ? '4px' : '0 10px',
    height: icon && !armed ? undefined : 32,
    borderRadius: 8,
    border: armed ? `0.5px solid ${armedBorder}` : 'none',
    background: armed ? armedBg : restingBg,
    color: armed ? armedColor : 'var(--hachi-muted)',
    font: '500 13px var(--font-body)',
    cursor: 'pointer',
    transition: 'background var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease)',
    whiteSpace: 'nowrap',
    ...style,
  };

  const ariaLabelValue = armed
    ? `${ariaLabel ?? confirmLabel} — press again to confirm`
    : (ariaLabel ?? label);

  return (
    <button
      type="button"
      className={className}
      onClick={handleClick}
      onBlur={disarm}
      aria-label={ariaLabelValue}
      aria-pressed={armed}
      style={btnStyle}
    >
      {icon && !armed ? (
        <Icon name={icon} size={15} />
      ) : (
        armed ? confirmLabel : label
      )}
    </button>
  );
}
