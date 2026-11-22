// Pure formatting/lookup helpers shared by the conversation screen's
// message, attachment, and action-card rendering.

export { fmtUSD } from '../../lib/ui/format'

// Derive an attachment's icon, tint, type label, and image-ness from its name +
// media type. Ports the prototype `_attMeta` so chips look consistent whether the
// upload metadata or only the original file is known.
export interface AttMeta {
  icon: string
  tint: string
  label: string
  isImage: boolean
}
export function attMeta(name: string, mediaType: string): AttMeta {
  const t = (mediaType || '').toLowerCase()
  const ext = name.includes('.') ? (name.split('.').pop() || '').toLowerCase() : ''
  if (t.startsWith('image/')) return { icon: 'image', tint: 'var(--hachi-brand)', label: 'Image', isImage: true }
  if (t === 'application/pdf' || ext === 'pdf') return { icon: 'file-text', tint: 'var(--hachi-danger)', label: 'PDF', isImage: false }
  if (t.startsWith('text/') || ['txt', 'md', 'csv', 'log', 'json'].includes(ext))
    return { icon: 'file-text', tint: 'var(--hachi-trust)', label: ext ? ext.toUpperCase() : 'Text', isImage: false }
  if (['doc', 'docx'].includes(ext)) return { icon: 'file-text', tint: 'var(--hachi-brand)', label: 'Doc', isImage: false }
  return { icon: 'file', tint: 'var(--hachi-muted)', label: ext ? ext.toUpperCase() : 'File', isImage: false }
}
export function sizeStr(b?: number): string {
  if (b == null) return ''
  if (b < 1024) return b + ' B'
  if (b < 1048576) return (b / 1024).toFixed(b < 10240 ? 1 : 0) + ' KB'
  return (b / 1048576).toFixed(1) + ' MB'
}

export { statusMeta } from '../../lib/ui/status'
export type { StatusMeta } from '../../lib/ui/status'
