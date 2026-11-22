# 19 — Voice Platform

> Phase 2 / Gate B. Initiative **F**. Best-positioned modality — a provider abstraction already
> half-exists. Mostly *formalization*, not greenfield. Seams are `file:line`.

## 1. Problem

`core/voice.py` already has injectable, OpenAI-compatible `SpeechToText`/`TextToSpeech`
(`:296,383`, `from_env` at `:314/:409`) and 5 tools (`voice_tools.py`), plus keyless local
playback. But there is no `SpeechProvider` contract, STT/TTS are not capabilities in the router,
and there is no streaming/conversation mode.

## 2. Contract

```python
# core/providers/speech.py
class SpeechProvider(Protocol):
    name: str
    def capabilities(self) -> set[Capability]          # subset of {SPEECH_TO_TEXT, TEXT_TO_SPEECH}
    def transcribe(self, audio: bytes, *, media_type: str, language: str | None = None) -> str: ...
    def synthesize(self, text: str, *, voice: str, fmt: str = "mp3") -> bytes: ...
```

Resolved by capability via `ProviderRegistry.get_speech(Capability.SPEECH_TO_TEXT|TEXT_TO_SPEECH)`
([13](13-provider-architecture.md) §3), wrapped by `resilient_call`. The brief's cross-provider
workflow (Deepgram STT → Claude reasoning → … → ElevenLabs TTS) is exactly: `get_speech(STT)` +
`ModelRouter.select(REASONING)` + `get_speech(TTS)` — each chosen by capability.

## 3. One implementation

`OpenAICompatibleSpeechProvider` **wraps the existing `SpeechToText`/`TextToSpeech`**
(`voice.py:296,383`) — no rewrite; it already targets any OpenAI-compatible Whisper/TTS endpoint,
so Deepgram/Groq-via-compat work today. Keyless local playback (`AudioPlayer`, `voice.py:573`)
stays as-is. Env config (`HACHI_STT_*`/`HACHI_TTS_*`) is absorbed into `[voice]` config with env
fallback (matching the established precedence).

## 4. Agent surface (mostly unchanged)

The 5 existing tools (`transcribe_audio`, `speak_text`, `transcribe_and_summarize`, `play_audio`,
`get_audio_info`) are re-pointed from `SpeechToText.from_env()` to
`ProviderRegistry.get_speech(...)`, gaining resilience + capability-routing for free. Tool schemas
and behavior are unchanged → back-compatible.

## 5. What it touches

`core/providers/speech.py` (new contract) + adapter wrapping `core/voice.py:296,383`;
`tools/voice_tools.py:350` (`register_voice_tools` resolves provider from registry);
`gateway/orchestrator.py` (`BootDeps` exposes speech via the registry); `core/settings.py`
(`[voice]` section, env fallback). No change to `AudioPlayer` or the extractive summarizer.

## 6. What could break (and the guard)

- **Re-pointing tools to the registry** could regress env-key resolution. *Guard:* the registry
  resolves keys from the same `SecretStore`/env; existing voice tests pass unchanged; a test
  asserts `HACHI_STT_*` still works via config fallback.
- **Resilience changes timing** on transcription. *Guard:* bounded retry; large files already
  capped at 25 MB (`voice.py:83`).

## 7. Deferred (seam only, per §4a)

Native ElevenLabs/Deepgram/Azure SDK adapters (the OpenAI-compat impl covers them via compatible
endpoints today; native adapters are "add a provider"); **streaming STT/TTS, interruptions,
voice-conversation mode, push-to-talk, and the mic UI** — these are a large, separate build
requiring a gateway WebSocket route and frontend work, explicitly deferred until the batch voice
tools prove demand. The `SpeechProvider` contract is forward-compatible with a `stream_*` method
added later.
