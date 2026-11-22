// VoiceSettings â€” the "Voice" settings panel.
//
// Friendly front: a status hero with a one-click "Test voice", a provider toggle,
// and a voice picker you can audition (click a voice to hear it). The technical
// bits â€” API-key env-var names, models, custom base URLs â€” collapse under
// "Advanced". One "Save voice settings" button persists the whole form.
//
// Data: GET/PUT /voice/config, POST /voice/speak (preview/test). UI-only redesign.

import React, { useEffect, useRef, useState } from 'react';
import {
  getVoiceConfig,
  setVoiceConfig,
  speakText,
  type VoiceConfig,
  type VoiceConfigPatch,
} from '../../lib/data/domains/voice';
import { Icon } from '../icons/Icon';
import { cardStyle, sectionHeadingStyle, PanelHeader } from './shared';
import { Input } from '../ui/Input';

const OPENAI_VOICES = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer'];
const SAMPLE_TEXT = "Hi, I'm Hachi. This is how I'll sound.";

export default function VoiceSettings() {
  const [config, setConfig] = useState<VoiceConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveOk, setSaveOk] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  // Editable fields
  const [ttsProvider, setTtsProvider] = useState('openai');
  const [ttsVoice, setTtsVoice] = useState('alloy');
  const [sttModel, setSttModel] = useState('');
  const [ttsModel, setTtsModel] = useState('');
  const [sttBaseUrl, setSttBaseUrl] = useState('');
  const [ttsBaseUrl, setTtsBaseUrl] = useState('');
  const [sttApiKeyEnv, setSttApiKeyEnv] = useState('');
  const [ttsApiKeyEnv, setTtsApiKeyEnv] = useState('');
  const [elApiKeyEnv, setElApiKeyEnv] = useState('');
  const [elVoiceId, setElVoiceId] = useState('');

  // Preview/test playback
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const urlRef = useRef<string | null>(null);
  const [previewing, setPreviewing] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getVoiceConfig()
      .then((cfg) => {
        if (cancelled) return;
        setConfig(cfg);
        setTtsProvider(cfg.tts_provider);
        setTtsVoice(cfg.tts_voice);
        setSttModel(cfg.stt_model ?? '');
        setTtsModel(cfg.tts_model ?? '');
        setElVoiceId(cfg.elevenlabs_voice_id ?? '');
      })
      .catch(() => {
        /* gateway may be offline; show empty form */
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function stopAudio() {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    if (urlRef.current) {
      URL.revokeObjectURL(urlRef.current);
      urlRef.current = null;
    }
    setPreviewing(null);
  }

  // Cleanup on unmount.
  useEffect(() => () => stopAudio(), []);

  async function play(key: string, voice: string) {
    setPreviewError(null);
    if (previewing === key) {
      stopAudio();
      return;
    }
    stopAudio();
    setPreviewing(key);
    try {
      const url = await speakText(SAMPLE_TEXT, { provider: ttsProvider, voice });
      urlRef.current = url;
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => stopAudio();
      audio.onerror = () => {
        setPreviewError('Could not play the audio.');
        stopAudio();
      };
      await audio.play();
    } catch (e: unknown) {
      setPreviewError(
        e instanceof Error ? e.message : 'Could not play â€” check your API key under Advanced.'
      );
      setPreviewing(null);
    }
  }

  async function handleSave() {
    setSaving(true);
    setSaveError(null);
    setSaveOk(false);
    const patch: VoiceConfigPatch = {};
    if (ttsProvider) patch.tts_provider = ttsProvider;
    if (ttsVoice) patch.tts_voice = ttsVoice;
    if (sttModel.trim()) patch.stt_model = sttModel.trim();
    if (ttsModel.trim()) patch.tts_model = ttsModel.trim();
    if (sttBaseUrl.trim()) patch.stt_base_url = sttBaseUrl.trim();
    if (ttsBaseUrl.trim()) patch.tts_base_url = ttsBaseUrl.trim();
    if (sttApiKeyEnv.trim()) patch.stt_api_key_env = sttApiKeyEnv.trim();
    if (ttsApiKeyEnv.trim()) patch.tts_api_key_env = ttsApiKeyEnv.trim();
    if (elApiKeyEnv.trim()) patch.elevenlabs_api_key_env = elApiKeyEnv.trim();
    if (elVoiceId.trim()) patch.elevenlabs_voice_id = elVoiceId.trim();
    try {
      const updated = await setVoiceConfig(patch);
      setConfig(updated);
      setSaveOk(true);
      setTimeout(() => setSaveOk(false), 2500);
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : 'Could not save voice settings');
    } finally {
      setSaving(false);
    }
  }

  const configured = config?.configured ?? false;
  const ttsProviders = config?.available?.tts_providers ?? ['openai', 'elevenlabs'];
  const voices = config?.available?.voices ?? OPENAI_VOICES;
  const spokenVoice = ttsProvider === 'elevenlabs' ? elVoiceId || 'default voice' : ttsVoice;

  if (loading) {
    return (
      <div>
        <PanelHeader title="Voice" subtitle="Talk to Hachi, and let it talk back." />
        <div style={{ ...cardStyle, fontSize: 13, color: 'var(--hachi-muted)' }}>
          Loading voice configâ€¦
        </div>
      </div>
    );
  }

  return (
    <div>
      <PanelHeader title="Voice" subtitle="Talk to Hachi, and let it talk back." />

      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        {/* Status hero */}
        <div style={{ ...cardStyle, display: 'flex', alignItems: 'center', gap: 14 }}>
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: 12,
              background: configured ? 'var(--hachi-success-tint)' : 'var(--hachi-cream)',
              color: configured ? 'var(--hachi-success)' : 'var(--hachi-muted)',
              display: 'grid',
              placeItems: 'center',
              flexShrink: 0,
            }}
          >
            <Icon name="mic" size={22} />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 15, fontWeight: 500 }}>
              {configured ? 'Voice is ready' : "Voice isn't set up yet"}
            </div>
            <div style={{ fontSize: 12.5, color: 'var(--hachi-muted)', marginTop: 2 }}>
              {configured
                ? `Listening with Whisper Â· speaking with ${spokenVoice} (${ttsProvider})`
                : 'Add an API key under Advanced to enable speech.'}
            </div>
          </div>
          <button
            type="button"
            onClick={() => void play('__test__', ttsProvider === 'elevenlabs' ? elVoiceId : ttsVoice)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              height: 34,
              padding: '0 14px',
              borderRadius: 10,
              border: '0.5px solid var(--hachi-line)',
              background: 'var(--hachi-canvas)',
              color: 'var(--hachi-ink)',
              font: '500 13px var(--font-body)',
              cursor: 'pointer',
              flexShrink: 0,
            }}
          >
            <Icon name={previewing === '__test__' ? 'volume-2' : 'play'} size={14} />
            {previewing === '__test__' ? 'Playingâ€¦' : 'Test voice'}
          </button>
        </div>

        {/* Hachi's voice (TTS) */}
        <div style={cardStyle}>
          <h3 style={{ ...sectionHeadingStyle, marginBottom: 14 }}>Hachi's voice</h3>

          <div style={{ fontSize: 12, color: 'var(--hachi-muted)', marginBottom: 8 }}>Provider</div>
          <div
            style={{
              display: 'inline-flex',
              border: '0.5px solid var(--hachi-line)',
              borderRadius: 10,
              overflow: 'hidden',
              marginBottom: 18,
            }}
          >
            {ttsProviders.map((p, i) => {
              const sel = ttsProvider === p;
              return (
                <button
                  key={p}
                  type="button"
                  onClick={() => {
                    setTtsProvider(p);
                    stopAudio();
                  }}
                  style={{
                    padding: '8px 18px',
                    border: 'none',
                    borderLeft: i > 0 ? '0.5px solid var(--hachi-line)' : 'none',
                    background: sel ? 'var(--hachi-brand)' : 'var(--hachi-surface)',
                    color: sel ? '#fff' : 'var(--hachi-muted)',
                    font: `${sel ? 500 : 400} 13px var(--font-body)`,
                    cursor: 'pointer',
                  }}
                >
                  {p}
                </button>
              );
            })}
          </div>

          {ttsProvider === 'elevenlabs' ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <Input
                label="ElevenLabs voice ID"
                value={elVoiceId}
                onChange={setElVoiceId}
                placeholder="21m00Tcm4TlvDq8ikWAM"
                helperText='Find voice IDs in your ElevenLabs dashboard. Default: "Rachel".'
              />
              <button
                type="button"
                onClick={() => void play('voice:el', elVoiceId)}
                style={{
                  alignSelf: 'flex-start',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  height: 32,
                  padding: '0 13px',
                  borderRadius: 9,
                  border: '0.5px solid var(--hachi-line)',
                  background: 'var(--hachi-canvas)',
                  color: 'var(--hachi-ink)',
                  font: '500 12.5px var(--font-body)',
                  cursor: 'pointer',
                }}
              >
                <Icon name={previewing === 'voice:el' ? 'volume-2' : 'play'} size={13} />
                {previewing === 'voice:el' ? 'Playingâ€¦' : 'Preview voice'}
              </button>
            </div>
          ) : (
            <>
              <div style={{ fontSize: 12, color: 'var(--hachi-muted)', marginBottom: 8 }}>
                Voice <span style={{ opacity: 0.8 }}>â€” click one to hear it</span>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {voices.map((v) => {
                  const sel = ttsVoice === v;
                  const isPlaying = previewing === `voice:${v}`;
                  return (
                    <button
                      key={v}
                      type="button"
                      aria-pressed={sel}
                      onClick={() => {
                        setTtsVoice(v);
                        void play(`voice:${v}`, v);
                      }}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 7,
                        padding: '7px 12px',
                        borderRadius: 9,
                        border: `1px solid ${sel ? 'var(--hachi-brand)' : 'var(--hachi-line)'}`,
                        background: sel ? 'var(--hachi-brand-tint)' : 'var(--hachi-canvas)',
                        color: sel ? 'var(--hachi-brand)' : 'var(--hachi-ink)',
                        font: `${sel ? 500 : 400} 12.5px var(--font-body)`,
                        cursor: 'pointer',
                        textTransform: 'capitalize',
                      }}
                    >
                      <Icon
                        name={isPlaying ? 'volume-2' : 'play'}
                        size={13}
                        style={{ color: sel ? 'var(--hachi-brand)' : 'var(--hachi-muted)' }}
                      />
                      {v}
                    </button>
                  );
                })}
              </div>
            </>
          )}

          {previewError && (
            <div style={{ fontSize: 12, color: 'var(--hachi-danger)', marginTop: 12 }}>
              {previewError}
            </div>
          )}
        </div>

        {/* Understanding you (STT) */}
        <div style={cardStyle}>
          <h3 style={{ ...sectionHeadingStyle, marginBottom: 14 }}>Understanding you</h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
            <span style={{ color: 'var(--hachi-muted)', display: 'inline-flex' }}>
              <Icon name="mic" size={18} />
            </span>
            <div style={{ flex: 1, fontSize: 13 }}>
              Speech recognition uses OpenAI Whisper. Tap the mic in the conversation composer to
              talk instead of type.
            </div>
            <span
              style={{
                fontSize: 11,
                fontWeight: 500,
                color: 'var(--hachi-trust)',
                background: 'var(--hachi-trust-tint)',
                padding: '3px 9px',
                borderRadius: 999,
                flexShrink: 0,
              }}
            >
              On
            </span>
          </div>
        </div>

        {/* Advanced */}
        <div style={cardStyle}>
          <button
            type="button"
            onClick={() => setAdvancedOpen((v) => !v)}
            aria-expanded={advancedOpen}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 11,
              width: '100%',
              background: 'transparent',
              border: 'none',
              padding: 0,
              cursor: 'pointer',
              textAlign: 'left',
            }}
          >
            <span style={{ color: 'var(--hachi-muted)', display: 'inline-flex' }}>
              <Icon name="settings" size={17} />
            </span>
            <div style={{ flex: 1 }}>
              <div style={{ ...sectionHeadingStyle, fontSize: 15 }}>Advanced</div>
              <div style={{ fontSize: 12, color: 'var(--hachi-muted)', marginTop: 2 }}>
                API key env vars, models, custom endpoints
              </div>
            </div>
            <Icon name={advancedOpen ? 'chevron-down' : 'chevron-right'} size={16} />
          </button>

          {advancedOpen && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 18 }}>
              <div style={{ fontSize: 12.5, color: 'var(--hachi-muted)' }}>
                Keys are referenced by the name of the environment variable that holds them â€” they
                are never stored in settings directly.
              </div>

              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: 'var(--hachi-muted)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                }}
              >
                Speech-to-text (Whisper)
              </div>
              <Input
                label="STT API key env var"
                value={sttApiKeyEnv}
                onChange={setSttApiKeyEnv}
                placeholder="OPENAI_API_KEY"
                helperText="Defaults to OPENAI_API_KEY."
              />
              <Input
                label="STT model"
                value={sttModel}
                onChange={setSttModel}
                placeholder="whisper-1"
              />
              <Input
                label="STT base URL"
                value={sttBaseUrl}
                onChange={setSttBaseUrl}
                placeholder="https://api.openai.com/v1"
                helperText="Override for self-hosted or compatible endpoints."
              />

              {ttsProvider === 'openai' ? (
                <>
                  <div
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: 'var(--hachi-muted)',
                      textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                      marginTop: 4,
                    }}
                  >
                    Text-to-speech (OpenAI)
                  </div>
                  <Input
                    label="TTS API key env var"
                    value={ttsApiKeyEnv}
                    onChange={setTtsApiKeyEnv}
                    placeholder="OPENAI_API_KEY"
                    helperText="Defaults to OPENAI_API_KEY."
                  />
                  <Input label="TTS model" value={ttsModel} onChange={setTtsModel} placeholder="tts-1" />
                  <Input
                    label="TTS base URL"
                    value={ttsBaseUrl}
                    onChange={setTtsBaseUrl}
                    placeholder="https://api.openai.com/v1"
                  />
                </>
              ) : (
                <>
                  <div
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: 'var(--hachi-muted)',
                      textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                      marginTop: 4,
                    }}
                  >
                    Text-to-speech (ElevenLabs)
                  </div>
                  <Input
                    label="ElevenLabs API key env var"
                    value={elApiKeyEnv}
                    onChange={setElApiKeyEnv}
                    placeholder="ELEVENLABS_API_KEY"
                    helperText="Name of the env var holding your ElevenLabs API key."
                  />
                </>
              )}
            </div>
          )}
        </div>

        {/* Save */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={saving}
            style={{
              height: 38,
              padding: '0 18px',
              borderRadius: 10,
              border: 'none',
              background: 'var(--hachi-brand-hover)',
              color: 'var(--hachi-canvas)',
              font: '500 13px var(--font-body)',
              cursor: saving ? 'default' : 'pointer',
              opacity: saving ? 0.6 : 1,
            }}
          >
            {saving ? 'Savingâ€¦' : 'Save voice settings'}
          </button>
          {saveOk && <span style={{ fontSize: 13, color: 'var(--hachi-trust)' }}>Saved</span>}
          {saveError && <span style={{ fontSize: 13, color: 'var(--hachi-danger)' }}>{saveError}</span>}
        </div>
      </div>
    </div>
  );
}
