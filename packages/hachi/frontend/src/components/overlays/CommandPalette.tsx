// ============================================================
// CommandPalette — global ⌘K / Ctrl+K overlay
// ============================================================

import React, { useEffect, useRef, useState, CSSProperties } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { useStore } from '../../lib/store/store';
import { Icon } from '../icons/Icon';
import { useFocusTrap } from '../../lib/hooks/useFocusTrap';

// ---- nav route map ----
const navRoutes: Record<string, string> = {
  home:         '/',
  chat:         '/conversation',
  work:         '/work',
  approvals:    '/approvals',
  memory:       '/memory',
  skills:       '/skills',
  og:           '/og',
  authoring:    '/authoring',
  integrations: '/integrations',
  review:       '/review',
  settings:     '/settings',
};

function safeRoute(key: string): string {
  const route = navRoutes[key];
  if (!route && import.meta.env.DEV) {
    console.warn('[CommandPalette] unknown nav key:', key);
  }
  return route ?? '/';
}

const navMeta = [
  { key: 'home',         label: 'Today',         icon: 'home' },
  { key: 'chat',         label: 'Conversation',   icon: 'chat' },
  { key: 'work',         label: 'Work',           icon: 'work' },
  { key: 'approvals',    label: 'The leash',      icon: 'leash' },
  { key: 'memory',       label: 'Memory',         icon: 'memory' },
  { key: 'skills',       label: 'The library',    icon: 'skills' },
  { key: 'og',           label: 'OG explorer',    icon: 'network' },
  { key: 'authoring',    label: 'Authoring',      icon: 'file-code' },
  { key: 'integrations', label: 'Integrations',   icon: 'plug' },
  { key: 'review',       label: 'Review',         icon: 'star' },
  { key: 'settings',     label: 'Settings',       icon: 'settings' },
];

// ---- fuzzy scorer ----
// Subsequence match: every char of query must appear in label in order.
// Score: +3 word-start, +2 consecutive, +1 plain match; -0.1 per gap char.
// Returns -1 for no match.
export function fuzzyScore(query: string, label: string): number {
  if (!query) return 0;
  const q = query.toLowerCase();
  const l = label.toLowerCase();
  let qi = 0;
  let score = 0;
  let prev = -2; // initialize so first char gap is 0
  for (let li = 0; li < l.length && qi < q.length; li++) {
    if (l[li] === q[qi]) {
      const isWordStart = li === 0 || l[li - 1] === ' ' || l[li - 1] === '-';
      const isConsecutive = prev === li - 1;
      const charScore = isWordStart ? 3 : isConsecutive ? 2 : 1;
      const gapPenalty = Math.max(0, (li - prev - 1)) * 0.1;
      score += charScore - gapPenalty;
      prev = li;
      qi++;
    }
  }
  return qi === q.length ? score : -1;
}

// ---- recent commands (localStorage) ----
const RECENTS_KEY = 'hachi.palette.recents';
const MAX_RECENTS = 5;

function getRecents(): string[] {
  try {
    return JSON.parse(localStorage.getItem(RECENTS_KEY) ?? '[]');
  } catch {
    return [];
  }
}

function pushRecent(label: string) {
  const prev = getRecents().filter((l) => l !== label);
  const next = [label, ...prev].slice(0, MAX_RECENTS);
  try { localStorage.setItem(RECENTS_KEY, JSON.stringify(next)); } catch { /* quota */ }
}

