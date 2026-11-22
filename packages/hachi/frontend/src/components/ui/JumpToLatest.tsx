// JumpToLatest — floating pill shown when the user scrolls up mid-stream.
// Clicking it snaps back to the bottom and resumes auto-follow.

interface JumpToLatestProps {
  onClick: () => void
  label?: string
}

export function JumpToLatest({ onClick, label = '↓ Latest' }: JumpToLatestProps) {
  return (
    <div
      style={{
        position: 'absolute',
        bottom: 16,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 10,
        pointerEvents: 'none',
        display: 'flex',
        justifyContent: 'center',
      }}
    >
      <button
        type="button"
        className="hachi-jump-pill"
        onClick={onClick}
        aria-label="Jump to latest message"
        style={{
          pointerEvents: 'auto',
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          padding: '6px 14px',
          borderRadius: 999,
          border: '0.5px solid var(--hachi-line)',
          font: '500 13px var(--font-body)',
          cursor: 'pointer',
          boxShadow: '0 2px 8px rgba(28,26,32,.12)',
        }}
      >
        {label}
      </button>
    </div>
  )
}
