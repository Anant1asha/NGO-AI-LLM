// ConversationComposer — the message input row: text/slash-commands,
// attachments, voice modes (push-to-talk/dictate/continuous), and send/stop.

import React, { memo, useCallback, useEffect, useRef, useState } from 'react'
import { useStore } from '../../lib/store/store'
import { Icon } from '../icons/Icon'
import {
  uploadFile,
  makeOptimisticAttachment,
  getFileMeta,
} from '../../lib/data/domains/files'
import {
  startRecognition,
  recordAndTranscribe,
  browserSpeechSupported,
  type RecognizerHandle,
  type RecordController,
} from '../../lib/voice/speech'
import { SlashItem } from './SlashItem'
import { AttachmentChip } from './AttachmentChip'
import { VoiceOption } from './VoiceOption'
import { VoiceWave } from './VoiceWave'

// ---- slash command items (prototype renderVals lines 2214–2219) ------
// H4: /routine, /dry-run, /budget, /delegate, /plan removed — no backend endpoint
// exists for any of them (see docs/bug-bank.md BB-50). Only list commands with a
// real 1:1 backing: /model, /memory, /remember (gateway slash commands) and
// /sessions (a real client-side action via handleSlashPick).

const SLASH_ITEMS = [
  { cmd: '/model', desc: 'change the AI model' },
  { cmd: '/memory', desc: 'search stored memory' },
  { cmd: '/remember', desc: 'save a fact to memory' },
  { cmd: '/sessions', desc: 'switch to a previous session' },
]

interface ConversationComposerProps {
  onOpenSessionsPicker: () => void
  onStartContinuous: () => void
  gatewayReady: boolean
}

type ComposerVoiceMode = null | 'push' | 'dictate'

