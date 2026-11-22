import { CSSProperties, useId, useState } from 'react';

export interface InputProps {
  value?: string;
  onChange?: (v: string) => void;
  placeholder?: string;
  label?: string;
  mono?: boolean;
  type?: string;
  style?: CSSProperties;
  id?: string;
  'aria-label'?: string;
  /** Validation/error message. Renders a role="alert" slot below the input,
   *  sets aria-invalid + aria-describedby, and switches the border to danger. */
  error?: string;
  /** Non-error helper text rendered below the input (ignored while `error` is set). */
  helperText?: string;
  required?: boolean;
  disabled?: boolean;
}

export function Input({
  value,
  onChange,
  placeholder,
  label,
  mono = false,
  type = 'text',
  style,
  id,
  'aria-label': ariaLabel,
  error,
  helperText,
  required = false,
  disabled = false,
}: InputProps) {
  const [focused, setFocused] = useState(false);
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const errorId = `${inputId}-error`;
  const helperId = `${inputId}-helper`;
  const hasError = Boolean(error);

  const wrapStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--space-1)',
    ...style,
  };

  const labelStyle: CSSProperties = {
    font: 'var(--text-small)',
    color: 'var(--text-muted)',
    fontWeight: 'var(--weight-medium)' as CSSProperties['fontWeight'],
  };

  const borderColor = hasError
    ? 'var(--hachi-danger)'
    : focused
    ? 'var(--hachi-brand)'
    : 'var(--hachi-line)';

  const inputStyle: CSSProperties = {
    height: '40px',
    padding: '0 var(--space-3)',
    borderRadius: 'var(--radius-md)',
    background: disabled ? 'var(--hachi-cream)' : 'var(--hachi-surface)',
    border: `0.5px solid ${borderColor}`,
    outline: focused ? `2px solid ${hasError ? 'var(--hachi-danger-tint)' : 'var(--hachi-brand-tint)'}` : 'none',
    outlineOffset: '2px',
    font: mono ? 'var(--text-mono)' : 'var(--text-body)',
    color: 'var(--text-default)',
    width: '100%',
    boxSizing: 'border-box',
    opacity: disabled ? 0.6 : 1,
    cursor: disabled ? 'not-allowed' : 'text',
    transition: `border-color var(--dur-fast) var(--ease), outline-color var(--dur-fast) var(--ease)`,
  };

  const describedBy = hasError ? errorId : helperText ? helperId : undefined;

  return (
    <div style={wrapStyle}>
      {label && (
        <label htmlFor={inputId} style={labelStyle}>
          {label}
          {required && (
            <span aria-hidden="true" style={{ color: 'var(--hachi-danger)' }}>
              {' '}*
            </span>
          )}
        </label>
      )}
      <input
        id={inputId}
        type={type}
        value={value}
        onChange={e => onChange?.(e.target.value)}
        placeholder={placeholder}
        style={inputStyle}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        aria-label={!label ? ariaLabel : undefined}
        required={required}
        disabled={disabled}
        aria-invalid={hasError}
        aria-describedby={describedBy}
      />
      {hasError ? (
        <span id={errorId} role="alert" style={{ font: 'var(--text-small)', color: 'var(--hachi-danger)' }}>
          {error}
        </span>
      ) : helperText ? (
        <span id={helperId} style={{ font: 'var(--text-small)', color: 'var(--text-muted)' }}>
          {helperText}
        </span>
      ) : null}
    </div>
  );
}
