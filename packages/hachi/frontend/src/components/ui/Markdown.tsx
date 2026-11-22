// Self-contained Markdown renderer — no external dependencies.
// Supports a pragmatic subset suitable for streaming assistant output:
//   - Headings (#, ##, …, ######)
//   - Unordered lists (- / * prefix)
//   - Ordered lists (1. prefix)
//   - Fenced code blocks (``` lang … ```)
//   - Paragraphs / blank-line separation
//   - Inline: bold (**…** / __…__), italic (*…* / _…_), code (`…`), links ([t](u))
//
// Streaming-safe: never throws on partial/unterminated input.
// Unclosed markers render as literal text until the closing marker arrives.

import { memo, useMemo, useState, useRef, useCallback } from 'react'
import type { ReactNode, CSSProperties } from 'react'

// ---- URL sanitizer --------------------------------------------------
// Allows only safe URL schemes. Returns null for anything disallowed
// (javascript:, data:, vbscript:, etc.).
//
// Attackers use leading whitespace / control chars and tab-embedded
// scheme names (e.g. "java\tscript:") to bypass naive checks, so we
// strip leading whitespace/control chars before extracting the scheme
// and compare case-insensitively.
function safeHref(href: string): string | null {
  // Strip leading ASCII whitespace and C0 control characters (U+0000–U+001F).
  // These can appear in raw markdown and are dropped by browsers silently.
  const trimmed = href.replace(/^\s+/, '')

  // Relative URLs are always safe: /, #, ./, ../
  if (
    trimmed.startsWith('/') ||
    trimmed.startsWith('#') ||
    trimmed.startsWith('./') ||
    trimmed.startsWith('../')
  ) {
    return trimmed
  }

  // Extract the scheme — everything up to and including the first colon,
  // then collapse any embedded whitespace/control chars that browsers ignore.
  const colonIdx = trimmed.indexOf(':')
  if (colonIdx === -1) {
    // No scheme → treat as a relative URL path (safe)
    return trimmed
  }
  // Collapse whitespace within the scheme (handles "java\tscript:")
  const scheme = trimmed.slice(0, colonIdx).replace(/\s+/g, '').toLowerCase()

  const ALLOWED_SCHEMES = new Set(['http', 'https', 'mailto', 'tel'])
  if (!ALLOWED_SCHEMES.has(scheme)) {
    return null
  }

  return trimmed
}

// ---- Inline parser --------------------------------------------------
// Tokenises a single text run into spans with optional formatting.

type InlineToken =
  | { kind: 'text'; value: string }
  | { kind: 'bold'; children: InlineToken[] }
  | { kind: 'italic'; children: InlineToken[] }
  | { kind: 'code'; value: string }
  | { kind: 'link'; href: string; children: InlineToken[] }

// Marker table: order matters — longer markers must come before sub-matches.
// We check ** before * so ** isn't accidentally consumed as two * tokens.
//
// IMPORTANT: this is only the PATTERN SOURCE. `parseInline` is recursive (bold/
// italic/link children are parsed by recursing), so it MUST NOT share a single
// stateful (`g`-flag) RegExp across calls: a nested call would reset the shared
// `lastIndex`, making the outer loop re-match the same token forever — an
// infinite loop that hangs the main thread on any text containing emphasis or a
// link. Each parseInline call therefore builds its own RegExp instance below.
// NOTE (HACHI-015 — LOW): The link href pattern `\(([^)]*)\)` stops at the
// first `)`, which truncates URLs that legally contain parentheses (e.g.
// Wikipedia links like `/wiki/Foo_(bar)`). Fixing this requires a more
// complex regex (e.g. balanced-paren counting) that cannot share the `g`-flag
// instance safety constraints documented above without careful testing. Given
// that the XSS fix (HACHI-001) and recursion safety take precedence, this
// limitation is left in place and documented here. URLs with parens should be
// encoded as `%28`/`%29` to work correctly with this renderer.
const INLINE_RE_SOURCE =
  '(`[^`]*`?)|(\\*\\*(?:[^*]|\\*(?!\\*))*\\*\\*)|(__(?:[^_]|_(?!_))*__)|(\\*(?:[^*])*\\*(?!\\*))|(_(?:[^_])*_(?!_))|(\\[([^\\]]*)\\]\\(([^)]*)\\))'

