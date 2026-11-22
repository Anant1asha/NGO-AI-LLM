// SlashItem — a row in the "/" slash-command autocomplete popup.

interface SlashItemProps {
  id?: string
  cmd: string
  desc: string
  active: boolean
  onPick: () => void
}

export function SlashItem({ id, cmd, desc, active, onPick }: SlashItemProps) {
  return (
    <button
      id={id}
      type="button"
      role="option"
      aria-selected={active}
      className="hachi-slash-item"
      onClick={onPick}
      style={{
        width: '100%',
        display: 'flex',
        alignItems: 'center',
        gap: 11,
        padding: '11px 14px',
        border: 'none',
        borderBottom: '0.5px solid var(--hachi-line)',
        background: active ? 'var(--hachi-cream)' : 'transparent',
        cursor: 'pointer',
        textAlign: 'left',
        font: 'inherit',
      }}
    >
      <span
        style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 13,
          color: 'var(--hachi-brand)',
          minWidth: 96,
        }}
      >
        {cmd}
      </span>
      <span style={{ fontSize: 13, color: 'var(--hachi-muted)' }}>{desc}</span>
    </button>
  )
}
