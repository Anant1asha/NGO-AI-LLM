import React, { useEffect, useMemo, useState, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { createFileRoute } from '@tanstack/react-router'
import { useStore } from '../lib/store/store'
import { Icon } from '../components/icons/Icon'
import type { OgNode } from '../lib/data/types'
import { loadOg } from '../lib/data/domains/og'
import { OgExplainer } from '../components/ui/OgExplainer'

const OG_WHY = 'LLM context is expensive. Loading 30-token index passes for 50 skill nodes costs ~1 500 tokens; loading full files would cost ~50 000+. The agent reads deeper (dense → full) only when it confirms a node is relevant.'

// ── palette constants ─────────────────────────────────────────────────────────
const OG_KIND_ICON: Record<string, string> = {
  root: 'brain',
  skill: 'network',
  leaf: 'file',
}

const OG_COLOR: Record<string, string> = {
  root: 'var(--hachi-trust)',
  skill: '#B5894E',
  leaf: '#8497B8',
}

// ── graph geometry ────────────────────────────────────────────────────────────
const GRAPH_W = 860
const GRAPH_H = 460
// Three columns: the focused node, its dependencies, and their dependencies.
const COL_X = [150, 430, 720]
// Cap nodes shown per tier so the focused view stays readable on large graphs.
const TIER_CAP = 16

function rOf(n: OgNode, maxFull: number): number {
  return 11 + (n.full / Math.max(1, maxFull)) * 15
}

interface FocusLayout {
  pos: Record<string, { x: number; y: number }>
  shown: OgNode[]
  edges: [string, string][]
}

/**
 * Focused dependency view (matches the OG Explorer design): the selected node
 * (default: a root) sits on the left, the nodes it depends on form the middle
 * column, and *their* dependencies form the right column — a clean three-tier,
 * left-to-right graph instead of dumping all N nodes at once. Click any node to
 * re-centre on it. A node with no dependencies instead shows the nodes that
 * depend on it, so selecting anything always reveals its neighbourhood.
 * Deterministic (no RNG); each tier is distributed evenly down its column.
 */
function computeFocusedLayout(nodes: OgNode[], centerId: string): FocusLayout {
  const byId = new Map(nodes.map((n) => [n.id, n]))
  let center = byId.get(centerId)
  if (!center) center = nodes.find((n) => n.kind === 'root') ?? nodes[0]
  if (!center) return { pos: {}, shown: [], edges: [] }
  const centerNode = center

  const depsOf = (id: string): string[] =>
    (byId.get(id)?.deps ?? []).filter((d) => byId.has(d) && d !== id)
  const parentsOf = (id: string): string[] =>
    nodes.filter((n) => n.id !== id && (n.deps ?? []).includes(id)).map((n) => n.id)
  const byFullDesc = (a: string, b: string) => (byId.get(b)?.full ?? 0) - (byId.get(a)?.full ?? 0)

  // Tier 1: the node's dependencies; if it has none (a leaf), the nodes that
  // depend on it — so the view is never just a lonely dot.
  let tier1 = depsOf(centerNode.id)
  if (tier1.length === 0) tier1 = parentsOf(centerNode.id)
  tier1 = [...new Set(tier1)].sort(byFullDesc).slice(0, TIER_CAP)

  // Tier 2: dependencies of the tier-1 nodes (excluding the centre + tier 1).
  const seen = new Set<string>([centerNode.id, ...tier1])
  const tier2: string[] = []
  for (const t1 of tier1) {
    for (const d of depsOf(t1)) {
      if (!seen.has(d)) {
        seen.add(d)
        tier2.push(d)
      }
    }
  }
  const tier2Capped = [...new Set(tier2)].sort(byFullDesc).slice(0, TIER_CAP)

  const columns = [[centerNode.id], tier1, tier2Capped]
  const pos: Record<string, { x: number; y: number }> = {}
  columns.forEach((col, ci) => {
    const gap = GRAPH_H / (col.length + 1)
    col.forEach((id, i) => {
      pos[id] = { x: COL_X[ci], y: gap * (i + 1) }
    })
  })

  const shownIds = new Set<string>([centerNode.id, ...tier1, ...tier2Capped])
  const edges: [string, string][] = []
  for (const id of shownIds) {
    for (const d of depsOf(id)) {
      if (shownIds.has(d)) edges.push([id, d])
    }
  }
  const shown = [...shownIds]
    .map((id) => byId.get(id))
    .filter((n): n is OgNode => n != null)
  return { pos, shown, edges }
}

// ── sub-components ────────────────────────────────────────────────────────────

interface StatCardProps {
  icon: string
  label: string
  value: string | number
  valueColor?: string
}

function StatCard({ icon, label, value, valueColor }: StatCardProps) {
  return (
    <div
      style={{
        background: 'var(--hachi-surface)',
        border: '0.5px solid var(--hachi-line)',
        borderRadius: 14,
        padding: 15,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 7,
          fontSize: 12,
          color: 'var(--hachi-muted)',
          marginBottom: 9,
        }}
      >
        <Icon name={icon} size={14} />
        {label}
      </div>
      <div
        style={{
          fontFamily: 'var(--font-display)',
          fontWeight: 500,
          fontSize: 24,
          fontVariantNumeric: 'tabular-nums',
          color: valueColor ?? 'var(--hachi-ink)',
        }}
      >
        {value}
      </div>
    </div>
  )
}

// ── graph SVG ─────────────────────────────────────────────────────────────────
interface GraphPanelProps {
  nodes: OgNode[]
  ogSel: string
  ogHover: string | null
  setOgSel: (id: string) => void
  setOgHover: (id: string | null) => void
}

function GraphPanel({ nodes, ogSel, ogHover, setOgSel, setOgHover }: GraphPanelProps) {
  // clamp to 1 so rOf never divides by zero (avoids NaN radius when all full===0)
  const maxFull = Math.max(1, ...nodes.map((n) => n.full))

  // Focused three-tier layout around the selected node; re-centres when the
  // selection changes (click a node to focus on it), but not on hover.
  const { pos, shown, edges } = useMemo(
    () => computeFocusedLayout(nodes, ogSel),
    [nodes, ogSel],
  )

  const nodeById = (id: string) =>
    shown.find((n) => n.id === id) ?? nodes.find((n) => n.id === id)

  // ordered flat list (left-to-right, then top-down) for arrow-key navigation
  const orderedIds = shown
    .slice()
    .sort(
      (a, b) =>
        (pos[a.id]?.x ?? 0) - (pos[b.id]?.x ?? 0) ||
        (pos[a.id]?.y ?? 0) - (pos[b.id]?.y ?? 0),
    )
    .map((n) => n.id)

  const active = ogHover ?? ogSel

  const isLit = (id: string): boolean => {
    if (!ogHover && !ogSel) return true
    return (
      id === active ||
      edges.some(([a, b]) => (a === active && b === id) || (b === active && a === id))
    )
  }

  function handleNodeKeyDown(e: React.KeyboardEvent, nodeId: string) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      setOgSel(nodeId)
      return
    }
    const idx = orderedIds.indexOf(nodeId)
    if (idx === -1) return  // node not in the ordered list (unknown kind) — bail
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault()
      const next = orderedIds[idx + 1]
      if (next) {
        setOgSel(next)
        // move focus to the next node's <g> via the SVG foreignObject workaround
        const svgEl = (e.currentTarget as SVGElement).closest('svg')
        if (svgEl) {
          const gEls = svgEl.querySelectorAll<SVGGElement>('g[tabindex="0"]')
          const nextEl = Array.from(gEls).find(
            (g) => g.getAttribute('data-id') === next
          )
          nextEl?.focus()
        }
      }
    }
    if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault()
      const prev = orderedIds[idx - 1]
      if (prev) {
        setOgSel(prev)
        const svgEl = (e.currentTarget as SVGElement).closest('svg')
        if (svgEl) {
          const gEls = svgEl.querySelectorAll<SVGGElement>('g[tabindex="0"]')
          const prevEl = Array.from(gEls).find(
            (g) => g.getAttribute('data-id') === prev
          )
          prevEl?.focus()
        }
      }
    }
  }

  return (
    <div style={{ padding: '8px 8px 0' }}>
      <svg
        viewBox="0 0 860 460"
        style={{ width: '100%', height: 'auto', display: 'block' }}
        aria-label="ObjectGraph dependency diagram"
        role="img"
      >
        <defs>
          <marker
            id="ogarrow"
            markerWidth={7}
            markerHeight={7}
            refX={6}
            refY={3.5}
            orient="auto"
          >
            <path d="M0 0 L7 3.5 L0 7 z" fill="var(--hachi-line)" />
          </marker>
          <marker
            id="ogarrowOn"
            markerWidth={7.5}
            markerHeight={7.5}
            refX={6}
            refY={3.5}
            orient="auto"
          >
            <path d="M0 0 L7 3.5 L0 7 z" fill="var(--hachi-trust)" />
          </marker>
        </defs>

        {/* edges */}
        {edges.map(([a, b], i) => {
          const pa = pos[a]
          const pb = pos[b]
          const na = nodeById(a)
          const nb = nodeById(b)
          if (!pa || !pb || !na || !nb) return null
          const ra = rOf(na, maxFull)
          const rb = rOf(nb, maxFull)
          const x1 = pa.x + ra
          const x2 = pb.x - rb
          const mx = (x1 + x2) / 2
          const act = active && (a === active || b === active)
          const d = `M ${x1} ${pa.y} C ${mx} ${pa.y}, ${mx} ${pb.y}, ${x2} ${pb.y}`
          return (
            <path
              key={'e' + i}
              d={d}
              fill="none"
              stroke={act ? 'var(--hachi-trust)' : 'var(--hachi-line)'}
              strokeWidth={act ? 2.2 : 1.3}
              opacity={active && !act ? 0.22 : 0.9}
              strokeLinecap="round"
              strokeDasharray={act ? '5 4' : '0'}
              markerEnd={act ? 'url(#ogarrowOn)' : 'url(#ogarrow)'}
              style={act ? { animation: 'ogflow .7s linear infinite' } : undefined}
            />
          )
        })}

        {/* nodes */}
        {shown.map((n) => {
          const p = pos[n.id]
          if (!p) return null
          const r = rOf(n, maxFull)
          const sel = ogSel === n.id
          const lit = isLit(n.id)
          const color = OG_COLOR[n.kind] ?? 'var(--hachi-muted)'
          const nameY = p.y + r + 13

          return (
            <g
              key={n.id}
              data-id={n.id}
              tabIndex={0}
              role="button"
              aria-label={`${n.name} (${n.kind}) — index ${n.index} tokens, full ${n.full} tokens${sel ? ', selected' : ''}`}
              aria-pressed={sel}
              style={{ cursor: 'pointer', outline: 'none' }}
              onClick={() => setOgSel(n.id)}
              onMouseEnter={() => setOgHover(n.id)}
              onMouseLeave={() => setOgHover(null)}
              onFocus={() => setOgHover(n.id)}
              onBlur={() => setOgHover(null)}
              onKeyDown={(e) => handleNodeKeyDown(e, n.id)}
            >
              {/* focus ring — visible when keyboard-focused */}
              <circle
                cx={p.x}
                cy={p.y}
                r={r + 9}
                fill="none"
                stroke="var(--hachi-brand)"
                strokeWidth={2}
                opacity={0}
                className="og-focus-ring"
                style={{ pointerEvents: 'none' }}
              />
              {/* selection glow ring */}
              <circle
                cx={p.x}
                cy={p.y}
                r={r + 6}
                fill={color}
                opacity={sel ? 0.18 : 0}
              />
              {/* node circle */}
              <circle
                cx={p.x}
                cy={p.y}
                r={r}
                fill="var(--hachi-surface)"
                stroke={color}
                strokeWidth={sel ? 2.5 : 1.6}
                opacity={lit ? 1 : 0.35}
                style={
                  sel
                    ? { filter: `drop-shadow(0 0 7px ${color})` }
                    : undefined
                }
              />
              {/* index token count */}
              <text
                x={p.x}
                y={p.y + 4}
                textAnchor="middle"
                fontSize={11}
                fontWeight={500}
                fill={color}
                opacity={lit ? 1 : 0.4}
                style={{ fontFamily: 'var(--font-mono)', pointerEvents: 'none' }}
                aria-hidden="true"
              >
                {n.index}
              </text>
              {/* WCAG 1.4.1 — node kind is currently color-only (amber/slate/navy);
                  this small badge repeats it as a shape so it doesn't rely on hue alone. */}
              <g
                transform={`translate(${p.x + r * 0.5}, ${p.y - r * 0.5 - 6})`}
                style={{ pointerEvents: 'none' }}
                opacity={lit ? 1 : 0.4}
                aria-hidden="true"
              >
                <circle r={7} fill="var(--hachi-surface)" stroke={color} strokeWidth={1} />
                <g transform="translate(-5, -5)">
                  <Icon name={OG_KIND_ICON[n.kind] ?? 'file'} size={10} style={{ color }} />
                </g>
              </g>
              {/* label below node */}
              <text
                x={p.x}
                y={nameY}
                textAnchor="middle"
                fontSize={13}
                fill="var(--hachi-ink)"
                opacity={lit ? 1 : 0.4}
                style={{ fontFamily: 'var(--font-body)', pointerEvents: 'none' }}
                aria-hidden="true"
              >
                {n.name.replace('.og', '')}
              </text>
            </g>
          )
        })}
      </svg>

      {/* legend */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          padding: '10px 10px 12px',
          fontSize: 11.5,
          color: 'var(--hachi-muted)',
        }}
      >
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <span
            style={{
              width: 9,
              height: 9,
              borderRadius: '50%',
              background: 'var(--hachi-trust)',
              display: 'inline-block',
            }}
          />
          root (brain)
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <span
            style={{
              width: 9,
              height: 9,
              borderRadius: '50%',
              background: '#B5894E',
              display: 'inline-block',
            }}
          />
          skill
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <span
            style={{
              width: 9,
              height: 9,
              borderRadius: '50%',
              background: '#8497B8',
              display: 'inline-block',
            }}
          />
          leaf
        </span>
        <span style={{ marginLeft: 'auto' }}>label = index-pass tokens · size = full size</span>
      </div>
    </div>
  )
}

