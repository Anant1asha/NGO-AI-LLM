// MessageItem — renders a single chat turn (you/hachi), including
// attachments, action cards, routine proposals, and the streaming cursor.
// Wrapped in React.memo so that updating the last streaming message text does
// NOT re-render every prior (stable) message in the list.

import { memo, useState, useCallback } from 'react'
import { Icon } from '../icons/Icon'
import { HachiMark } from '../brand/HachiMark'
import { Markdown } from '../ui/Markdown'
import type { ChatMessage } from '../../lib/data/types'
import { attMeta } from './helpers'
import { TtsButton } from './TtsButton'
import { StreamingCursor } from './StreamingText'
import { ActionCardRow } from './ActionCardRow'
import { RoutineCard } from './RoutineCard'
import { fmtRelative } from '../../lib/ui/format'

interface MessageItemProps {
  msg: ChatMessage
  isLast: boolean
  isStreaming: boolean
  operator: boolean
  onRetry?: () => void
  lastUsedModel?: string | null
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    }).catch(() => {/* clipboard unavailable */})
  }, [text])

  return (
    <button
      type="button"
      className="hachi-ghost-icon-btn-bg"
      onClick={handleCopy}
      title={copied ? 'Copied!' : 'Copy message'}
      aria-label={copied ? 'Copied!' : 'Copy message'}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        padding: '3px 9px',
        borderRadius: 8,
        border: '0.5px solid var(--hachi-line)',
        color: copied ? 'var(--hachi-success-fg)' : 'var(--hachi-muted)',
        font: '500 12px var(--font-body)',
        cursor: 'pointer',
      }}
    >
      <Icon name={copied ? 'check' : 'copy'} size={13} />
      {copied ? 'Copied' : 'Copy'}
    </button>
  )
}

export const MessageItem = memo(function MessageItem({ msg, isLast, isStreaming, operator, onRetry, lastUsedModel }: MessageItemProps) {
  const isYou = msg.role === 'you'
  const isHachi = msg.role === 'hachi'
  const showCursor = isStreaming && isHachi && isLast
  // Structural error flag takes precedence; fall back to text match for old persisted messages.
  const isError = isHachi && !isStreaming && (msg.error === true || msg.text === 'Something went wrong — please try again.')

  if (isYou) {
    const hasAttachments = !!(msg.attachments && msg.attachments.length > 0)
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
        {/* attachments — chips above the bubble, right-aligned */}
        {hasAttachments && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7, justifyContent: 'flex-end', maxWidth: '80%' }}>
            {msg.attachments!.map((a, i) => {
              const meta = attMeta(a.name, a.mediaType)
              return (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    background: 'var(--hachi-surface)',
                    border: '0.5px solid var(--hachi-line)',
                    borderRadius: 10,
                    padding: '5px 9px 5px 5px',
                  }}
                >
                  <div
                    style={{
                      width: 30,
                      height: 30,
                      borderRadius: 6,
                      background: 'var(--hachi-cream)',
                      display: 'grid',
                      placeItems: 'center',
                      flexShrink: 0,
                      color: meta.tint,
                    }}
                  >
                    <Icon name={meta.icon} size={15} />
                  </div>
                  <span
                    style={{
                      fontSize: 12,
                      fontWeight: 500,
                      color: 'var(--hachi-ink)',
                      maxWidth: 130,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {a.name}
                  </span>
                </div>
              )
            })}
          </div>
        )}
        {/* text bubble */}
        {msg.text && (
          <div
            style={{
              maxWidth: '80%',
              minWidth: 0,
              background: 'var(--hachi-cream)',
              border: '0.5px solid var(--hachi-line)',
              borderRadius: '16px 16px 4px 16px',
              padding: '12px 16px',
              fontSize: 15,
              lineHeight: '24px',
              overflowWrap: 'anywhere',
              wordBreak: 'break-word',
            }}
          >
            <Markdown text={msg.text} />
          </div>
        )}
      </div>
    )
  }

  if (isHachi) {
    const hasRoutine = !!(msg.routine && msg.routine.title)

    return (
      <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
        {/* Hachi avatar */}
        <div
          style={{
            flexShrink: 0,
            width: 34,
            height: 34,
            borderRadius: 10,
            background: 'var(--hachi-cream)',
            display: 'grid',
            placeItems: 'center',
            marginTop: 2,
          }}
        >
          <HachiMark size={22} />
        </div>

        {/* message body */}
        <div
          style={{
            flex: 1,
            minWidth: 0,
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
            paddingTop: 4,
          }}
        >
          {/* text + blinking cursor */}
          <div
            style={{
              fontSize: 15,
              lineHeight: '24px',
              color: isError ? 'var(--hachi-danger)' : 'var(--hachi-ink)',
              overflowWrap: 'anywhere',
              wordBreak: 'break-word',
              minWidth: 0,
            }}
          >
            <Markdown text={msg.text} isStreaming={showCursor} />
            {showCursor && <StreamingCursor />}
          </div>

          {/* action row: [Copy] [Listen] [via model] · timestamp */}
          {!showCursor && msg.text && !isError && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                flexWrap: 'wrap',
              }}
            >
              <CopyButton text={msg.text} />
              <TtsButton text={msg.text} />
              {isLast && lastUsedModel && (
                <span
                  style={{
                    fontSize: 11,
                    color: 'var(--hachi-muted)',
                    fontFamily: 'var(--font-mono, monospace)',
                    opacity: 0.7,
                  }}
                >
                  via {lastUsedModel}
                </span>
              )}
              {msg.ts && (
                <time
                  dateTime={new Date(msg.ts).toISOString()}
                  title={new Date(msg.ts).toLocaleString()}
                  style={{
                    fontSize: 11,
                    color: 'var(--hachi-muted)',
                    marginLeft: 'auto',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {fmtRelative(msg.ts)}
                </time>
              )}
            </div>
          )}

          {/* retry button on error */}
          {isError && onRetry && (
            <button
              type="button"
              className="hachi-danger-outline-btn"
              onClick={onRetry}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                height: 32,
                padding: '0 12px',
                borderRadius: 8,
                border: '1px solid var(--hachi-danger)',
                background: 'transparent',
                color: 'var(--hachi-danger)',
                font: '500 13px var(--font-body)',
                cursor: 'pointer',
                alignSelf: 'flex-start',
              }}
            >
              <Icon name="repeat" size={13} />
              Retry
            </button>
          )}

          {/* action cards */}
          {msg.cards.map((card) => (
            <ActionCardRow
              key={card.key}
              card={card}
              msgId={msg.id}
              operator={operator}
            />
          ))}

          {/* routine proposal card */}
          {hasRoutine && msg.routine && (
            <RoutineCard routine={msg.routine} msgId={msg.id} />
          )}
        </div>
      </div>
    )
  }

  return null
})
