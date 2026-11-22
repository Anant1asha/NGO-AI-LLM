import React from "react";

/**
 * Hachi Button — sentence case, radius 10, flat. Torii red used only for `primary`.
 */
export function Button({
  variant = "primary",
  size = "md",
  icon = null,
  disabled = false,
  type = "button",
  onClick,
  children,
  style = {},
  ...rest
}) {
  const sizes = {
    sm: { padding: "0 12px", height: 32, fontSize: 13 },
    md: { padding: "0 16px", height: 40, fontSize: 14 },
  };

  const variants = {
    primary: {
      background: "var(--hachi-brand)",
      color: "var(--text-on-brand)",
      border: "0.5px solid transparent",
    },
    secondary: {
      background: "transparent",
      color: "var(--hachi-trust)",
      border: "1px solid var(--hachi-trust)",
    },
    ghost: {
      background: "transparent",
      color: "var(--text-muted)",
      border: "0.5px solid transparent",
    },
    danger: {
      background: "var(--hachi-danger)",
      color: "#FBF7EF",
      border: "0.5px solid transparent",
    },
  };

  const base = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    fontFamily: "var(--font-body)",
    fontWeight: 500,
    lineHeight: 1,
    borderRadius: "var(--radius-md)",
    cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.45 : 1,
    transition: "background var(--dur) var(--ease), color var(--dur) var(--ease), border-color var(--dur) var(--ease)",
    whiteSpace: "nowrap",
    ...sizes[size],
    ...variants[variant],
    ...style,
  };

  const hoverBg = {
    primary: "var(--hachi-brand-hover)",
    secondary: "var(--hachi-trust-tint)",
    ghost: "var(--hachi-cream)",
    danger: "#A93226",
  }[variant];

  const onEnter = (e) => { if (!disabled) e.currentTarget.style.background = hoverBg; };
  const onLeave = (e) => { if (!disabled) e.currentTarget.style.background = variants[variant].background; };

  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      style={base}
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
      {...rest}
    >
      {icon}
      {children}
    </button>
  );
}
