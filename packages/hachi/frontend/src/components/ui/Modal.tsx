import { useEffect } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import { useFocusTrap } from '../../lib/hooks/useFocusTrap'

export interface ModalProps {
  /** Unmount instead of passing open=false — Modal is always "open" when rendered. */
  onClose: () => void
  /** id of the <h2> title element inside children, wired to aria-labelledby. */
  titleId: string
  children: ReactNode
  /**
   * When true, clicking the backdrop does NOT close (prevents silently discarding
   * typed content such as API keys). Escape still closes.
   */
  dirtyGuard?: boolean
  /** Panel width in px. Defaults to 500. */
  width?: number
  /** Extra styles merged into the panel. */
  style?: CSSProperties
}

export function Modal({ onClose, titleId, children, dirtyGuard = false, width = 500, style }: ModalProps) {
  const trapRef = useFocusTrap<HTMLDivElement>(true)

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.stopPropagation()
        onClose()
      }
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [onClose])

  return (
    <div
      role="presentation"
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(28,26,32,.4)',
        display: 'grid',
        placeItems: 'center',
        padding: 24,
        zIndex: 60,
      }}
      onClick={() => { if (!dirtyGuard) onClose() }}
    >
      <div
        ref={trapRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        style={{
          width,
          maxWidth: '96vw',
          maxHeight: '88vh',
          background: 'var(--hachi-surface)',
          border: '0.5px solid var(--hachi-line)',
          borderRadius: 'var(--radius-lg, 16px)',
          overflow: 'hidden',
          boxShadow: '0 24px 60px rgba(28,26,32,.24)',
          display: 'flex',
          flexDirection: 'column',
          ...style,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  )
}
