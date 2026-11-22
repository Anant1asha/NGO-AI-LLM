import { Link } from '@tanstack/react-router'
import { Icon } from '../icons/Icon'

export interface NavItemProps {
  label: string
  icon: string
  active: boolean
  badge?: number
  route: string
  onNavigate?: () => void
}

export function NavItem({ label, icon, active, badge, route, onNavigate }: NavItemProps) {
  const iconColor = active ? 'var(--hachi-brand)' : 'var(--hachi-muted)'
  const fontWeight = active ? '500' : '400'

  return (
    <Link
      to={route as never}
      onClick={onNavigate}
      aria-current={active ? 'page' : undefined}
      className="hachi-nav-item"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        width: '100%',
        padding: '9px 12px',
        borderRadius: '10px',
        border: 'none',
        background: 'transparent',
        color: 'var(--hachi-ink)',
        font: 'inherit',
        fontWeight,
        fontSize: '14px',
        cursor: 'pointer',
        textAlign: 'left',
        textDecoration: 'none',
        transition: 'background var(--dur) var(--ease)',
      }}
    >
      <span style={{ color: iconColor, display: 'inline-flex' }}>
        <Icon name={icon} size={18} />
      </span>
      <span style={{ flex: 1 }}>{label}</span>
      {badge != null && badge > 0 && (
        <span
          style={{
            minWidth: '20px',
            height: '20px',
            padding: '0 6px',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: '999px',
            background: 'var(--hachi-brand)',
            color: 'var(--hachi-canvas)',
            fontSize: '11px',
            fontWeight: '500',
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {badge}
        </span>
      )}
    </Link>
  )
}
