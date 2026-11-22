// TtsButton — "Listen" / "Stop" read-aloud control under a completed
// Hachi message, backed by the browser's SpeechSynthesis API.

import { useState } from 'react'
import { Icon } from '../icons/Icon'

export function TtsButton({ text }: { text: string }) {
  const [speaking, setSpeaking] = useState(false)

  function handleSpeak() {
    if (!('speechSynthesis' in window)) return
    if (speaking) {
      window.speechSynthesis.cancel()
      setSpeaking(false)
      return
    }
    // Strip markdown for a cleaner read-aloud experience.
    const plain = text
      .replace(/```[\s\S]*?```/g, '')
      .replace(/`([^`]+)`/g, '$1')
      .replace(/[*_~#>]/g, '')
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
      .trim()
    const utterance = new SpeechSynthesisUtterance(plain)
    utterance.onend = () => setSpeaking(false)
    utterance.onerror = () => setSpeaking(false)
    window.speechSynthesis.speak(utterance)
    setSpeaking(true)
  }

  if (!('speechSynthesis' in window)) return null

  return (
    <button
      type="button"
      className="hachi-ghost-icon-btn-bg"
      onClick={handleSpeak}
      title={speaking ? 'Stop speaking' : 'Read aloud'}
      style={{
        alignSelf: 'flex-start',
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        padding: '3px 9px',
        borderRadius: 8,
        border: '0.5px solid var(--hachi-line)',
        color: speaking ? 'var(--hachi-brand)' : 'var(--hachi-muted)',
        font: '500 12px var(--font-body)',
        cursor: 'pointer',
      }}
    >
      <Icon name="volume-2" size={13} />
      {speaking ? 'Stop' : 'Listen'}
    </button>
  )
}
