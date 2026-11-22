export interface StatusMeta {
  bg: string
  fg: string
  dot: string
  text: string
}

const STATUS_MAP: Record<string, StatusMeta> = {
  working:    { bg: 'var(--hachi-working-tint)', fg: 'var(--hachi-working-fg)', dot: 'var(--hachi-working)', text: 'working' },
  'on-watch': { bg: 'var(--hachi-trust-tint)',   fg: 'var(--hachi-trust)',      dot: 'var(--hachi-trust)',   text: 'on watch' },
  done:       { bg: 'var(--hachi-success-tint)', fg: 'var(--hachi-success-fg)', dot: 'var(--hachi-success)', text: 'done' },
  blocked:    { bg: 'var(--hachi-danger-tint)',  fg: 'var(--hachi-danger-fg)',  dot: 'var(--hachi-danger)',  text: 'blocked' },
}

export function statusMeta(st: string): StatusMeta {
  return STATUS_MAP[st] ?? { bg: 'var(--hachi-surface)', fg: 'var(--hachi-muted)', dot: 'var(--hachi-muted)', text: st }
}
