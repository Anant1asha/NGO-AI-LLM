import { describe, it, expect } from 'vitest'
import { renderToString } from 'react-dom/server'
import { Markdown } from './Markdown'

// Regression guard for the streaming-crash root cause (2026-06-21):
// `parseInline` recurses for bold/italic/link children. It previously shared a
// single module-level `g`-flag RegExp, so a nested call reset the shared
// `lastIndex` and the outer loop re-matched the same token forever — an infinite
// loop that froze the main thread (RESULT_CODE_HUNG) on ANY assistant reply
// containing emphasis or a link. If this regresses, these renders never return.
describe('Markdown — recursion / inline parsing', () => {
  it('renders bold inside a numbered-list line without hanging', () => {
    const html = renderToString(
      <Markdown text="1. **GitHub** — your personal repos, organization, or a specific repository?" />
    )
    expect(html).toContain('GitHub')
    expect(html).toContain('<strong')
  })

  it('handles emphasis, inline code, and a link together', () => {
    const html = renderToString(
      <Markdown text="see `gateway.py` and *note* the [docs](http://x.co) plus **bold**" />
    )
    expect(html).toContain('<code')
    expect(html).toContain('<em')
    expect(html).toContain('<a ')
    expect(html).toContain('<strong')
  })

  it('handles many emphasis tokens on one line', () => {
    const html = renderToString(<Markdown text="**a** **b** **c** _d_ _e_ trailing" />)
    expect(html).toContain('trailing')
  })

  it('renders plain text unchanged', () => {
    const html = renderToString(<Markdown text="just plain text, no markdown" />)
    expect(html).toContain('just plain text, no markdown')
  })
})

// Fenced code block rendering
describe('Markdown — fenced code blocks', () => {
  it('renders a fenced code block as <pre><code>, not inline', () => {
    const html = renderToString(
      <Markdown text={'Run this:\n```\nhachi setup --tier enhanced\n```\nDone.'} />
    )
    expect(html).toContain('<pre')
    expect(html).toContain('<code')
    expect(html).toContain('hachi setup --tier enhanced')
    // Code content must be inside <pre>, not in a bare <p>
    expect(html).toMatch(/<pre[^>]*>[\s\S]*hachi setup --tier enhanced[\s\S]*<\/pre>/)
  })

  it('captures the language tag and renders the display label', () => {
    const html = renderToString(
      <Markdown text={'```python\nprint("hello")\n```'} />
    )
    expect(html).toContain('Python')
    expect(html).toContain('print')
  })

  it('gives the copy button an accessible name', () => {
    const html = renderToString(<Markdown text={'```python\nx = 1\n```'} />)
    expect(html).toContain('aria-label="Copy code"')
  })

  it('handles unclosed fenced block (streaming partial input) with isStreaming', () => {
    // During streaming, an unclosed fence must render as a styled code block
    const html = renderToString(<Markdown text={'```python\ndef foo():\n    return 1'} isStreaming />)
    expect(html).toContain('<pre')
    // Syntax highlighter splits tokens into spans — check tokens individually
    expect(html).toContain('def')
    expect(html).toContain('foo')
    expect(html).toContain('return')
  })

  it('text before and after code block renders as paragraphs', () => {
    const html = renderToString(
      <Markdown text={'Before\n```js\nconsole.log(1)\n```\nAfter'} />
    )
    expect(html).toContain('Before')
    expect(html).toContain('After')
    // Syntax highlighter splits "console" and "log" into separate spans
    expect(html).toContain('console')
    expect(html).toContain('log')
  })
})

