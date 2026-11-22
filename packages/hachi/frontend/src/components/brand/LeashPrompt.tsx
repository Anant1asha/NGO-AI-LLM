import React, { useState, useEffect, CSSProperties } from 'react'
import { HachiMark } from './HachiMark'
import { ConfirmButton } from '../ui/ConfirmButton'

/** localStorage key — suppress leash explanation after first interaction. */
const LEASH_EXPLAIN_KEY = 'hachi.leash-explain-dismissed'

export interface LeashPromptProps {
  /** Plain-language request headline, e.g. "Hachi wants to run a command". */
  request: string
  /** One-line reason rendered after "why:". */
  why: string
  /** The exact action shown verbatim in mono (e.g. "npm install"). Optional. */
  action?: string
  /** Risk qualifier appended in muted text, e.g. "writes outside workspace". Optional. */
  riskNote?: string
  /** Risk pill badge: label + fg/bg colors (from riskMeta). Drives button weighting when label === 'high risk'. */
  riskPill?: { label: string; fg: string; bg: string }
  /** Files/paths this action touches — rendered as mono chips. */
  touches?: string[]
  /** Called when user taps "Allow once". */
  onAllowOnce: () => void
  /** Called when user taps "Always allow". */
  onAlwaysAllow: () => void
  /** Called when user taps "Decline". */
  onDecline: () => void
  /**
   * Pre-formatted countdown label (e.g. "1m 30s" from useCountdown().label).
   * null → render "no auto-decline — Hachi waits until you decide".
   * undefined → omit the countdown row entirely.
   */
  countdown?: string | null
  /** Progress bar for timed approvals: 0–100 percent remaining + bar color. */
  countdownBar?: { pct: number; color: string }
  /** data-testid for the header region (for regression tests). */
  headerTestId?: string
  /** data-testid for the action-buttons region (for regression tests). */
  actionsTestId?: string
  style?: CSSProperties
}

/**
 * LeashPrompt — Hachi's signature calm permission card.
 *
 * Never looks like an error. Always a matter-of-fact question.
 * The caption "you hold the leash" anchors user control at the bottom.
 *
 * Button order (left→right): Decline · Allow once · Always allow.
 * Button weighting (T10):
 *   low/medium: Decline and Allow once both outlined — neither is dominant.
 *   high: Decline is SOLID trust (the safe default is visually dominant).
 * "Always allow" is always the quiet ghost third option (arm-then-confirm).
 *
 * Ported from design-system/components/hachi/LeashPrompt.jsx + contract §5.
 */