function parseInline(text: string): InlineToken[] {
  // Local, per-call regex instance — recursion-safe (see INLINE_RE_SOURCE note).
  const re = new RegExp(INLINE_RE_SOURCE, 'g')
  const tokens: InlineToken[] = []
  let lastIndex = 0

  let m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) {
    // Defensive: a zero-width match would never advance lastIndex → infinite
    // loop. Skip a char and continue. (Not expected with the current pattern.)
    if (m.index === re.lastIndex) {
      re.lastIndex += 1
      continue
    }

    // Push any literal text before this match
    if (m.index > lastIndex) {
      tokens.push({ kind: 'text', value: text.slice(lastIndex, m.index) })
    }

    const [full, code, boldStar, boldUnd, italicStar, italicUnd, , linkText, linkHref] = m

    if (code !== undefined) {
      // Inline code — strip surrounding backticks; tolerate unclosed (trailing `)
      const inner = full.startsWith('`') && full.endsWith('`') && full.length > 1
        ? full.slice(1, -1)
        : full.slice(1)
      tokens.push({ kind: 'code', value: inner })
    } else if (boldStar !== undefined || boldUnd !== undefined) {
      const inner = (boldStar ?? boldUnd).slice(2, -2)
      tokens.push({ kind: 'bold', children: parseInline(inner) })
    } else if (italicStar !== undefined || italicUnd !== undefined) {
      const inner = (italicStar ?? italicUnd).slice(1, -1)
      tokens.push({ kind: 'italic', children: parseInline(inner) })
    } else if (linkText !== undefined && linkHref !== undefined) {
      tokens.push({ kind: 'link', href: linkHref, children: parseInline(linkText) })
    } else {
      // Fallback: treat the whole match as literal text (shouldn't normally happen)
      tokens.push({ kind: 'text', value: full })
    }

    lastIndex = re.lastIndex
  }

  // Remaining literal text
  if (lastIndex < text.length) {
    tokens.push({ kind: 'text', value: text.slice(lastIndex) })
  }

  return tokens
}

function renderInlineTokens(tokens: InlineToken[], keyPrefix: string): ReactNode[] {
  return tokens.map((tok, i) => {
    const key = `${keyPrefix}-${i}`
    switch (tok.kind) {
      case 'text':
        return tok.value
      case 'code':
        return (
          <code
            key={key}
            style={{
              fontFamily: 'var(--font-mono, monospace)',
              fontSize: '0.88em',
              background: 'var(--hachi-cream, rgba(0,0,0,0.06))',
              borderRadius: 4,
              padding: '1px 5px',
            }}
          >
            {tok.value}
          </code>
        )
      case 'bold':
        return <strong key={key}>{renderInlineTokens(tok.children, key)}</strong>
      case 'italic':
        return <em key={key}>{renderInlineTokens(tok.children, key)}</em>
      case 'link': {
        const allowedHref = safeHref(tok.href)
        if (allowedHref === null) {
          // Disallowed scheme (javascript:, data:, vbscript:, etc.) — render
          // the link text as plain inline content, no <a> wrapper.
          return <span key={key}>{renderInlineTokens(tok.children, key)}</span>
        }
        return (
          <a
            key={key}
            href={allowedHref}
            rel="noreferrer noopener"
            target="_blank"
            style={{ color: 'var(--hachi-trust, #4c6ef5)', textDecoration: 'underline' }}
          >
            {renderInlineTokens(tok.children, key)}
          </a>
        )
      }
    }
  })
}

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  return renderInlineTokens(parseInline(text), keyPrefix)
}

// ---- Block-level parser ---------------------------------------------

interface ListItem { text: string; depth: number }

type BlockNode =
  | { kind: 'heading'; level: number; text: string }
  | { kind: 'ul'; items: ListItem[] }
  | { kind: 'ol'; items: ListItem[] }
  | { kind: 'paragraph'; lines: string[] }
  | { kind: 'code'; lang: string; code: string }
  | { kind: 'blank' }
  | { kind: 'blockquote'; lines: string[] }
  | { kind: 'hr' }
  | { kind: 'table'; headers: string[]; rows: string[][] }

