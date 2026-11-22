import { CSSProperties, ReactNode, UIEvent, useEffect, useRef, useState } from 'react';

export type TerminalLineTone = 'default' | 'muted' | 'brand' | 'working' | 'success' | 'danger';

export interface TerminalLine {
  text: string;
  /** One of TerminalLineTone; accepts any string and falls back to the default color. */
  tone?: string;
}

export interface TerminalProps {
  lines?: TerminalLine[];
  prompt?: string;
  children?: ReactNode;
  style?: CSSProperties;
  /** When false: hides the blinking caret and renders "run ended" in the prompt bar. Default true. */
  streaming?: boolean;
}

const TONE_COLOR: Record<TerminalLineTone, string> = {
  default: '#FBF7EF',
  muted: '#9C968C',
  brand: '#E25A44',
  working: '#E0922E',
  success: '#3F9D6B',
  danger: '#C0392B',
};

export function Terminal({ lines = [], prompt, children, style, streaming = true }: TerminalProps) {
  const outputRef = useRef<HTMLDivElement>(null);
  // Both state (for pill re-render) and ref (for rAF pin without stale reads).
  const [following, setFollowing] = useState(true);
  const followOutputRef = useRef(true);
  const scrollRafRef = useRef<number | null>(null);

  useEffect(() => {
    if (!followOutputRef.current) return;
    if (scrollRafRef.current != null) return;
    const schedule =
      typeof requestAnimationFrame === 'function'
        ? requestAnimationFrame
        : ((cb: FrameRequestCallback) => setTimeout(cb, 16) as unknown as number);
    scrollRafRef.current = schedule(() => {
      const el = outputRef.current;
      if (el) el.scrollTop = el.scrollHeight;
      scrollRafRef.current = null;
    });
  }, [lines]);

  useEffect(() => {
    return () => {
      if (scrollRafRef.current != null) {
        if (typeof cancelAnimationFrame === 'function') {
          cancelAnimationFrame(scrollRafRef.current);
        } else {
          clearTimeout(scrollRafRef.current as unknown as ReturnType<typeof setTimeout>);
        }
      }
    };
  }, []);

  const handleOutputScroll = (event: UIEvent<HTMLDivElement>) => {
    const el = event.currentTarget;
    const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 96;
    followOutputRef.current = isNearBottom;
    setFollowing(isNearBottom);
  };

  const jumpToLatest = () => {
    const el = outputRef.current;
    if (el) el.scrollTop = el.scrollHeight;
    followOutputRef.current = true;
    setFollowing(true);
    el?.focus();
  };

  const surfaceStyle: CSSProperties = {
    background: '#16151A',
    borderRadius: 'var(--radius-lg)',
    border: '0.5px solid #2A2730',
    fontFamily: 'var(--font-mono)',
    fontSize: 'var(--type-mono-size)',
    lineHeight: 'var(--type-mono-lh)',
    color: '#FBF7EF',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    position: 'relative',
    ...style,
  };

  const outputStyle: CSSProperties = {
    flex: 1,
    overflowY: 'auto',
    padding: 'var(--space-4)',
    paddingBottom: 'var(--space-2)',
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
  };

  const promptBarStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--space-2)',
    padding: 'var(--space-2) var(--space-4)',
    borderTop: '0.5px solid #2A2730',
    minHeight: '36px',
  };

  const promptLabelStyle: CSSProperties = {
    color: streaming ? '#E25A44' : 'var(--hachi-muted)',
    fontWeight: 'var(--weight-medium)' as CSSProperties['fontWeight'],
    userSelect: 'none',
    flexShrink: 0,
  };

  const promptTextStyle: CSSProperties = {
    color: '#FBF7EF',
    flexGrow: 1,
    minWidth: 0,
  };

  return (
    <div style={surfaceStyle}>
      {/* output lines */}
      <div
        ref={outputRef}
        onScroll={handleOutputScroll}
        style={outputStyle}
        role="log"
        aria-live="polite"
        aria-atomic="false"
        tabIndex={0}
        aria-label="Run output"
      >
        {lines.map((line, i) => (
          <div
            key={i}
            style={{
              color: TONE_COLOR[(line.tone ?? 'default') as TerminalLineTone] ?? TONE_COLOR.default,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-all',
            }}
          >
            {line.text}
          </div>
        ))}
        {children}
      </div>

      {/* Jump to latest pill — shown when user has scrolled away mid-stream */}
      {!following && streaming && (
        <button
          type="button"
          onClick={jumpToLatest}
          style={{
            position: 'absolute',
            bottom: '48px',
            left: '50%',
            transform: 'translateX(-50%)',
            background: '#2A2730',
            border: '0.5px solid #3A3740',
            borderRadius: 'var(--radius-pill)',
            color: '#FBF7EF',
            fontSize: '12px',
            fontFamily: 'var(--font-mono)',
            padding: '4px 12px',
            cursor: 'pointer',
            whiteSpace: 'nowrap',
            zIndex: 1,
          }}
        >
          ↓ Latest
        </button>
      )}

      {/* prompt bar */}
      <div style={promptBarStyle}>
        <span style={promptLabelStyle}>hachi ▸</span>
        {!streaming ? (
          <span style={{ color: 'var(--hachi-muted)', fontSize: 'var(--type-mono-size)' }}>
            run ended
          </span>
        ) : (
          <>
            {prompt !== undefined && (
              <span style={promptTextStyle}>{prompt}</span>
            )}
            {/* blinking caret — className enables the reduced-motion rule */}
            <span
              className="hachi-caret"
              style={{
                display: 'inline-block',
                width: '8px',
                height: '14px',
                background: '#E25A44',
                animation: 'hachi-caret-blink 1s step-end infinite',
                flexShrink: 0,
                alignSelf: 'center',
              }}
              aria-hidden="true"
            />
          </>
        )}
      </div>

      <style>{`
        @keyframes hachi-caret-blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
        @media (prefers-reduced-motion: reduce) {
          [class*="hachi-caret"] { animation: none !important; }
        }
      `}</style>
    </div>
  );
}
