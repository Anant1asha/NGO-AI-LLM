import React from "react";

/** Card — surface on canvas, 0.5px hairline, radius 16, flat (no shadow). */
export function Card({ padding = 24, style = {}, children, ...rest }) {
  return (
    <div
      style={{
        background: "var(--surface-card)",
        border: "0.5px solid var(--hachi-line)",
        borderRadius: "var(--radius-lg)",
        padding,
        ...style,
      }}
      {...rest}
    >
      {children}
    </div>
  );
}
