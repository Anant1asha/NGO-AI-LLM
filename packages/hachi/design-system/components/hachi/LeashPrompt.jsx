import React from "react";
import { HachiMark } from "./HachiMark.jsx";
import { Button } from "../core/Button.jsx";

/**
 * LeashPrompt — Hachi's signature permission card. Calm, plain-language, never an error.
 * Dog icon + plain request + exact action (mono) + one-line "why" + three choices.
 * Caption: "you hold the leash".
 */
export function LeashPrompt({
  request = "Hachi wants to run a command",
  action = "npm install",
  why = "Install the dependencies for your build",
  onDeny,
  onAllowOnce,
  onAlwaysAllow,
  style = {},
}) {
  return (
    <div
      role="dialog"
      aria-label={request}
      style={{
        width: 420,
        maxWidth: "100%",
        background: "var(--surface-card)",
        border: "0.5px solid var(--hachi-line)",
        borderRadius: "var(--radius-lg)",
        padding: 24,
        display: "flex",
        flexDirection: "column",
        gap: 16,
        ...style,
      }}
    >
      <div style={{ display: "flex", gap: 14, alignItems: "flex-start" }}>
        <div style={{
          flexShrink: 0,
          width: 48, height: 48,
          borderRadius: "var(--radius-md)",
          background: "var(--hachi-cream)",
          display: "grid", placeItems: "center",
        }}>
          <HachiMark size={34} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4, paddingTop: 2 }}>
          <div style={{ font: "var(--text-heading)", fontSize: 18, lineHeight: "24px", color: "var(--text-default)" }}>
            {request}
          </div>
          <div style={{ font: "var(--text-small)", color: "var(--text-muted)" }}>
            why: {why}
          </div>
        </div>
      </div>

      <div style={{
        background: "var(--hachi-cream)",
        border: "0.5px solid var(--hachi-line)",
        borderRadius: "var(--radius-md)",
        padding: "12px 14px",
        fontFamily: "var(--font-mono)",
        fontSize: 13,
        lineHeight: "22px",
        color: "var(--text-default)",
        wordBreak: "break-word",
      }}>
        <span style={{ color: "var(--hachi-brand)" }}>hachi&nbsp;▸</span> {action}
      </div>

      <div style={{ display: "flex", gap: 8 }}>
        <Button variant="secondary" size="md" onClick={onDeny} style={{ flex: 1 }}>Deny</Button>
        <Button variant="primary" size="md" onClick={onAllowOnce} style={{ flex: 1 }}>Allow once</Button>
        <Button variant="ghost" size="md" onClick={onAlwaysAllow} style={{ flex: 1 }}>Always allow</Button>
      </div>

      <div style={{
        display: "flex", alignItems: "center", gap: 8,
        font: "var(--text-small)", color: "var(--text-muted)",
        borderTop: "0.5px solid var(--hachi-line)", paddingTop: 12,
      }}>
        <HachiMark size={16} variant="knockout" style={{ color: "var(--hachi-muted)" }} />
        you hold the leash
      </div>
    </div>
  );
}
