import React, { CSSProperties } from 'react'

export type MascotState = 'on-watch' | 'working' | 'done' | 'blocked' | 'resting'

export interface HachiMascotProps {
  state: MascotState
  /** Cell size multiplier — each pixel = scale px. @default 3 */
  scale?: number
  /** Show decorative overlay: loyal-loop when working, floating "z" when resting. @default false */
  decor?: boolean
  /** Suppress all CSS animations (breathe, blink, loop, z-float). @default false */
  reduceMotion?: boolean
  style?: CSSProperties
}

/*
 * Base pixel grid (16 cols × 15 rows). Character legend:
 *   R = body (var(--hachi-brand))
 *   C = cream face/urajiro (#F3E9D2)
 *   E = eye/ink (#16151A, blinks when on-watch)
 *   N = nose/ink (#16151A, no blink)
 *   . = transparent
 *
 * Per-state morphs are applied after copying the base grid (matching HachiMascot.dc.html).
 */
const BASE_ROWS: readonly string[] = [
  '.RR..........RR.',
  'RRRR........RRRR',
  'RRCR........RCRR',
  'RRCRRRRRRRRRRCRR',
  'RRRRRRRRRRRRRRRR',
  'RRRRRRRRRRRRRRRR',
  'RRRCRRRRRRRRCRRR',
  'RRREERRRRRREERRR',
  'RRREERRRRRREERRR',
  'RRRRRRRRRRRRRRRR',
  'RRRRRCCCCCCRRRRR',
  'RRRCCCCCCCCCCRRR',
  'RRCCCCCNNCCCCCRR',
  'RRCCCCCNNCCCCCRR',
  'RRRCCCCCCCCCCRRR',
]

type NormKey = 'watch' | 'work' | 'done' | 'blocked' | 'rest'

function normState(state: MascotState): NormKey {
  switch (state) {
    case 'on-watch':
      return 'watch'
    case 'working':
      return 'work'
    case 'done':
      return 'done'
    case 'blocked':
      return 'blocked'
    case 'resting':
      return 'rest'
  }
}

/**
 * Apply per-state pixel mutations to a copy of the base grid.
 * Matches the `spriteRows()` logic in HachiMascot.dc.html exactly.
 */
function spriteRows(key: NormKey): string[] {
  const rows = BASE_ROWS.map((r) => r.split(''))

  const set = (row: number, cols: number[], ch: string) => {
    cols.forEach((c) => {
      rows[row][c] = ch
    })
  }

  const eye = [3, 4, 11, 12]

  if (key === 'done') {
    // Content squint: top row of eyes becomes cream, bottom remains ink
    set(7, eye, 'C')
    set(8, eye, 'E')
  } else if (key === 'rest') {
    // Closed line: both rows go transparent/cream, only bottom ink remains
    set(6, [3, 12], 'R')
    set(7, eye, 'R')
    set(8, eye, 'E')
  } else if (key === 'blocked') {
    // Ears back + furrow brow
    set(0, [1, 2, 13, 14], '.')
    set(1, [0, 3, 12, 15], '.')
    set(6, [4, 11], 'E')
  }

  return rows.map((r) => r.join(''))
}

/**
 * Compute inline style for a single pixel cell.
 * The `blink` flag attaches the hm-blink keyframe (on-watch eyes only).
 */
function cellStyle(ch: string, sz: number, blink: boolean): CSSProperties {
  switch (ch) {
    case 'R':
      return { width: sz, height: sz, background: 'var(--hachi-brand,#D64933)', flexShrink: 0 }
    case 'C':
      return { width: sz, height: sz, background: '#F3E9D2', flexShrink: 0 }
    case 'E':
      return {
        width: sz,
        height: sz,
        background: '#16151A',
        flexShrink: 0,
        ...(blink ? { animation: 'hm-blink 4.6s infinite' } : {}),
      }
    case 'N':
    case 'M':
      return { width: sz, height: sz, background: '#16151A', flexShrink: 0 }
    default:
      return { width: sz, height: sz, background: 'transparent', flexShrink: 0 }
  }
}

