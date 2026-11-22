// ActionCardRow — the collapsible tool-call/status card rendered under a
// Hachi message.

import React, { useEffect, useState } from 'react'
import { useStore } from '../../lib/store/store'
import { Icon } from '../icons/Icon'
import type { ActionCard } from '../../lib/data/types'
import { fmtUSD, statusMeta } from './helpers'

interface ActionCardRowProps {
  card: ActionCard
  msgId: number
  operator: boolean
}

export const ActionCardRow = React.memo(function ActionCardRow({ card, msgId, operator }: ActionCardRowProps) {
  const toggleCard = useStore((s) => s.toggleCard)
  // In operator mode, cards start expanded; otherwise start collapsed.
  // Local expanded state is layered on top of the store-level `expanded` flag.
  const [localExpanded, setLocalExpanded] = useState(operator ? true : card.expanded)

  // Sync when card.expanded changes (e.g. operator toggle)
  useEffect(() => {
    setLocalExpanded(operator ? true : card.expanded)
  }, [card.expanded, operator])

  const sm = statusMeta(card.status)
  const isExpanded = localExpanded
  const rot = isExpanded ? 180 : 0

  function handleToggle() {
    setLocalExpanded((v) => !v)
    toggleCard(msgId, card.key)
  }

  return (
    <div
      style={{
        border: '0.5px solid var(--hachi-line)',
        borderRadius: 12,
        background: 'var(--hachi-surface)',
        overflow: 'hidden',
      }}
    >
      <button
        type="button"
        onClick={handleToggle}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '12px 14px',
          border: 'none',
          background: 'transparent',
          cursor: 'pointer',
          textAlign: 'left',
          font: 'inherit',
        }}
      >
        {/* icon */}
        <span style={{ color: 'var(--hachi-muted)', display: 'inline-flex' }}>
          <Icon name={card.icon} size={16} />
        </span>

        {/* title + operator tool sig */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 500, fontSize: 14, color: 'var(--hachi-ink)' }}>
            {card.title}
          </div>
          {operator && card.tool && (
            <div
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 11,
                color: 'var(--hachi-muted)',
                marginTop: 2,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {card.tool}
            </div>
          )}
        </div>

        {/* status pill */}
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            padding: '4px 10px',
            borderRadius: 999,
            background: sm.bg,
            color: sm.fg,
            fontSize: 12,
            fontWeight: 500,
            flexShrink: 0,
          }}
        >
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: sm.dot,
              flexShrink: 0,
            }}
          />
          {sm.text}
        </span>

        {/* cost */}
        {card.cost > 0 && (
          <span
            style={{
              fontSize: 12,
              color: 'var(--hachi-muted)',
              fontVariantNumeric: 'tabular-nums',
              flexShrink: 0,
            }}
          >
            {fmtUSD(card.cost)}
          </span>
        )}

        {/* chevron */}
        <span
          style={{
            color: 'var(--hachi-muted)',
            display: 'inline-flex',
            transform: `rotate(${rot}deg)`,
            transition: 'transform var(--dur) var(--ease)',
            flexShrink: 0,
          }}
        >
          <Icon name="chevron-down" size={15} />
        </span>
      </button>

      {/* expanded detail */}
      {isExpanded && card.detail && (
        <div
          style={{
            padding: '0 14px 14px 41px',
            fontSize: 13,
            lineHeight: '21px',
            color: 'var(--hachi-muted)',
            fontFamily: 'var(--font-mono)',
            whiteSpace: 'pre-wrap',
          }}
        >
          {card.detail}
        </div>
      )}
    </div>
  )
})