const HEADING_RE = /^(#{1,6})\s+(.*)$/
const UL_RE = /^( *)[-*]\s+(.+)$/
const OL_RE = /^( *)\d+\.\s+(.+)$/
const HR_RE = /^(\*{3,}|-{3,}|_{3,})\s*$/
const TABLE_ROW_RE = /^\|(.+)\|$/
const TABLE_SEP_RE = /^\|[\s\-:|]+\|/

// When isStreaming is true, an unclosed fenced code block is flagged so the
// renderer can show the styled container immediately (no FOUC on fence close).
type ParseOptions = { isStreaming?: boolean }

function parseBlocks(text: string, opts: ParseOptions = {}): BlockNode[] {
  const rawLines = text.split('\n')
  const blocks: BlockNode[] = []

  let i = 0
  while (i < rawLines.length) {
    const line = rawLines[i]

    // Blank line
    if (line.trim() === '') {
      blocks.push({ kind: 'blank' })
      i++
      continue
    }

    // Fenced code block (``` or ~~~)
    if (line.startsWith('```') || line.startsWith('~~~')) {
      const fence = line.slice(0, 3)
      const lang = line.slice(3).trim().toLowerCase()
      const codeLines: string[] = []
      i++
      let closedFence = false
      while (i < rawLines.length && !rawLines[i].startsWith(fence)) {
        codeLines.push(rawLines[i])
        i++
      }
      if (i < rawLines.length) {
        closedFence = true
        i++ // consume closing fence
      }
      // Drop a single trailing empty line added by the model after the fence
      while (codeLines.length > 0 && codeLines[codeLines.length - 1].trim() === '') {
        codeLines.pop()
      }
      // During streaming an unclosed fence is still rendered as a code block so
      // the styled container appears immediately. We mark it so tests can assert it.
      if (!closedFence && !opts.isStreaming) {
        // Not streaming and fence is unclosed: emit as paragraph text to avoid
        // a dangling styled container in completed messages.
        blocks.push({ kind: 'paragraph', lines: [fence + lang, ...codeLines] })
      } else {
        blocks.push({ kind: 'code', lang, code: codeLines.join('\n') })
      }
      continue
    }

    // Heading
    const hm = HEADING_RE.exec(line)
    if (hm) {
      blocks.push({ kind: 'heading', level: hm[1].length, text: hm[2] })
      i++
      continue
    }

    // Horizontal rule (must come before list/paragraph so `---` isn't a stray paragraph)
    if (HR_RE.test(line)) {
      blocks.push({ kind: 'hr' })
      i++
      continue
    }

    // Blockquote — collect consecutive `> ` lines
    if (line.startsWith('> ') || line === '>') {
      const bqLines: string[] = []
      while (i < rawLines.length && (rawLines[i].startsWith('> ') || rawLines[i] === '>')) {
        bqLines.push(rawLines[i].startsWith('> ') ? rawLines[i].slice(2) : '')
        i++
      }
      blocks.push({ kind: 'blockquote', lines: bqLines })
      continue
    }

    // Table — pipe-row followed immediately by a separator row
    if (TABLE_ROW_RE.test(line) && i + 1 < rawLines.length && TABLE_SEP_RE.test(rawLines[i + 1])) {
      const parseRow = (l: string): string[] =>
        l.replace(/^\||\|$/g, '').split('|').map((c) => c.trim())
      const headers = parseRow(line)
      i += 2 // skip header + separator
      const rows: string[][] = []
      while (i < rawLines.length && TABLE_ROW_RE.test(rawLines[i])) {
        rows.push(parseRow(rawLines[i]))
        i++
      }
      blocks.push({ kind: 'table', headers, rows })
      continue
    }

    // Unordered list — collect consecutive UL lines (including indented sub-items)
    if (UL_RE.test(line)) {
      const items: ListItem[] = []
      let mm: RegExpExecArray | null
      while (i < rawLines.length && (mm = UL_RE.exec(rawLines[i]))) {
        const depth = Math.min(Math.floor(mm[1].length / 2), 3)
        items.push({ text: mm[2], depth })
        i++
      }
      blocks.push({ kind: 'ul', items })
      continue
    }

    // Ordered list — collect consecutive OL lines (including indented sub-items)
    if (OL_RE.test(line)) {
      const items: ListItem[] = []
      let mm: RegExpExecArray | null
      while (i < rawLines.length && (mm = OL_RE.exec(rawLines[i]))) {
        const depth = Math.min(Math.floor(mm[1].length / 2), 3)
        items.push({ text: mm[2], depth })
        i++
      }
      blocks.push({ kind: 'ol', items })
      continue
    }

    // Regular paragraph — collect non-blank, non-structural lines.
    // Note: pipe-delimited lines that don't form a valid table (no separator row)
    // are allowed in paragraphs — they must not be excluded here or the outer
    // while loop would spin forever without advancing `i`.
    const lines: string[] = []
    while (
      i < rawLines.length &&
      rawLines[i].trim() !== '' &&
      !HEADING_RE.test(rawLines[i]) &&
      !HR_RE.test(rawLines[i]) &&
      !UL_RE.test(rawLines[i]) &&
      !OL_RE.test(rawLines[i]) &&
      !(rawLines[i].startsWith('> ') || rawLines[i] === '>') &&
      !rawLines[i].startsWith('```') &&
      !rawLines[i].startsWith('~~~')
    ) {
      lines.push(rawLines[i])
      i++
    }
    if (lines.length > 0) {
      blocks.push({ kind: 'paragraph', lines })
    }
  }

  return blocks
}

// ---- Heading font sizes ------------------------------------------

function headingStyle(level: number): CSSProperties {
  const sizes: Record<number, CSSProperties> = {
    1: { fontSize: '1.25em', fontWeight: 700, lineHeight: '1.3', margin: '0.6em 0 0.3em' },
    2: { fontSize: '1.15em', fontWeight: 700, lineHeight: '1.3', margin: '0.6em 0 0.25em' },
    3: { fontSize: '1.05em', fontWeight: 600, lineHeight: '1.3', margin: '0.5em 0 0.2em' },
    4: { fontSize: '1em', fontWeight: 600, lineHeight: '1.3', margin: '0.5em 0 0.2em' },
    5: { fontSize: '0.95em', fontWeight: 600, lineHeight: '1.3', margin: '0.4em 0 0.15em' },
    6: { fontSize: '0.9em', fontWeight: 600, lineHeight: '1.3', margin: '0.4em 0 0.15em' },
  }
  return sizes[level] ?? sizes[6]
}

// ---- Syntax highlighting --------------------------------------------

const PY_KW = new Set(
  'False None True and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield'.split(
    ' '
  )
)
const PY_BUILTIN = new Set(
  'print input len range type str int float list dict set tuple bool open enumerate zip map filter sorted reversed sum min max abs repr vars dir hasattr getattr setattr isinstance issubclass'.split(
    ' '
  )
)
const JS_KW = new Set(
  'const let var function return if else for while do break continue class extends import export default from new typeof instanceof void delete in of async await try catch finally throw switch case yield'.split(
    ' '
  )
)
const JS_BUILTIN = new Set(
  'console log warn error JSON parse stringify Math floor ceil round abs Object Array Promise setTimeout clearTimeout setInterval clearInterval fetch window document'.split(
    ' '
  )
)

type SyntaxKind = 'kw' | 'builtin' | 'str' | 'cmt' | 'num' | 'fn' | 'plain'
type SyntaxToken = { t: SyntaxKind; v: string }

const SYNTAX_COLORS: Record<SyntaxKind, string | undefined> = {
  kw: 'var(--syntax-kw, #c792ea)',
  builtin: 'var(--syntax-builtin, #82aaff)',
  fn: 'var(--syntax-fn, #82aaff)',
  str: 'var(--syntax-str, #c3e88d)',
  cmt: 'var(--syntax-cmt, #546e7a)',
  num: 'var(--syntax-num, #f78c6c)',
  plain: undefined,
}

const YAML_KW = new Set(['true', 'false', 'null', 'yes', 'no', 'on', 'off'])
const BASH_KW = new Set([
  'if', 'then', 'else', 'elif', 'fi', 'for', 'do', 'done', 'while', 'until',
  'case', 'esac', 'in', 'function', 'return', 'export', 'local', 'readonly',
  'source', 'echo', 'printf', 'exit', 'set', 'unset', 'shift', 'eval',
])

function tokenizeYamlLine(line: string): SyntaxToken[] {
  const tokens: SyntaxToken[] = []
  const trimmed = line.trimStart()
  const indent = line.length - trimmed.length

  if (indent > 0) tokens.push({ t: 'plain', v: line.slice(0, indent) })

  // Comment
  if (trimmed.startsWith('#')) {
    tokens.push({ t: 'cmt', v: trimmed })
    return tokens
  }
  // List item marker
  if (trimmed.startsWith('- ')) {
    tokens.push({ t: 'builtin', v: '- ' })
    tokens.push(...tokenizeYamlLine(trimmed.slice(2)))
    return tokens
  }
  // key: value
  const colonIdx = trimmed.indexOf(': ')
  if (colonIdx > 0) {
    const key = trimmed.slice(0, colonIdx)
    tokens.push({ t: 'fn', v: key }, { t: 'plain', v: ': ' })
    const rest = trimmed.slice(colonIdx + 2)
    if (rest.startsWith('"') || rest.startsWith("'")) {
      tokens.push({ t: 'str', v: rest })
    } else if (YAML_KW.has(rest.trim())) {
      tokens.push({ t: 'kw', v: rest })
    } else {
      tokens.push({ t: 'plain', v: rest })
    }
    return tokens
  }
  // bare key with no value (mapping header)
  if (/^[\w-]+:$/.test(trimmed)) {
    tokens.push({ t: 'fn', v: trimmed })
    return tokens
  }
  tokens.push({ t: 'plain', v: trimmed })
  return tokens
}

function tokenizeBashLine(line: string): SyntaxToken[] {
  if (line.trimStart().startsWith('#')) return [{ t: 'cmt', v: line }]

  const tokens: SyntaxToken[] = []
  let i = 0
  while (i < line.length) {
    // $VAR or ${VAR}
    if (line[i] === '$') {
      let j = i + 1
      if (line[j] === '{') {
        j++
        while (j < line.length && line[j] !== '}') j++
        if (j < line.length) j++
      } else {
        while (j < line.length && /\w/.test(line[j])) j++
      }
      tokens.push({ t: 'fn', v: line.slice(i, j) })
      i = j
      continue
    }
    // Flag (-x / --flag)
    if (line[i] === '-' && (i === 0 || /\s/.test(line[i - 1]))) {
      let j = i + 1
      while (j < line.length && /[\w-]/.test(line[j])) j++
      if (j > i + 1) { tokens.push({ t: 'builtin', v: line.slice(i, j) }); i = j; continue }
    }
    // String
    if (line[i] === '"' || line[i] === "'") {
      const q = line[i]; let j = i + 1
      while (j < line.length && line[j] !== q) { if (line[j] === '\\') j++; j++ }
      if (j < line.length) j++
      tokens.push({ t: 'str', v: line.slice(i, j) }); i = j; continue
    }
    // Word / keyword
    if (/[a-zA-Z_]/.test(line[i])) {
      let j = i
      while (j < line.length && /[\w-]/.test(line[j])) j++
      const word = line.slice(i, j)
      tokens.push({ t: BASH_KW.has(word) ? 'kw' : 'plain', v: word }); i = j; continue
    }
    // Comment mid-line
    if (line[i] === '#') { tokens.push({ t: 'cmt', v: line.slice(i) }); break }
    tokens.push({ t: 'plain', v: line[i] }); i++
  }
  return tokens
}

function tokenizeTomlLine(line: string): SyntaxToken[] {
  const trimmed = line.trim()
  if (trimmed.startsWith('#')) return [{ t: 'cmt', v: line }]
  if (trimmed.startsWith('[')) return [{ t: 'kw', v: line }]
  const eqIdx = trimmed.indexOf(' = ')
  if (eqIdx > 0) {
    const indent = line.length - line.trimStart().length
    const key = trimmed.slice(0, eqIdx)
    const rest = trimmed.slice(eqIdx + 3)
    const restToken: SyntaxToken = (rest.startsWith('"') || rest.startsWith("'"))
      ? { t: 'str', v: rest }
      : { t: 'plain', v: rest }
    return [
      { t: 'plain', v: line.slice(0, indent) },
      { t: 'fn', v: key },
      { t: 'plain', v: ' = ' },
      restToken,
    ]
  }
  return [{ t: 'plain', v: line }]
}

function tokenizeLine(line: string, lang: string): SyntaxToken[] {
  const isPy = lang === 'python' || lang === 'py'
  const isJs =
    lang === 'js' ||
    lang === 'javascript' ||
    lang === 'ts' ||
    lang === 'typescript' ||
    lang === 'jsx' ||
    lang === 'tsx'
  const isYaml = lang === 'yaml' || lang === 'yml'
  const isBash = lang === 'bash' || lang === 'sh' || lang === 'shell' || lang === 'zsh'
  const isToml = lang === 'toml'

  if (isYaml) return tokenizeYamlLine(line)
  if (isBash) return tokenizeBashLine(line)
  if (isToml) return tokenizeTomlLine(line)

  if (!isPy && !isJs) return [{ t: 'plain', v: line }]

  const tokens: SyntaxToken[] = []
  let i = 0

  while (i < line.length) {
    // Python comment
    if (isPy && line[i] === '#') {
      tokens.push({ t: 'cmt', v: line.slice(i) })
      break
    }
    // JS/TS line comment
    if (isJs && line.slice(i, i + 2) === '//') {
      tokens.push({ t: 'cmt', v: line.slice(i) })
      break
    }

    // String literal (single or double quoted, no multiline)
    if (line[i] === '"' || line[i] === "'") {
      const quote = line[i]
      let j = i + 1
      while (j < line.length && line[j] !== quote) {
        if (line[j] === '\\') j++
        j++
      }
      if (j < line.length) j++
      tokens.push({ t: 'str', v: line.slice(i, j) })
      i = j
      continue
    }

    // Template literal (JS)
    if (isJs && line[i] === '`') {
      let j = i + 1
      while (j < line.length && line[j] !== '`') {
        if (line[j] === '\\') j++
        j++
      }
      if (j < line.length) j++
      tokens.push({ t: 'str', v: line.slice(i, j) })
      i = j
      continue
    }

    // Number
    if (/\d/.test(line[i]) && (i === 0 || !/\w/.test(line[i - 1]))) {
      let j = i
      while (j < line.length && /[\d._]/.test(line[j])) j++
      tokens.push({ t: 'num', v: line.slice(i, j) })
      i = j
      continue
    }

    // Identifier / keyword / builtin / function call
    if (/[a-zA-Z_]/.test(line[i])) {
      let j = i
      while (j < line.length && /\w/.test(line[j])) j++
      const word = line.slice(i, j)
      const isKw = isPy ? PY_KW.has(word) : JS_KW.has(word)
      const isBuiltin = isPy ? PY_BUILTIN.has(word) : JS_BUILTIN.has(word)
      const isFn = !isKw && !isBuiltin && j < line.length && line[j] === '('
      tokens.push({ t: isKw ? 'kw' : isBuiltin ? 'builtin' : isFn ? 'fn' : 'plain', v: word })
      i = j
      continue
    }

    // Plain run (operators, punctuation, whitespace)
    let j = i
    while (
      j < line.length &&
      !/[a-zA-Z_"'`#\d]/.test(line[j]) &&
      !(isPy && line[j] === '#') &&
      !(isJs && line.slice(j, j + 2) === '//')
    ) {
      j++
    }
    if (j > i) {
      tokens.push({ t: 'plain', v: line.slice(i, j) })
      i = j
    } else {
      tokens.push({ t: 'plain', v: line[i] })
      i++
    }
  }

  return tokens
}

function renderHighlighted(code: string, lang: string): ReactNode {
  const normalizedLang = lang.toLowerCase().trim()
  const highlightable = new Set([
    'python', 'py', 'js', 'javascript', 'ts', 'typescript', 'jsx', 'tsx',
    'yaml', 'yml', 'bash', 'sh', 'shell', 'zsh', 'toml',
  ])
  if (!highlightable.has(normalizedLang)) return code
  const lang_ = normalizedLang

  const lines = code.split('\n')
  return lines.map((line, li) => (
    <span key={li}>
      {tokenizeLine(line, lang_).map((tok, ti) => {
        const color = SYNTAX_COLORS[tok.t]
        return color ? (
          <span key={ti} style={{ color }}>
            {tok.v}
          </span>
        ) : (
          <span key={ti}>{tok.v}</span>
        )
      })}
      {li < lines.length - 1 && '\n'}
    </span>
  ))
}

// ---- Language display helpers ----------------------------------------

const LANG_DISPLAY: Record<string, string> = {
  python: 'Python',
  py: 'Python',
  javascript: 'JavaScript',
  js: 'JavaScript',
  typescript: 'TypeScript',
  ts: 'TypeScript',
  tsx: 'TSX',
  jsx: 'JSX',
  bash: 'Shell',
  shell: 'Shell',
  sh: 'Shell',
  zsh: 'Shell',
  json: 'JSON',
  html: 'HTML',
  css: 'CSS',
  sql: 'SQL',
  rust: 'Rust',
  go: 'Go',
  java: 'Java',
  c: 'C',
  cpp: 'C++',
  ruby: 'Ruby',
  rb: 'Ruby',
  yaml: 'YAML',
  yml: 'YAML',
  toml: 'TOML',
  md: 'Markdown',
  markdown: 'Markdown',
}

function formatLang(lang: string): string {
  return LANG_DISPLAY[lang] ?? (lang ? lang.charAt(0).toUpperCase() + lang.slice(1) : 'Code')
}

// ---- CodeBlock component --------------------------------------------

function CopyIcon(): JSX.Element {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="5" y="5" width="9" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.4" />
      <path d="M3 11H2.5A1.5 1.5 0 011 9.5v-7A1.5 1.5 0 012.5 1h7A1.5 1.5 0 0111 2.5V3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  )
}

function CheckIcon(): JSX.Element {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M3 8l4 4 6-6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

// F1: memo prevents settled code blocks from re-rendering on every streaming token
// in the active bubble. useMemo inside caches the highlight result so a fence
// close (code unchanged, only block-open→closed) skips the tokenizer entirely.
const CodeBlock = memo(function CodeBlock({ lang, code }: { lang: string; code: string }): JSX.Element {
  const [copied, setCopied] = useState(false)
  const copyBtnRef = useRef<HTMLButtonElement>(null)
  const normalizedLang = lang.toLowerCase().trim()
  // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional: cache on (code, normalizedLang)
  const highlighted = useMemo(() => renderHighlighted(code, normalizedLang), [code, normalizedLang])

  const handleCopy = useCallback(() => {
    const write = async () => {
      try {
        await navigator.clipboard.writeText(code)
      } catch {
        // Fallback for iframes / non-HTTPS contexts where clipboard API is blocked
        const el = document.createElement('textarea')
        el.value = code
        el.style.cssText = 'position:fixed;opacity:0;pointer-events:none'
        document.body.appendChild(el)
        el.select()
        try { document.execCommand('copy') } catch { /* ignore */ }
        document.body.removeChild(el)
      }
      setCopied(true)
      copyBtnRef.current?.animate(
        [{ transform: 'scale(1)' }, { transform: 'scale(1.3)' }, { transform: 'scale(1)' }],
        { duration: 250, easing: 'ease-out' }
      )
      setTimeout(() => setCopied(false), 2000)
    }
    void write()
  }, [code])

  const displayLang = formatLang(lang)

  return (
    <div
      style={{
        borderRadius: 8,
        overflow: 'hidden',
        margin: '0.65em 0',
        border: '1px solid rgba(255,255,255,0.09)',
        background: 'var(--hachi-code-bg)',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '5px 12px',
          background: 'rgba(255,255,255,0.04)',
          borderBottom: '1px solid rgba(255,255,255,0.07)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ opacity: 0.45 }}>
            <path d="M5 4L1 8l4 4M11 4l4 4-4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span
            style={{
              fontSize: '0.76em',
              fontFamily: 'var(--font-mono, monospace)',
              color: 'var(--hachi-code-icon)',
              letterSpacing: '0.01em',
            }}
          >
            {displayLang}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <button
            ref={copyBtnRef}
            type="button"
            onClick={handleCopy}
            title={copied ? 'Copied!' : 'Copy code'}
            aria-label={copied ? 'Copied to clipboard' : 'Copy code'}
            style={{
              background: copied ? 'var(--hachi-code-copied-bg)' : 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '3px 8px',
              borderRadius: 4,
              color: copied ? 'var(--hachi-code-copied)' : 'var(--hachi-code-icon)',
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              transition: 'color 0.2s, background 0.2s',
            }}
          >
            {copied ? (
              <>
                <CheckIcon />
                <span style={{ fontSize: '0.74em', fontFamily: 'inherit', fontWeight: 500 }}>
                  Copied!
                </span>
              </>
            ) : (
              <CopyIcon />
            )}
          </button>
        </div>
      </div>

      {/* Code */}
      <pre
        style={{
          margin: 0,
          padding: '14px 16px',
          overflowX: 'auto',
          fontFamily: 'var(--font-mono, monospace)',
          fontSize: '0.87em',
          lineHeight: '1.65',
          color: 'var(--hachi-code-text)',
        }}
      >
        <code>{highlighted}</code>
      </pre>
    </div>
  )
})

// ---- Nested list renderer -------------------------------------------

interface ListTreeNode { text: string; children: ListTreeNode[] }

function buildListTree(items: ListItem[]): ListTreeNode[] {
  const root: ListTreeNode[] = []
  const stack: ListTreeNode[][] = [root]

  for (const item of items) {
    const depth = Math.min(item.depth, 2)
    while (stack.length > depth + 1) stack.pop()
    while (stack.length < depth + 1) {
      const parent = stack[stack.length - 1]
      if (parent.length === 0) parent.push({ text: '', children: [] })
      stack.push(parent[parent.length - 1].children)
    }
    stack[stack.length - 1].push({ text: item.text, children: [] })
  }
  return root
}

function renderTreeNodes(nodes: ListTreeNode[], kind: 'ul' | 'ol', depth: number, kp: string): ReactNode {
  const Tag = kind === 'ul' ? 'ul' as const : 'ol' as const
  const listStyle = kind === 'ul' ? (depth === 0 ? 'disc' : 'circle') : 'decimal'
  return (
    <Tag
      key={kp}
      style={{ margin: depth === 0 ? '0.25em 0' : '0.1em 0', paddingLeft: '1.5em', listStyleType: listStyle }}
    >
      {nodes.map((n, ni) => (
        <li key={`${kp}-${ni}`} style={{ lineHeight: 'inherit', margin: '0.1em 0' }}>
          {n.text ? renderInline(n.text, `${kp}-${ni}-t`) : null}
          {n.children.length > 0 && renderTreeNodes(n.children, kind, depth + 1, `${kp}-${ni}-c`)}
        </li>
      ))}
    </Tag>
  )
}

function renderNestedList(items: ListItem[], kind: 'ul' | 'ol', key: string): ReactNode {
  return renderTreeNodes(buildListTree(items), kind, 0, key)
}

// ---- Render blocks --------------------------------------------------

function renderBlock(block: BlockNode, blockIdx: number): ReactNode {
  const key = `b${blockIdx}`
  switch (block.kind) {
    case 'blank':
      // Blank lines add visual spacing via paragraph gap
      return <div key={key} style={{ height: '0.6em' }} />

    case 'heading': {
      // Offset the SEMANTIC tag so chat messages never emit a page-level <h1>/<h2>
      // (each message could otherwise interleave real <h1>s with the app's own
      // heading outline). The visual size still maps to the markdown level via
      // headingStyle so a message's own heading hierarchy is preserved.
      const semanticLevel = Math.min(block.level + 2, 6)
      const Tag = `h${semanticLevel}` as 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6'
      return (
        <Tag key={key} style={headingStyle(block.level)}>
          {renderInline(block.text, key)}
        </Tag>
      )
    }

    case 'ul':
      return renderNestedList(block.items, 'ul', key)

    case 'ol':
      return renderNestedList(block.items, 'ol', key)

    case 'code':
      return <CodeBlock key={key} lang={block.lang} code={block.code} />

    case 'hr':
      return (
        <hr
          key={key}
          style={{ border: 'none', borderTop: '0.5px solid var(--hachi-line)', margin: '0.8em 0' }}
        />
      )

    case 'blockquote': {
      const bqContent: ReactNode[] = []
      block.lines.forEach((bql, bqi) => {
        if (bqi > 0) bqContent.push(<br key={`${key}-bqbr${bqi}`} />)
        renderInline(bql, `${key}-bq${bqi}`).forEach((n, ni) =>
          bqContent.push(<span key={`${key}-bq${bqi}-s${ni}`}>{n}</span>)
        )
      })
      return (
        <blockquote
          key={key}
          style={{
            margin: '0.4em 0',
            padding: '6px 12px',
            borderLeft: '2px solid var(--hachi-line)',
            color: 'var(--hachi-muted)',
          }}
        >
          {bqContent}
        </blockquote>
      )
    }

    case 'table':
      return (
        <div key={key} style={{ overflowX: 'auto', margin: '0.6em 0' }}>
          <table style={{ borderCollapse: 'collapse', fontSize: '13px', width: '100%' }}>
            <thead>
              <tr>
                {block.headers.map((h, hi) => (
                  <th
                    key={hi}
                    scope="col"
                    style={{
                      padding: '6px 10px', textAlign: 'left', fontWeight: 500,
                      borderBottom: '1px solid var(--hachi-line)',
                      color: 'var(--hachi-muted)', whiteSpace: 'nowrap',
                    }}
                  >
                    {renderInline(h, `${key}-th${hi}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row, ri) => (
                <tr key={ri}>
                  {row.map((cell, ci) => (
                    <td
                      key={ci}
                      style={{ padding: '5px 10px', borderBottom: '0.5px solid var(--hachi-line)' }}
                    >
                      {renderInline(cell, `${key}-td${ri}-${ci}`)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )

    case 'paragraph': {
      // Within a paragraph, individual lines are separated by <br> to preserve
      // single-newline breaks (equivalent to pre-wrap newlines).
      const content: ReactNode[] = []
      block.lines.forEach((line, li) => {
        if (li > 0) content.push(<br key={`${key}-br${li}`} />)
        const spans = renderInline(line, `${key}-ln${li}`)
        spans.forEach((s, si) => content.push(<span key={`${key}-ln${li}-s${si}`}>{s}</span>))
      })
      return (
        <p key={key} style={{ margin: '0.15em 0' }}>
          {content}
        </p>
      )
    }
  }
}

// ---- Public component -----------------------------------------------
//
// Wrapped in React.memo so that parent re-renders (e.g. store flushes that only
// change the streaming message) do NOT re-render completed message bubbles.
// parseBlocks is additionally memoized on `text` so re-parsing only happens when
// the text prop actually changes — not on every store flush that re-creates the
// parent component's subtree.

export const Markdown = memo(function Markdown({
  text,
  isStreaming,
}: {
  text: string
  isStreaming?: boolean
}): JSX.Element {
  // eslint-disable-next-line react-hooks/rules-of-hooks -- memo wrapper is a function component
  const blocks = useMemo(() => parseBlocks(text, { isStreaming }), [text, isStreaming])

  return (
    <div
      style={{
        // Inherit font, color, lineHeight from parent — no overrides needed.
        // whiteSpace is NOT set here; the block structure handles newlines.
        // min-height prevents the container collapsing to zero while text===''
        // then expanding on first token, which causes a layout shift (FIX 1).
        minHeight: '1.6em',
      }}
    >
      {blocks.map((block, i) => renderBlock(block, i))}
    </div>
  )
})
