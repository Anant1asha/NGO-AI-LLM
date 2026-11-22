import React from "react";

/** Switch — flat toggle. On = Torii red. The leash you can flip. */
export function Switch({ checked = false, onChange, disabled = false, label, style = {} }) {
  const toggle = () => { if (!disabled) onChange?.(!checked); };
  return (
    <label style={{ display: "inline-flex", alignItems: "center", gap: 10, cursor: disabled ? "not-allowed" : "pointer", opacity: disabled ? 0.45 : 1, ...style }}>
      <span
        role="switch"
        aria-checked={checked}
        tabIndex={disabled ? -1 : 0}
        onClick={toggle}
        onKeyDown={(e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); toggle(); } }}
        style={{
          width: 40,
          height: 24,
          borderRadius: "var(--radius-pill)",
          background: checked ? "var(--hachi-brand)" : "var(--hachi-line)",
          border: "0.5px solid " + (checked ? "var(--hachi-brand)" : "var(--hachi-line)"),
          position: "relative",
          transition: "background var(--dur) var(--ease)",
          flexShrink: 0,
        }}
      >
        <span style={{
          position: "absolute",
          top: 2,
          left: checked ? 18 : 2,
          width: 18,
          height: 18,
          borderRadius: "50%",
          background: "var(--surface-card)",
          transition: "left var(--dur) var(--ease)",
        }} />
      </span>
      {label && <span style={{ font: "var(--text-body)", color: "var(--text-default)" }}>{label}</span>}
    </label>
  );
}