// Streaming mode — FIX 1 tests
describe('Markdown — streaming / isStreaming prop (FIX 1)', () => {
  it('(a) unclosed fence with isStreaming renders a styled <pre> container, not bare text', () => {
    // Text has an opening ``` fence but no closing fence — simulates mid-stream code block.
    const html = renderToString(
      <Markdown text={"```python\ndef f():"} isStreaming />
    )
    // The styled code-block container (<pre>) must be present
    expect(html).toContain('<pre')
    // The partial code content should be inside it
    expect(html).toContain('def')
    expect(html).toContain('f')
    // Must NOT render as a bare paragraph / text blob (no <pre> would indicate that)
    expect(html).not.toMatch(/```python[\s\S]*?def f\(\):<\/p>/)
  })

  it('(b) transitioning from streaming to done produces the same <pre> structure — stable key means no remount', () => {
    // Both streaming and done should produce a code block for a *closed* fence.
    // The block `key` is `b<index>` which is identical in both renders,
    // so React reuses the DOM node rather than unmounting/remounting.
    // We verify structural equivalence: same outer element, same code content.
    const codeText = "```python\ndef f():\n    return 1\n```"

    const htmlStreaming = renderToString(<Markdown text={codeText} isStreaming />)
    const htmlDone = renderToString(<Markdown text={codeText} isStreaming={false} />)

    // Both should contain a <pre> (code block chrome)
    expect(htmlStreaming).toContain('<pre')
    expect(htmlDone).toContain('<pre')

    // Both should contain the code content tokens
    expect(htmlStreaming).toContain('def')
    expect(htmlDone).toContain('def')

    // The wrapping div structure is the same — React will reconcile rather than remount
    // (the block key `b0` appears in both renders as the same element type)
    // We check that both renders emit the code block with the same lang label
    expect(htmlStreaming).toContain('Python')
    expect(htmlDone).toContain('Python')
  })

  it('unclosed fence without isStreaming renders as paragraph (no <pre> block)', () => {
    // When streaming is false and the fence is unclosed, we fall back to paragraph text.
    // The backtick line is rendered as inline code markup inside a <p>, NOT a styled <pre>.
    const html = renderToString(
      <Markdown text={"```python\ndef f():"} isStreaming={false} />
    )
    // Must NOT produce a styled code-block <pre>
    expect(html).not.toContain('<pre')
    // Content tokens should still be present (as inline/paragraph text)
    expect(html).toContain('def')
    expect(html).toContain('f')
  })

  it('empty text renders a container with min-height (no collapse to zero)', () => {
    const html = renderToString(<Markdown text="" />)
    // The wrapping div must have minHeight set (anti-FOUC)
    expect(html).toContain('min-height')
  })
})

// F1 — CodeBlock memo correctness (BB: fence-memo trap)
// CodeBlock is now wrapped in React.memo with useMemo on renderHighlighted.
// These tests verify memo wrapping doesn't FOUC or change rendered output.
describe('Markdown — CodeBlock memo (F1)', () => {
  it('renders identical highlighted output on repeated renders of the same code', () => {
    // If the memoization is unsafe (e.g. wrong deps) the two renders would differ.
    const text = '```python\ndef greet(name: str) -> str:\n    return f"hi {name}"\n```'
    const html1 = renderToString(<Markdown text={text} />)
    const html2 = renderToString(<Markdown text={text} />)
    expect(html1).toBe(html2)
    // Highlight tokens should be present (span-split by tokenizer)
    expect(html1).toContain('def')
    expect(html1).toContain('greet')
    expect(html1).toContain('return')
  })

  it('open-fence then close-fence produces same token spans (fence-memo trap)', () => {
    // An open fence renders the code as a partial streaming block.
    // When the fence closes the code content is identical — the useMemo cache
    // must return the same highlighted output without a flicker (FOUC).
    const partialCode = 'def greet(name: str) -> str:\n    return f"hi {name}"'
    const openFence = `\`\`\`python\n${partialCode}`
    const closedFence = `\`\`\`python\n${partialCode}\n\`\`\``

    const htmlOpen = renderToString(<Markdown text={openFence} isStreaming />)
    const htmlClosed = renderToString(<Markdown text={closedFence} />)

    // Both renders must produce the same Python syntax tokens — no FOUC on close.
    expect(htmlOpen).toContain('def')
    expect(htmlOpen).toContain('greet')
    expect(htmlClosed).toContain('def')
    expect(htmlClosed).toContain('greet')
    // The highlighted spans for the shared prefix must be structurally identical.
    // Extract the <code> body from each and compare token presence.
    const extractSpans = (html: string) =>
      Array.from(html.matchAll(/<span[^>]*>([^<]+)<\/span>/g)).map((m) => m[1])
    const openSpans = extractSpans(htmlOpen)
    const closedSpans = extractSpans(htmlClosed)
    // Every token in the open render must appear in the closed render.
    openSpans.forEach((tok) => expect(closedSpans).toContain(tok))
  })
})

