import { Icon } from '../icons/Icon'
import { HachiMark } from '../brand/HachiMark'

export interface BudgetWidgetProps {
  spent: number
  budget: number
  onClick: () => void
}

export function BudgetWidget({ spent, budget, onClick }: BudgetWidgetProps) {
  const pct = budget > 0 ? Math.min(100, (spent / budget) * 100) : 0
  const spentStr = `$${spent.toFixed(2)}`
  const budgetStr = `$${budget.toFixed(2)}`

  return (
    <button
      type="button"
      className="hachi-budget-widget"
      onClick={onClick}
      aria-label={`Today's budget: ${spentStr} spent of ${budgetStr}`}
      style={{
        textAlign: 'left',
        background: 'var(--hachi-cream)',
        borderRadius: '10px',
        padding: '14px',
        cursor: 'pointer',
        font: 'inherit',
        width: '100%',
        transition: 'border-color var(--dur) var(--ease)',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          fontSize: '13px',
          color: 'var(--hachi-muted)',
          marginBottom: '8px',
        }}
      >
        <Icon name="dollar" size={14} />
        today's budget
      </div>
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          gap: '6px',
          marginBottom: '10px',
        }}
      >
        <span
          style={{
            fontFamily: 'var(--font-display)',
            fontWeight: '500',
            fontSize: '22px',
            color: 'var(--hachi-ink)',
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {spentStr}
        </span>
        <span style={{ fontSize: '13px', color: 'var(--hachi-muted)' }}>
          of {budgetStr}
        </span>
      </div>
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(pct)}
        aria-label={`Budget used: ${spentStr} of ${budgetStr}`}
        style={{
          height: '4px',
          borderRadius: '999px',
          background: 'var(--hachi-line)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            background: 'var(--hachi-brand)',
            borderRadius: '999px',
            transition: 'width var(--dur-slow) var(--ease)',
          }}
        />
      </div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '7px',
          marginTop: '12px',
          fontSize: '13px',
          color: 'var(--hachi-muted)',
        }}
      >
        <HachiMark size={15} variant="knockout" />
        you hold the leash
      </div>
    </button>
  )
}
