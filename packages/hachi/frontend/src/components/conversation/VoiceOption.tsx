// VoiceOption — a row in the "Talk to Hachi" menu.

import { Icon } from '../icons/Icon'

interface VoiceOptionProps {
  icon: string
  name: string
  desc: string
  onPick: () => void
}

export function VoiceOption({ icon, name, desc, onPick }: VoiceOptionProps) {
  return (
    <button
      type="button"
      role="menuitem"
      className="hachi-voice-option"
      onClick={onPick}
      style={{
        width: '100%',
        display: 'flex',
        alignItems: 'flex-start',
        gap: 12,
        padding: '12px 14px',
        border: 'none',
        borderBottom: '0.5px solid var(--hachi-line)',
        background: 'transparent',
        cursor: 'pointer',
        textAlign: 'left',
        font: 'inherit',
      }}
    >
      <span
        style={{
          flexShrink: 0,
          width: 34,
          height: 34,
          borderRadius: 9,
          background: 'var(--hachi-cream)',
          display: 'grid',
          placeItems: 'center',
          color: 'var(--hachi-brand)',
        }}
      >
        <Icon name={icon} size={18} />
      </span>
      <span style={{ minWidth: 0 }}>
        <span style={{ display: 'block', fontSize: 14, fontWeight: 500, color: 'var(--hachi-ink)' }}>
          {name}
        </span>
        <span
          style={{
            display: 'block',
            fontSize: 12.5,
            color: 'var(--hachi-muted)',
            lineHeight: '17px',
            marginTop: 1,
          }}
        >
          {desc}
        </span>
      </span>
    </button>
  )
}