// Security regression tests — HACHI-001 (DOM XSS via unsanitized link hrefs).
// These guard against javascript:, data:, and other dangerous URL schemes being
// rendered as live <a href> attributes. If any of these fail, the XSS fix has
// regressed and users of this renderer are at risk.
describe('Markdown — XSS / link sanitization (HACHI-001)', () => {
  it('strips javascript: href — produces no <a with javascript: href', () => {
    const html = renderToString(<Markdown text="[x](javascript:alert(1))" />)
    // Must not contain an anchor pointing to a javascript: URL
    expect(html).not.toMatch(/<a[^>]+href=["']javascript:/i)
    // The link text "x" must still be visible
    expect(html).toContain('x')
  })

  it('strips javascript: href with no parens in payload', () => {
    // Variant without parens — still a javascript: URL
    const html = renderToString(<Markdown text="[x](javascript:location='evil')" />)
    expect(html).not.toMatch(/<a[^>]+href=["']javascript:/i)
    expect(html).toContain('x')
  })

  it('strips javascript: href with leading whitespace (bypass attempt)', () => {
    // Browsers ignore leading whitespace before the scheme
    const html = renderToString(<Markdown text="[x](  javascript:alert(1))" />)
    expect(html).not.toMatch(/<a[^>]+href=["']javascript:/i)
    expect(html).toContain('x')
  })

  it('strips data: href (inline script/image injection)', () => {
    const html = renderToString(
      <Markdown text="[x](data:text/html,<script>alert(1)</script>)" />
    )
    expect(html).not.toMatch(/<a[^>]+href=["']data:/i)
    expect(html).toContain('x')
  })

  it('strips vbscript: href', () => {
    const html = renderToString(<Markdown text="[x](vbscript:MsgBox(1))" />)
    expect(html).not.toMatch(/<a[^>]+href=["']vbscript:/i)
    expect(html).toContain('x')
  })

  it('allows https: href with correct attributes', () => {
    const html = renderToString(<Markdown text="[ok](https://example.com)" />)
    expect(html).toMatch(/<a[^>]+href="https:\/\/example\.com"/)
    expect(html).toMatch(/target="_blank"/)
    expect(html).toMatch(/rel="[^"]*noopener/)
    expect(html).toContain('ok')
  })

  it('allows http: href', () => {
    const html = renderToString(<Markdown text="[link](http://example.com)" />)
    expect(html).toMatch(/<a[^>]+href="http:\/\/example\.com"/)
  })

  it('allows mailto: href', () => {
    const html = renderToString(<Markdown text="[email](mailto:user@example.com)" />)
    expect(html).toMatch(/<a[^>]+href="mailto:user@example\.com"/)
  })

  it('allows relative / href', () => {
    const html = renderToString(<Markdown text="[home](/home)" />)
    expect(html).toMatch(/<a[^>]+href="\/home"/)
  })

  it('allows relative # href (same-page anchor)', () => {
    const html = renderToString(<Markdown text="[top](#top)" />)
    expect(html).toMatch(/<a[^>]+href="#top"/)
  })

  it('raw <img onerror> in text stays escaped — no live onerror attribute', () => {
    // The renderer should HTML-escape raw angle brackets in text nodes;
    // React does this automatically for string children.
    const html = renderToString(<Markdown text="<img src=x onerror=alert(1)>" />)
    // Must not contain an actual <img element (with real angle brackets and attrs)
    expect(html).not.toMatch(/<img\s[^>]*onerror/)
    // The text content should still be present in some escaped form
    expect(html).toContain('&lt;img')
  })
})

// T31 — Tables
describe('Markdown — tables (T31)', () => {
  it('renders a basic table with <table>, <th scope="col">, and <td>', () => {
    const text = '| Name | Age |\n|---|---|\n| Alice | 30 |\n| Bob | 25 |'
    const html = renderToString(<Markdown text={text} />)
    expect(html).toContain('<table')
    expect(html).toContain('<th')
    expect(html).toContain('scope="col"')
    expect(html).toContain('<td')
    expect(html).toContain('Alice')
    expect(html).toContain('Bob')
    expect(html).toContain('Name')
    expect(html).toContain('Age')
  })

  it('wraps table in overflow-x: auto container', () => {
    const text = '| A | B |\n|---|---|\n| 1 | 2 |'
    const html = renderToString(<Markdown text={text} />)
    expect(html).toContain('overflow-x')
    expect(html).toContain('auto')
  })

  it('renders inline formatting inside table cells', () => {
    const text = '| Name | Status |\n|---|---|\n| **Alice** | `active` |'
    const html = renderToString(<Markdown text={text} />)
    expect(html).toContain('<strong')
    expect(html).toContain('<code')
  })

  it('does not produce a table without a separator row', () => {
    const text = '| A | B |\n| 1 | 2 |'
    const html = renderToString(<Markdown text={text} />)
    expect(html).not.toContain('<table')
  })
})

// T31 — Blockquotes
describe('Markdown — blockquotes (T31)', () => {
  it('renders > lines as <blockquote> with a left border color', () => {
    const html = renderToString(<Markdown text="> This is quoted text" />)
    expect(html).toContain('<blockquote')
    expect(html).toContain('This is quoted text')
    expect(html).toContain('border-left')
  })

  it('collects consecutive > lines into one blockquote', () => {
    const text = '> Line one\n> Line two'
    const html = renderToString(<Markdown text={text} />)
    const count = (html.match(/<blockquote/g) ?? []).length
    expect(count).toBe(1)
    expect(html).toContain('Line one')
    expect(html).toContain('Line two')
  })

  it('renders inline formatting inside blockquotes', () => {
    const html = renderToString(<Markdown text="> **bold** and _italic_" />)
    expect(html).toContain('<strong')
    expect(html).toContain('<em')
  })
})

// T31 — Horizontal rule
describe('Markdown — horizontal rule (T31)', () => {
  it('renders --- as <hr>', () => {
    const html = renderToString(<Markdown text={"Line above\n---\nLine below"} />)
    expect(html).toContain('<hr')
    expect(html).toContain('Line above')
    expect(html).toContain('Line below')
  })

  it('renders *** as <hr>', () => {
    const html = renderToString(<Markdown text="***" />)
    expect(html).toContain('<hr')
  })

  it('renders ___ as <hr>', () => {
    const html = renderToString(<Markdown text="___" />)
    expect(html).toContain('<hr')
  })
})

// T31 — Nested lists
describe('Markdown — nested lists (T31)', () => {
  it('renders a flat unordered list as <ul><li>', () => {
    const text = '- Alpha\n- Beta\n- Gamma'
    const html = renderToString(<Markdown text={text} />)
    expect(html).toContain('<ul')
    expect(html).toContain('<li')
    expect(html).toContain('Alpha')
    expect(html).toContain('Beta')
    expect(html).toContain('Gamma')
  })

  it('renders indented list items as nested <ul>', () => {
    const text = '- Parent\n  - Child\n  - Child 2'
    const html = renderToString(<Markdown text={text} />)
    const ulCount = (html.match(/<ul/g) ?? []).length
    expect(ulCount).toBeGreaterThanOrEqual(2)
    expect(html).toContain('Parent')
    expect(html).toContain('Child')
    expect(html).toContain('Child 2')
  })

  it('renders ordered list with nested sub-items', () => {
    const text = '1. First\n2. Second\n   1. Sub'
    const html = renderToString(<Markdown text={text} />)
    expect(html).toContain('<ol')
    expect(html).toContain('First')
    expect(html).toContain('Sub')
  })
})
