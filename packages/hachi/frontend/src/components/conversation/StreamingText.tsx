// StreamingCursor / StreamingText — the actively-streaming assistant text
// rendering path, split out and memoized so a growing response doesn't
// force the whole message list to re-render on every flush.

import { memo } from 'react'

// ---- StreamingCursor -----------------------------------------------
// Isolated so its CSS animation doesn't force the whole message list to
// re-render on every animation frame. Only renders when isStreaming=true.

export const StreamingCursor = memo(function StreamingCursor() {
  return (
    <span
      style={{
        display: 'inline-block',
        width: 8,
        height: 17,
        background: 'var(--hachi-brand)',
        marginLeft: 2,
        verticalAlign: 'text-bottom',
        animation: 'hachiBlink 1s steps(1) infinite',
      }}
    />
  )
})

// ---- StreamingText -------------------------------------------------
// Renders the actively-streaming assistant text as append-only, memoized
// chunks. CRITICAL for performance: rendering `<span>{fullText}</span>` and
// growing `fullText` every flush forces the browser to re-lay-out the ENTIRE
// message on each update — O(size) per flush, O(size²) over the response, which
// hangs the main thread (RESULT_CODE_HUNG) on long replies. By splitting into
// fixed-size chunks, every chunk except the last is a stable string: memo()
// skips re-rendering them, so React touches no DOM and the browser re-flows only
// the final (small) chunk. Streaming cost becomes O(size) total.
const STREAM_CHUNK_SIZE = 2048

const StreamingChunk = memo(function StreamingChunk({ text }: { text: string }) {
  return <>{text}</>
})

export const StreamingText = memo(function StreamingText({ text }: { text: string }) {
  const chunks: string[] = []
  for (let i = 0; i < text.length; i += STREAM_CHUNK_SIZE) {
    chunks.push(text.slice(i, i + STREAM_CHUNK_SIZE))
  }
  return (
    <span style={{ whiteSpace: 'pre-wrap' }}>
      {chunks.map((c, i) => (
        <StreamingChunk key={i} text={c} />
      ))}
    </span>
  )
})
