// OgExplainer — canonical .og explainer banner.
// Single localStorage key across all screens so "dismiss once, gone everywhere".

import { useState, useRef, useCallback, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Icon } from '../icons/Icon'

const KEY = 'hachi.og.explainer.dismissed'

function readDismissed(): boolean {
  try { return localStorage.getItem(KEY) === '1' } catch { return false }
}

const TOOLTIP_W = 260

interface WhyTooltipProps { text: string }

function WhyTooltip({ text }: WhyTooltipProps) {
  const [visible, setVisible] = useState(false)
  const [coords, setCoords] = useState<{ top: number; left: number } | null>(null)
  const triggerRef = useRef<HTMLSpanElement>(null)

  const measure = useCallback(() => {
    if (!triggerRef.current) return
    const r = triggerRef.current.getBoundingClientRect()
    const left = Math.max(8, Math.min(r.left, window.innerWidth - TOOLTIP_W - 8))
    setCoords({ top: r.bottom + 6, left })
  }, [])

  const show = useCallback(() => { measure(); setVisible(true) }, [measure])
  const hide = useCallback(() => setVisible(false), [])

  return (
    <>
      <span
        ref={triggerRef}
        tabIndex={0}
        role="button"
        aria-describedby="og-why-tooltip"
        style={{ color: 'var(--hachi-brand)', cursor: 'help', borderBottom: '1px dashed var(--hachi-brand)', outline: 'none' }}
        onFocus={show}
        onBlur={hide}
        onMouseEnter={show}
        onMouseLeave={hide}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') visible ? hide() : show() }}
      >
        Why?
      </span>
      {visible && coords && createPortal(
        <span
          id="og-why-tooltip"
          role="tooltip"
          style={{
            position: 'fixed',
            top: coords.top,
            left: coords.left,
            zIndex: 9999,
            background: 'var(--hachi-surface)',
            border: '0.5px solid var(--hachi-line)',
            borderRadius: 10,
            padding: '10px 13px',
            fontSize: 12,
            color: 'var(--hachi-muted)',
            lineHeight: '18px',
            width: TOOLTIP_W,
            boxShadow: '0 4px 16px rgba(0,0,0,0.18)',
            whiteSpace: 'normal',
            pointerEvents: 'none',
          }}
        >{text}</span>,
        document.body,
      )}
    </>
  )
}

export interface OgExplainerProps {
  headline: string
  body: ReactNode
  whyTooltip?: string
}

export function OgExplainer({ headline, body, whyTooltip }: OgExplainerProps) {
  const [dismissed, setDismissed] = useState(readDismissed)

  if (dismissed) return null

  function dismiss() {
    try { localStorage.setItem(KEY, '1') } catch { /* ignore */ }
    setDismissed(true)
  }

  return (
    <div
      role="note"
      aria-label="ObjectGraph explainer"
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 12,
        padding: '12px 16px',
        borderRadius: 12,
        background: 'var(--hachi-brand-tint)',
        border: '0.5px solid var(--hachi-brand)',
        fontSize: 13,
        color: 'var(--hachi-ink)',
        lineHeight: '20px',
      }}
    >
      <span style={{ color: 'var(--hachi-brand)', display: 'inline-flex', flexShrink: 0, marginTop: 2 }}>
        <Icon name="file-code" size={15} />
      </span>
      <span style={{ flex: 1 }}>
        {headline && <strong style={{ fontWeight: 500 }}>{headline} </strong>}
        {body}
        {whyTooltip && (
          <>{' '}<WhyTooltip text={whyTooltip} /></>
        )}
      </span>
      <button
        type="button"
        className="hachi-ghost-icon-btn-bg"
        aria-label="Dismiss explainer"
        onClick={dismiss}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 26,
          height: 26,
          borderRadius: 6,
          border: 'none',
          color: 'var(--hachi-muted)',
          cursor: 'pointer',
          flexShrink: 0,
        }}
      >
        <Icon name="x" size={13} />
      </button>
    </div>
  )
}
