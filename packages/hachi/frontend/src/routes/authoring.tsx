import React, { useEffect, useState } from 'react'
import { OgExplainer } from '../components/ui/OgExplainer'
import { createFileRoute } from '@tanstack/react-router'
import { useStore } from '../lib/store/store'
import { Icon } from '../components/icons/Icon'
import type { AuthTarget, DiffLine } from '../lib/data/types'
import {
  loadAuthoring,
  loadAuthoringSource,
  applyAuthoring,
  revertAuthoring,
  generateAuthoring,
  saveAuthoringSource,
} from '../lib/data/domains/authoring'

// ---- syntax-highlight tokeniser (ported from prototype _ogTokens) ----
interface TokenPart {
  text: string
  color: string
}

function tokenise(line: string): TokenPart[] {
  const parts: TokenPart[] = []
  const re =
    /("[^"]*"|@\w+|\b(?:node|pass|tools|budget|strategy|cite|required|max_subagents)\b)/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(line)) !== null) {
    if (m.index > last) {
      parts.push({ text: line.slice(last, m.index), color: 'var(--hachi-ink)' })
    }
    const tok = m[0]
    let color = 'var(--hachi-trust)'
    if (tok[0] === '"') color = 'var(--hachi-success-fg)'
    else if (tok[0] === '@') color = 'var(--hachi-muted)'
    parts.push({ text: tok, color })
    last = m.index + tok.length
  }
  if (last < line.length) {
    parts.push({ text: line.slice(last), color: 'var(--hachi-ink)' })
  }
  if (parts.length === 0) {
    parts.push({ text: line || ' ', color: 'var(--hachi-ink)' })
  }
  return parts
}

// ---- diff-line row colours ----
function diffRowStyle(type: '' | 'add' | 'del', isDiff: boolean) {
  if (isDiff && type === 'add') {
    return {
      bg: 'rgba(63,157,107,0.18)',
      gutColor: 'var(--hachi-success-fg)',
      barColor: 'var(--hachi-success)',
    }
  }
  if (isDiff && type === 'del') {
    return {
      bg: 'rgba(192,57,43,0.18)',
      gutColor: 'var(--hachi-danger-fg)',
      barColor: 'var(--hachi-danger)',
    }
  }
  return { bg: 'transparent', gutColor: 'var(--hachi-muted)', barColor: 'transparent' }
}

const AUTH_KIND_ICON: Record<AuthTarget['kind'], string> = {
  brain: 'brain',
  config: 'settings',
  skill: 'file-code',
}

const AUTHORING_WHY = 'Pass 1 reads only the index (~30 tokens) to route to the right node. Pass 2 reads dense summaries. Pass 3 reads full content only when truly needed — most queries never reach it.'

