import { CSSProperties, ReactNode, AriaAttributes, forwardRef } from 'react';
import { LoyalLoop } from './LoyalLoop';

export interface ButtonProps extends AriaAttributes {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'md' | 'lg';
  type?: 'button' | 'submit' | 'reset';
  onClick?: () => void;
  disabled?: boolean;
  loading?: boolean;
  className?: string;
  children?: ReactNode;
  style?: CSSProperties;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button({
  variant = 'primary',
  size = 'md',
  type = 'button',
  onClick,
  disabled = false,
  loading = false,
  className,
  children,
  style,
  ...ariaProps
}, ref) {
  const isDisabled = disabled || loading;
  const height = size === 'lg' ? '44px' : '40px';
  const px = size === 'lg' ? 'var(--space-5)' : 'var(--space-4)';

  const variantClass = `hachi-btn-${variant}`;

  const variantStyles: CSSProperties = (() => {
    switch (variant) {
      case 'primary':
        return { color: 'var(--hachi-canvas)', border: 'none' };
      case 'secondary':
        return { color: 'var(--hachi-trust)', border: '0.5px solid var(--hachi-trust)' };
      case 'ghost':
        return { border: 'none' };
      case 'danger':
        return { color: 'var(--hachi-canvas)', border: 'none' };
    }
  })();

  const disabledStyles: CSSProperties = isDisabled
    ? { opacity: 0.45, cursor: 'not-allowed', pointerEvents: 'none' }
    : { cursor: 'pointer' };

  const baseStyles: CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 'var(--space-2)',
    height,
    padding: `0 ${px}`,
    borderRadius: 'var(--radius-md)',
    fontFamily: 'var(--font-body)',
    fontSize: 'var(--type-body-size)',
    fontWeight: 'var(--weight-medium)' as CSSProperties['fontWeight'],
    lineHeight: 1,
    letterSpacing: 0,
    transition: `background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease)`,
    whiteSpace: 'nowrap',
    userSelect: 'none',
    ...variantStyles,
    ...disabledStyles,
    ...style,
  };

  return (
    <button
      ref={ref}
      type={type}
      className={[variantClass, className].filter(Boolean).join(' ')}
      onClick={onClick}
      disabled={isDisabled}
      aria-disabled={isDisabled || undefined}
      aria-busy={loading || undefined}
      style={baseStyles}
      {...ariaProps}
    >
      {loading ? <LoyalLoop size={14} label="Loading…" /> : children}
    </button>
  );
});
