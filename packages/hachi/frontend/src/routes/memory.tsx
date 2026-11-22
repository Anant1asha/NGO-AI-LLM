// ============================================================
// Memory screen — /memory
// Recreates prototype lines 669–797 faithfully.
// Screen-local state: memSearch, recallQuery, recallDone, hovered buttons.
// All domain mutations via useStore.
//
// Layout: two tabs — "Recall" (semantic search) and "Audit" (history/sessions).
// This reduces cognitive load on a trust-critical feature (MED-019).
// ============================================================

import React, { useCallback, useEffect, useRef, useState } from 'react'
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useStore } from '../lib/store/store'
import {
  loadMemory,
  recallMemory,
  addFact as addFactRemote,
  saveFact as saveFactRemote,
  delFact as delFactRemote,
} from '../lib/data/domains/memory'
import { Icon } from '../components/icons/Icon'
import { HachiMascot } from '../components/brand/HachiMascot'
import { ConfirmButton } from '../components/ui/ConfirmButton'
import type { MemGroup, Fact, BlockedItem, RecallHit, Session, SkillUsage } from '../lib/data/types'
import { PendingCard } from '../components/ui/PendingCard'

// ============================================================
// Valid vault collection names accepted by POST /memory/facts
// ============================================================
const VAULT_GROUPS: { id: string; label: string }[] = [
  { id: 'user_profile', label: 'About me' },
  { id: 'core_memory', label: 'Core memory' },
  { id: 'agent_profile', label: 'Agent profile' },
]

// ============================================================
// Small hover-aware button helpers (screen-local, no css class needed)
// ============================================================
function GhostIconBtn({
  onClick,
  hoverBg,
  hoverColor,
  'aria-label': ariaLabel,
  children,
}: {
  onClick: () => void
  hoverBg: string
  hoverColor: string
  'aria-label': string
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      className="hachi-ghost-icon-btn"
      onClick={onClick}
      aria-label={ariaLabel}
      style={{
        border: 'none',
        background: 'transparent',
        color: 'var(--hachi-muted)',
        cursor: 'pointer',
        display: 'inline-flex',
        padding: '4px',
        borderRadius: '6px',
        transition: 'background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease)',
        ['--hover-bg' as string]: hoverBg,
        ['--hover-color' as string]: hoverColor,
      }}
    >
      {children}
    </button>
  )
}

function TextBtn({
  onClick,
  children,
  style,
  hoverStyle,
  disabled,
}: {
  onClick: () => void
  children: React.ReactNode
  style: React.CSSProperties
  /** Only `background` is honored — carried to CSS via the --hover-bg custom property. */
  hoverStyle: React.CSSProperties
  disabled?: boolean
}) {
  return (
    <button
      className="hachi-text-btn"
      onClick={onClick}
      disabled={disabled}
      style={{
        ...style,
        ...(disabled ? { opacity: 0.55, cursor: 'not-allowed' } : {}),
        ['--hover-bg' as string]: hoverStyle.background,
      }}
    >
      {children}
    </button>
  )
}