export function LeashPrompt({
  request,
  why,
  action,
  riskNote,
  riskPill,
  touches,
  onAllowOnce,
  onAlwaysAllow,
  onDecline,
  countdown,
  countdownBar,
  headerTestId,
  actionsTestId,
  style,
}: LeashPromptProps) {
  const isHighRisk = riskPill?.label === 'high risk'

  const [showExplain, setShowExplain] = useState<boolean>(
    () => localStorage.getItem(LEASH_EXPLAIN_KEY) !== '1'
  )

  // Reset explanation visibility when a new prompt is presented (request changes while mounted).
  useEffect(() => {
    setShowExplain(localStorage.getItem(LEASH_EXPLAIN_KEY) !== '1')
  }, [request])

  /**
   * Mark explanation as seen.
   * localStorage.setItem can throw in Safari private browsing (QuotaExceededError);
   * we swallow the error so the downstream action callback always fires.
   */
  const markSeen = () => {
    try {
      localStorage.setItem(LEASH_EXPLAIN_KEY, '1')
    } catch {
      // Storage unavailable (e.g. private browsing quota) — continue without persisting.
    }
    setShowExplain(false)
  }

  const handleAllowOnce = () => { markSeen(); onAllowOnce() }
  const handleDecline = () => { markSeen(); onDecline() }

  return (
    <div
      role="group"
      aria-label={request}
      style={{
        width: 420,
        maxWidth: '100%',
        background: 'var(--surface-card, var(--hachi-surface, #FFFDF8))',
        border: '0.5px solid var(--border-hairline, var(--hachi-line, #E2D9C9))',
        borderRadius: 'var(--radius-lg, 16px)',
        padding: 24,
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
        ...style,
      }}
    >
      {/* Header row: mark avatar + request + risk pill + why */}
      <div data-testid={headerTestId} style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
        <div
          style={{
            flexShrink: 0,
            width: 48,
            height: 48,
            borderRadius: 'var(--radius-md, 10px)',
            background: 'var(--surface-cream, var(--hachi-cream, #F3E9D2))',
            display: 'grid',
            placeItems: 'center',
          }}
        >
          <HachiMark size={34} />
        </div>
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
            paddingTop: 2,
            minWidth: 0,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <span
              style={{
                fontFamily: 'var(--font-body, Inter, system-ui, sans-serif)',
                fontSize: 17,
                fontWeight: 500,
                lineHeight: '24px',
                color: 'var(--text-default, var(--hachi-ink, #1C1A20))',
              }}
            >
              {request}
            </span>
            {riskPill && (
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  padding: '3px 9px',
                  borderRadius: 999,
                  background: riskPill.bg,
                  color: riskPill.fg,
                  fontSize: 12,
                  fontWeight: 500,
                  fontFamily: 'var(--font-body, Inter, system-ui, sans-serif)',
                  flexShrink: 0,
                }}
              >
                {riskPill.label}
              </span>
            )}
          </div>
          <div
            style={{
              fontFamily: 'var(--font-body, Inter, system-ui, sans-serif)',
              fontSize: 13,
              lineHeight: '20px',
              color: 'var(--text-muted, var(--hachi-muted, #696460))',
            }}
          >
            why: {why}
          </div>
        </div>
      </div>

      {/* Leash explanation — shown once on first encounter, suppressed after any interaction */}
      {showExplain && (
        <div
          style={{
            fontSize: 12,
            lineHeight: '18px',
            fontFamily: 'var(--font-body, Inter, system-ui, sans-serif)',
            color: 'var(--text-muted, var(--hachi-muted, #696460))',
            background: 'var(--hachi-trust-tint, #E4EAF3)',
            borderRadius: 'var(--radius-md, 10px)',
            padding: '8px 12px',
          }}
        >
          The leash keeps you in control — Hachi stops here for any risky or
          irreversible action and waits for your decision before proceeding.
        </div>
      )}

      {/* Action block (mono) — only rendered when action is provided */}
      {action && (
        <div
          style={{
            background: 'var(--surface-cream, var(--hachi-cream, #F3E9D2))',
            border: '0.5px solid var(--border-hairline, var(--hachi-line, #E2D9C9))',
            borderRadius: 'var(--radius-md, 10px)',
            padding: '12px 14px',
            fontFamily: 'var(--font-mono, JetBrains Mono, monospace)',
            fontSize: 13,
            lineHeight: '22px',
            color: 'var(--text-default, var(--hachi-ink, #1C1A20))',
            wordBreak: 'break-word',
          }}
        >
          <span style={{ color: 'var(--hachi-brand, #C94230)' }}>
            {'hachi ▸'}
          </span>{' '}
          {action}
        </div>
      )}

      {/* What this touches — file chips */}
      {touches && touches.length > 0 && (
        <div>
          <div
            style={{
              fontSize: 12,
              color: 'var(--text-muted, var(--hachi-muted, #696460))',
              marginBottom: 8,
              fontFamily: 'var(--font-body, Inter, system-ui, sans-serif)',
            }}
          >
            What this touches
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
            {touches.map((f, i) => (
              <span
                key={i}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '6px 10px',
                  borderRadius: 8,
                  background: 'var(--hachi-canvas)',
                  border: '0.5px solid var(--hachi-line)',
                  fontFamily: 'var(--font-mono, JetBrains Mono, monospace)',
                  fontSize: 12,
                  color: 'var(--hachi-ink)',
                }}
              >
                {f}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Risk note — muted text qualifier, e.g. "writes outside workspace" */}
      {riskNote && (
        <div
          style={{
            fontSize: 12,
            lineHeight: '18px',
            fontFamily: 'var(--font-body, Inter, system-ui, sans-serif)',
            color: 'var(--text-muted, var(--hachi-muted, #696460))',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          <span
            style={{
              display: 'inline-block',
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: 'var(--hachi-danger, #C0392B)',
              flexShrink: 0,
            }}
          />
          {riskNote}
        </div>
      )}

      {/* Countdown line — null = "no auto-decline"; string = "auto-declines in …"; undefined = hidden */}
      {countdown !== undefined && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 12,
            lineHeight: '18px',
            fontFamily: 'var(--font-mono, JetBrains Mono, monospace)',
            color: 'var(--text-muted, var(--hachi-muted, #696460))',
          }}
        >
          {countdown !== null
            ? <>auto-declines in {countdown}</>
            : <>no auto-decline — Hachi waits until you decide</>
          }
        </div>
      )}

      {/* Countdown progress bar — only when caller provides bar data (timed approvals) */}
      {countdownBar && (
        <div
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(countdownBar.pct)}
          style={{
            height: 3,
            borderRadius: 999,
            background: 'var(--hachi-line)',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              width: countdownBar.pct + '%',
              height: '100%',
              background: countdownBar.color,
              borderRadius: 999,
              transition: 'width 1s linear',
            }}
          />
        </div>
      )}

      {/* Actions: Decline · Allow once — equal weight (T10).
          low/medium: both outlined. high: Decline is solid trust (dominant safe default).
          Always allow is always the quiet ghost option (arm-then-confirm via ConfirmButton).
          Resting backgrounds live in interactive.css classes (BB-76). */}
      <div data-testid={actionsTestId} style={{ display: 'flex', gap: 8 }}>
        <button
          type="button"
          className={isHighRisk ? 'hachi-leash-decline-high-btn' : 'hachi-leash-decline-btn'}
          onClick={handleDecline}
          style={{
            flex: 1,
            height: 44,
            padding: '0 14px',
            borderRadius: 'var(--radius-md, 10px)',
            border: isHighRisk ? '0.5px solid transparent' : '1.5px solid var(--hachi-trust, #2F4B7C)',
            color: isHighRisk ? undefined : 'var(--hachi-trust, #2F4B7C)',
            fontFamily: 'var(--font-body, Inter, system-ui, sans-serif)',
            fontSize: 14,
            fontWeight: 500,
            cursor: 'pointer',
            transition: isHighRisk
              ? 'opacity var(--dur-fast, 120ms) var(--ease, cubic-bezier(.2,.7,.3,1))'
              : 'background var(--dur-fast, 120ms) var(--ease, cubic-bezier(.2,.7,.3,1))',
          }}
        >
          Decline
        </button>
        <button
          type="button"
          className="hachi-leash-allow-once-btn"
          onClick={handleAllowOnce}
          style={{
            flex: 1,
            height: 44,
            padding: '0 14px',
            borderRadius: 'var(--radius-md, 10px)',
            border: '1.5px solid var(--hachi-brand, #C94230)',
            color: 'var(--hachi-brand, #C94230)',
            fontFamily: 'var(--font-body, Inter, system-ui, sans-serif)',
            fontSize: 14,
            fontWeight: 500,
            cursor: 'pointer',
            transition: 'background var(--dur-fast, 120ms) var(--ease, cubic-bezier(.2,.7,.3,1))',
          }}
        >
          Allow once
        </button>
        <ConfirmButton
          label="Always allow"
          confirmLabel="Always allow — confirm"
          onConfirm={() => { markSeen(); onAlwaysAllow() }}
          tone="neutral"
          ariaLabel="Always allow — grants a standing permission"
          style={{
            flex: 1,
            height: 44,
            borderRadius: 'var(--radius-md, 10px)',
            fontFamily: 'var(--font-body, Inter, system-ui, sans-serif)',
            fontSize: 13,
          }}
        />
      </div>

      {/* Footer caption */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          fontSize: 13,
          lineHeight: '20px',
          fontFamily: 'var(--font-body, Inter, system-ui, sans-serif)',
          color: 'var(--text-muted, var(--hachi-muted, #696460))',
          borderTop: '0.5px solid var(--border-hairline, var(--hachi-line, #E2D9C9))',
          paddingTop: 12,
        }}
      >
        <HachiMark
          size={16}
          variant="knockout"
          style={{ color: 'var(--text-muted, var(--hachi-muted, #696460))' }}
        />
        you hold the leash
      </div>
    </div>
  )
}
