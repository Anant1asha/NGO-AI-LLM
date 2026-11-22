// ============================================================
// Review screen — /review   (eval loop)
// Lists agent interaction turns; lets the user rate each thumbs-up/down
// with optional notes, wired to:
//   GET  /interactions
//   PUT  /interactions/{id}/rating
// ============================================================

import { useState, useEffect } from 'react';
import { createFileRoute } from '@tanstack/react-router';
import { useStore } from '../lib/store/store';
import { Icon } from '../components/icons/Icon';
import { Markdown } from '../components/ui/Markdown';
import type { AgentInteraction } from '../lib/data/types';
import { loadInteractions, rateInteraction } from '../lib/data/domains/interactions';
import { extractInjectedAttachments } from '../lib/data/domains/chat';
import { PendingCard } from '../components/ui/PendingCard';
import { fmtUSD, fmtTokens } from '../lib/ui/format';

// ---- sub-component: a single interaction card ----

function InteractionCard({ ix }: { ix: AgentInteraction }) {
  const [notesOpen, setNotesOpen] = useState(false);
  const [notesValue, setNotesValue] = useState(ix.notes ?? '');

  async function handleRate(r: 'up' | 'down') {
    await rateInteraction(ix.id, r, notesValue.trim() || undefined);
  }

  return (
    <div
      style={{
        background: 'var(--hachi-surface)',
        border: '0.5px solid var(--hachi-line)',
        borderRadius: 14,
        padding: 18,
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}
    >
      {/* meta row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          fontSize: 12,
          color: 'var(--hachi-muted)',
          flexWrap: 'wrap',
        }}
      >
        <span style={{ fontFamily: 'var(--font-mono)' }}>{ix.tsHuman}</span>
        {ix.modelUsed && (
          <>
            <span style={{ opacity: 0.4 }}>·</span>
            <span>{ix.modelUsed}</span>
          </>
        )}
        {ix.tokenCost != null && (
          <>
            <span style={{ opacity: 0.4 }}>·</span>
            <span style={{ fontVariantNumeric: 'tabular-nums' }}>{ix.tokenCost != null ? fmtUSD(ix.tokenCost) : '—'}</span>
          </>
        )}
        {ix.tokens != null && (
          <>
            <span style={{ opacity: 0.4 }}>·</span>
            <span style={{ fontVariantNumeric: 'tabular-nums' }}>{ix.tokens != null ? fmtTokens(ix.tokens) : '—'} tok</span>
          </>
        )}
        <div style={{ flex: 1 }} />
        {/* current rating badge */}
        {ix.rating === 'up' && (
          <span style={{ color: 'var(--hachi-trust)', display: 'inline-flex', gap: 4, alignItems: 'center' }}>
            <Icon name="arrow-up" size={13} />
            thumbs up
          </span>
        )}
        {ix.rating === 'down' && (
          <span style={{ color: 'var(--hachi-danger, #c0392b)', display: 'inline-flex', gap: 4, alignItems: 'center' }}>
            <Icon name="arrow-up" size={13} style={{ transform: 'rotate(180deg)' }} />
            thumbs down
          </span>
        )}
      </div>

      {/* user input */}
      {ix.userInput && (
        <div>
          <div style={{ fontSize: 11, color: 'var(--hachi-muted)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            You
          </div>
          <div
            style={{
              background: 'var(--hachi-canvas)',
              border: '0.5px solid var(--hachi-line)',
              borderRadius: 10,
              padding: '10px 14px',
              fontSize: 13,
              color: 'var(--hachi-ink)',
              lineHeight: '20px',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {extractInjectedAttachments(ix.userInput).text}
          </div>
        </div>
      )}

      {/* agent output */}
      {ix.agentOutput && (
        <div>
          <div style={{ fontSize: 11, color: 'var(--hachi-muted)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Hachi
          </div>
          <div
            style={{
              background: 'var(--hachi-surface)',
              border: '0.5px solid var(--hachi-line)',
              borderRadius: 10,
              padding: '10px 14px',
              fontSize: 13,
              color: 'var(--hachi-ink)',
              lineHeight: '20px',
              wordBreak: 'break-word',
              maxHeight: 200,
              overflow: 'auto',
            }}
            className="hachi-scroll"
          >
            <Markdown text={ix.agentOutput} />
          </div>
        </div>
      )}

      {/* tool calls + memory hits (string lists) */}
      {(ix.toolCalls.length > 0 || ix.memoryHits.length > 0) && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {ix.toolCalls.map((tc, i) => (
            <span
              key={i}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                fontSize: 11,
                color: 'var(--hachi-ink)',
                background: 'var(--hachi-canvas)',
                border: '0.5px solid var(--hachi-line)',
                borderRadius: 6,
                padding: '2px 8px',
                fontFamily: 'var(--font-mono)',
              }}
            >
              <Icon name="terminal" size={11} />
              {tc}
            </span>
          ))}
          {ix.memoryHits.map((mh, i) => (
            <span
              key={i}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                fontSize: 11,
                color: 'var(--hachi-trust)',
                background: 'var(--hachi-trust-tint)',
                border: '0.5px solid var(--hachi-trust)',
                borderRadius: 6,
                padding: '2px 8px',
              }}
            >
              <Icon name="memory" size={11} />
              {mh}
            </span>
          ))}
        </div>
      )}

      {/* rating row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 2 }}>
        <button
          type="button"
          className="hachi-rating-btn"
          aria-label="Thumbs up"
          aria-pressed={ix.rating === 'up'}
          onClick={() => void handleRate('up')}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 5,
            height: 32,
            padding: '0 12px',
            borderRadius: 10,
            border: ix.rating === 'up' ? '1px solid var(--hachi-trust)' : '0.5px solid var(--hachi-line)',
            background: ix.rating === 'up' ? 'var(--hachi-trust-tint)' : undefined,
            color: ix.rating === 'up' ? 'var(--hachi-trust)' : 'var(--hachi-muted)',
            font: '500 12px var(--font-body)',
            cursor: 'pointer',
            transition: 'background var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease)',
          }}
        >
          <Icon name="arrow-up" size={13} />
          Good
        </button>

        <button
          type="button"
          className="hachi-rating-btn"
          aria-label="Thumbs down"
          aria-pressed={ix.rating === 'down'}
          onClick={() => void handleRate('down')}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 5,
            height: 32,
            padding: '0 12px',
            borderRadius: 10,
            border: ix.rating === 'down' ? '1px solid var(--hachi-danger, #c0392b)' : '0.5px solid var(--hachi-line)',
            background: ix.rating === 'down'
              ? 'color-mix(in srgb, var(--hachi-danger, #c0392b) 10%, transparent)'
              : undefined,
            color: ix.rating === 'down' ? 'var(--hachi-danger, #c0392b)' : 'var(--hachi-muted)',
            font: '500 12px var(--font-body)',
            cursor: 'pointer',
            transition: 'background var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease)',
          }}
        >
          <Icon name="arrow-up" size={13} style={{ transform: 'rotate(180deg)' }} />
          Poor
        </button>

        {/* notes toggle */}
        <button
          type="button"
          onClick={() => setNotesOpen((v) => !v)}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 5,
            height: 32,
            padding: '0 12px',
            borderRadius: 10,
            border: '0.5px solid var(--hachi-line)',
            background: notesOpen ? 'var(--hachi-cream)' : 'var(--hachi-canvas)',
            color: 'var(--hachi-muted)',
            font: '12px var(--font-body)',
            cursor: 'pointer',
          }}
          aria-expanded={notesOpen}
        >
          <Icon name="pencil" size={12} />
          {ix.notes ? 'Edit note' : 'Add note'}
        </button>

        {ix.notes && !notesOpen && (
          <span
            style={{
              fontSize: 12,
              color: 'var(--hachi-muted)',
              fontStyle: 'italic',
              flex: 1,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {ix.notes}
          </span>
        )}
      </div>

      {/* notes input */}
      {notesOpen && (
        <div style={{ display: 'flex', gap: 8 }}>
          <textarea
            value={notesValue}
            onChange={(e) => setNotesValue(e.target.value)}
            placeholder="Add a note about this turn…"
            aria-label="Add a note about this turn"
            rows={2}
            style={{
              flex: 1,
              padding: '8px 12px',
              borderRadius: 10,
              border: '0.5px solid var(--hachi-line)',
              background: 'var(--hachi-canvas)',
              color: 'var(--hachi-ink)',
              font: '13px var(--font-body)',
              resize: 'vertical',
              outline: 'none',
            }}
          />
          <button
            type="button"
            onClick={() => {
              // Save with the current rating (or "up" if unrated) + note.
              void rateInteraction(ix.id, ix.rating ?? 'up', notesValue.trim() || undefined);
              setNotesOpen(false);
            }}
            style={{
              height: 36,
              padding: '0 14px',
              borderRadius: 10,
              border: '1px solid var(--hachi-trust)',
              background: 'var(--hachi-trust-tint)',
              color: 'var(--hachi-trust)',
              font: '500 13px var(--font-body)',
              cursor: 'pointer',
              alignSelf: 'flex-start',
              marginTop: 1,
            }}
          >
            Save
          </button>
        </div>
      )}
    </div>
  );
}

// ---- main screen ----

function Review() {
  const interactions = useStore((s) => s.interactions) as AgentInteraction[];
  const loadedReview = useStore((s) => s.loaded.review);

  useEffect(() => { void loadInteractions(); }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* header bar */}
      <div
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
          Review
        </h1>
        <span style={{ fontSize: 13, color: 'var(--hachi-muted)' }}>
          rate each turn to improve Hachi
        </span>
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 12, color: 'var(--hachi-muted)' }}>
          {interactions.length} turn{interactions.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* scrollable body */}
      <div
        className="hachi-scroll"
        style={{ flex: 1, overflow: 'auto', padding: '24px 32px 64px' }}
      >
        <div style={{ maxWidth: 880, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 12 }}>
          {!loadedReview ? (
            <PendingCard label="Loading interactions…" />
          ) : interactions.length === 0 ? (
            <div
              style={{
                background: 'var(--hachi-surface)',
                border: '0.5px solid var(--hachi-line)',
                borderRadius: 14,
                padding: '48px 24px',
                textAlign: 'center',
                color: 'var(--hachi-muted)',
                fontSize: 14,
              }}
            >
              <div style={{ marginBottom: 8 }}>
                <Icon name="eye" size={28} />
              </div>
              No interactions to review yet — start a conversation with Hachi.
            </div>
          ) : (
            interactions.map((ix) => (
              <InteractionCard key={ix.id} ix={ix} />
            ))
          )}
        </div>
      </div>
    </div>
  );
}

export const Route = createFileRoute('/review')({
  component: Review,
});
