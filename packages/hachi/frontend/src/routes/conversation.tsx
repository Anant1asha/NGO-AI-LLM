// Conversation screen — /conversation
// Faithfully ports prototype markup lines 212–336 and logic handlers.
// Screen-local view state only in useState; all domain mutations go through useStore.
//
// Presentational sub-components (SessionPicker, MessageItem + its ActionCardRow/
// RoutineCard/TtsButton/StreamingText children, the voice/attachment/starter/slash
// rows, and ConversationComposer) live in components/conversation/ — this file
// keeps only the route's own state and layout.

import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react'
import { createFileRoute, useSearch, useNavigate } from '@tanstack/react-router'
import { useStore } from '../lib/store/store'
import { Icon } from '../components/icons/Icon'
import { HachiMark } from '../components/brand/HachiMark'
import { LeashPrompt } from '../components/brand/LeashPrompt'
import type { Integration } from '../lib/data/types'
// Side-effect import: registers the "chat" loader with bootstrapLiveData()
// and makes loadSessions available for the per-route refresh below.
import {
  loadSessions,
  loadConversationHistory,
  loadSessionMessages,
  abortSseLive,
  deleteSessionLive,
  cleanupEmptySessionsLive,
} from '../lib/data/domains/chat'
import ContinuousVoice from '../components/voice/ContinuousVoice'
import { getVoiceConfig } from '../lib/data/domains/voice'
import { SessionPicker } from '../components/conversation/SessionPicker'
import { MessageItem } from '../components/conversation/MessageItem'
import { StarterButton } from '../components/conversation/StarterButton'
import { ConversationComposer } from '../components/conversation/ConversationComposer'
import { JumpToLatest } from '../components/ui/JumpToLatest'
// ---- chat starters (prototype renderVals lines 2209–2213) -----------
// HIGH-019: integrations required to show certain starters

interface ChatStarter {
  label: string
  icon: string
  text: string
  requiresIntegration?: string  // integration name that must be "connected"
}

const CHAT_STARTERS: ChatStarter[] = [
  { label: 'Summarise my inbox', icon: 'mail', text: 'Summarise my inbox and flag anything urgent', requiresIntegration: 'Google' },
  { label: 'Draft a reply to Priya', icon: 'pencil', text: 'Draft a reply to Priya about the Q3 deck', requiresIntegration: 'Google' },
  { label: 'Create a routine', icon: 'repeat', text: 'Every weekday at 8, summarise my inbox and message me the urgent ones' },
]

// Hoisted so the object reference is stable across renders (no inline allocation).
const STREAMING_ROW_STYLE: React.CSSProperties = { contain: 'content' }

// ---- Conversation component ----------------------------------------

