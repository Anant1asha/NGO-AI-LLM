import { LoyalLoop } from './LoyalLoop'

interface PendingCardProps {
  /** Muted label shown below the spinner, e.g. "Checking…". */
  label?: string
}

/**
 * Loading placeholder for list screens.
 *
 * Rendered while a domain's first fetch is in flight so users never
 * see the empty state as a false "nothing here" message (T13).
 * Disappears once the domain's `loaded` flag becomes true.
 */
export function PendingCard({ label = 'Checking…' }: PendingCardProps) {
  return (
    <div
      role="status"
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: 120,
        gap: 12,
        color: 'var(--text-muted, var(--hachi-muted))',
        fontFamily: 'var(--font-body, Inter, system-ui, sans-serif)',
        fontSize: 13,
      }}
    >
      <LoyalLoop size={32} label={label} />
      <span>{label}</span>
    </div>
  )
}
