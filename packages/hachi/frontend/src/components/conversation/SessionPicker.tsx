// SessionPicker (M8 MED-020) — the "recent sessions" dropdown in the
// conversation header.

import { useEffect, useRef } from 'react'
import { Icon } from '../icons/Icon'
import { ConfirmButton } from '../ui/ConfirmButton'
import type { Session } from '../../lib/data/types'

interface SessionPickerProps {
  sessions: Session[]
  activeId: string | null
  onSwitch: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
  onCleanupEmpty: () => void
  onClose: () => void
}

export function SessionPicker({ sessions, activeId, onSwitch, onNew, onDelete, onCleanupEmpty, onClose }: SessionPickerProps) {
  const ref = useRef<HTMLDivElement>(null)

  // Close on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose])

  // Close on Escape
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <div
      ref={ref}
      role="group"
      aria-label="Recent sessions"
      style={{
        position: 'absolute',
        top: 'calc(100% + 6px)',
        left: 0,
        minWidth: 260,
        maxWidth: 340,
        background: 'var(--hachi-surface)',
        border: '0.5px solid var(--hachi-line)',
        borderRadius: 12,
        boxShadow: '0 8px 24px rgba(28,26,32,.10)',
        zIndex: 50,
        maxHeight: '60vh',
        overflowY: 'auto',
        overflowX: 'hidden',
      }}
    >
      {/* New conversation row */}
      <button
        type="button"
        className="hachi-ghost-icon-btn-bg"
        onClick={() => { onNew(); onClose() }}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '11px 14px',
          border: 'none',
          borderBottom: '0.5px solid var(--hachi-line)',
          cursor: 'pointer',
          textAlign: 'left',
          font: 'inherit',
          color: 'var(--hachi-brand)',
          fontSize: 13,
          fontWeight: 500,
        }}
      >
        <Icon name="plus" size={14} />
        New conversation
      </button>

      {/* Session list — FIX 3: filter out obviously-empty unnamed sessions (0 turns, no title) */}
      {sessions.filter((s) => s.active || !(s.turns === 0 && (s.title === 'Unnamed session' || !s.title))).length === 0 && (
        <div style={{ padding: '12px 14px', fontSize: 13, color: 'var(--hachi-muted)' }}>
          No recent sessions
        </div>
      )}
      {sessions.filter((s) => s.active || !(s.turns === 0 && (s.title === 'Unnamed session' || !s.title))).map((s) => {
        const isActive = s.id === activeId
        return (
          <div
            key={s.id}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '6px 8px 6px 10px',
              borderBottom: '0.5px solid var(--hachi-line)',
              background: isActive ? 'var(--hachi-cream)' : 'transparent',
            }}
          >
            <button
              type="button"
              aria-current={isActive ? 'true' : undefined}
              onClick={() => { onSwitch(s.id); onClose() }}
              style={{
                flex: 1,
                minWidth: 0,
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '8px 6px',
                border: 'none',
                background: 'transparent',
                cursor: 'pointer',
                textAlign: 'left',
                font: 'inherit',
              }}
            >
              <span style={{ color: isActive ? 'var(--hachi-brand)' : 'var(--hachi-muted)', display: 'inline-flex', flexShrink: 0 }}>
                <Icon name={isActive ? 'circle-check' : 'message-square'} size={14} />
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontSize: 13,
                    fontWeight: isActive ? 500 : 400,
                    color: 'var(--hachi-ink)',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {s.title}
                </div>
                <div style={{ fontSize: 11, color: 'var(--hachi-muted)', marginTop: 1 }}>
                  {s.date}{s.turns ? ` · ${s.turns} turn${s.turns !== 1 ? 's' : ''}` : ''}
                </div>
              </div>
            </button>
            <ConfirmButton
              label="Delete"
              confirmLabel="Delete?"
              onConfirm={() => onDelete(s.id)}
              tone="danger"
              icon="trash"
              ariaLabel={`Delete ${s.title}`}
              style={{ flexShrink: 0 }}
            />
          </div>
        )
      })}

      {/* FIX 3: Clean up empty sessions affordance */}
      <button
        type="button"
        className="hachi-ghost-icon-btn-bg"
        onClick={() => { onCleanupEmpty(); onClose() }}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '10px 14px',
          border: 'none',
          borderTop: '0.5px solid var(--hachi-line)',
          cursor: 'pointer',
          textAlign: 'left',
          font: 'inherit',
          fontSize: 12,
          color: 'var(--hachi-muted)',
        }}
      >
        <Icon name="trash" size={12} />
        Clean up empty sessions
      </button>
    </div>
  )
}