// ============================================================
// Fact card — view or edit mode
// ============================================================
function FactCard({
  fact,
  groupId,
  editingFactId,
  editingText,
  onEdit,
  onDelete,
  onSetEditText,
  onCancelEdit,
  onSave,
}: {
  fact: Fact
  groupId: string
  editingFactId: string | null
  editingText: string
  onEdit: () => void
  onDelete: () => void
  onSetEditText: (v: string) => void
  onCancelEdit: () => void
  onSave: () => void
}) {
  const isEditing = editingFactId === fact.id

  return (
    <div
      style={{
        background: 'var(--hachi-surface)',
        border: '0.5px solid var(--hachi-line)',
        borderRadius: '14px',
        padding: '15px',
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
      }}
    >
      {!isEditing ? (
        <>
          <div style={{ fontSize: '14px', lineHeight: '21px' }}>{fact.text || <span style={{ color: 'var(--hachi-muted)', fontStyle: 'italic' }}>empty fact</span>}</div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '12px', color: 'var(--hachi-muted)' }}>{fact.source}</span>
            <div style={{ display: 'flex', gap: '2px' }}>
              <GhostIconBtn onClick={onEdit} hoverBg="var(--hachi-cream)" hoverColor="var(--hachi-trust)" aria-label="Edit fact">
                <Icon name="pencil" size={15} />
              </GhostIconBtn>
              <ConfirmButton
                label="Delete"
                confirmLabel="Delete?"
                onConfirm={onDelete}
                tone="danger"
                icon="trash"
                ariaLabel="Delete fact"
              />
            </div>
          </div>
        </>
      ) : (
        <>
          <textarea
            value={editingText}
            onChange={(e) => onSetEditText(e.target.value)}
            rows={2}
            placeholder="What should Hachi remember?"
            aria-label="Edit memory fact"
            style={{
              width: '100%',
              resize: 'none',
              border: '0.5px solid var(--hachi-brand)',
              borderRadius: '8px',
              background: 'var(--hachi-canvas)',
              font: 'inherit',
              fontSize: '14px',
              lineHeight: '21px',
              color: 'var(--hachi-ink)',
              outline: 'none',
              padding: '9px 11px',
              boxSizing: 'border-box',
            }}
          />
          <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
            <TextBtn
              onClick={onCancelEdit}
              style={{
                height: '30px',
                padding: '0 12px',
                borderRadius: '8px',
                border: 'none',
                background: 'transparent',
                color: 'var(--hachi-muted)',
                font: '500 13px var(--font-body)',
                cursor: 'pointer',
              }}
              hoverStyle={{ background: 'var(--hachi-cream)' }}
            >
              Cancel
            </TextBtn>
            <TextBtn
              onClick={onSave}
              style={{
                height: '30px',
                padding: '0 13px',
                borderRadius: '8px',
                border: '0.5px solid transparent',
                background: 'var(--hachi-brand-hover)',
                color: 'var(--hachi-canvas)',
                font: '500 13px var(--font-body)',
                cursor: 'pointer',
              }}
              hoverStyle={{ background: 'var(--hachi-brand-active)' }}
            >
              Save
            </TextBtn>
          </div>
        </>
      )}
    </div>
  )
}

// ============================================================
// Tab bar — local sub-view switcher
// ============================================================
type MemTab = 'recall' | 'audit'

function TabBar({ active, onChange }: { active: MemTab; onChange: (t: MemTab) => void }) {
  const tabs: { key: MemTab; label: string; icon: string }[] = [
    { key: 'recall', label: 'Recall', icon: 'sparkles' },
    { key: 'audit', label: 'Audit & History', icon: 'shield' },
  ]
  return (
    <div
      style={{
        display: 'flex',
        gap: '4px',
        padding: '4px',
        background: 'var(--hachi-surface)',
        border: '0.5px solid var(--hachi-line)',
        borderRadius: '12px',
        width: 'fit-content',
      }}
    >
      {tabs.map((t) => {
        const isActive = t.key === active
        return (
          <button
            key={t.key}
            type="button"
            onClick={() => onChange(t.key)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              height: '32px',
              padding: '0 14px',
              borderRadius: '9px',
              border: 'none',
              background: isActive ? 'var(--hachi-canvas)' : 'transparent',
              color: isActive ? 'var(--hachi-ink)' : 'var(--hachi-muted)',
              font: `${isActive ? 500 : 400} 13px var(--font-body)`,
              cursor: 'pointer',
              boxShadow: isActive ? '0 1px 3px rgba(0,0,0,0.07)' : 'none',
              transition: 'background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease)',
            }}
          >
            <Icon name={t.icon} size={14} />
            {t.label}
          </button>
        )
      })}
    </div>
  )
}


