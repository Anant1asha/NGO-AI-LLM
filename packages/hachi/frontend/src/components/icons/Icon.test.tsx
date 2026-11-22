import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderToString } from 'react-dom/server'
import { Icon } from './Icon'

describe('Icon registry — no silently-blank icons (BB-36)', () => {
  it('renders real markup (not an empty <svg/>) for "bar-chart"', () => {
    const html = renderToString(<Icon name="bar-chart" size={17} />)
    expect(html).toMatch(/<(path|circle|line|polygon|rect)/)
  })

  it('falls back to an empty <svg/> for a genuinely unregistered name', () => {
    const html = renderToString(<Icon name="loader" size={15} />)
    expect(html).not.toMatch(/<(path|circle|line|polygon|rect)/)
  })

  it('every registered icon renders real markup (no empty-string entries)', () => {
    const names = [
      'home', 'chat', 'work', 'leash', 'shield', 'memory', 'skills', 'plug',
      'settings', 'search', 'bar-chart', 'refresh', 'dollar', 'circle-check',
    ]
    for (const name of names) {
      const html = renderToString(<Icon name={name} size={16} />)
      expect(html, `icon "${name}" rendered blank`).toMatch(/<(path|circle|line|polygon|rect)/)
    }
  })
})

// T32a — console.warn for unknown icon names in dev
describe('Icon — unknown name warning (T32a)', () => {
  let warnSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('calls console.warn with the unknown name in dev', () => {
    renderToString(<Icon name="__nonexistent_icon_t32a__" size={16} />)
    expect(warnSpy).toHaveBeenCalledWith('[Icon] unknown name:', '__nonexistent_icon_t32a__')
  })

  it('does not warn for a valid registered icon', () => {
    renderToString(<Icon name="home" size={16} />)
    expect(warnSpy).not.toHaveBeenCalled()
  })
})

// T32c — alias dedup: message-square ≡ chat, file-text ≡ file
describe('Icon — aliases (T32c)', () => {
  it('message-square renders the same SVG paths as chat', () => {
    const chat = renderToString(<Icon name="chat" size={16} />)
    const msg = renderToString(<Icon name="message-square" size={16} />)
    expect(msg).toContain(chat.slice(chat.indexOf('<path'), chat.indexOf('</svg>')))
  })

  it('file-text renders the same SVG paths as file', () => {
    const file = renderToString(<Icon name="file" size={16} />)
    const fileText = renderToString(<Icon name="file-text" size={16} />)
    expect(fileText).toContain(file.slice(file.indexOf('<path'), file.indexOf('</svg>')))
  })

  it('aliases produce real markup (not blank)', () => {
    const aliases = ['message-square', 'file-text']
    for (const name of aliases) {
      const html = renderToString(<Icon name={name} size={16} />)
      expect(html, `alias "${name}" rendered blank`).toMatch(/<(path|circle|line|polygon|rect)/)
    }
  })
})
