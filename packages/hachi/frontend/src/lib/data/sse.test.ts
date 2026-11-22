import { afterEach, describe, expect, it, vi } from 'vitest'

import { streamSSE } from './sse'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('streamSSE', () => {
  it('does not retain an abort listener for every received chunk', async () => {
    const encoder = new TextEncoder()
    let chunk = 0
    const body = new ReadableStream<Uint8Array>({
      pull(controller) {
        if (chunk === 100) {
          controller.close()
          return
        }
        chunk += 1
        controller.enqueue(encoder.encode(`id: ${chunk}\ndata: ${chunk}\n\n`))
      },
    })
    vi.stubGlobal('fetch', vi.fn(async () => new Response(body, { status: 200 })))
    const listenerSpy = vi.spyOn(AbortSignal.prototype, 'addEventListener')
    const messages: string[] = []

    await streamSSE('/stream', { onMessage: (message) => messages.push(message.data) })

    expect(messages).toHaveLength(100)
    expect(listenerSpy).not.toHaveBeenCalled()
  })

  it('cancels a stalled reader at the idle timeout', async () => {
    const cancel = vi.fn()
    const body = new ReadableStream<Uint8Array>({ cancel })
    vi.stubGlobal('fetch', vi.fn(async () => new Response(body, { status: 200 })))

    await streamSSE('/stream', { onMessage: vi.fn() }, { idleTimeoutMs: 10 })

    expect(cancel).toHaveBeenCalledOnce()
  })
})
