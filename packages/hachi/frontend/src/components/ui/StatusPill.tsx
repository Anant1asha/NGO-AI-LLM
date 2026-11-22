import { CSSProperties, ReactNode } from 'react';
import { statusMeta } from '../../lib/ui/status';

export type { StatusMeta } from '../../lib/ui/status';
export { statusMeta } from '../../lib/ui/status';

export type StatusValue = 'working' | 'on-watch' | 'done' | 'blocked';

export interface StatusPillProps {
  status: string;
  children?: ReactNode;
}

export function StatusPill({ status, children }: StatusPillProps) {
  const meta = statusMeta(status);

  const pillStyle: CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 'var(--space-1)',
    paddingInline: 'var(--space-2)',
    paddingBlock: '3px',
    borderRadius: 'var(--radius-pill)',
    background: meta.bg,
    color: meta.fg,
    fontFamily: 'var(--font-body)',
    fontSize: 'var(--type-small-size)',
    fontWeight: 'var(--weight-medium)' as CSSProperties['fontWeight'],
    lineHeight: '20px',
    whiteSpace: 'nowrap',
  };

  const dotStyle: CSSProperties = {
    width: '6px',
    height: '6px',
    borderRadius: '50%',
    background: meta.dot,
    flexShrink: 0,
  };

  return (
    <span style={pillStyle}>
      <span style={dotStyle} aria-hidden="true" />
      {children ?? meta.text}
    </span>
  );
}