// ── tree view ─────────────────────────────────────────────────────────────────
interface TreePanelProps {
  nodes: OgNode[]
  ogSel: string
  setOgSel: (id: string) => void
}

function TreePanel({ nodes, ogSel, setOgSel }: TreePanelProps) {
  const depthOf = (kind: string) =>
    kind === 'root' ? 0 : kind === 'skill' ? 1 : 2

  return (
    <div style={{ padding: 12 }}>
      {nodes.map((n) => {
        const isSel = ogSel === n.id

        return (
          <div
            key={n.id}
            className="hachi-og-tree-row"
            role="button"
            tabIndex={0}
            aria-current={isSel ? 'true' : undefined}
            onClick={() => setOgSel(n.id)}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setOgSel(n.id); } }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              marginLeft: depthOf(n.kind) * 16,
              padding: '8px 14px',
              cursor: 'pointer',
              borderRadius: 8,
              background: isSel ? 'var(--hachi-cream)' : undefined,
              transition: 'background var(--dur-fast) var(--ease)',
            }}
          >
            <span
              style={{ color: 'var(--hachi-muted)', display: 'inline-flex' }}
            >
              <Icon name={OG_KIND_ICON[n.kind] ?? 'file'} size={13} />
            </span>
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 12.5,
                flex: 1,
              }}
            >
              {n.name}
            </span>
            <span style={{ fontSize: 12, color: 'var(--hachi-muted)' }}>
              {n.full}t
            </span>
          </div>
        )
      })}
    </div>
  )
}

