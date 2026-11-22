// StarterButton — a suggested chat-starter pill shown on an empty conversation.

import { Icon } from '../icons/Icon'

interface StarterButtonProps {
  label: string
  icon: string
  onClick: () => void
}

export function StarterButton({ label, icon, onClick }: StarterButtonProps) {
  return (
    <button
      type="button"
      className="hachi-starter-pill"
      onClick={onClick}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 7,
        padding: '9px 14px',
        borderRadius: 999,
        border: '0.5px solid var(--hachi-line)',
        background: 'var(--hachi-surface)',
        color: 'var(--hachi-ink)',
        font: 'inherit',
        fontSize: 13,
        cursor: 'pointer',
      }}
    >
      <span style={{ color: 'var(--hachi-muted)', display: 'inline-flex' }}>
        <Icon name={icon} size={14} />
      </span>
      {label}
    </button>
  )
}