function Conversation() {
  // Narrow the messages subscription to avoid re-running all derived state on
  // every store flush (which happens ~20×/s during streaming).
  // We subscribe to the array reference directly but use a stable memoized
  // list keyed on a cheap signature so React skips reconciling completed bubbles
  // when only the streaming tail changes.
  const messagesRaw = useStore((s) => s.messages)
  const messagesLen = messagesRaw.length
  const lastMsgId = messagesLen > 0 ? messagesRaw[messagesLen - 1].id : -1
  const streaming = useStore((s) => s.streaming)
  const inContext = useStore((s) => s.inContext)
  const operator = useStore((s) => s.operator)
  const spent = useStore((s) => s.spent)
  const budget = useStore((s) => s.budget)
  const sessions = useStore((s) => s.sessions)
  const integrations = useStore((s) => s.integrations)
  const startTask = useStore((s) => s.startTask)
  const icAllow = useStore((s) => s.icAllow)
  const icAlwaysAllow = useStore((s) => s.icAlwaysAllow)
  const icDeny = useStore((s) => s.icDeny)

  const switchSession = useStore((s) => s.switchSession)
  const newSession = useStore((s) => s.newSession)
  const dataMode = useStore((s) => s.dataMode)
  const showToast = useStore((s) => s.showToast)
  // FIX 4: last used model id (from usage SSE event via store)
  const lastUsedModel = useStore((s) => s.lastUsedModel)

  // Optional `?session=<id>` search param — set by memory.tsx when navigating
  // to a past session so we display that session's transcript instead of the active one.
  const { session: sessionParam } = useSearch({ from: '/conversation' })
  const navigate = useNavigate()

  // Memoize the messages array passed to the list: re-create only when length,
  // last id, or streaming flag changes (not on every token flush of the tail).
  // This means the .map() over the list re-runs only on structural changes, not
  // on every ~48ms delta flush. MessageItem is already React.memo'd so even
  // when messages is a new array, unchanged items bail out in reconciliation.
  const streamingText = streaming && messagesLen > 0 ? messagesRaw[messagesLen - 1].text : ''
  const messages = useMemo(
    () => messagesRaw,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [messagesLen, lastMsgId, streaming, streamingText]
  )

  const scrollRef = useRef<HTMLDivElement>(null)
  // followOutputRef drives the rAF pin (non-stale); followingState drives the pill render.
  const followOutputRef = useRef(true)
  const [following, setFollowing] = useState(true)
  const scrollRafRef = useRef<number | null>(null)
  // M8: session picker open state
  const [pickerOpen, setPickerOpen] = useState(false)

  // Continuous-voice overlay state
  const [continuousOpen, setContinuousOpen] = useState(false)
  // Track the last completed assistant text so the overlay can auto-TTS it.
  const [lastAssistantText, setLastAssistantText] = useState('')
  // Track whether gateway voice is configured (for graceful fallback).
  const [gatewayVoiceReady, setGatewayVoiceReady] = useState<boolean | null>(null)

  // The transcript is intentionally NOT virtualized. Messages are hard-capped at
  // 400 (store.capMessages) — a safe DOM size — and a dynamic virtualizer's
  // ResizeObserver measurement of the actively-streaming (continuously-growing)
  // message caused a main-thread freeze (RESULT_CODE_HUNG). A plain memoized
  // list is robust: React.memo on MessageItem means only the streaming message
  // re-renders during a turn; all prior messages stay stable. The streaming text
  // itself is chunked (StreamingText) so its own re-render cost is bounded.
  const lastMsg = messages.length > 0 ? messages[messages.length - 1] : null
  const isStreamingLast = streaming && lastMsg?.role === 'hachi'

  // M11: streaming chat was silent to screen readers — no aria-live region existed
  // at all. Announce the reply once it finishes streaming (not on every token flush,
  // which would be both spammy and defeat the point of chunking the visible render).
  const [srAnnouncement, setSrAnnouncement] = useState('')
  useEffect(() => {
    if (streaming) return
    if (lastMsg && lastMsg.role === 'hachi' && lastMsg.text.trim() && lastMsg.text !== srAnnouncement) {
      setSrAnnouncement(lastMsg.text)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [streaming, lastMsg?.text])

  // Refresh recent sessions list on navigate-to (idempotent loader)
  useEffect(() => { void loadSessions() }, [])

  // Probe gateway voice config once on mount to decide default mode.
  useEffect(() => {
    getVoiceConfig()
      .then((cfg) => setGatewayVoiceReady(cfg.configured))
      .catch(() => setGatewayVoiceReady(false))
  }, [])

  // While the continuous overlay is open, track the last completed (non-streaming)
  // assistant message so the overlay can auto-speak it via gateway/browser TTS.
  useEffect(() => {
    if (!continuousOpen) return
    if (streaming) return  // still in-flight; wait for it to finish
    const last = [...messages].reverse().find((m) => m.role === 'hachi' && m.text.trim())
    if (last && last.text !== lastAssistantText) {
      setLastAssistantText(last.text)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [streaming, messages.length, continuousOpen])

  // Restore conversation history on mount and when the active session changes.
  // Guards: skipped in mock mode, skipped if a stream is in-flight.
  // Skipped when a past-session param is present (handled by the effect below).
  const activeSessionId = sessions.find((s) => s.active)?.id ?? null
  useEffect(() => {
    if (sessionParam && sessionParam !== activeSessionId) {
      // Past-session display handled by the sessionParam effect below.
      return
    }
    void loadConversationHistory()
  // Re-run whenever the active session id changes (e.g. user switches sessions
  // or the sessions list loads for the first time on a refresh).
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSessionId, sessionParam])

  // When a past session id arrives via ?session=<id>, fetch and display its transcript.
  // This is display-only: sending a message still goes to the active/new session.
  useEffect(() => {
    if (!sessionParam) return
    if (sessionParam === activeSessionId) {
      // Same as the live session — just show the normal conversation history.
      void loadConversationHistory()
      return
    }
    // Load the selected past session's transcript.
    void loadSessionMessages(sessionParam).then((msgs) => {
      if (msgs === null) {
        // 404 or unavailable — fall back to the active session
        showToast('Session not found — showing current conversation', 'info')
        void loadConversationHistory()
      } else if (msgs.length === 0) {
        useStore.getState().hydrate({ messages: [] })
      } else {
        useStore.getState().hydrate({ messages: msgs })
      }
    }).catch(() => {
      showToast('Could not load session history', 'blocked')
      void loadConversationHistory()
    })
  // Only re-run when the session param changes (ignore activeSessionId here).
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionParam])

  // Abort the SSE stream when the conversation screen unmounts so the reader
  // is released and the idle timeout doesn't keep it alive in the background.
  useEffect(() => {
    return () => {
      abortSseLive()
    }
  }, [])

  // Follow output while the user is near the bottom.
  // Use requestAnimationFrame to batch many rapid flush events into at most one
  // scrollTop write per frame (~60/s cap), avoiding a forced layout reflow on
  // every ~48ms token flush (~20/s). The rAF is cancelled and re-scheduled on
  // each effect run so multiple flushes in the same frame coalesce into one write.
  const streamingLen = isStreamingLast ? lastMsg?.text.length ?? 0 : 0
  useEffect(() => {
    if (!followOutputRef.current || !scrollRef.current) return
    const el = scrollRef.current
    // Cancel any pending rAF from a prior flush in this same frame
    if (scrollRafRef.current != null) {
      cancelAnimationFrame(scrollRafRef.current)
    }
    scrollRafRef.current = requestAnimationFrame(() => {
      scrollRafRef.current = null
      if (followOutputRef.current && el) {
        el.scrollTop = el.scrollHeight
      }
    })
  }, [messages.length, streamingLen])

  const handleTranscriptScroll = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 96
    followOutputRef.current = atBottom
    setFollowing(atBottom)
  }, [])

  const jumpToLatest = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
    followOutputRef.current = true
    setFollowing(true)
    el.focus()
  }, [])

  const chatEmpty = messages.length === 0

  // Computed state text for header (prototype logic line 2187).
  // HACHI-002: derive `working` from `streaming` alone — the old empty-bubble
  // clause ( m.text === '' ) pinned "Hachi is working" forever when a POST
  // failed and left an empty, non-streaming assistant bubble.
  const working = streaming
  const chatState = working ? 'Hachi is working' : 'Hachi is on watch'

  // LOW-020: active session title — only use a session explicitly marked active.
  // Falling back to sessions[0] would show the previous session's title on a fresh
  // conversation (newSessionLive clears all active flags but keeps the list).
  const activeSession = sessions.find((s) => s.active) ?? null
  const sessionLabel = activeSession?.title ?? 'New conversation'

  // True when we're displaying a historical session that is not the live one.
  const isPastSession = !!(sessionParam && sessionParam !== activeSessionId)

  // HIGH-019: filter chat starters to those whose integration is connected (or have no requirement)
  const connectedIntegrationNames = new Set(
    (integrations as Integration[]).filter((i) => i.status === 'connected').map((i) => i.name)
  )
  const visibleStarters = CHAT_STARTERS.filter(
    (s) => !s.requiresIntegration || connectedIntegrationNames.has(s.requiresIntegration)
  )

  const handleDeleteSession = (sessionId: string) => {
    if (dataMode !== 'live') {
      showToast('Session deletion is available in live mode only', 'blocked')
      return
    }
    void (async () => {
      const ok = await deleteSessionLive(sessionId)
      if (ok) {
        showToast('Session deleted', 'success')
      } else {
        showToast('Could not delete session — please try again', 'blocked')
      }
    })()
  }

  // FIX 3: clean up 0-message sessions via backend route
  const handleCleanupEmpty = () => {
    if (dataMode !== 'live') {
      showToast('Available in live mode only', 'blocked')
      return
    }
    void (async () => {
      await cleanupEmptySessionsLive()
      showToast('Empty sessions cleaned up', 'success')
    })()
  }

  // MED-020 / retry fix: retry IN PLACE — reuses the failed assistant bubble and
  // re-sends the last prompt without appending a duplicate "you" message. Also relies
  // on the SSE session guard (chat.ts) so a stale stream can't render a foreign reply.
  const handleRetry = useCallback(() => {
    useStore.getState().retryLastMessage()
  }, [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* ---- header ---- */}
      <div
        className="hachi-conv-header"
        style={{
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          padding: '0 32px',
          height: 68,
          flexShrink: 0,
          borderBottom: '0.5px solid var(--hachi-line)',
        }}
      >
        {/* M8 MED-020: session title — clickable to open session picker */}
        <div style={{ position: 'relative' }}>
          <button
            type="button"
            className="hachi-session-title-btn"
            aria-haspopup="menu"
            aria-expanded={pickerOpen}
            onClick={() => setPickerOpen((v) => !v)}
            // Names the action as well as the session — the bare label told users nothing
            // about the picker. Keeps the full title, which the 320px maxWidth truncates.
            title={`${sessionLabel} — switch conversation`}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 5,
              maxWidth: 320,
              padding: '4px 8px',
              borderRadius: 8,
              // Background + border live in interactive.css, keyed off aria-expanded:
              // an inline value would out-specify the :hover rule and kill it.
              cursor: 'pointer',
              font: 'inherit',
              fontSize: 16,
              fontWeight: 500,
              fontFamily: 'var(--font-display)',
              color: 'var(--hachi-ink)',
            }}
          >
            <span
              style={{
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {sessionLabel}
            </span>
            <span style={{ display: 'inline-flex', flexShrink: 0, transform: pickerOpen ? 'rotate(180deg)' : 'none', transition: 'transform var(--dur) var(--ease)' }}>
              <Icon name="chevron-down" size={12} />
            </span>
          </button>
          {pickerOpen && (
            <SessionPicker
              sessions={sessions}
              activeId={activeSession?.id ?? null}
              onSwitch={(id) => switchSession(id)}
              onNew={() => newSession()}
              onDelete={handleDeleteSession}
              onCleanupEmpty={handleCleanupEmpty}
              onClose={() => setPickerOpen(false)}
            />
          )}
        </div>
        <span
          data-status
          style={{
            position: 'absolute',
            left: '50%',
            transform: 'translateX(-50%)',
            fontSize: 13,
            color: 'var(--hachi-muted)',
            pointerEvents: 'none',
          }}
        >
          {chatState}
        </span>
      </div>

      {/* Announces the completed reply to screen readers — streaming updates the
          visible transcript on every chunk, but this only updates once per turn. */}
      <div className="hachi-sr-only" aria-live="polite" role="status">
        {srAnnouncement}
      </div>

      {/* Past-session read-only banner */}
      {isPastSession && (
        <div
          role="status"
          style={{
            background: 'var(--hachi-cream)',
            borderBottom: '0.5px solid var(--hachi-line)',
            padding: '10px 32px',
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            fontSize: 13,
            color: 'var(--hachi-muted)',
            flexShrink: 0,
          }}
        >
          <Icon name="lock" size={13} />
          Viewing a past conversation — read-only
          <button
            type="button"
            className="hachi-ghost-icon-btn-bg"
            onClick={() => navigate({ to: '/conversation' })}
            style={{
              marginLeft: 'auto',
              padding: '4px 10px',
              borderRadius: 8,
              border: '0.5px solid var(--hachi-line)',
              font: '500 12px var(--font-body)',
              color: 'var(--hachi-brand)',
              cursor: 'pointer',
            }}
          >
            Back to current conversation
          </button>
        </div>
      )}

      {/* ---- transcript scroll area ---- */}
      <div style={{ flex: 1, minHeight: 0, position: 'relative' }}>
        {!following && (streaming || messages.length > 0) && (
          <JumpToLatest onClick={jumpToLatest} label="↓ New reply" />
        )}
      <div
        ref={scrollRef}
        onScroll={handleTranscriptScroll}
        className="hachi-scroll"
        style={{ height: '100%', overflow: 'auto', padding: '28px 0' }}
      >
        <div
          className="hachi-transcript-inner"
          style={{
            maxWidth: 760,
            margin: '0 auto',
            padding: '0 32px',
          }}
        >
          {/* ---- empty / welcome state ---- */}
          {chatEmpty && (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                textAlign: 'center',
                gap: 18,
                padding: '48px 0',
              }}
            >
              <HachiMark size={56} />
              <div>
                <div
                  style={{
                    fontFamily: 'var(--font-display)',
                    fontWeight: 500,
                    fontSize: 22,
                    marginBottom: 6,
                  }}
                >
                  Hachi is on watch
                </div>
                <div style={{ fontSize: 15, color: 'var(--hachi-muted)' }}>
                  What would you like to do? Hachi works on your machine and asks before anything
                  risky.
                </div>
              </div>
              {/* HIGH-019: only show starters whose integration is connected */}
              {visibleStarters.length > 0 && (
                <div
                  style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: 9,
                    justifyContent: 'center',
                    maxWidth: 560,
                  }}
                >
                  {visibleStarters.map((s) => (
                    <StarterButton
                      key={s.label}
                      label={s.label}
                      icon={s.icon}
                      onClick={() => startTask(s.text)}
                    />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ---- message list (plain, memoized; capped at 400 messages) ---- */}
          {!chatEmpty && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20, width: '100%' }}>
              {messages.map((msg, idx) => {
                const isLast = idx === messages.length - 1
                const streamingThis = isLast && isStreamingLast
                return (
                  // `contain: content` on the streaming row bounds its reflow/paint
                  // so the growing text never re-lays-out the messages above it.
                  <div key={msg.id} style={streamingThis ? STREAMING_ROW_STYLE : undefined}>
                    <MessageItem
                      msg={msg}
                      isLast={isLast}
                      isStreaming={streamingThis}
                      operator={operator}
                      onRetry={handleRetry}
                      lastUsedModel={isLast ? lastUsedModel : null}
                    />
                  </div>
                )
              })}
            </div>
          )}

          {/* ---- in-context leash prompt ---- */}
          {inContext && (
            <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
              {/* spacer aligns with Hachi avatar column */}
              <div style={{ width: 34, flexShrink: 0 }} />
              <LeashPrompt
                request={inContext.request}
                action={inContext.action}
                why={inContext.why}
                onAllowOnce={icAllow}
                onAlwaysAllow={icAlwaysAllow}
                onDecline={icDeny}
              />
            </div>
          )}
        </div>
      </div>
      </div>{/* end transcript scroll wrapper */}

      {/* ---- composer (hidden while viewing a past session) ---- */}
      {!isPastSession && (
        <ConversationComposer
          onOpenSessionsPicker={() => setPickerOpen(true)}
          onStartContinuous={() => setContinuousOpen(true)}
          gatewayReady={gatewayVoiceReady ?? false}
        />
      )}

      {/* ---- continuous voice overlay ---- */}
      <ContinuousVoice
        open={continuousOpen}
        gatewayReady={gatewayVoiceReady ?? false}
        streaming={streaming}
        assistantText={lastAssistantText}
        onTranscript={(text) => {
          // Reuse the same send path as the composer.
          useStore.getState().startTask(text)
        }}
        onClose={() => {
          setContinuousOpen(false)
          setLastAssistantText('')
        }}
      />

    </div>
  )
}

// ---- Route export (TanStack Router file-based routing) --------------

interface ConversationSearch {
  session?: string
}

function validateConversationSearch(search: Record<string, unknown>): ConversationSearch {
  return {
    session: typeof search.session === 'string' ? search.session : undefined,
  }
}

export const Route = createFileRoute('/conversation')({
  validateSearch: validateConversationSearch,
  component: Conversation,
})