export const ConversationComposer = memo(function ConversationComposer({
  onOpenSessionsPicker,
  onStartContinuous,
  gatewayReady,
}: ConversationComposerProps) {
  const composer = useStore((s) => s.composer)
  const slashOpen = useStore((s) => s.slashOpen)
  const streaming = useStore((s) => s.streaming)
  const pendingAttachments = useStore((s) => s.pendingAttachments)
  const setComposer = useStore((s) => s.setComposer)
  const startTask = useStore((s) => s.startTask)
  const stopStreaming = useStore((s) => s.stopStreaming)
  const showToast = useStore((s) => s.showToast)
  const addPendingAttachment = useStore((s) => s.addPendingAttachment)
  const updatePendingAttachment = useStore((s) => s.updatePendingAttachment)
  const removePendingAttachment = useStore((s) => s.removePendingAttachment)

  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const voiceMenuRef = useRef<HTMLDivElement>(null)
  const voiceBtnRef = useRef<HTMLButtonElement>(null)
  const [slashIdx, setSlashIdx] = useState(-1)
  const [slashDismissed, setSlashDismissed] = useState(false)
  const [uploading, setUploading] = useState(false)

  // ── voice state ──
  const [voiceMenuOpen, setVoiceMenuOpen] = useState(false)
  const [voiceMode, setVoiceMode] = useState<ComposerVoiceMode>(null)
  const [pushRecording, setPushRecording] = useState(false)
  const voiceModeRef = useRef<ComposerVoiceMode>(null)
  const dictateRef = useRef<RecognizerHandle | null>(null)
  const dictateBaseRef = useRef('')
  const dictateRecorderRef = useRef<RecordController | null>(null)
  const pushRecognizerRef = useRef<RecognizerHandle | null>(null)
  const pushRecorderRef = useRef<RecordController | null>(null)
  const hasBrowserSpeech = browserSpeechSupported()

  useEffect(() => {
    voiceModeRef.current = voiceMode
  }, [voiceMode])

  // Reset slashDismissed veto whenever the user clears the slash prefix
  useEffect(() => {
    if (!composer.startsWith('/')) setSlashDismissed(false)
  }, [composer])

  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 140) + 'px'
  }, [composer])

  // Stop any in-flight recognition / recording when the composer unmounts.
  useEffect(() => {
    return () => {
      dictateRef.current?.abort()
      pushRecognizerRef.current?.abort()
      dictateRecorderRef.current?.cancel()
      pushRecorderRef.current?.cancel()
    }
  }, [])

  const canSend = (composer.trim().length > 0 || pendingAttachments.length > 0) && !streaming

  const firstToken = composer.startsWith('/') ? composer.split(' ')[0] : ''
  const filtered = SLASH_ITEMS.filter((i) => i.cmd.startsWith(firstToken))
  const menuVisible = slashOpen && !slashDismissed && filtered.length > 0

  // Drive slashIdx: 0 when menu opens or filtered list changes, -1 when hidden
  useEffect(() => {
    setSlashIdx(menuVisible ? 0 : -1)
  }, [menuVisible, filtered.length]) // eslint-disable-line react-hooks/exhaustive-deps

  function handleInput(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setComposer(e.target.value)
  }

  function handleSend() {
    if (canSend) startTask(composer)
  }

  function handleSlashPick(cmd: string) {
    if (cmd === '/sessions') {
      setComposer('')
      setSlashIdx(-1)
      onOpenSessionsPicker()
      return
    }
    setComposer(cmd + ' ')
    setSlashIdx(-1)
  }

  // ── File picker ──────────────────────────────────────────────
  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? [])
    if (!files.length) return
    // Reset input so picking the same file again re-triggers
    e.target.value = ''

    for (const file of files) {
      // Unique local key so we can update the chip once the server responds.
      const localId = `local-${Date.now()}-${Math.random().toString(36).slice(2)}`
      // 1. Show the chip immediately with uploading=true.
      const optimistic = makeOptimisticAttachment(file, localId)
      addPendingAttachment(optimistic)
      setUploading(true)

      // 2. Upload in the background; update or error the chip when done.
      // Pass the already-determined mediaType so the server gets it via ?media_type=
      // even when the browser omits the multipart Content-Type (HEIC, AVIF, etc.).
      uploadFile(file, optimistic.mediaType)
        .then(async (realFileId) => {
          const meta = await getFileMeta(realFileId)
          updatePendingAttachment(localId, {
            fileId: realFileId,
            uploading: false,
            name: meta?.name ?? file.name,
            mediaType: meta?.media_type ?? optimistic.mediaType,
            size: meta?.size ?? file.size,
          })
        })
        .catch((err: unknown) => {
          const msg = err instanceof Error ? err.message : 'Upload failed'
          updatePendingAttachment(localId, { uploading: false, error: msg })
        })
        .finally(() => {
          setUploading(false)
        })
    }
  }

  // ── Voice menu ────────────────────────────────────────────────
  // Close the "Talk to Hachi" menu on outside click / Escape.
  useEffect(() => {
    if (!voiceMenuOpen) return
    function onDown(e: MouseEvent) {
      const target = e.target as Node
      // Ignore clicks on the toggle button — its own onClick handles closing,
      // otherwise mousedown-close + click-reopen would leave the menu stuck open.
      if (voiceBtnRef.current && voiceBtnRef.current.contains(target)) return
      if (voiceMenuRef.current && !voiceMenuRef.current.contains(target)) {
        setVoiceMenuOpen(false)
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setVoiceMenuOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [voiceMenuOpen])

  function pickVoice(mode: 'push' | 'dictate' | 'continuous') {
    setVoiceMenuOpen(false)
    if (mode === 'continuous') {
      onStartContinuous()
      return
    }
    if (mode === 'dictate') {
      startDictate()
      return
    }
    // push-to-talk: reveal the hold row; recording starts on hold.
    setVoiceMode('push')
  }

  // ── Dictate: stream a live transcript into the composer ──
  function startDictate() {
    dictateBaseRef.current = composer.trim() ? composer.trim() + ' ' : ''
    if (hasBrowserSpeech) {
      const handle = startRecognition({
        continuous: true,
        onPartial: (text) => setComposer((dictateBaseRef.current + text).trimStart()),
        onEnd: () => {
          dictateRef.current = null
          if (voiceModeRef.current === 'dictate') setVoiceMode(null)
        },
        onError: (err) => {
          if (err === 'not-allowed' || err === 'service-not-allowed') {
            showToast('Microphone access denied', 'blocked')
          }
        },
      })
      if (!handle) {
        showToast('Dictation is not available in this browser', 'blocked')
        return
      }
      dictateRef.current = handle
      setVoiceMode('dictate')
      return
    }
    // Fallback: gateway record → transcribe (no live preview).
    if (gatewayReady) {
      setVoiceMode('dictate')
      recordAndTranscribe()
        .then((ctrl) => {
          dictateRecorderRef.current = ctrl
          void ctrl.done.then((text) => {
            dictateRecorderRef.current = null
            if (text) setComposer((dictateBaseRef.current + text).trimStart())
            if (voiceModeRef.current === 'dictate') setVoiceMode(null)
          })
        })
        .catch(() => {
          showToast('Microphone access denied', 'blocked')
          setVoiceMode(null)
        })
      return
    }
    showToast('Dictation needs a Chromium browser or a configured voice provider', 'blocked')
  }

  function stopDictate() {
    if (dictateRef.current) {
      dictateRef.current.stop() // onEnd resets voiceMode
      return
    }
    if (dictateRecorderRef.current) {
      dictateRecorderRef.current.stop() // done handler resets voiceMode
      return
    }
    setVoiceMode(null)
  }

  // ── Push-to-talk: hold to record, release to transcribe + send ──
  function holdStart() {
    if (voiceModeRef.current !== 'push' || pushRecording) return
    if (hasBrowserSpeech) {
      const handle = startRecognition({
        continuous: false,
        onFinal: (text) => {
          pushRecognizerRef.current = null
          const t = text.trim()
          setPushRecording(false)
          setVoiceMode(null)
          if (t && !useStore.getState().streaming) startTask(t)
        },
        onError: (err) => {
          pushRecognizerRef.current = null
          setPushRecording(false)
          if (err === 'not-allowed' || err === 'service-not-allowed') {
            showToast('Microphone access denied', 'blocked')
          }
        },
      })
      if (!handle) {
        showToast('Push-to-talk is not available in this browser', 'blocked')
        return
      }
      pushRecognizerRef.current = handle
      setPushRecording(true)
      return
    }
    if (gatewayReady) {
      setPushRecording(true)
      recordAndTranscribe()
        .then((ctrl) => {
          pushRecorderRef.current = ctrl
        })
        .catch(() => {
          setPushRecording(false)
          showToast('Microphone access denied', 'blocked')
        })
      return
    }
    showToast('Push-to-talk needs a Chromium browser or a configured voice provider', 'blocked')
  }

  function holdEnd() {
    if (!pushRecording) return
    if (pushRecognizerRef.current) {
      pushRecognizerRef.current.stop() // onFinal sends + resets
      return
    }
    if (pushRecorderRef.current) {
      const ctrl = pushRecorderRef.current
      pushRecorderRef.current = null
      setPushRecording(false)
      setVoiceMode(null)
      ctrl.stop()
      void ctrl.done.then((text) => {
        const t = text.trim()
        if (t && !useStore.getState().streaming) startTask(t)
      })
      return
    }
    setPushRecording(false)
  }

  function exitVoice() {
    pushRecognizerRef.current?.abort()
    pushRecognizerRef.current = null
    pushRecorderRef.current?.cancel()
    pushRecorderRef.current = null
    setPushRecording(false)
    setVoiceMode(null)
  }

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (slashOpen) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSlashIdx((i) => Math.min(i + 1, Math.max(0, filtered.length - 1)))
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSlashIdx((i) => Math.max(i - 1, 0))
        return
      }
      if (e.key === 'Enter') {
        e.preventDefault()
        if (filtered[slashIdx]) handleSlashPick(filtered[slashIdx].cmd)
        return
      }
      if (e.key === 'Escape') {
        e.preventDefault()
        setSlashDismissed(true)
        return
      }
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (canSend) startTask(composer)
    }
  }, [slashOpen, slashIdx, filtered, canSend, composer, startTask, setSlashDismissed])

  const dictating = voiceMode === 'dictate'
  const isPush = voiceMode === 'push'

  return (
    <div
      className="hachi-composer-wrap"
      style={{
        flexShrink: 0,
        borderTop: '0.5px solid var(--hachi-line)',
        background: 'var(--hachi-canvas)',
        padding: '16px 32px 22px',
      }}
    >
      <div
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={menuVisible}
        style={{
          maxWidth: 760,
          margin: '0 auto',
          position: 'relative',
        }}
      >
        {menuVisible && (
          <div
            id="hachi-slash-listbox"
            style={{
              position: 'absolute',
              bottom: 'calc(100% + 8px)',
              left: 0,
              right: 0,
              background: 'var(--hachi-surface)',
              border: '0.5px solid var(--hachi-line)',
              borderRadius: 12,
              overflow: 'hidden',
              boxShadow: '0 8px 24px rgba(28,26,32,.08)',
              zIndex: 10,
            }}
            role="listbox"
            aria-label="Slash commands"
          >
            {filtered.map((item, idx) => (
              <SlashItem
                key={item.cmd}
                id={`slash-item-${idx}`}
                cmd={item.cmd}
                desc={item.desc}
                active={idx === slashIdx}
                onPick={() => handleSlashPick(item.cmd)}
              />
            ))}
          </div>
        )}

        {/* Pending attachment chips */}
        {pendingAttachments.length > 0 && (
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 8,
              padding: '0 2px 10px',
            }}
          >
            {pendingAttachments.map((a) => (
              <AttachmentChip
                key={a.fileId}
                attachment={a}
                onRemove={() => {
                  if (a.localUrl) URL.revokeObjectURL(a.localUrl)
                  removePendingAttachment(a.fileId)
                }}
              />
            ))}
          </div>
        )}

        {/* Talk-to-Hachi voice menu */}
        {voiceMenuOpen && (
          <div
            ref={voiceMenuRef}
            role="menu"
            aria-label="Talk to Hachi"
            style={{
              position: 'absolute',
              bottom: 'calc(100% + 8px)',
              right: 0,
              width: 308,
              background: 'var(--hachi-surface)',
              border: '0.5px solid var(--hachi-line)',
              borderRadius: 14,
              overflow: 'hidden',
              boxShadow: '0 8px 28px rgba(28,26,32,.12)',
              zIndex: 11,
              animation: 'hachiPop .14s ease',
            }}
          >
            <div
              style={{
                padding: '11px 14px 9px',
                fontSize: 12,
                color: 'var(--hachi-muted)',
                borderBottom: '0.5px solid var(--hachi-line)',
              }}
            >
              Talk to Hachi
            </div>
            <VoiceOption
              icon="mic"
              name="Push to talk"
              desc="Hold the button, release to send."
              onPick={() => pickVoice('push')}
            />
            <VoiceOption
              icon="audio-lines"
              name="Dictate"
              desc="Speak and I'll type it into the box."
              onPick={() => pickVoice('dictate')}
            />
            <VoiceOption
              icon="headphones"
              name="Continuous"
              desc="Hands-free, back-and-forth conversation."
              onPick={() => pickVoice('continuous')}
            />
          </div>
        )}

        {/* Hidden file input (shared by the attach button) */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="image/*,text/*,application/json,application/pdf,.md,.csv,.ts,.tsx,.js,.jsx,.py,.go,.rs,.java"
          style={{ display: 'none' }}
          onChange={handleFileChange}
        />

        {/* ── input row: normal + dictate ── */}
        {!isPush && (
          <div
            style={{
              display: 'flex',
              gap: 6,
              alignItems: 'flex-end',
              background: 'var(--hachi-surface)',
              border: '0.5px solid var(--hachi-line)',
              borderRadius: 14,
              padding: '7px 8px',
            }}
          >
            {/* File attach */}
            <button
              type="button"
              className="hachi-composer-attach-btn"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading || streaming}
              title="Attach a file"
              style={{
                flexShrink: 0,
                width: 42,
                height: 42,
                borderRadius: 10,
                border: 'none',
                background: 'transparent',
                color: uploading ? 'var(--hachi-brand)' : 'var(--hachi-muted)',
                display: 'grid',
                placeItems: 'center',
                cursor: uploading || streaming ? 'default' : 'pointer',
                opacity: streaming ? 0.4 : 1,
              }}
            >
              <Icon name={uploading ? 'refresh' : 'paperclip'} size={18} />
            </button>

            <textarea
              ref={textareaRef}
              value={composer}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              rows={1}
              placeholder="Message Hachi…  /  for commands"
              aria-label="Message Hachi"
              aria-autocomplete="list"
              aria-controls="hachi-slash-listbox"
              aria-activedescendant={menuVisible && slashIdx >= 0 ? `slash-item-${slashIdx}` : undefined}
              style={{
                flex: 1,
                resize: 'none',
                border: 'none',
                background: 'transparent',
                font: 'inherit',
                fontSize: 15,
                lineHeight: '24px',
                color: 'var(--hachi-ink)',
                outline: 'none',
                padding: '9px 4px',
                maxHeight: 140,
                overflowY: 'auto',
              }}
            />

            {/* Dictating indicator + stop, OR the Talk-to-Hachi mic */}
            {dictating ? (
              <>
                <div
                  style={{
                    flexShrink: 0,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 9,
                    padding: '0 6px 0 2px',
                  }}
                >
                  <VoiceWave height={20} color="var(--hachi-brand)" />
                  <span style={{ fontSize: 12.5, color: 'var(--hachi-muted)', whiteSpace: 'nowrap' }}>
                    Dictating…
                  </span>
                </div>
                <button
                  type="button"
                  onClick={stopDictate}
                  title="Stop dictation"
                  aria-label="Stop dictation"
                  style={{
                    flexShrink: 0,
                    width: 42,
                    height: 42,
                    borderRadius: 10,
                    border: 'none',
                    background: 'var(--hachi-brand)',
                    color: 'var(--hachi-canvas)',
                    display: 'grid',
                    placeItems: 'center',
                    cursor: 'pointer',
                  }}
                >
                  <Icon name="stop" size={15} />
                </button>
              </>
            ) : (
              <button
                ref={voiceBtnRef}
                type="button"
                className="hachi-composer-voice-btn"
                onClick={() => setVoiceMenuOpen((v) => !v)}
                aria-haspopup="menu"
                aria-expanded={voiceMenuOpen}
                title="Talk to Hachi"
                style={{
                  flexShrink: 0,
                  width: 42,
                  height: 42,
                  borderRadius: 10,
                  border: 'none',
                  background: voiceMenuOpen ? 'var(--hachi-cream)' : undefined,
                  color: voiceMenuOpen ? 'var(--hachi-ink)' : undefined,
                  display: 'grid',
                  placeItems: 'center',
                  cursor: 'pointer',
                }}
              >
                <Icon name="mic" size={18} />
              </button>
            )}

            {streaming && (
              <button
                type="button"
                className="hachi-cancel-btn"
                aria-label="Stop generating"
                onClick={stopStreaming}
                style={{
                  flexShrink: 0,
                  width: 42,
                  height: 42,
                  borderRadius: 10,
                  border: '1px solid var(--hachi-trust)',
                  background: 'transparent',
                  color: 'var(--hachi-trust)',
                  display: 'grid',
                  placeItems: 'center',
                  cursor: 'pointer',
                }}
              >
                <Icon name="stop" size={16} />
              </button>
            )}

            <button
              type="button"
              className="hachi-mcp-submit-btn"
              aria-label="Send message"
              onClick={handleSend}
              disabled={!canSend}
              style={{
                flexShrink: 0,
                width: 42,
                height: 42,
                borderRadius: 10,
                border: '0.5px solid transparent',
                display: 'grid',
                placeItems: 'center',
              }}
            >
              <Icon name="send" size={16} />
            </button>
          </div>
        )}

        {/* ── input row: push-to-talk ── */}
        {isPush && (
          <div
            style={{
              display: 'flex',
              gap: 10,
              alignItems: 'center',
              background: 'var(--hachi-surface)',
              border: '0.5px solid var(--hachi-line)',
              borderRadius: 14,
              padding: 8,
            }}
          >
            <button
              type="button"
              className="hachi-composer-attach-btn"
              onClick={exitVoice}
              title="Leave voice"
              aria-label="Leave voice"
              style={{
                flexShrink: 0,
                width: 42,
                height: 42,
                borderRadius: 10,
                border: 'none',
                background: 'transparent',
                color: 'var(--hachi-muted)',
                display: 'grid',
                placeItems: 'center',
                cursor: 'pointer',
              }}
            >
              <Icon name="x" size={18} />
            </button>
            <button
              type="button"
              onMouseDown={holdStart}
              onMouseUp={holdEnd}
              onMouseLeave={holdEnd}
              onTouchStart={(e) => {
                e.preventDefault()
                holdStart()
              }}
              onTouchEnd={(e) => {
                e.preventDefault()
                holdEnd()
              }}
              aria-label={pushRecording ? 'Release to send' : 'Hold to talk'}
              style={{
                flex: 1,
                height: 48,
                borderRadius: 11,
                border: `0.5px solid ${pushRecording ? 'transparent' : 'var(--hachi-line)'}`,
                background: pushRecording ? 'var(--hachi-brand)' : 'var(--hachi-cream)',
                color: pushRecording ? 'var(--hachi-canvas)' : 'var(--hachi-ink)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 11,
                cursor: 'pointer',
                font: 'inherit',
                userSelect: 'none',
              }}
            >
              {pushRecording ? (
                <>
                  <VoiceWave height={22} color="currentColor" />
                  <span style={{ fontSize: 14, fontWeight: 500 }}>Release to send</span>
                </>
              ) : (
                <>
                  <Icon name="mic" size={18} />
                  <span style={{ fontSize: 14, fontWeight: 500 }}>Hold to talk</span>
                </>
              )}
            </button>
          </div>
        )}

        <div
          style={{
            fontSize: 12,
            color: 'var(--hachi-muted)',
            marginTop: 8,
            textAlign: 'center',
          }}
        >
          Hachi runs on your machine · it asks before anything risky · you can stop anytime
        </div>
      </div>
    </div>
  )
})