// ── detail panel ──────────────────────────────────────────────────────────────
interface DetailPanelProps {
  dn: OgNode
  nodes: OgNode[]
  setOgSel: (id: string) => void
}

function DetailPanel({ dn, nodes, setOgSel }: DetailPanelProps) {
  const savedPct = Math.round((1 - dn.index / dn.full) * 100)
  const barWidth = Math.round((dn.index / dn.full) * 100)

  const nodeById = (id: string) => nodes.find((n) => n.id === id)

  const deps = (dn.deps ?? [])
    .map((d) => nodeById(d))
    .filter((d): d is OgNode => Boolean(d))

  const usedBy = nodes.filter((n) => (n.deps ?? []).includes(dn.id))

  const kindColor = OG_COLOR[dn.kind] ?? 'var(--hachi-muted)'
  const kindIcon = OG_KIND_ICON[dn.kind] ?? 'file'

  return (
    <>
      {/* three-pass card */}
      <div
        style={{
          background: 'var(--hachi-surface)',
          border: '0.5px solid var(--hachi-line)',
          borderRadius: 16,
          padding: 18,
        }}
      >
        {/* header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            marginBottom: 16,
          }}
        >
          <span
            style={{ color: 'var(--hachi-muted)', display: 'inline-flex' }}
          >
            <Icon name={kindIcon} size={16} />
          </span>
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontWeight: 500,
              fontSize: 14,
              flex: 1,
            }}
          >
            {dn.name}
          </span>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '4px 10px',
              borderRadius: 999,
              background: 'var(--hachi-cream)',
              color: kindColor,
              fontSize: 12,
              fontWeight: 500,
            }}
          >
            <span
              style={{
                width: 7,
                height: 7,
                borderRadius: '50%',
                background: kindColor,
                display: 'inline-block',
              }}
            />
            {dn.kind}
          </span>
        </div>

        <div
          style={{
            fontSize: 13,
            color: 'var(--hachi-muted)',
            marginBottom: 12,
          }}
        >
          Three-pass read
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
          {/* pass 1 — index */}
          <div
            style={{
              border: '0.5px solid var(--hachi-brand)',
              borderRadius: 10,
              padding: '12px 13px',
              background: 'var(--hachi-brand-tint)',
            }}
          >
            <div
              style={{
                fontSize: 12,
                color: 'var(--hachi-muted)',
                marginBottom: 3,
              }}
            >
              1 · Index
            </div>
            <div
              style={{
                fontFamily: 'var(--font-display)',
                fontWeight: 500,
                fontSize: 21,
                color: 'var(--hachi-brand)',
              }}
            >
              {dn.index}
              <span
                style={{
                  fontSize: 12,
                  color: 'var(--hachi-muted)',
                  fontWeight: 400,
                }}
              >
                {' '}
                tok
              </span>
            </div>
            <div
              style={{
                fontSize: 12.5,
                color: 'var(--hachi-muted)',
                marginTop: 4,
              }}
            >
              Signature + summary. Loaded first, for routing.
            </div>
          </div>

          {/* pass 2 — dense */}
          <div
            style={{
              border: '0.5px solid var(--hachi-line)',
              borderRadius: 10,
              padding: '12px 13px',
              background: 'var(--hachi-canvas)',
            }}
          >
            <div
              style={{
                fontSize: 12,
                color: 'var(--hachi-muted)',
                marginBottom: 3,
              }}
            >
              2 · Dense
            </div>
            <div
              style={{
                fontFamily: 'var(--font-display)',
                fontWeight: 500,
                fontSize: 21,
                color: 'var(--hachi-working)',
              }}
            >
              {dn.dense}
              <span
                style={{
                  fontSize: 12,
                  color: 'var(--hachi-muted)',
                  fontWeight: 400,
                }}
              >
                {' '}
                tok
              </span>
            </div>
            <div
              style={{
                fontSize: 12.5,
                color: 'var(--hachi-muted)',
                marginTop: 4,
              }}
            >
              Compressed body. Loaded when the node is selected.
            </div>
          </div>

          {/* pass 3 — full */}
          <div
            style={{
              border: '0.5px solid var(--hachi-line)',
              borderRadius: 10,
              padding: '12px 13px',
              background: 'var(--hachi-canvas)',
            }}
          >
            <div
              style={{
                fontSize: 12,
                color: 'var(--hachi-muted)',
                marginBottom: 3,
              }}
            >
              3 · Full
            </div>
            <div
              style={{
                fontFamily: 'var(--font-display)',
                fontWeight: 500,
                fontSize: 21,
                color: 'var(--hachi-ink)',
              }}
            >
              {dn.full}
              <span
                style={{
                  fontSize: 12,
                  color: 'var(--hachi-muted)',
                  fontWeight: 400,
                }}
              >
                {' '}
                tok
              </span>
            </div>
            <div
              style={{
                fontSize: 12.5,
                color: 'var(--hachi-muted)',
                marginTop: 4,
              }}
            >
              Complete source. Loaded only if the task drills in.
            </div>
          </div>
        </div>

        {/* savings bar */}
        <div style={{ marginTop: 18 }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: 12,
              marginBottom: 7,
            }}
          >
            <span style={{ color: 'var(--hachi-muted)' }}>
              Index-pass vs the whole node
            </span>
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                color: 'var(--hachi-success)',
              }}
            >
              {'−'}{savedPct}% tokens
            </span>
          </div>
          <div
            style={{
              position: 'relative',
              height: 30,
              borderRadius: 6,
              background: 'var(--hachi-line)',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                position: 'absolute',
                inset: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-end',
                paddingRight: 10,
              }}
            >
              <span
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 11,
                  color: 'var(--hachi-muted)',
                }}
              >
                vs full: {dn.full} tok
              </span>
            </div>
            <div
              style={{
                width: `${barWidth}%`,
                height: '100%',
                background: 'var(--hachi-brand)',
                display: 'grid',
                placeItems: 'center',
                minWidth: 52,
              }}
            >
              <span
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 11,
                  color: 'var(--hachi-canvas)',
                  fontWeight: 500,
                }}
              >
                {dn.index}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* connections card */}
      <div
        style={{
          background: 'var(--hachi-surface)',
          border: '0.5px solid var(--hachi-line)',
          borderRadius: 16,
          padding: 18,
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            marginBottom: 14,
          }}
        >
          <span
            style={{ color: 'var(--hachi-muted)', display: 'inline-flex' }}
          >
            <Icon name="network" size={16} />
          </span>
          <span style={{ fontWeight: 500, fontSize: 14 }}>Connections</span>
        </div>

        <div
          style={{
            fontSize: 12,
            color: 'var(--hachi-muted)',
            marginBottom: 9,
          }}
        >
          Depends on
        </div>

        {deps.length > 0 ? (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {deps.map((d) => (
              <button
                key={d.id}
                className="hachi-og-chip"
                onClick={() => setOgSel(d.id)}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 7,
                  height: 30,
                  padding: '0 11px',
                  borderRadius: 8,
                  border: '0.5px solid var(--hachi-line)',
                  background: 'var(--hachi-canvas)',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 12,
                  color: 'var(--hachi-ink)',
                  cursor: 'pointer',
                  transition: 'background var(--dur-fast) var(--ease)',
                }}
              >
                <Icon name="network" size={12} />
                {d.name}{' '}
                <span style={{ color: 'var(--hachi-muted)' }}>{d.index}t</span>
              </button>
            ))}
          </div>
        ) : (
          <div style={{ fontSize: 13, color: 'var(--hachi-muted)' }}>
            Leaf node — no dependencies. Cheapest to load.
          </div>
        )}

        {usedBy.length > 0 && (
          <>
            <div
              style={{
                fontSize: 12,
                color: 'var(--hachi-muted)',
                margin: '14px 0 9px',
              }}
            >
              Used by
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {usedBy.map((u) => (
                <button
                  key={u.id}
                  className="hachi-og-chip"
                  onClick={() => setOgSel(u.id)}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 7,
                    height: 30,
                    padding: '0 11px',
                    borderRadius: 8,
                    border: '0.5px solid var(--hachi-line)',
                    background: 'var(--hachi-canvas)',
                    fontFamily: 'var(--font-mono)',
                    fontSize: 12,
                    color: 'var(--hachi-ink)',
                    cursor: 'pointer',
                    transition: 'background var(--dur-fast) var(--ease)',
                  }}
                >
                  <Icon name="network" size={12} />
                  {u.name}
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </>
  )
}

// ── main screen component ─────────────────────────────────────────────────────
function OgExplorer() {
  const ogNodes = useStore((s) => s.ogNodes)
  const ogSel = useStore((s) => s.ogSel)
  const ogView = useStore((s) => s.ogView)
  const setOgSel = useStore((s) => s.setOgSel)
  const setOgView = useStore((s) => s.setOgView)
  // HACHI-016: distinguish disconnected vs. connected-but-empty skill index
  const reconnecting = useStore((s) => s.reconnecting)

  // fetch live data on mount (idempotent; bootstrapLiveData also fires on app mount)
  useEffect(() => { void loadOg() }, [])

  // Default the focused graph to the most useful starting node once skills load.
  // Real skill graphs are sparse and often have no single root, so prefer a root
  // node if one exists, else centre on the most-connected node for a meaningful
  // (non-empty) neighbourhood instead of an isolated dot.
  useEffect(() => {
    if (ogNodes.length > 0 && !ogNodes.some((n) => n.id === ogSel)) {
      const conn = new Map(ogNodes.map((n) => [n.id, n.deps?.length ?? 0]))
      ogNodes.forEach((n) =>
        (n.deps ?? []).forEach((d) => conn.set(d, (conn.get(d) ?? 0) + 1)),
      )
      const start =
        ogNodes.find((n) => n.kind === 'root') ??
        [...ogNodes].sort((a, b) => (conn.get(b.id) ?? 0) - (conn.get(a.id) ?? 0))[0]
      if (start) setOgSel(start.id)
    }
  }, [ogSel, ogNodes, setOgSel])

  // hover is screen-local (store.setOgHover is a no-op shim per contract)
  const [ogHover, setOgHover] = useState<string | null>(null)

  // computed stats
  const totalFull = ogNodes.reduce((a, n) => a + n.full, 0)
  const totalIndex = ogNodes.reduce((a, n) => a + n.index, 0)
  const ogStats = {
    nodes: ogNodes.length,
    fullK: (totalFull / 1000).toFixed(1) + 'K',
    indexCost: totalIndex,
    // guard against NaN when ogNodes is empty (totalFull === 0)
    avoidedPct:
      totalFull > 0
        ? Math.round((1 - totalIndex / totalFull) * 100) + '%'
        : '0%',
  }

  // selected node (fallback to first)
  const dn = ogNodes.find((n) => n.id === ogSel) ?? ogNodes[0]

  const isGraph = ogView === 'graph'
  const isTree = ogView === 'tree'

  const tabBtnStyle = (active: boolean): React.CSSProperties => ({
    height: 28,
    padding: '0 13px',
    border: 'none',
    borderRadius: 6,
    font: '500 12px var(--font-body)',
    cursor: 'pointer',
    background: active ? 'var(--hachi-surface)' : 'transparent',
    color: active ? 'var(--hachi-ink)' : 'var(--hachi-muted)',
    transition: 'background var(--dur-fast) var(--ease)',
  })

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
      }}
    >
      {/* header */}
      <div
        className="hachi-og-header"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          padding: '0 32px',
          height: 68,
          flexShrink: 0,
          borderBottom: '0.5px solid var(--hachi-line)',
        }}
      >
        <h1
          style={{
            margin: 0,
            fontFamily: 'var(--font-display)',
            fontWeight: 500,
            fontSize: 22,
            lineHeight: '26px',
          }}
        >
          OG explorer
        </h1>
        <span
          style={{ fontSize: 13, color: 'var(--hachi-muted)' }}
        >
          how Hachi reads only what a task needs
        </span>
      </div>

      {/* scrollable body */}
      <div
        className="hachi-scroll hachi-og-body"
        style={{ flex: 1, overflow: 'auto', padding: '24px 32px 64px' }}
      >
        <div
          style={{
            maxWidth: 1080,
            margin: '0 auto',
            display: 'flex',
            flexDirection: 'column',
            gap: 18,
          }}
        >
          {/* .og explainer banner */}
          <OgExplainer
            headline=".og three-pass reading"
            body="loads only the index (~30 tokens) on first pass, so Hachi avoids paying for full skill files on every turn."
            whyTooltip={OG_WHY}
          />

          {/* description */}
          <div
            style={{
              fontSize: 14,
              color: 'var(--hachi-muted)',
              lineHeight: '22px',
              maxWidth: 760,
            }}
          >
            The .og library is an object graph, read in three passes — index, then
            dense, then full — so Hachi loads only what a task needs instead of
            whole files.
          </div>

          {/* stat cards */}
          <div
            className="hachi-og-stat-grid"
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(4, 1fr)',
              gap: 12,
            }}
          >
            <StatCard
              icon="network"
              label="Nodes"
              value={ogStats.nodes}
            />
            <StatCard
              icon="hash"
              label="If fully loaded"
              value={ogStats.fullK}
            />
            <StatCard
              icon="zap"
              label="Index-pass cost"
              value={ogStats.indexCost}
              valueColor="var(--hachi-trust)"
            />
            <StatCard
              icon="sparkles"
              label="Tokens avoided"
              value={ogStats.avoidedPct}
              valueColor="var(--hachi-success)"
            />
          </div>

          {/* main two-column area */}
          <div
            className="hachi-og-panels"
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 16,
              alignItems: 'start',
            }}
          >
            {/* left: graph / tree panel */}
            <div
              style={{
                flex: '1 1 440px',
                minWidth: 0,
                background: 'var(--hachi-surface)',
                border: '0.5px solid var(--hachi-line)',
                borderRadius: 16,
                overflow: 'hidden',
              }}
            >
              {/* panel header */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '14px 16px',
                  borderBottom: '0.5px solid var(--hachi-line)',
                }}
              >
                <span
                  style={{
                    color: 'var(--hachi-muted)',
                    display: 'inline-flex',
                  }}
                >
                  <Icon name="network" size={16} />
                </span>
                <span
                  style={{ fontWeight: 500, fontSize: 14, flex: 1 }}
                >
                  Object graph
                </span>
                {/* view toggle */}
                <div
                  style={{
                    display: 'inline-flex',
                    background: 'var(--hachi-cream)',
                    borderRadius: 8,
                    padding: 2,
                  }}
                >
                  <button
                    onClick={() => setOgView('graph')}
                    style={tabBtnStyle(isGraph)}
                  >
                    Graph
                  </button>
                  <button
                    onClick={() => setOgView('tree')}
                    style={tabBtnStyle(isTree)}
                  >
                    Tree
                  </button>
                </div>
              </div>

              {/* HACHI-016: branch empty state copy — disconnected vs. connected-but-empty index */}
              {ogNodes.length === 0 ? (
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 10,
                    padding: '56px 32px',
                    color: 'var(--hachi-muted)',
                    textAlign: 'center',
                  }}
                >
                  <span style={{ opacity: 0.4 }}>
                    <Icon name="network" size={32} />
                  </span>
                  {reconnecting ? (
                    <>
                      <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--hachi-ink)' }}>
                        Not connected
                      </div>
                      <div style={{ fontSize: 13, maxWidth: 320, lineHeight: '20px' }}>
                        Connect to a running Hachi gateway — the .og graph will
                        populate once the gateway is reachable.
                      </div>
                    </>
                  ) : (
                    <>
                      <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--hachi-ink)' }}>
                        Skill index is empty
                      </div>
                      <div style={{ fontSize: 13, maxWidth: 320, lineHeight: '20px' }}>
                        The gateway is connected but no .og skills have been indexed yet.
                        Run a task or trigger a skill index build to populate the graph.
                      </div>
                    </>
                  )}
                </div>
              ) : (
                <>
                  {/* graph view */}
                  {isGraph && (
                    <GraphPanel
                      nodes={ogNodes}
                      ogSel={ogSel}
                      ogHover={ogHover}
                      setOgSel={setOgSel}
                      setOgHover={setOgHover}
                    />
                  )}

                  {/* tree view */}
                  {isTree && (
                    <TreePanel
                      nodes={ogNodes}
                      ogSel={ogSel}
                      setOgSel={setOgSel}
                    />
                  )}
                </>
              )}
            </div>

            {/* right: detail panels */}
            {dn && (
              <div
                style={{
                  flex: '1 1 320px',
                  minWidth: 0,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 16,
                }}
              >
                <DetailPanel
                  dn={dn}
                  nodes={ogNodes}
                  setOgSel={setOgSel}
                />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── route export (TanStack Router file-based) ─────────────────────────────────
export const Route = createFileRoute('/og')({
  component: OgExplorer,
})
