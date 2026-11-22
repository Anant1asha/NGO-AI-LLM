import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

// Regression guard for BB-76: a `<button>` that never declares a base `background`
// falls through to the User-Agent stylesheet, which paints it `ButtonFace` —
// #F0F0F0 cold grey on Windows/Chrome. On Hachi's warm bone canvas (#FBF7EF) that
// reads as a foreign, unthemed chip. The .tsx idiom `background: open ? tok : undefined`
// is deliberate (it hands the rest state to CSS so the `:hover` rule still wins —
// an inline value would out-specify it), so the base rule MUST exist in CSS.
//
// .hachi-rating-btn is the correct precedent: it pairs `:hover` with a base
// `background: var(--hachi-canvas)`. These classes did not, and rendered grey.
//
// Lives outside `src/` on purpose: this is a node-side test that reads a file, and
// tsconfig scopes typechecking to `src`. Importing `node:fs` from `src` fails
// `tsc --noEmit` (no @types/node), and Vitest stubs `?raw` CSS imports to '' so the
// browser-side alternative reads empty and the assertions silently pass on nothing.

const HERE = dirname(fileURLToPath(import.meta.url))
const CSS = readFileSync(join(HERE, '..', 'src', 'styles', 'interactive.css'), 'utf-8')

/** Selectors that carry a `background` declaration, split into base vs. state rules. */
function backgroundSelectors(rawCss: string): { base: Set<string>; state: Set<string> } {
  // Strip comments first — otherwise a comment above a rule is swallowed into the
  // selector capture and the rule silently stops matching.
  const css = rawCss.replace(/\/\*[\s\S]*?\*\//g, '')
  const base = new Set<string>()
  const state = new Set<string>()
  for (const [, selector, body] of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    if (!/(^|[\s;])background(-color)?\s*:/.test(body)) continue
    for (const sel of selector.split(',')) {
      const trimmed = sel.trim()
      const baseMatch = /^\.([\w-]+)$/.exec(trimmed)
      if (baseMatch) base.add(baseMatch[1])
      const stateMatch = /^\.([\w-]+):(hover|focus|active)/.exec(trimmed)
      if (stateMatch) state.add(stateMatch[1])
    }
  }
  return { base, state }
}

describe('interactive.css — buttons must not inherit the UA ButtonFace grey', () => {
  it('actually loaded the stylesheet', () => {
    // Guards the guard: if the read ever returns empty, every assertion below would
    // pass vacuously. This is exactly how the `?raw` version failed.
    expect(CSS.length).toBeGreaterThan(1000)
    expect(CSS).toContain('.hachi-session-title-btn')
  })

  it('parser distinguishes a base background from a :hover-only one', () => {
    // Negative control: proves the parser can still see the defect, so a green run
    // below means "the rule is there", not "the parser stopped matching".
    const { base, state } = backgroundSelectors(`
      /* a comment that must not be swallowed into the selector */
      .has-base { background: red; }
      .has-base:hover { background: blue; }
      .hover-only:hover { background: blue; }
    `)
    expect([...base]).toEqual(['has-base'])
    expect([...state].sort()).toEqual(['has-base', 'hover-only'])
  })

  // Scoped to the classes fixed for this bug. The wider audit (other classes that
  // define :hover without a base background) is tracked separately — several of
  // those set an inline background in .tsx, so they render correctly today.
  const GUARDED = [
    'hachi-session-title-btn',
    'hachi-composer-voice-btn',
    'hachi-leash-always-btn',
  ]

  it.each(GUARDED)('.%s declares a base background, not only :hover', (cls) => {
    const { base, state } = backgroundSelectors(CSS)

    expect(state.has(cls), `.${cls}:hover should still set a background`).toBe(true)
    expect(
      base.has(cls),
      `.${cls} defines a :hover background but no base background — the rest state ` +
        `falls through to the UA stylesheet and paints #F0F0F0 grey. Add a base rule.`
    ).toBe(true)
  })
})

describe('interactive.css — overflow link hover treatment (BB-86)', () => {
  it('.hachi-more-approvals-link has a :hover underline rule', () => {
    expect(CSS).toContain('.hachi-more-approvals-link:hover')
    expect(CSS).toContain('text-decoration: underline')
  })
})