/**
 * Build a 2-D array of cell styles from a sprite row array.
 */
function buildGrid(
  rows: string[],
  sz: number,
  blink: boolean
): CSSProperties[][] {
  return rows.map((row) =>
    row.split('').map((ch) => cellStyle(ch, sz, blink))
  )
}

/**
 * HachiMascot — pixel-grid morphing sprite for all five Hachi states.
 *
 * States:
 *  - on-watch  : breathes slowly, eyes blink every ~4.6s
 *  - working   : fast breathe + loyal-loop amber figure-8 overlay (when decor=true)
 *  - done      : medium breathe, eyes squint (content)
 *  - blocked   : medium breathe, ears pulled back
 *  - resting   : very slow breathe, eyes closed, floating "z" (when decor=true)
 *
 * Body cells use var(--hachi-brand); face cells #F3E9D2 (cream); eyes #16151A (ink).
 * Ported faithfully from .design-bundle/project/HachiMascot.dc.html.
 */
export function HachiMascot({
  state,
  scale = 3,
  decor = false,
  reduceMotion = false,
  style,
}: HachiMascotProps) {
  const motion = !reduceMotion
  const sz = Math.max(1, Math.min(16, scale))
  const key = normState(state)
  const blink = key === 'watch' && motion

  const grid = buildGrid(spriteRows(key), sz, blink)

  // Breathe animation durations per state (matching the prototype)
  const breatheDur: Record<NormKey, string> = {
    work: '1.6s',
    watch: '3.6s',
    rest: '5.4s',
    done: '4s',
    blocked: '4s',
  }

  const wrapStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    ...(motion
      ? { animation: `hm-breathe ${breatheDur[key]} ease-in-out infinite` }
      : {}),
  }

  const spriteW = 16 * sz
  const spriteH = 15 * sz
  const showLoop = decor && key === 'work'
  const showZ = decor && key === 'rest'
  const padTop = showLoop ? Math.round(sz * 5) : 0
  const loopW = spriteW
  const loopH = Math.round(spriteW * 0.56)

  const loopAnimStyle: CSSProperties = motion
    ? { animation: 'hm-loop 2.6s linear infinite' }
    : { strokeDashoffset: -90 }

  const zStyle: CSSProperties = {
    position: 'absolute',
    top: 0,
    right: -Math.round(sz * 3),
    fontFamily: 'JetBrains Mono, monospace',
    fontSize: Math.round(sz * 4),
    lineHeight: 1,
    color: '#9C968C',
    ...(motion ? { animation: 'hm-zfloat 2.8s ease-in-out infinite' } : {}),
  }

  const boxStyle: CSSProperties = {
    position: 'relative',
    display: 'inline-flex',
    alignItems: 'flex-end',
    justifyContent: 'center',
    width: spriteW,
    height: spriteH + padTop,
    ...style,
  }

  return (
    <div style={boxStyle}>
      {/* Loyal-loop figure-8 overlay — shown when working + decor */}
      {showLoop && (
        <svg
          viewBox="0 0 100 56"
          width={loopW}
          height={loopH}
          style={{
            position: 'absolute',
            top: 0,
            left: '50%',
            transform: 'translateX(-50%)',
          }}
          aria-hidden="true"
        >
          <path
            d="M 39 28 C 39 16 23 16 23 28 C 23 40 39 40 49 28 C 59 16 75 16 75 28 C 75 40 59 40 49 28 Z"
            fill="none"
            stroke="#E0922E"
            strokeWidth={7}
            strokeLinecap="round"
            strokeDasharray="60 200"
            style={loopAnimStyle}
          />
        </svg>
      )}

      {/* Floating "z" — shown when resting + decor */}
      {showZ && (
        <span style={zStyle} aria-hidden="true">
          z
        </span>
      )}

      {/* Pixel sprite */}
      <div style={wrapStyle}>
        {grid.map((row, ri) => (
          <div key={ri} style={{ display: 'flex', lineHeight: 0 }}>
            {row.map((cellSt, ci) => (
              <div key={ci} style={cellSt} />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
