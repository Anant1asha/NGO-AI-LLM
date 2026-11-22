// ContinuousVoice — hands-free, back-and-forth voice overlay for Hachi.
//
// Renders the design's full-screen "Continuous voice" overlay (pulsing orb,
// status + caption, mute / end controls) and drives a real conversational loop:
//
//   listening → (utterance) → thinking → speaking → listening …
//
// Two engines:
//   - gateway  — MediaRecorder + Web Audio silence detection → POST /voice/
//                transcribe for STT, POST /voice/speak for TTS. Preferred when
//                gateway voice is configured.
//   - browser  — Web Speech recognition for STT + SpeechSynthesis for TTS.
//                Universal fallback; needs no backend / API keys.
//
// The parent owns the chat: onTranscript(text) sends the message, then feeds the
// completed assistant reply back via assistantText (with streaming=false). This
// component watches that to know when to speak and resume listening.

import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Icon } from '../icons/Icon'
import { HachiMark } from '../brand/HachiMark'
import { speakText } from '../../lib/data/domains/voice'
import {
  startRecognition,
  browserSpeak,
  cancelBrowserSpeak,
  browserSpeechSupported,
  pickAudioMime,
  type RecognizerHandle,
} from '../../lib/voice/speech'
import { transcribeAudio } from '../../lib/data/domains/voice'

type Phase = 'idle' | 'listening' | 'thinking' | 'speaking'
type Engine = 'gateway' | 'browser' | 'none'

interface ContinuousVoiceProps {
  open: boolean
  /** True when gateway STT/TTS is configured (prefer it over the browser engine). */
  gatewayReady: boolean
  /** Store streaming flag — true while the assistant reply is in flight. */
  streaming: boolean
  /** Latest completed assistant reply text (used for TTS). */
  assistantText: string
  /** Send the recognised utterance as a chat message. */
  onTranscript: (text: string) => void
  onClose: () => void
}

// RMS below this (0–255 Uint8 analyser scale) counts as silence.
const SILENCE_THRESHOLD = 12
// Consecutive silent frames before an utterance is considered finished (~625ms at 60fps).
// Reduced from 40 → 25 (FIX P3: cut ~250ms tail on VAD hangover).
// Exported so the VAD regression test can assert the value without rendering the component.
export const SILENCE_HANGOVER_FRAMES = 25
// Hard cap on a single utterance so a silent mic can never trap the loop.
const MAX_UTTERANCE_MS = 15_000