export function CommandPalette() {
  const open               = useStore((s) => s.palette.open);
  const query              = useStore((s) => s.palette.query);
  const closePalette       = useStore((s) => s.closePalette);
  const setPaletteQuery    = useStore((s) => s.setPaletteQuery);
  const openPalette        = useStore((s) => s.openPalette);
  const openSetup          = useStore((s) => s.openSetup);
  const simulateReconnect  = useStore((s) => s.simulateReconnect);
  const openRun            = useStore((s) => s.openRun);
  const startTask          = useStore((s) => s.startTask);
  const sessions           = useStore((s) => s.sessions);
  const switchSession      = useStore((s) => s.switchSession);

  const [activeIndex, setActiveIndex] = useState<number>(0);

  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const trapRef  = useFocusTrap<HTMLDivElement>(open);

  // Global ⌘K / Ctrl+K toggle + Esc to close
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        if (open) { closePalette(); } else { openPalette(); }
      }
      if (e.key === 'Escape') closePalette();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, closePalette, openPalette]);

  // Focus input when opened; reset active index when palette opens/closes.
  useEffect(() => {
    if (open && inputRef.current) inputRef.current.focus();
    if (!open) setActiveIndex(0);
  }, [open]);

  if (!open) return null;

  const pq = query.trim().toLowerCase();

  const go = (route: string) => { closePalette(); navigate({ to: route }); };

  const execItem = (item: PaletteItemData) => {
    pushRecent(item.label);
    item.go();
  };

  const placesAll = navMeta.map((n) => ({
    label: 'Go to ' + n.label,
    icon: n.icon,
    shortcut: null as string | null,
    go: () => go(safeRoute(n.key)),
  }));

  const actionsAll = [
    { label: 'Start a new task',               icon: 'plus',     shortcut: 'N',  go: () => go('/conversation') },
    { label: 'Watch a live run',               icon: 'eye',      shortcut: null, go: () => { closePalette(); openRun(undefined, 'home'); } },
    { label: 'Create a routine',               icon: 'repeat',   shortcut: null, go: () => { closePalette(); startTask('Every weekday at 8, summarise my inbox and message me the urgent ones'); navigate({ to: '/conversation' }); } },
    { label: 'Tighten a spend limit',          icon: 'dollar',   shortcut: null, go: () => go('/settings') },
    { label: 'Connect an account',             icon: 'plug',     shortcut: null, go: () => go('/integrations') },
    { label: 'Re-run setup',                   icon: 'sparkles', shortcut: null, go: () => { closePalette(); openSetup(); } },
    { label: 'Preview the reconnecting state', icon: 'refresh',  shortcut: null, go: () => { closePalette(); simulateReconnect(); } },
  ];

  const recentSessions = sessions.slice(0, 3).map((sess) => ({
    label: sess.title,
    icon: 'chat' as string,
    shortcut: null as string | null,
    go: () => { switchSession(sess.id); closePalette(); navigate({ to: '/conversation' }); },
  }));

  // Fuzzy filter + sort — score > 0 means "matches"
  const fuzzyFilt = <T extends { label: string }>(arr: T[]): T[] => {
    if (!pq) return arr;
    return arr
      .map((x) => ({ x, score: fuzzyScore(pq, x.label) }))
      .filter(({ score }) => score >= 0)
      .sort((a, b) => b.score - a.score)
      .map(({ x }) => x);
  };

  // When query is empty, show recent commands first (from localStorage)
  const recentLabels = pq ? [] : getRecents();
  const allItems = [...placesAll, ...actionsAll, ...recentSessions];
  const recentItemsAll = recentLabels
    .map((lbl) => allItems.find((i) => i.label === lbl))
    .filter(Boolean) as PaletteItemData[];

  const paletteGroups = pq
    ? [
        { title: 'Go to',  items: fuzzyFilt(placesAll) },
        { title: 'Do',     items: fuzzyFilt(actionsAll) },
        { title: 'Recent', items: fuzzyFilt(recentSessions) },
      ].filter((g) => g.items.length > 0)
    : [
        recentItemsAll.length > 0 ? { title: 'Recent', items: recentItemsAll } : null,
        { title: 'Go to',  items: placesAll },
        { title: 'Do',     items: actionsAll },
        recentSessions.length > 0 ? { title: 'Conversations', items: recentSessions } : null,
      ].filter(Boolean) as { title: string; items: PaletteItemData[] }[];

  const isEmpty = paletteGroups.length === 0;
  const flatItems = paletteGroups.flatMap((g) => g.items);

  const handleQueryChange = (v: string) => {
    setPaletteQuery(v);
    setActiveIndex(0); // reset to first when query changes
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((i) => {
        const next = i + 1;
        return next >= flatItems.length ? 0 : next; // wrap
      });
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((i) => {
        const next = i - 1;
        return next < 0 ? flatItems.length - 1 : next; // wrap
      });
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const item = flatItems[activeIndex] ?? flatItems[0];
      if (item) execItem(item);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      closePalette();
    }
  };

  const activeItemId = activeIndex >= 0 ? `palette-item-${activeIndex}` : undefined;

  const backdropStyle: CSSProperties = {
    position: 'fixed', inset: 0, background: 'rgba(28,26,32,.45)',
    display: 'flex', justifyContent: 'center', alignItems: 'flex-start',
    paddingTop: '14vh', zIndex: 50,
  };
  const panelStyle: CSSProperties = {
    width: 560, maxWidth: '92vw', background: 'var(--hachi-surface)',
    border: '0.5px solid var(--hachi-line)', borderRadius: 16, overflow: 'hidden',
    boxShadow: '0 24px 60px rgba(28,26,32,.22)',
  };
  const inputRowStyle: CSSProperties = {
    display: 'flex', alignItems: 'center', gap: 11, padding: '16px 18px',
    borderBottom: '0.5px solid var(--hachi-line)',
  };
  const escPillStyle: CSSProperties = {
    fontFamily: 'var(--font-mono)', fontSize: 11, border: '0.5px solid var(--hachi-line)',
    borderRadius: 5, padding: '2px 6px', color: 'var(--hachi-muted)',
  };
  const listStyle: CSSProperties = { maxHeight: '50vh', overflow: 'auto', padding: 8 };
  const groupLabelStyle: CSSProperties = {
    padding: '8px 10px 4px', fontSize: 12, color: 'var(--hachi-muted)',
  };

  return (
    <div style={backdropStyle} onClick={closePalette}>
      <div
        ref={trapRef}
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        style={panelStyle}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={inputRowStyle}>
          <Icon name="search" size={18} style={{ color: 'var(--hachi-muted)' }} />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => handleQueryChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Jump to a place, or do something…"
            style={{ flex: 1, border: 'none', background: 'transparent', font: 'inherit', fontSize: 16, color: 'var(--hachi-ink)', outline: 'none' }}
            role="combobox"
            aria-expanded={!isEmpty}
            aria-controls="palette-listbox"
            aria-autocomplete="list"
            aria-activedescendant={activeItemId}
          />
          <span style={escPillStyle}>esc</span>
        </div>

        <div
          id="palette-listbox"
          role="listbox"
          aria-label="Commands"
          className="hachi-scroll"
          style={listStyle}
        >
          {(() => {
            let flatIdx = 0;
            return paletteGroups.map((grp) => (
              <div key={grp.title}>
                <div style={groupLabelStyle}>{grp.title}</div>
                {grp.items.map((item) => {
                  const idx = flatIdx++;
                  return (
                    <PaletteItem
                      key={item.label}
                      item={item}
                      id={`palette-item-${idx}`}
                      active={activeIndex === idx}
                      onHover={() => setActiveIndex(idx)}
                      onActivate={() => execItem(item)}
                    />
                  );
                })}
              </div>
            ));
          })()}
          {isEmpty && (
            <div style={{ padding: 20, textAlign: 'center', color: 'var(--hachi-muted)', fontSize: 14 }}>
              Nothing matches "{query}".
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

interface PaletteItemData {
  label: string;
  icon: string;
  shortcut: string | null;
  go: () => void;
}

function PaletteItem({
  item, id, active, onHover, onActivate,
}: {
  item: PaletteItemData;
  id: string;
  active: boolean;
  onHover: () => void;
  onActivate: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  // Scroll into view when this item becomes active via keyboard
  useEffect(() => {
    if (active) ref.current?.scrollIntoView({ block: 'nearest' });
  }, [active]);

  return (
    <div
      ref={ref}
      id={id}
      role="option"
      aria-selected={active}
      // onMouseDown prevents the input from losing focus on click
      onMouseDown={(e) => e.preventDefault()}
      onClick={onActivate}
      onMouseEnter={onHover}
      style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '10px 12px', borderRadius: 10, cursor: 'pointer',
        background: active ? 'var(--hachi-cream)' : 'transparent',
        transition: 'background var(--dur-fast) var(--ease)',
      }}
    >
      <span style={{ color: 'var(--hachi-muted)', display: 'inline-flex' }}>
        <Icon name={item.icon} size={17} />
      </span>
      <span style={{ flex: 1, fontSize: 14, color: 'var(--hachi-ink)' }}>
        {item.label}
      </span>
      {item.shortcut && (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--hachi-muted)', border: '0.5px solid var(--hachi-line)', borderRadius: 5, padding: '1px 6px' }}>
          {item.shortcut}
        </span>
      )}
    </div>
  );
}
