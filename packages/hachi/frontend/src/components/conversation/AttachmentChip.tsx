// AttachmentChip — a pending/uploaded attachment pill in the composer.

import { Icon } from '../icons/Icon'
import type { PendingAttachment } from '../../lib/data/types'
import { openFileContent } from '../../lib/data/domains/files'
import { attMeta, sizeStr } from './helpers'

interface AttachmentChipProps {
  attachment: PendingAttachment
  onRemove: () => void
}

export function AttachmentChip({ attachment, onRemove }: AttachmentChipProps) {
  const meta = attMeta(attachment.name, attachment.mediaType)
  const hasError = !!attachment.error
  const canOpen = !attachment.uploading && !hasError && !attachment.fileId.startsWith('local-')

  // Second line: error → upload status → "Type · size".
  const sub = hasError
    ? attachment.error && attachment.error.length <= 32
      ? attachment.error
      : 'Upload failed — hover for detail'
    : attachment.uploading
      ? 'Uploading…'
      : meta.label + (attachment.size ? ' · ' + sizeStr(attachment.size) : '')

  return (
    <div
      title={attachment.error ?? attachment.name}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 9,
        background: hasError ? 'var(--hachi-danger-tint)' : 'var(--hachi-surface)',
        border: `0.5px solid ${hasError ? 'var(--hachi-danger)' : 'var(--hachi-line)'}`,
        borderRadius: 11,
        padding: '6px 8px 6px 6px',
        maxWidth: 236,
        opacity: attachment.uploading ? 0.75 : 1,
        transition: 'opacity 0.15s',
        animation: 'hachiPop .14s ease',
      }}
    >
      {/* Thumbnail (image) or icon tile */}
      {meta.isImage && attachment.localUrl ? (
        <div
          style={{
            width: 34,
            height: 34,
            borderRadius: 7,
            flexShrink: 0,
            backgroundImage: `url("${attachment.localUrl}")`,
            backgroundSize: 'cover',
            backgroundPosition: 'center',
          }}
        />
      ) : (
        <div
          style={{
            width: 34,
            height: 34,
            borderRadius: 7,
            background: 'var(--hachi-cream)',
            display: 'grid',
            placeItems: 'center',
            flexShrink: 0,
            color: hasError ? 'var(--hachi-danger)' : meta.tint,
          }}
        >
          <Icon name={hasError ? 'circle-alert' : meta.icon} size={17} />
        </div>
      )}

      {/* Name + meta — clicking opens the uploaded file */}
      <button
        type="button"
        onClick={() => {
          if (canOpen) void openFileContent(attachment.fileId)
        }}
        disabled={!canOpen}
        style={{
          display: 'flex',
          flexDirection: 'column',
          minWidth: 0,
          flex: 1,
          background: 'transparent',
          border: 'none',
          padding: 0,
          textAlign: 'left',
          cursor: canOpen ? 'pointer' : 'default',
        }}
      >
        <span
          style={{
            fontSize: 12.5,
            fontWeight: 500,
            color: hasError ? 'var(--hachi-danger)' : 'var(--hachi-ink)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            maxWidth: 140,
          }}
        >
          {attachment.name}
        </span>
        <span style={{ fontSize: 11, color: hasError ? 'var(--hachi-danger)' : 'var(--hachi-muted)' }}>
          {sub}
        </span>
      </button>

      {/* Remove button */}
      <button
        type="button"
        className="hachi-attachment-remove-btn"
        onClick={onRemove}
        title="Remove"
        aria-label={`Remove ${attachment.name}`}
        style={{
          flexShrink: 0,
          width: 20,
          height: 20,
          borderRadius: 6,
          display: 'grid',
          placeItems: 'center',
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          color: 'var(--hachi-muted)',
        }}
      >
        <Icon name="x" size={13} />
      </button>
    </div>
  )
}