export default function ContinuousVoice({
  open,
  gatewayReady,
  streaming,
  assistantText,
  onTranscript,
  onClose,
}: ContinuousVoiceProps) {
  const engine: Engine = gatewayReady
    ? 'gateway'
    : browserSpeechSupported()
      ? 'browser'
      : 'none'

  const [phase, setPhase] = useState<Phase>('idle')
  const [muted, setMuted] = useState(false)
  const [statusText, setStatusText] = useState('Listening…')
  const [captionText, setCaptionText] = useState("Say something — I'm listening.")
  const [errorText, setErrorText] = useState<string | null>(null)

  // ── refs that survive renders without triggering them ──
  const phaseRef = useRef<Phase>('idle')
  const mutedRef = useRef(false)
  const openRef = useRef(false)
  const awaitingReplyRef = useRef(false)
  const baselineReplyRef = useRef('')
  const latestReplyRef = useRef('')

  // gateway STT
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const silenceCountRef = useRef(0)
  const heardSpeechRef = useRef(false)
  const rafRef = useRef<number | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const maxUtteranceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const isAcquiringRef = useRef(false)

  // browser STT
  const recognizerRef = useRef<RecognizerHandle | null>(null)

  // gateway TTS
  const currentAudioRef = useRef<HTMLAudioElement | null>(null)
  const currentObjUrlRef = useRef<string | null>(null)

  useEffect(() => {
    phaseRef.current = phase
  }, [phase])
  useEffect(() => {
    mutedRef.current = muted
  }, [muted])

  // ── teardown helpers ──

  /**
   * Stop the current MediaRecorder + VAD loop but KEEP the shared MediaStream
   * and AudioContext alive for the next utterance (FIX P2: stream reuse).
   * Only tears down the cheap per-utterance objects.
   */
  const stopGatewayCapture = useCallback(() => {
    if (maxUtteranceTimerRef.current !== null) {
      clearTimeout(maxUtteranceTimerRef.current)
      maxUtteranceTimerRef.current = null
    }
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current)
      rafRef.current = null
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try {
        mediaRecorderRef.current.stop()
      } catch {
        /* ignore */
      }
    }
    mediaRecorderRef.current = null
    // NOTE: streamRef / audioContextRef / analyserRef are NOT closed here —
    // they are shared across utterances and only closed by teardownGatewayAudio.
    isAcquiringRef.current = false
  }, [])

  /**
   * Full teardown of the shared MediaStream + AudioContext.
   * Call only on voice session end (handleEnd / close).
   */
  const teardownGatewayAudio = useCallback(() => {
    stopGatewayCapture()
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
    if (audioContextRef.current) {
      try {
        void audioContextRef.current.close()
      } catch {
        /* ignore */
      }
      audioContextRef.current = null
      analyserRef.current = null
    }
  }, [stopGatewayCapture])

  const stopBrowserCapture = useCallback(() => {
    if (recognizerRef.current) {
      recognizerRef.current.abort()
      recognizerRef.current = null
    }
  }, [])

  const stopTts = useCallback(() => {
    if (currentAudioRef.current) {
      currentAudioRef.current.pause()
      currentAudioRef.current = null
    }
    if (currentObjUrlRef.current) {
      URL.revokeObjectURL(currentObjUrlRef.current)
      currentObjUrlRef.current = null
    }
    cancelBrowserSpeak()
  }, [])

  const stopEverything = useCallback(() => {
    teardownGatewayAudio()
    stopBrowserCapture()
    stopTts()
  }, [teardownGatewayAudio, stopBrowserCapture, stopTts])

  // forward declaration via ref so callbacks can call the latest startListening
  const startListeningRef = useRef<() => void>(() => {})

  // ── handle a recognised utterance ──

  const handleText = useCallback(
    (raw: string) => {
      if (!openRef.current) return
      const text = raw.trim()
      if (!text) {
        // Nothing heard — quietly resume listening unless muted.
        if (!mutedRef.current) startListeningRef.current()
        return
      }
      baselineReplyRef.current = latestReplyRef.current
      awaitingReplyRef.current = true
      setPhase('thinking')
      setStatusText('Hachi is thinking…')
      setCaptionText(text)
      onTranscript(text)
    },
    [onTranscript],
  )

  // ── gateway STT: MediaRecorder + silence detection ──

  const handleGatewayStop = useCallback(async () => {
    const blob = new Blob(chunksRef.current, { type: pickAudioMime() || 'audio/webm' })
    chunksRef.current = []
    if (!openRef.current) return
    if (blob.size < 1200) {
      if (!mutedRef.current) startListeningRef.current()
      return
    }
    setPhase('thinking')
    setStatusText('Transcribing…')
    try {
      const res = await transcribeAudio(blob)
      handleText(res.text)
    } catch {
      if (!openRef.current) return
      setErrorText('Could not transcribe — tap mute then unmute to retry.')
      setPhase('listening')
    }
  }, [handleText])

  const pollSilence = useCallback(() => {
    if (!analyserRef.current || phaseRef.current !== 'listening') return
    const data = new Uint8Array(analyserRef.current.frequencyBinCount)
    analyserRef.current.getByteTimeDomainData(data)
    let sum = 0
    for (let i = 0; i < data.length; i++) {
      const d = data[i] - 128
      sum += d * d
    }
    const rms = Math.sqrt(sum / data.length)
    if (rms < SILENCE_THRESHOLD) {
      silenceCountRef.current++
    } else {
      silenceCountRef.current = 0
      if (!heardSpeechRef.current) {
        // FIX P3: First speech detected — arm the max-utterance timer now
        // (not before, so leading silence never counts toward the timeout and
        // the recording is never sent to STT if only silence was captured).
        heardSpeechRef.current = true
        if (maxUtteranceTimerRef.current === null) {
          maxUtteranceTimerRef.current = setTimeout(() => {
            maxUtteranceTimerRef.current = null
            if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
              mediaRecorderRef.current.stop()
            }
          }, MAX_UTTERANCE_MS)
        }
      }
    }
    if (silenceCountRef.current >= SILENCE_HANGOVER_FRAMES && heardSpeechRef.current) {
      if (maxUtteranceTimerRef.current !== null) {
        clearTimeout(maxUtteranceTimerRef.current)
        maxUtteranceTimerRef.current = null
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.stop()
      }
      return
    }
    rafRef.current = requestAnimationFrame(pollSilence)
  }, [])

  const startGatewayListening = useCallback(async () => {
    if (isAcquiringRef.current || phaseRef.current === 'listening') return
    isAcquiringRef.current = true
    chunksRef.current = []
    silenceCountRef.current = 0
    heardSpeechRef.current = false

    // FIX P2: Reuse the existing MediaStream + AudioContext across utterances.
    // Only acquire getUserMedia when we don't already have a live stream.
    if (!streamRef.current || streamRef.current.getTracks().every((t) => t.readyState === 'ended')) {
      let stream: MediaStream
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      } catch {
        isAcquiringRef.current = false
        setErrorText('Microphone access denied')
        return
      }
      if (!openRef.current || mutedRef.current) {
        stream.getTracks().forEach((t) => t.stop())
        isAcquiringRef.current = false
        return
      }
      streamRef.current = stream

      // Build AudioContext + Analyser once per stream acquisition.
      const ctx = new AudioContext()
      audioContextRef.current = ctx
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 512
      analyserRef.current = analyser
      ctx.createMediaStreamSource(stream).connect(analyser)
    }

    // Resume a suspended AudioContext (browser may suspend on tab switch).
    if (audioContextRef.current && audioContextRef.current.state === 'suspended') {
      try {
        await audioContextRef.current.resume()
      } catch { /* ignore */ }
    }

    // Build a fresh MediaRecorder from the shared stream (cheap — no getUserMedia).
    const mimeType = pickAudioMime()
    const recorder = new MediaRecorder(streamRef.current!, mimeType ? { mimeType } : undefined)
    mediaRecorderRef.current = recorder
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data)
    }
    // onstop: do NOT stop stream tracks — they are reused next utterance.
    recorder.onstop = () => {
      void handleGatewayStop()
    }
    recorder.start(200)
    isAcquiringRef.current = false

    setPhase('listening')
    setErrorText(null)
    setStatusText('Listening…')
    setCaptionText("Say something — I'm listening.")

    // FIX P3: Pre-speech gate — only start the max-utterance timer once we
    // have heard actual speech (heardSpeechRef.current = true).  The VAD loop
    // sets heardSpeechRef before calling this, but for the initial "open" call
    // we defer the timer start to the first detected speech event instead of
    // starting it unconditionally here.
    // The timer is armed inside pollSilence when heardSpeechRef first flips.
    // Clear any stale timer from a previous utterance.
    if (maxUtteranceTimerRef.current !== null) {
      clearTimeout(maxUtteranceTimerRef.current)
      maxUtteranceTimerRef.current = null
    }

    rafRef.current = requestAnimationFrame(pollSilence)
  }, [handleGatewayStop, pollSilence])

  // ── browser STT ──

  const startBrowserListening = useCallback(() => {
    if (phaseRef.current === 'listening' && recognizerRef.current) return
    stopBrowserCapture()
    const handle = startRecognition({
      continuous: false,
      onFinal: (text) => {
        recognizerRef.current = null
        handleText(text)
      },
      onError: (err) => {
        recognizerRef.current = null
        if (err === 'no-speech' || err === 'aborted') {
          if (openRef.current && !mutedRef.current) startListeningRef.current()
          return
        }
        if (err === 'not-allowed' || err === 'service-not-allowed') {
          setErrorText('Microphone access denied')
        }
      },
    })
    if (!handle) {
      setErrorText('Voice input is not available in this browser')
      return
    }
    recognizerRef.current = handle
    setPhase('listening')
    setErrorText(null)
    setStatusText('Listening…')
    setCaptionText("Say something — I'm listening.")
  }, [handleText, stopBrowserCapture])

  const startListening = useCallback(() => {
    if (!openRef.current || mutedRef.current) return
    if (engine === 'gateway') void startGatewayListening()
    else if (engine === 'browser') startBrowserListening()
  }, [engine, startGatewayListening, startBrowserListening])

  useEffect(() => {
    startListeningRef.current = startListening
  }, [startListening])

  // ── speak a reply, then resume listening ──

  const speakReply = useCallback(
    async (text: string) => {
      if (!openRef.current) return
      setPhase('speaking')
      setStatusText('Hachi is speaking')
      setCaptionText(text)
      try {
        if (engine === 'gateway') {
          const objUrl = await speakText(text, { format: 'mp3' })
          if (!openRef.current) {
            URL.revokeObjectURL(objUrl)
            return
          }
          currentObjUrlRef.current = objUrl
          const audio = new Audio(objUrl)
          currentAudioRef.current = audio
          await new Promise<void>((resolve) => {
            audio.onended = () => resolve()
            audio.onerror = () => resolve()
            audio.play().catch(() => resolve())
          })
        } else {
          await browserSpeak(text)
        }
      } catch {
        // Non-fatal: fall through and resume listening.
      } finally {
        if (currentObjUrlRef.current) {
          URL.revokeObjectURL(currentObjUrlRef.current)
          currentObjUrlRef.current = null
        }
        currentAudioRef.current = null
      }
      if (openRef.current && !mutedRef.current) startListening()
    },
    [engine, startListening],
  )

  // ── watch the assistant reply: speak it once streaming finishes ──

  useEffect(() => {
    latestReplyRef.current = assistantText
    if (!open || !awaitingReplyRef.current) return
    if (streaming) {
      setPhase('thinking')
      setStatusText('Hachi is thinking…')
      return
    }
    if (assistantText && assistantText !== baselineReplyRef.current) {
      awaitingReplyRef.current = false
      void speakReply(assistantText)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assistantText, streaming, open])

  // ── open / close lifecycle ──

  useEffect(() => {
    openRef.current = open
    if (open) {
      latestReplyRef.current = assistantText
      baselineReplyRef.current = assistantText
      awaitingReplyRef.current = false
      setMuted(false)
      mutedRef.current = false
      setErrorText(null)
      if (engine === 'none') {
        setPhase('idle')
        setStatusText('Voice mode unavailable')
        setCaptionText('Use a Chromium browser or configure a voice provider in Settings.')
      } else {
        startListening()
      }
    } else {
      stopEverything()
      awaitingReplyRef.current = false
      setPhase('idle')
    }
    return () => {
      if (!open) return
      stopEverything()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  // ── controls ──

  const toggleMute = useCallback(() => {
    const next = !mutedRef.current
    mutedRef.current = next
    setMuted(next)
    if (next) {
      stopGatewayCapture()
      stopBrowserCapture()
      stopTts()
      awaitingReplyRef.current = false
      setPhase('listening')
      setStatusText('Muted')
      setCaptionText('Tap the mic to resume.')
    } else {
      setStatusText('Listening…')
      setCaptionText("Say something — I'm listening.")
      startListening()
    }
  }, [stopGatewayCapture, stopBrowserCapture, stopTts, startListening])

  const handleEnd = useCallback(() => {
    stopEverything()
    onClose()
  }, [stopEverything, onClose])

  if (!open) return null

  const showThinkingDots = phase === 'thinking'

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Continuous voice"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9000,
        background: 'rgba(28,26,32,.58)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 38,
        animation: 'hachiPop .2s ease',
      }}
    >
      {/* top label */}
      <div
        style={{
          position: 'absolute',
          top: 26,
          left: 0,
          right: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 8,
          fontSize: 13,
          color: 'rgba(247,241,228,.7)',
        }}
      >
        <Icon name="headphones" size={15} />
        <span>Continuous voice · hands-free</span>
      </div>

      {/* orb + rings */}
      <div style={{ position: 'relative', width: 208, height: 208, display: 'grid', placeItems: 'center' }}>
        {phase !== 'idle' && (
          <>
            <div
              style={{
                position: 'absolute',
                width: 200,
                height: 200,
                borderRadius: '50%',
                border: '1.5px solid rgba(243,233,210,.45)',
                animation: 'hachiRing 2.6s ease-out infinite',
              }}
            />
            <div
              style={{
                position: 'absolute',
                width: 200,
                height: 200,
                borderRadius: '50%',
                border: '1.5px solid rgba(243,233,210,.35)',
                animation: 'hachiRing 2.6s ease-out infinite 1.3s',
              }}
            />
          </>
        )}
        <div
          style={{
            width: 130,
            height: 130,
            borderRadius: '50%',
            background: 'var(--hachi-canvas)',
            boxShadow: '0 20px 64px rgba(0,0,0,.4)',
            display: 'grid',
            placeItems: 'center',
            animation: 'hachiOrb 3s ease-in-out infinite',
          }}
        >
          {showThinkingDots ? (
            <div style={{ display: 'flex', gap: 7 }}>
              <span style={dotStyle(0)} />
              <span style={dotStyle(0.2)} />
              <span style={dotStyle(0.4)} />
            </div>
          ) : (
            <HachiMark size={62} />
          )}
        </div>
      </div>

      {/* status + caption */}
      <div style={{ textAlign: 'center', minHeight: 90, maxWidth: 540, padding: '0 24px' }}>
        <div style={{ fontFamily: 'var(--font-display)', fontWeight: 500, fontSize: 22, color: '#F7F1E4' }}>
          {statusText}
        </div>
        <div style={{ fontSize: 15, lineHeight: '24px', color: 'rgba(247,241,228,.78)', marginTop: 10 }}>
          {errorText ?? captionText}
        </div>
      </div>

      {/* controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
        <button
          type="button"
          onClick={toggleMute}
          disabled={engine === 'none'}
          title={muted ? 'Resume' : 'Mute'}
          aria-label={muted ? 'Resume listening' : 'Mute'}
          style={{
            width: 58,
            height: 58,
            borderRadius: '50%',
            border: '1px solid rgba(247,241,228,.3)',
            background: muted ? 'rgba(217,119,87,.35)' : 'rgba(247,241,228,.12)',
            color: '#F7F1E4',
            display: 'grid',
            placeItems: 'center',
            cursor: engine === 'none' ? 'default' : 'pointer',
            opacity: engine === 'none' ? 0.4 : 1,
          }}
        >
          <Icon name={muted ? 'audio-lines' : 'mic'} size={22} />
        </button>
        <button
          type="button"
          onClick={handleEnd}
          title="End voice"
          aria-label="End voice"
          style={{
            width: 58,
            height: 58,
            borderRadius: '50%',
            border: 'none',
            background: 'var(--hachi-danger)',
            color: '#fff',
            display: 'grid',
            placeItems: 'center',
            cursor: 'pointer',
          }}
        >
          <Icon name="phone-off" size={22} />
        </button>
      </div>

      {/* scoped keyframes */}
      <style>{`
        @keyframes hachiRing { 0% { transform: scale(0.9); opacity: .55; } 70% { opacity: 0; } 100% { transform: scale(1.9); opacity: 0; } }
        @keyframes hachiOrb { 0%,100% { transform: scale(1); } 50% { transform: scale(1.05); } }
        @keyframes hachiThink { 0%,80%,100% { opacity: .25; transform: translateY(0); } 40% { opacity: 1; transform: translateY(-4px); } }
      `}</style>
    </div>
  )
}

function dotStyle(delay: number): React.CSSProperties {
  return {
    width: 9,
    height: 9,
    borderRadius: '50%',
    background: 'var(--hachi-brand)',
    animation: `hachiThink 1.1s ease-in-out infinite ${delay}s`,
  }
}
