// RoutineCard — the "create a recurring routine" proposal card rendered
// under a Hachi message.

import React from 'react'
import { useStore } from '../../lib/store/store'
import { Icon } from '../icons/Icon'
import type { ChatMessage } from '../../lib/data/types'
import { fmtUSD } from './helpers'

interface RoutineCardProps {
  routine: NonNullable<ChatMessage['routine']>
  msgId: number
}

export const RoutineCard = React.memo(function RoutineCard({ routine, msgId }: RoutineCardProps) {
  const dryRunRoutine = useStore((s) => s.dryRunRoutine)
  const createRoutine = useStore((s) => s.createRoutine)

  const steps = routine.steps ?? []
  const needs = routine.needs ?? []
  const created = !!routine.created
  const notCreated = !created

  return (
    <div
      style={{
        border: '0.5px solid var(--hachi-line)',
        borderRadius: 14,
        background: 'var(--hachi-surface)',
        padding: 18,
        display: 'flex',
        flexDirection: 'column',
        gap: 14,
      }}
    >
      {/* title row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ color: 'var(--hachi-trust)', display: 'inline-flex' }}>
          <Icon name="repeat" size={18} />
        </span>
        <span
          style={{
            fontFamily: 'var(--font-display)',
            fontWeight: 500,
            fontSize: 16,
          }}
        >
          {routine.title}
        </span>
      </div>

      {/* trigger */}
      {routine.trigger && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            fontSize: 13,
            color: 'var(--hachi-muted)',
          }}
        >
          <Icon name="calendar" size={14} />
          {routine.trigger}
        </div>
      )}

      {/* steps */}
      {steps.length > 0 && (
        <div>
          <div style={{ fontSize: 12, color: 'var(--hachi-muted)', marginBottom: 7 }}>
            Steps
          </div>
          {steps.map((step, i) => (
            <div
              key={i}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 9,
                fontSize: 14,
                padding: '4px 0',
              }}
            >
              <span
                style={{
                  width: 5,
                  height: 5,
                  borderRadius: '50%',
                  background: 'var(--hachi-trust)',
                  flexShrink: 0,
                }}
              />
              {step}
            </div>
          ))}
        </div>
      )}

      {/* footer: needs + cost */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderTop: '0.5px solid var(--hachi-line)',
          paddingTop: 12,
        }}
      >
        <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap' }}>
          {needs.map((need, i) => (
            <span
              key={i}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
                padding: '4px 9px',
                borderRadius: 999,
                background: 'var(--hachi-cream)',
                fontSize: 12,
                color: 'var(--hachi-ink)',
              }}
            >
              <Icon name="leash" size={12} />
              {need}
            </span>
          ))}
        </div>
        {typeof routine.costPerRun === 'number' && (
          <span
            style={{
              fontSize: 13,
              color: 'var(--hachi-muted)',
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {fmtUSD(routine.costPerRun)}/run
          </span>
        )}
      </div>

      {/* actions (not yet created) */}
      {notCreated && (
        <div style={{ display: 'flex', gap: 9 }}>
          <button
            type="button"
            className="hachi-cancel-btn"
            onClick={() => dryRunRoutine(msgId)}
            style={{
              flex: 1,
              height: 38,
              borderRadius: 10,
              border: '1px solid var(--hachi-trust)',
              background: 'transparent',
              color: 'var(--hachi-trust)',
              font: '500 13px var(--font-body)',
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 7,
            }}
          >
            <Icon name="play" size={14} />
            Try once (dry run)
          </button>
          <button
            type="button"
            className="hachi-mcp-submit-btn"
            onClick={() => createRoutine(msgId)}
            style={{
              flex: 1,
              height: 38,
              borderRadius: 10,
              border: '0.5px solid transparent',
              background: 'var(--hachi-brand-hover)',
              color: 'var(--hachi-canvas)',
              font: '500 13px var(--font-body)',
              cursor: 'pointer',
            }}
          >
            Create routine
          </button>
        </div>
      )}

      {/* created confirmation */}
      {created && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            fontSize: 13,
            color: 'var(--hachi-success-fg)',
            background: 'var(--hachi-success-tint)',
            padding: '9px 12px',
            borderRadius: 10,
          }}
        >
          <Icon name="check" size={15} />
          On watch — runs weekdays at 8:00
        </div>
      )}
    </div>
  )
})
