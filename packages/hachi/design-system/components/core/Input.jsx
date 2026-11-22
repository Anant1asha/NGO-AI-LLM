import React from "react";

/** Input — cream-white surface, hairline border, red focus ring. Optional label. */
export function Input({ label, hint, mono = false, style = {}, id, ...rest }) {
  const inputId = id || (label ? `in-${label.replace(/\s+/g, "-").toLowerCase()}` : undefined);
  const [focus, setFocus] = React.useState(false);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {label && (
        <label htmlFor={inputId} style={{ font: "var(--text-small)", color: "var(--text-default)", fontWeight: 500 }}>
          {label}
        </label>
      )}
      <input
        id={inputId}
        onFocus={(e) => { setFocus(true); rest.onFocus?.(e); }}
        onBlur={(e) => { setFocus(false); rest.onBlur?.(e); }}
        style={{
          height: 40,
          padding: "0 12px",
          background: "var(--surface-card)",
          color: "var(--text-default)",
          fontFamily: mono ? "var(--font-mono)" : "var(--font-body)",
          fontSize: mono ? 13 : 14,
          border: focus ? "1px solid var(--hachi-brand)" : "0.5px solid var(--hachi-line)",
          borderRadius: "var(--radius-md)",
          boxShadow: focus ? "0 0 0 3px var(--hachi-brand-tint)" : "none",
          outline: "none",
          transition: "border-color var(--dur) var(--ease), box-shadow var(--dur) var(--ease)",
          ...style,
        }}
        {...rest}
      />
      {hint && <span style={{ font: "var(--text-small)", color: "var(--text-muted)" }}>{hint}</span>}
    </div>
  );
}