// ============================================================
// Main Memory component
// ============================================================
function Memory() {
  const navigate = useNavigate()

  // --- store ---
  const memGroups = useStore((s) => s.memGroups)
  const blocked = useStore((s) => s.blocked)
  const proposed = useStore((s) => s.proposed)
  const recall = useStore((s) => s.recall)
  const loadedMemory = useStore((s) => s.loaded.memory)
  const sessions = useStore((s) => s.sessions)
  const skillUsage = useStore((s) => s.skillUsage)
  const editingFactId = useStore((s) => s.editingFactId)
  const editingText = useStore((s) => s.editingText)

  const startEditFact = useStore((s) => s.startEditFact)
  const delFact = useStore((s) => s.delFact)
  const setEditText = useStore((s) => s.setEditText)
  const cancelEdit = useStore((s) => s.cancelEdit)
  const saveFact = useStore((s) => s.saveFact)
  const approveProposed = useStore((s) => s.approveProposed)
  const rejectProposed = useStore((s) => s.rejectProposed)
  const showToast = useStore((s) => s.showToast)

  // --- load on mount (refresh-on-navigate; bootstrapLiveData also runs on app mount) ---
  useEffect(() => { void loadMemory() }, [])

  // --- local state ---
  const [memSearch, setMemSearch] = useState('')
  // LOW-006: start empty; placeholder communicates intent without pre-filling a repo-specific example
  const [recallQuery, setRecallQuery] = useState('')
  // HIGH-010: start false so "Closest Matches" only renders after the user submits a query
  const [recallDone, setRecallDone] = useState(false)
  // LOW-008: disable Recall button while a fetch is in-flight
  const [recallLoading, setRecallLoading] = useState(false)
  // MED-019: sub-view tabs — "Recall" vs "Audit & History"
  const [activeTab, setActiveTab] = useState<MemTab>('recall')

  const addFactInputRef = useRef<HTMLTextAreaElement>(null)

  // --- inline add-fact form state ---
  // addFormOpen: whether the inline form is visible
  const [addFormOpen, setAddFormOpen] = useState(false)
  // addFactText: text the user is typing for the new fact
  const [addFactText, setAddFactText] = useState('')
  // addFactGroup: which vault collection to write to (must match backend's _VAULT_GROUP_MAP)
  const [addFactGroup, setAddFactGroup] = useState('user_profile')
  // addFactSaving: true while the POST is in-flight (disables submit button)
  const [addFactSaving, setAddFactSaving] = useState(false)

  // --- computed ---
  const q = memSearch.trim().toLowerCase()
  const filteredGroups: MemGroup[] = memGroups
    .map((g) => ({
      ...g,
      facts: g.facts.filter((f) => !q || f.text.toLowerCase().includes(q)),
    }))
    .filter((g) => g.facts.length > 0)
  const memEmpty = q.length > 0 && filteredGroups.length === 0
  const vaultEmpty = q.length === 0 && memGroups.every((g: MemGroup) => g.facts.length === 0)

  const openAddFact = useCallback(() => {
    setAddFormOpen(true)
    setTimeout(() => addFactInputRef.current?.focus(), 50)
  }, [])

  // --- session renderVals ---
  const sessionRows = sessions.map((s: Session) => ({
    ...s,
    turnsLabel: s.turns + ' turns',
    label: s.active ? 'Current' : 'Resume',
    icon: s.active ? 'eye' : 'chat',
    // HIGH-011: Navigate to /conversation. The gateway has no dedicated resume
    // endpoint — session history is display-only; the chat module's ensureSession()
    // creates a fresh session when the user sends their first message. For the
    // active session navigate immediately; for past sessions pass the session id
    // as a search param so the conversation screen loads that session's transcript.
    resume: () => {
      if (s.active) {
        void navigate({ to: '/conversation' })
        return
      }
      showToast('Opening conversation — context from "' + s.title + '" is shown above for reference', 'info')
      void navigate({ to: '/conversation', search: { session: s.id } })
    },
  }))

  // skill usage — calls as string + saved with minus sign
  const skillRows = skillUsage.map((k: SkillUsage) => ({
    ...k,
    callsLabel: k.calls + ' calls',
    savedLabel: '−' + k.saved,
  }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* ---- header ---- */}
      <div
        className="hachi-mem-header"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '16px',
          padding: '0 32px',
          height: '68px',
          flexShrink: 0,
          borderBottom: '0.5px solid var(--hachi-line)',
        }}
      >
        <h1
          style={{
            margin: 0,
            fontFamily: 'var(--font-display)',
            fontWeight: 500,
            fontSize: '22px',
            lineHeight: '26px',
          }}
        >
          Memory
        </h1>
        <span style={{ fontSize: '13px', color: 'var(--hachi-muted)' }}>
          what Hachi knows about you
        </span>
        <div style={{ flex: 1 }} />
        {/* add a fact — only shown on Recall tab where groups are visible */}
        {activeTab === 'recall' && (
          <TextBtn
            onClick={() => {
              setAddFormOpen((v) => !v)
              setAddFactText('')
              setAddFactGroup('user_profile')
            }}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '7px',
              height: '38px',
              padding: '0 14px',
              borderRadius: '10px',
              border: '0.5px solid var(--hachi-line)',
              background: 'var(--hachi-canvas)',
              color: 'var(--hachi-ink)',
              font: '500 13px var(--font-body)',
              cursor: 'pointer',
            }}
            hoverStyle={{ background: 'var(--hachi-cream)' }}
          >
            <Icon name="plus" size={15} />
            Add a fact
          </TextBtn>
        )}
        {/* search */}
        <div
          className="hachi-mem-search"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            height: '38px',
            padding: '0 12px',
            background: 'var(--hachi-surface)',
            border: '0.5px solid var(--hachi-line)',
            borderRadius: '10px',
            width: '240px',
            color: 'var(--hachi-muted)',
          }}
        >
          <Icon name="search" size={15} />
          <input
            value={memSearch}
            onChange={(e) => setMemSearch(e.target.value)}
            placeholder="Search memory"
            aria-label="Search memory"
            style={{
              flex: 1,
              border: 'none',
              background: 'transparent',
              font: 'inherit',
              fontSize: '13px',
              color: 'var(--hachi-ink)',
              outline: 'none',
            }}
          />
        </div>
      </div>

      {/* ---- scrollable body ---- */}
      <div
        className="hachi-scroll hachi-mem-body"
        style={{ flex: 1, overflow: 'auto', padding: '24px 32px 64px' }}
      >
        <div
          style={{
            maxWidth: '820px',
            margin: '0 auto',
            display: 'flex',
            flexDirection: 'column',
            gap: '26px',
          }}
        >
          {/* ---- MED-019: tab switcher ---- */}
          <TabBar active={activeTab} onChange={setActiveTab} />

          {/* ============================================================
              TAB: Recall — semantic search + proposed change + memory groups
              ============================================================ */}
          {activeTab === 'recall' && (
            <>
              {/* ---- semantic recall ---- */}
              <div
                style={{
                  background: 'var(--hachi-surface)',
                  border: '0.5px solid var(--hachi-line)',
                  borderRadius: '16px',
                  padding: '18px',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '9px',
                    marginBottom: '13px',
                  }}
                >
                  <span style={{ color: 'var(--hachi-trust)', display: 'inline-flex' }}>
                    <Icon name="sparkles" size={17} />
                  </span>
                  <span style={{ fontWeight: 500, fontSize: '15px' }}>Ask memory anything</span>
                </div>
                <div style={{ display: 'flex', gap: '10px' }}>
                  <input
                    value={recallQuery}
                    onChange={(e) => {
                      setRecallQuery(e.target.value)
                      setRecallDone(false)
                    }}
                    // LOW-006: placeholder communicates intent; no pre-filled example
                    placeholder="What do you want Hachi to recall?"
                    aria-label="Ask memory anything"
                    style={{
                      flex: 1,
                      minWidth: 0,
                      height: '40px',
                      padding: '0 13px',
                      border: '0.5px solid var(--hachi-line)',
                      borderRadius: '10px',
                      background: 'var(--hachi-canvas)',
                      font: 'inherit',
                      fontSize: '14px',
                      color: 'var(--hachi-ink)',
                      outline: 'none',
                    }}
                  />
                  {/* LOW-008: disabled + loading state during fetch */}
                  <TextBtn
                    disabled={recallLoading}
                    onClick={() => {
                      if (recallLoading) return
                      setRecallLoading(true)
                      void recallMemory(recallQuery).finally(() => {
                        setRecallLoading(false)
                        setRecallDone(true)
                      })
                    }}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '7px',
                      height: '40px',
                      padding: '0 15px',
                      borderRadius: '10px',
                      border: '0.5px solid transparent',
                      background: 'var(--hachi-brand-hover)',
                      color: 'var(--hachi-canvas)',
                      font: '500 13px var(--font-body)',
                      cursor: recallLoading ? 'not-allowed' : 'pointer',
                    }}
                    hoverStyle={{ background: 'var(--hachi-brand-active)' }}
                  >
                    <Icon name={recallLoading ? 'refresh' : 'search'} size={15} />
                    {recallLoading ? 'Recalling…' : 'Recall'}
                  </TextBtn>
                </div>

                {/* LOW-010: only render results section after a query has been submitted */}
                {recallDone && (
                  <>
                    <div
                      style={{
                        fontSize: '12px',
                        color: 'var(--hachi-muted)',
                        margin: '14px 0 8px',
                      }}
                    >
                      Closest matches
                    </div>
                    {recall.length === 0 ? (
                      <div style={{ fontSize: '13.5px', color: 'var(--hachi-muted)', padding: '8px 0' }}>
                        No matches found.
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {recall.map((r: RecallHit) => (
                          <div
                            key={r.fact}
                            style={{
                              display: 'flex',
                              gap: '12px',
                              alignItems: 'flex-start',
                              padding: '11px 13px',
                              background: 'var(--hachi-canvas)',
                              border: '0.5px solid var(--hachi-line)',
                              borderRadius: '10px',
                            }}
                          >
                            <span
                              style={{
                                color: 'var(--hachi-trust)',
                                flexShrink: 0,
                                marginTop: '1px',
                                display: 'inline-flex',
                              }}
                            >
                              <Icon name="sparkles" size={15} />
                            </span>
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div style={{ fontSize: '13.5px', lineHeight: '20px' }}>{r.fact}</div>
                              <div
                                style={{
                                  fontFamily: 'var(--font-mono)',
                                  fontSize: '11.5px',
                                  color: 'var(--hachi-muted)',
                                  marginTop: '4px',
                                }}
                              >
                                {r.src}
                              </div>
                            </div>
                            <span
                              style={{
                                fontFamily: 'var(--font-mono)',
                                fontSize: '12px',
                                color: 'var(--hachi-trust)',
                                flexShrink: 0,
                              }}
                            >
                              {r.score}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>

              {/* ---- proposed change ---- */}
              {proposed && (
                <div
                  style={{
                    background: 'var(--hachi-surface)',
                    border: '0.5px solid var(--hachi-brand)',
                    borderRadius: '16px',
                    padding: '18px',
                    display: 'flex',
                    gap: '14px',
                    alignItems: 'flex-start',
                  }}
                >
                  <div
                    style={{
                      flexShrink: 0,
                      width: '38px',
                      height: '38px',
                      borderRadius: '10px',
                      background: 'var(--hachi-brand-tint)',
                      display: 'grid',
                      placeItems: 'center',
                      color: 'var(--hachi-brand)',
                    }}
                  >
                    <Icon name="sparkles" size={19} />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 500, fontSize: '15px', marginBottom: '6px' }}>
                      Hachi proposes an update
                    </div>
                    <div
                      style={{
                        fontSize: '14px',
                        color: 'var(--hachi-muted)',
                        lineHeight: '22px',
                      }}
                    >
                      {proposed.from}{' '}
                      <span style={{ color: 'var(--hachi-ink)' }}>→ {proposed.to}</span>
                    </div>
                    <div style={{ display: 'flex', gap: '9px', marginTop: '14px' }}>
                      <TextBtn
                        onClick={rejectProposed}
                        style={{
                          height: '34px',
                          padding: '0 14px',
                          borderRadius: '10px',
                          border: '1px solid var(--hachi-trust)',
                          background: 'transparent',
                          color: 'var(--hachi-trust)',
                          font: '500 13px var(--font-body)',
                          cursor: 'pointer',
                        }}
                        hoverStyle={{ background: 'var(--hachi-trust-tint)' }}
                      >
                        Reject
                      </TextBtn>
                      <TextBtn
                        onClick={approveProposed}
                        style={{
                          height: '34px',
                          padding: '0 14px',
                          borderRadius: '10px',
                          border: '0.5px solid transparent',
                          background: 'var(--hachi-brand-hover)',
                          color: 'var(--hachi-canvas)',
                          font: '500 13px var(--font-body)',
                          cursor: 'pointer',
                        }}
                        hoverStyle={{ background: 'var(--hachi-brand-active)' }}
                      >
                        Approve change
                      </TextBtn>
                    </div>
                  </div>
                </div>
              )}

              {/* ---- inline add-fact form ---- */}
              {addFormOpen && (
                <div
                  style={{
                    background: 'var(--hachi-surface)',
                    border: '0.5px solid var(--hachi-brand)',
                    borderRadius: '16px',
                    padding: '18px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px',
                  }}
                >
                  <div style={{ fontWeight: 500, fontSize: '15px' }}>Add a fact</div>

                  {/* Group selector */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                    <label
                      htmlFor="add-fact-group"
                      style={{ fontSize: '12px', color: 'var(--hachi-muted)', fontWeight: 500 }}
                    >
                      Collection
                    </label>
                    <select
                      id="add-fact-group"
                      value={addFactGroup}
                      onChange={(e) => setAddFactGroup(e.target.value)}
                      style={{
                        height: '36px',
                        padding: '0 10px',
                        borderRadius: '8px',
                        border: '0.5px solid var(--hachi-line)',
                        background: 'var(--hachi-canvas)',
                        font: 'inherit',
                        fontSize: '13px',
                        color: 'var(--hachi-ink)',
                        cursor: 'pointer',
                        outline: 'none',
                      }}
                    >
                      {VAULT_GROUPS.map((vg) => (
                        <option key={vg.id} value={vg.id}>
                          {vg.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Fact text input */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                    <label
                      htmlFor="add-fact-text"
                      style={{ fontSize: '12px', color: 'var(--hachi-muted)', fontWeight: 500 }}
                    >
                      Fact
                    </label>
                    <textarea
                      id="add-fact-text"
                      ref={addFactInputRef}
                      value={addFactText}
                      onChange={(e) => setAddFactText(e.target.value)}
                      rows={3}
                      placeholder="What should Hachi remember?"
                      style={{
                        width: '100%',
                        resize: 'vertical',
                        border: '0.5px solid var(--hachi-line)',
                        borderRadius: '8px',
                        background: 'var(--hachi-canvas)',
                        font: 'inherit',
                        fontSize: '14px',
                        lineHeight: '21px',
                        color: 'var(--hachi-ink)',
                        outline: 'none',
                        padding: '9px 11px',
                        boxSizing: 'border-box',
                      }}
                    />
                  </div>

                  {/* Actions */}
                  <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                    <TextBtn
                      onClick={() => {
                        setAddFormOpen(false)
                        setAddFactText('')
                      }}
                      style={{
                        height: '32px',
                        padding: '0 13px',
                        borderRadius: '8px',
                        border: 'none',
                        background: 'transparent',
                        color: 'var(--hachi-muted)',
                        font: '500 13px var(--font-body)',
                        cursor: 'pointer',
                      }}
                      hoverStyle={{ background: 'var(--hachi-cream)' }}
                    >
                      Cancel
                    </TextBtn>
                    <TextBtn
                      disabled={addFactSaving || !addFactText.trim()}
                      onClick={() => {
                        if (addFactSaving || !addFactText.trim()) return
                        setAddFactSaving(true)
                        void addFactRemote(addFactGroup, addFactText)
                          .then(() => {
                            setAddFormOpen(false)
                            setAddFactText('')
                            showToast('Saved — Hachi remembers it', 'success')
                          })
                          .catch((err: unknown) => {
                            const msg = err instanceof Error ? err.message : 'Failed to save fact'
                            showToast(msg, 'blocked')
                          })
                          .finally(() => {
                            setAddFactSaving(false)
                          })
                      }}
                      style={{
                        height: '32px',
                        padding: '0 14px',
                        borderRadius: '8px',
                        border: '0.5px solid transparent',
                        background: 'var(--hachi-brand-hover)',
                        color: 'var(--hachi-canvas)',
                        font: '500 13px var(--font-body)',
                        cursor: addFactSaving || !addFactText.trim() ? 'not-allowed' : 'pointer',
                      }}
                      hoverStyle={{ background: 'var(--hachi-brand-active)' }}
                    >
                      {addFactSaving ? 'Saving…' : 'Save fact'}
                    </TextBtn>
                  </div>
                </div>
              )}

              {/* ---- memory groups ---- */}
              {!loadedMemory && filteredGroups.length === 0 && (
                <PendingCard label="Loading memory…" />
              )}
              {filteredGroups.map((g: MemGroup) => (
                <div key={g.id}>
                  {/* LOW-004: group header always visible (groups are filtered to non-empty) */}
                  <h2
                    style={{
                      margin: '0 0 12px',
                      fontFamily: 'var(--font-display)',
                      fontWeight: 500,
                      fontSize: '15px',
                      color: 'var(--hachi-muted)',
                    }}
                  >
                    {g.title}
                  </h2>
                  <div
                    className="hachi-fact-grid"
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '1fr 1fr',
                      gap: '12px',
                    }}
                  >
                    {g.facts.map((fact: Fact) => (
                      <FactCard
                        key={fact.id}
                        fact={fact}
                        groupId={g.id}
                        editingFactId={editingFactId}
                        editingText={editingText}
                        onEdit={() => startEditFact(fact.id)}
                        onDelete={() => {
                          const factText = fact.text
                          const groupId  = g.id
                          // 1. Optimistic: remove from store immediately
                          delFact(groupId, fact.id)
                          // 2. Network delete
                          void delFactRemote(groupId, fact.id).catch((err: unknown) => {
                            const msg = err instanceof Error ? err.message : 'Failed to delete fact'
                            showToast(msg, 'blocked')
                          })
                          // 3. Undo toast — re-adds the fact content to recover from deletion
                          showToast('Fact forgotten', 'success', {
                            label: 'Undo',
                            onAction: () => { void addFactRemote(groupId, factText) },
                          })
                        }}
                        onSetEditText={setEditText}
                        onCancelEdit={cancelEdit}
                        onSave={() => {
                          const text = editingText
                          // 1. Optimistic: persist text in store immediately
                          saveFact(g.id, fact.id)
                          // 2. Network: DELETE old + POST new (or just POST for temp ids)
                          //    On failure, loadMemory() inside saveFactRemote reverts and
                          //    we show the error to the user.
                          void saveFactRemote(g.id, fact.id, text).catch((err: unknown) => {
                            const msg = err instanceof Error ? err.message : 'Failed to save fact'
                            showToast(msg, 'blocked')
                          })
                        }}
                      />
                    ))}
                  </div>
                </div>
              ))}

              {/* ---- empty state (search, no results) ---- */}
              {memEmpty && (
                <div
                  style={{
                    textAlign: 'center',
                    padding: '40px 0',
                    color: 'var(--hachi-muted)',
                  }}
                >
                  No memories match "{memSearch}".
                </div>
              )}

              {/* ---- first-run card (vault empty, no search) ---- */}
              {vaultEmpty && !addFormOpen && (
                <div
                  style={{
                    background: 'var(--hachi-surface)',
                    border: '0.5px solid var(--hachi-line)',
                    borderRadius: 16,
                    padding: '40px 24px',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: 16,
                    textAlign: 'center',
                  }}
                >
                  <HachiMascot state="on-watch" scale={3} decor={false} />
                  <p style={{ margin: 0, fontSize: 15, color: 'var(--hachi-muted)' }}>
                    Nothing remembered yet.
                  </p>
                  <button
                    type="button"
                    onClick={openAddFact}
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: 6,
                      height: 36, padding: '0 16px', borderRadius: 8,
                      background: 'var(--hachi-brand)', color: 'var(--hachi-canvas)',
                      border: 'none', cursor: 'pointer', font: 'inherit',
                      fontSize: 14, fontWeight: 500,
                    }}
                  >
                    Add a fact
                  </button>
                </div>
              )}
            </>
          )}

          {/* ============================================================
              TAB: Audit — blocked items + skill usage + sessions
              ============================================================ */}
          {activeTab === 'audit' && (
            <>
              {/* ---- blocked / quarantined ---- */}
              {/* LOW-004: only render section when blocked array is non-empty */}
              {blocked.length > 0 && (
                <div>
                  <h2
                    style={{
                      margin: '0 0 12px',
                      fontFamily: 'var(--font-display)',
                      fontWeight: 500,
                      fontSize: '15px',
                      color: 'var(--hachi-muted)',
                    }}
                  >
                    Blocked — Hachi refused to store
                  </h2>
                  <div
                    style={{
                      background: 'var(--hachi-surface)',
                      border: '0.5px solid var(--hachi-line)',
                      borderRadius: '14px',
                      overflow: 'hidden',
                    }}
                  >
                    {blocked.map((b: BlockedItem, i: number) => (
                      <div
                        key={b.id}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '11px',
                          padding: '13px 16px',
                          borderBottom:
                            i < blocked.length - 1
                              ? '0.5px solid var(--hachi-line)'
                              : undefined,
                        }}
                      >
                        <span style={{ color: 'var(--hachi-danger)', display: 'inline-flex' }}>
                          <Icon name="shield" size={16} />
                        </span>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: '14px' }}>{b.text}</div>
                          <div style={{ fontSize: '12px', color: 'var(--hachi-muted)', marginTop: '2px' }}>
                            {b.reason}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* ---- skills Hachi leans on ---- */}
              {/* LOW-004: only render section when skillRows array is non-empty */}
              {skillRows.length > 0 && (
                <div>
                  <h2
                    style={{
                      margin: '0 0 12px',
                      fontFamily: 'var(--font-display)',
                      fontWeight: 500,
                      fontSize: '15px',
                      color: 'var(--hachi-muted)',
                    }}
                  >
                    Skills Hachi leans on
                  </h2>
                  <div
                    style={{
                      background: 'var(--hachi-surface)',
                      border: '0.5px solid var(--hachi-line)',
                      borderRadius: '14px',
                      overflow: 'hidden',
                    }}
                  >
                    {skillRows.map((k, i) => (
                      <div
                        key={k.name}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '13px',
                          padding: '12px 16px',
                          borderBottom:
                            i < skillRows.length - 1
                              ? '0.5px solid var(--hachi-line)'
                              : undefined,
                        }}
                      >
                        <span
                          style={{
                            fontFamily: 'var(--font-mono)',
                            fontSize: '13px',
                            color: 'var(--hachi-ink)',
                            flex: 1,
                            minWidth: 0,
                          }}
                        >
                          {k.name}
                        </span>
                        <span style={{ fontSize: '12.5px', color: 'var(--hachi-muted)' }}>
                          {k.callsLabel}
                        </span>
                        <span
                          style={{
                            fontFamily: 'var(--font-mono)',
                            fontSize: '12.5px',
                            color: 'var(--hachi-muted)',
                            width: '48px',
                            textAlign: 'right',
                          }}
                        >
                          {k.tokens}
                        </span>
                        <span
                          style={{
                            fontSize: '11.5px',
                            fontWeight: 500,
                            color: 'var(--hachi-success)',
                            background: 'var(--hachi-success-tint)',
                            padding: '3px 9px',
                            borderRadius: '999px',
                            flexShrink: 0,
                          }}
                        >
                          {k.savedLabel} tokens
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* ---- resumable sessions ---- */}
              {/* LOW-004: only render section when sessionRows array is non-empty */}
              {sessionRows.length > 0 && (
                <div>
                  <h2
                    style={{
                      margin: '0 0 12px',
                      fontFamily: 'var(--font-display)',
                      fontWeight: 500,
                      fontSize: '15px',
                      color: 'var(--hachi-muted)',
                    }}
                  >
                    Sessions — pick up where you left off
                  </h2>
                  <div
                    style={{
                      background: 'var(--hachi-surface)',
                      border: '0.5px solid var(--hachi-line)',
                      borderRadius: '14px',
                      overflow: 'hidden',
                    }}
                  >
                    {sessionRows.map((s, i) => (
                      <div
                        key={s.id}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '13px',
                          padding: '13px 16px',
                          borderBottom:
                            i < sessionRows.length - 1
                              ? '0.5px solid var(--hachi-line)'
                              : undefined,
                        }}
                      >
                        <span style={{ color: 'var(--hachi-muted)', display: 'inline-flex' }}>
                          <Icon name={s.icon} size={16} />
                        </span>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: '14px' }}>{s.title}</div>
                          <div
                            style={{
                              fontSize: '12px',
                              color: 'var(--hachi-muted)',
                              marginTop: '2px',
                            }}
                          >
                            {s.turnsLabel} · {s.model} · {s.date}
                          </div>
                        </div>
                        <TextBtn
                          onClick={() => { void s.resume() }}
                          style={{
                            height: '32px',
                            padding: '0 13px',
                            borderRadius: '9px',
                            border: '0.5px solid var(--hachi-line)',
                            background: 'var(--hachi-canvas)',
                            color: 'var(--hachi-ink)',
                            font: '500 13px var(--font-body)',
                            cursor: 'pointer',
                          }}
                          hoverStyle={{ background: 'var(--hachi-cream)' }}
                        >
                          {s.label}
                        </TextBtn>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* ---- empty audit state ---- */}
              {blocked.length === 0 && skillRows.length === 0 && sessionRows.length === 0 && (
                <div
                  style={{
                    textAlign: 'center',
                    padding: '60px 0',
                    color: 'var(--hachi-muted)',
                    fontSize: '14px',
                  }}
                >
                  No audit data yet — history will appear here as Hachi works.
                </div>
              )}
            </>
          )}

        </div>
      </div>
    </div>
  )
}

export const Route = createFileRoute('/memory')({
  component: Memory,
})