// ---- Authoring screen ----
function Authoring() {
  const authTargets = useStore((s) => s.authTargets)
  const authSource = useStore((s) => s.authSource)
  const authSel = useStore((s) => s.authSel)
  const authMode = useStore((s) => s.authMode)
  const authAppliedTarget = useStore((s) => s.authAppliedTarget)
  const authApplied = authAppliedTarget === authSel

  const selectAuthTarget = useStore((s) => s.selectAuthTarget)
  const setAuthMode = useStore((s) => s.setAuthMode)
  const rejectPatch = useStore((s) => s.rejectPatch)

  // Load targets list on mount (and refresh on navigate).
  // HACHI-019: after targets arrive, if the current authSel is not in the live set,
  // switch to the first live target (or clear) so we never auto-fetch a phantom target.
  useEffect(() => {
    void loadAuthoring().then(() => {
      const targets = useStore.getState().authTargets
      if (targets.length === 0) return
      const currentSel = useStore.getState().authSel
      const inLiveSet = targets.some((t) => t.name === currentSel)
      if (!inLiveSet) {
        selectAuthTarget(targets[0].name)
      }
    })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // When the selected target changes, fetch its source.
  // HACHI-019: guard — only fetch when authSel is in the live targets set.
  // Surface any fetch error inline instead of silently swallowing it.
  useEffect(() => {
    if (!authSel) return
    setSourceFetchError(null)
    // If targets have loaded and this sel is not in the live set, skip the fetch.
    if (authTargets.length > 0 && !authTargets.some((t) => t.name === authSel)) {
      return
    }
    void loadAuthoringSource(authSel).then((result) => {
      if (result.fetchError) {
        setSourceFetchError(result.fetchError)
      }
    })
  }, [authSel, authTargets])

  // LOCAL: prompt input (LOW-002) and generated diff state (CRIT-002)
  const [prompt, setPrompt] = useState('')
  const [generatedDiff, setGeneratedDiff] = useState<DiffLine[] | null>(null)
  const [generateError, setGenerateError] = useState<string | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)

  // HACHI-019: inline source-fetch error (surfaces 400 / not-found errors instead of swallowing them)
  const [sourceFetchError, setSourceFetchError] = useState<string | null>(null)

  // Reset prompt and stale patch when the selected target changes (LOW-002).
  // Clearing generatedDiff prevents a prior target's diff from appearing under
  // the new target's name and being accidentally applied.
  useEffect(() => {
    setPrompt('')
    setGeneratedDiff(null)
    setGenerateError(null)
    setSourceFetchError(null)
  }, [authSel])



  // Handle Generate button click (CRIT-002)
  async function handleGenerate() {
    if (!authSel || !prompt.trim() || isGenerating) return
    setIsGenerating(true)
    setGenerateError(null)
    setGeneratedDiff(null)
    const result = await generateAuthoring(authSel, prompt.trim())
    setIsGenerating(false)
    if (result.error) {
      setGenerateError(result.error)
    } else {
      setGeneratedDiff(result.diff)
    }
  }

  // Compute visible diff lines:
  // If a generated diff exists, show it; otherwise fall back to authSource (LOW-003 / CRIT-002)
  const activeDiff: DiffLine[] = generatedDiff !== null ? generatedDiff : authSource
  const isDiff = authMode === 'diff'
  const visibleLines: DiffLine[] = activeDiff.filter(
    (l) => !(authMode === 'source' && l[0] === 'del')
  )

  // Derive diff summary counts from the active diff (LOW-003)
  const addCount = activeDiff.filter((l) => l[0] === 'add').length
  const delCount = activeDiff.filter((l) => l[0] === 'del').length
  const hasDiff = addCount > 0 || delCount > 0

  // Edit mode state (Step 3 — CONTRACT-AUTHORING-SAVE)
  const [editMode, setEditMode] = useState(false)
  const [editContent, setEditContent] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  // Derive plain-text source from authSource for the editor seed.
  // authSource holds DiffLine[] (neutral "" rows when not in diff state).
  const plainSource = authSource.map((l) => l[1]).join('\n')

  function enterEditMode() {
    setEditContent(plainSource)
    setSaveError(null)
    setEditMode(true)
  }

  function cancelEditMode() {
    setEditMode(false)
    setSaveError(null)
  }

  async function handleSave() {
    if (!authSel || isSaving) return
    setIsSaving(true)
    setSaveError(null)
    const result = await saveAuthoringSource(authSel, editContent)
    setIsSaving(false)
    if (result.ok) {
      setEditMode(false)
    } else {
      setSaveError(result.message ?? 'Save failed.')
    }
  }

  // Exit edit mode when the selected target changes
  useEffect(() => {
    setEditMode(false)
    setSaveError(null)
  }, [authSel])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header */}
      <div
        className="hachi-auth-header"
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
          Authoring
        </h1>
        <span style={{ fontSize: 13, color: 'var(--hachi-muted)' }}>
          edit Hachi's own brain — review every change first
        </span>
      </div>

      {/* Scrollable body */}
      <div
        className="hachi-scroll hachi-auth-body"
        style={{ flex: 1, overflow: 'auto', padding: '24px 32px 64px' }}
      >
        <div style={{ maxWidth: 1000, margin: '0 auto' }}>

          {/* E6-T1: .og explainer panel */}
          <OgExplainer
            headline=""
            body={<>Skills use the <strong style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}>.og</strong>{' '}format — a 3-pass graph that cuts token usage by up to 70 % vs. loading entire files.</>}
            whyTooltip={AUTHORING_WHY}
          />

          {/* Lead copy */}
          <div
            style={{
              fontSize: 14,
              color: 'var(--hachi-muted)',
              lineHeight: '22px',
              maxWidth: 740,
              marginBottom: 18,
            }}
          >
            Generate a patch, review the diff, then apply or reject. Nothing is written
            silently — you hold the leash here too.
          </div>

          {/* LOW-009: empty / loading state when no targets */}
          {authTargets.length === 0 ? (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 12,
                padding: '64px 32px',
                background: 'var(--hachi-surface)',
                border: '0.5px solid var(--hachi-line)',
                borderRadius: 16,
                color: 'var(--hachi-muted)',
              }}
            >
              <span style={{ opacity: 0.45 }}>
                <Icon name="folder" size={32} />
              </span>
              <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--hachi-ink)' }}>
                No .og targets found
              </div>
              <div style={{ fontSize: 13, textAlign: 'center', maxWidth: 340 }}>
                Connect to a running Hachi gateway to load your brain, skill, and config targets.
              </div>
            </div>
          ) : (
            /* Two-column layout */
            <div
              className="hachi-auth-grid"
              style={{
                display: 'grid',
                gridTemplateColumns: '260px minmax(0,1fr)',
                gap: 16,
                alignItems: 'start',
              }}
            >
              {/* ---- Left: targets list ---- */}
              <div
                style={{
                  background: 'var(--hachi-surface)',
                  border: '0.5px solid var(--hachi-line)',
                  borderRadius: 16,
                  padding: 14,
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    fontSize: 13,
                    color: 'var(--hachi-muted)',
                    marginBottom: 12,
                    padding: '0 2px',
                  }}
                >
                  <Icon name="folder" size={15} />
                  Targets
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  {authTargets.map((t) => {
                    const isSelected = t.name === authSel

                    return (
                      <div
                        key={t.name}
                        className="hachi-auth-target-row"
                        role="button"
                        tabIndex={0}
                        aria-current={isSelected ? 'true' : undefined}
                        onClick={() => selectAuthTarget(t.name)}
                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectAuthTarget(t.name); } }}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 9,
                          padding: '8px 10px',
                          borderRadius: 8,
                          cursor: 'pointer',
                          background: isSelected ? 'var(--hachi-brand-tint)' : undefined,
                          transition: 'background var(--dur-fast) var(--ease)',
                        }}
                      >
                        <span
                          style={{ color: 'var(--hachi-muted)', display: 'inline-flex' }}
                        >
                          <Icon name={AUTH_KIND_ICON[t.kind] ?? 'file-code'} size={13} />
                        </span>
                        <span
                          style={{
                            fontFamily: 'var(--font-mono)',
                            fontSize: 12.5,
                            flex: 1,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {t.name}
                        </span>
                        {t.dirty && (
                          <span
                            style={{
                              width: 7,
                              height: 7,
                              borderRadius: '50%',
                              background: 'var(--hachi-working)',
                              flexShrink: 0,
                            }}
                          />
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* ---- Right: viewer + generate panel ---- */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {/* Diff / Source viewer */}
                <div
                  style={{
                    background: 'var(--hachi-surface)',
                    border: '0.5px solid var(--hachi-line)',
                    borderRadius: 16,
                    overflow: 'hidden',
                  }}
                >
                  {/* Viewer header */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                      padding: '13px 16px',
                      borderBottom: '0.5px solid var(--hachi-line)',
                    }}
                  >
                    <span style={{ color: 'var(--hachi-muted)', display: 'inline-flex' }}>
                      <Icon name="file-code" size={15} />
                    </span>
                    <span
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontWeight: 500,
                        fontSize: 13,
                        flex: 1,
                      }}
                    >
                      {authSel}
                    </span>

                    {/* Diff / Source toggle (hidden in edit mode) */}
                    {!editMode && (
                    <div
                      style={{
                        display: 'inline-flex',
                        background: 'var(--hachi-cream)',
                        borderRadius: 8,
                        padding: 2,
                      }}
                    >
                      <button
                        onClick={() => setAuthMode('diff')}
                        title="Show unified diff — added lines (+) and removed lines (−) against the current saved state"
                        style={{
                          height: 28,
                          padding: '0 13px',
                          border: 'none',
                          borderRadius: 6,
                          font: '500 12px var(--font-body)',
                          cursor: 'pointer',
                          background: isDiff ? 'var(--hachi-surface)' : 'transparent',
                          color: isDiff ? 'var(--hachi-ink)' : 'var(--hachi-muted)',
                          transition: 'background var(--dur-fast) var(--ease)',
                        }}
                      >
                        Diff
                      </button>
                      <button
                        onClick={() => setAuthMode('source')}
                        title="Show the resulting file after the patch is applied — deleted lines are hidden"
                        style={{
                          height: 28,
                          padding: '0 13px',
                          border: 'none',
                          borderRadius: 6,
                          font: '500 12px var(--font-body)',
                          cursor: 'pointer',
                          background: !isDiff ? 'var(--hachi-surface)' : 'transparent',
                          color: !isDiff ? 'var(--hachi-ink)' : 'var(--hachi-muted)',
                          transition: 'background var(--dur-fast) var(--ease)',
                        }}
                      >
                        Source
                      </button>
                    </div>
                    )}

                    {/* Edit / Save / Cancel buttons */}
                    {editMode ? (
                      <div style={{ display: 'inline-flex', gap: 6 }}>
                        <button
                          className="hachi-ghost-icon-btn-bg"
                          onClick={cancelEditMode}
                          title="Discard edits and return to read-only view"
                          style={{
                            height: 28,
                            padding: '0 12px',
                            border: '0.5px solid var(--hachi-line)',
                            borderRadius: 6,
                            font: '500 12px var(--font-body)',
                            cursor: 'pointer',
                            color: 'var(--hachi-muted)',
                            transition: 'background var(--dur-fast) var(--ease)',
                          }}
                        >
                          Cancel
                        </button>
                        <button
                          className="hachi-mcp-submit-btn"
                          onClick={() => void handleSave()}
                          disabled={isSaving}
                          title="Save edited content to the gateway (POST /authoring/targets/{name}/source)"
                          style={{
                            height: 28,
                            padding: '0 13px',
                            border: 'none',
                            borderRadius: 6,
                            font: '500 12px var(--font-body)',
                            transition: 'background var(--dur-fast) var(--ease)',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 6,
                          }}
                        >
                          <Icon name="check" size={12} />
                          {isSaving ? 'Saving…' : 'Save'}
                        </button>
                      </div>
                    ) : (
                      <button
                        className="hachi-ghost-icon-btn-bg"
                        onClick={enterEditMode}
                        disabled={!authSel}
                        title="Switch to manual edit mode — type directly and save to the gateway"
                        style={{
                          height: 28,
                          padding: '0 12px',
                          border: '0.5px solid var(--hachi-line)',
                          borderRadius: 6,
                          font: '500 12px var(--font-body)',
                          cursor: authSel ? 'pointer' : 'not-allowed',
                          color: 'var(--hachi-muted)',
                          transition: 'background var(--dur-fast) var(--ease)',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 6,
                          opacity: authSel ? 1 : 0.4,
                        }}
                      >
                        <Icon name="file-code" size={12} />
                        Edit
                      </button>
                    )}
                  </div>

                  {/* Code viewer / edit textarea */}
                  {editMode ? (
                    <textarea
                      value={editContent}
                      onChange={(e) => setEditContent(e.target.value)}
                      spellCheck={false}
                      aria-label="Source editor"
                      style={{
                        display: 'block',
                        width: '100%',
                        minHeight: 380,
                        padding: '12px 16px',
                        background: 'var(--hachi-canvas)',
                        color: 'var(--hachi-ink)',
                        fontFamily: 'var(--font-mono)',
                        fontSize: 12.5,
                        lineHeight: '22px',
                        border: 'none',
                        outline: 'none',
                        resize: 'vertical',
                        boxSizing: 'border-box',
                      }}
                    />
                  ) : (
                  <div
                    className="hachi-scroll"
                    style={{
                      background: 'var(--hachi-canvas)',
                      maxHeight: 380,
                      overflow: 'auto',
                      padding: '12px 0',
                    }}
                  >
                    {/* HACHI-019: surface source-fetch errors inline instead of swallowing them */}
                    {sourceFetchError ? (
                      <div
                        style={{
                          padding: '24px',
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: 8,
                          color: 'var(--hachi-danger)',
                          fontSize: 13,
                          lineHeight: '20px',
                        }}
                      >
                        <Icon name="x" size={14} />
                        <span>{sourceFetchError}</span>
                      </div>
                    ) : visibleLines.length === 0 ? (
                      <div
                        style={{
                          padding: '32px 24px',
                          textAlign: 'center',
                          fontSize: 12.5,
                          color: 'var(--hachi-muted)',
                          fontFamily: 'var(--font-mono)',
                        }}
                      >
                        {isGenerating ? 'Generating…' : 'Select a target to view its source.'}
                      </div>
                    ) : (
                      visibleLines.map((l, i) => {
                        const type = l[0]
                        const lineText = l[1]
                        const { bg, gutColor, barColor } = diffRowStyle(type, isDiff)
                        const gutter = isDiff && type === 'add'
                          ? '+'
                          : isDiff && type === 'del'
                          ? '−'
                          : String(i + 1)
                        const parts = tokenise(lineText)

                        return (
                          <div
                            key={i}
                            style={{
                              display: 'flex',
                              alignItems: 'flex-start',
                              background: bg,
                              minHeight: 22,
                            }}
                          >
                            {/* Gutter */}
                            <span
                              style={{
                                width: 38,
                                flexShrink: 0,
                                textAlign: 'right',
                                paddingRight: 12,
                                fontFamily: 'var(--font-mono)',
                                fontSize: 12.5,
                                lineHeight: '22px',
                                color: gutColor,
                                userSelect: 'none',
                              }}
                            >
                              {gutter}
                            </span>
                            {/* Color bar */}
                            <span
                              style={{
                                width: 3,
                                flexShrink: 0,
                                alignSelf: 'stretch',
                                background: barColor,
                              }}
                            />
                            {/* Code tokens — overflow-hidden, no wrap */}
                            <span
                              style={{
                                flex: 1,
                                paddingLeft: 12,
                                fontFamily: 'var(--font-mono)',
                                fontSize: 12.5,
                                lineHeight: '22px',
                                color: 'var(--hachi-ink)',
                                whiteSpace: 'pre',
                                overflow: 'hidden',
                              }}
                            >
                              {parts.map((p, pi) => (
                                <span key={pi} style={{ color: p.color }}>
                                  {p.text}
                                </span>
                              ))}
                            </span>
                          </div>
                        )
                      })
                    )}
                  </div>
                  )}
                </div>

                {/* Save error banner (edit mode) */}
                {saveError && (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '10px 14px',
                      background: 'rgba(192,57,43,0.10)',
                      border: '0.5px solid var(--hachi-danger)',
                      borderRadius: 10,
                      fontSize: 13,
                      color: 'var(--hachi-danger)',
                    }}
                  >
                    <Icon name="x" size={14} />
                    <span style={{ flex: 1 }}>{saveError}</span>
                    <button
                      onClick={() => setSaveError(null)}
                      style={{
                        background: 'none',
                        border: 'none',
                        padding: 0,
                        cursor: 'pointer',
                        color: 'var(--hachi-danger)',
                        display: 'inline-flex',
                        alignItems: 'center',
                      }}
                    >
                      <Icon name="x" size={12} />
                    </button>
                  </div>
                )}

                {/* Generate patch panel */}
                <div
                  style={{
                    background: 'var(--hachi-surface)',
                    border: '0.5px solid var(--hachi-line)',
                    borderRadius: 16,
                    padding: 18,
                  }}
                >
                  {/* Panel header */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                      marginBottom: 13,
                    }}
                  >
                    <span style={{ color: 'var(--hachi-brand)', display: 'inline-flex' }}>
                      <Icon name="sparkles" size={16} />
                    </span>
                    <span style={{ fontWeight: 500, fontSize: 14 }}>Generate patch</span>
                  </div>

                  {/* Prompt row */}
                  <div style={{ display: 'flex', gap: 10, marginBottom: 14 }}>
                    <input
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) void handleGenerate() }}
                      aria-label="Describe the change you want"
                      style={{
                        flex: 1,
                        minWidth: 0,
                        height: 38,
                        padding: '0 12px',
                        border: '0.5px solid var(--hachi-line)',
                        borderRadius: 10,
                        background: 'var(--hachi-canvas)',
                        font: 'inherit',
                        fontSize: 13,
                        color: 'var(--hachi-ink)',
                        outline: 'none',
                      }}
                      placeholder="Describe the change you want…"
                    />
                    <button
                      className="hachi-mcp-submit-btn"
                      onClick={() => void handleGenerate()}
                      disabled={isGenerating || !authSel || !prompt.trim()}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 7,
                        height: 38,
                        padding: '0 14px',
                        borderRadius: 10,
                        border: '0.5px solid transparent',
                        font: '500 13px var(--font-body)',
                        transition: 'background var(--dur-fast) var(--ease)',
                        flexShrink: 0,
                      }}
                    >
                      <Icon name="sparkles" size={14} />
                      {isGenerating ? 'Generating…' : 'Generate'}
                    </button>
                  </div>

                  {/* Inline generate error */}
                  {generateError && (
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        padding: '10px 14px',
                        marginBottom: 12,
                        background: 'rgba(192,57,43,0.10)',
                        border: '0.5px solid var(--hachi-danger)',
                        borderRadius: 10,
                        fontSize: 13,
                        color: 'var(--hachi-danger)',
                      }}
                    >
                      <Icon name="x" size={14} />
                      {generateError}
                      <button
                        onClick={() => setGenerateError(null)}
                        style={{
                          marginLeft: 'auto',
                          background: 'none',
                          border: 'none',
                          padding: 0,
                          cursor: 'pointer',
                          color: 'var(--hachi-danger)',
                          display: 'inline-flex',
                          alignItems: 'center',
                        }}
                      >
                        <Icon name="x" size={12} />
                      </button>
                    </div>
                  )}

                  {/* Patch summary row — only shown when a diff exists (LOW-003) */}
                  {(hasDiff || authApplied) && (
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 12,
                        padding: '12px 14px',
                        background: 'var(--hachi-cream)',
                        border: '0.5px solid var(--hachi-line)',
                        borderRadius: 10,
                      }}
                    >
                      {/* Applied badge */}
                      {authApplied && (
                        <span
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 6,
                            padding: '4px 10px',
                            borderRadius: 999,
                            background: 'var(--hachi-success-tint)',
                            color: 'var(--hachi-success-fg)',
                            fontSize: 12,
                            fontWeight: 500,
                            flexShrink: 0,
                          }}
                        >
                          <span
                            style={{
                              width: 7,
                              height: 7,
                              borderRadius: '50%',
                              background: 'var(--hachi-success)',
                            }}
                          />
                          applied
                        </span>
                      )}

                      {/* Derived diff summary (LOW-003) */}
                      <span
                        style={{
                          fontFamily: 'var(--font-mono)',
                          fontSize: 13,
                          color: 'var(--hachi-muted)',
                        }}
                      >
                        {hasDiff
                          ? `+${addCount} −${delCount} lines · ${authSel ?? ''}`
                          : authSel ?? ''}
                      </span>

                      {/* Action buttons */}
                      <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
                        {authApplied ? (
                          <button
                            onClick={() => { if (authSel) void revertAuthoring(authSel) }}
                            className="hachi-ghost-icon-btn-bg"
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: 6,
                              height: 34,
                              padding: '0 13px',
                              borderRadius: 10,
                              border: '0.5px solid var(--hachi-line)',
                              background: 'var(--hachi-canvas)',
                              color: 'var(--hachi-ink)',
                              font: '500 13px var(--font-body)',
                              cursor: 'pointer',
                              transition: 'background var(--dur-fast) var(--ease)',
                            }}
                          >
                            <Icon name="refresh" size={13} />
                            Revert
                          </button>
                        ) : (
                          <>
                            <button
                              className="hachi-cancel-btn"
                              onClick={() => { rejectPatch(); setGeneratedDiff(null); setGenerateError(null) }}
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 6,
                                height: 34,
                                padding: '0 13px',
                                borderRadius: 10,
                                border: '1px solid var(--hachi-trust)',
                                color: 'var(--hachi-trust)',
                                font: '500 13px var(--font-body)',
                                cursor: 'pointer',
                                transition: 'background var(--dur-fast) var(--ease)',
                              }}
                            >
                              <Icon name="x" size={13} />
                              Reject
                            </button>
                            <button
                              className="hachi-mcp-submit-btn"
                              onClick={() => { if (authSel) void applyAuthoring(authSel).then(() => setGeneratedDiff(null)) }}
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 6,
                                height: 34,
                                padding: '0 13px',
                                borderRadius: 10,
                                border: '0.5px solid transparent',
                                font: '500 13px var(--font-body)',
                                cursor: 'pointer',
                                transition: 'background var(--dur-fast) var(--ease)',
                              }}
                            >
                              <Icon name="check" size={13} />
                              Apply patch
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Post-apply confirmation line */}
                  {authApplied && (
                    <div
                      style={{
                        marginTop: 11,
                        fontSize: 12.5,
                        color: 'var(--hachi-success-fg)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 7,
                      }}
                    >
                      <Icon name="check" size={14} />
                      Written to ~/.hachi/skills/{authSel} &middot; skill re-indexed
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export const Route = createFileRoute('/authoring')({
  component: Authoring,
})
