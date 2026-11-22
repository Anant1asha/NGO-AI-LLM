// Hachi TUI (Textual) — full-screen terminal layout: header, runs panel, output log, leash dialog, footer.
// Colors are the dark-surface literals (the TUI is always dark).
const TUI = {
  canvas: "#16151A", surface: "#201E25", line: "#322F38",
  ink: "#FBF7EF", muted: "#9C968C", brand: "#E25A44",
  amber: "#E0922E", green: "#3F9D6B", danger: "#E0594A", navy: "#7C9BD1",
};

function Panel({ title, accent = TUI.muted, children, style = {} }) {
  return (
    <div style={{ position: "relative", border: `1px solid ${TUI.line}`, borderRadius: 8, background: TUI.surface, padding: "14px 14px 12px", ...style }}>
      <span style={{ position: "absolute", top: -9, left: 12, padding: "0 6px", background: TUI.surface, color: accent, fontSize: 12 }}>{title}</span>
      {children}
    </div>
  );
}

function RunRow({ run, active, onClick }) {
  const dot = { working: TUI.amber, "on-watch": TUI.navy, done: TUI.green, blocked: TUI.danger }[run.status];
  const word = { working: "working", "on-watch": "on watch", done: "done", blocked: "blocked" }[run.status];
  return (
    <div onClick={onClick} style={{
      display: "flex", alignItems: "center", gap: 8, padding: "5px 8px", borderRadius: 5, cursor: "pointer",
      background: active ? TUI.canvas : "transparent", color: active ? TUI.ink : TUI.muted,
      borderLeft: `2px solid ${active ? TUI.brand : "transparent"}`,
    }}>
      <span style={{ color: dot }}>●</span>
      <span style={{ flex: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{run.title}</span>
      <span style={{ color: dot, fontSize: 12 }}>{word}</span>
    </div>
  );
}

function LeashDialog({ onChoose }) {
  const [hov, setHov] = React.useState(null);
  const btn = (key, label, idx, color) => (
    <button onClick={() => onChoose(label)} onMouseEnter={() => setHov(idx)} onMouseLeave={() => setHov(null)}
      style={{
        fontFamily: "inherit", fontSize: 13, cursor: "pointer",
        padding: "5px 12px", borderRadius: 5, border: `1px solid ${hov === idx ? color : TUI.line}`,
        background: hov === idx ? color : "transparent", color: hov === idx ? TUI.canvas : color,
      }}>
      <span style={{ opacity: 0.7 }}>{key}</span> {label}
    </button>
  );
  return (
    <div style={{ position: "absolute", inset: 0, background: "rgba(10,9,12,0.55)", display: "grid", placeItems: "center", borderRadius: 8 }}>
      <div style={{ width: 440, border: `1px solid ${TUI.brand}`, borderRadius: 8, background: TUI.surface, padding: 18 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, color: TUI.ink, fontSize: 14, marginBottom: 4 }}>
          <span style={{ color: TUI.brand }}>▸</span> Hachi wants to run a command
        </div>
        <div style={{ color: TUI.muted, fontSize: 12, marginBottom: 12 }}>why: install the dependencies for your build</div>
        <div style={{ background: TUI.canvas, border: `1px solid ${TUI.line}`, borderRadius: 5, padding: "9px 12px", color: TUI.ink, marginBottom: 14 }}>
          <span style={{ color: TUI.brand }}>hachi ▸</span> npm install
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {btn("d", "Deny", 0, TUI.navy)}
          {btn("a", "Allow once", 1, TUI.brand)}
          {btn("A", "Always allow", 2, TUI.muted)}
        </div>
        <div style={{ color: TUI.muted, fontSize: 12, marginTop: 12, borderTop: `1px solid ${TUI.line}`, paddingTop: 10 }}>you hold the leash</div>
      </div>
    </div>
  );
}

function FooterKey({ k, label }) {
  return (
    <span style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
      <span style={{ color: TUI.brand }}>{k}</span>
      <span style={{ color: TUI.muted }}>{label}</span>
    </span>
  );
}

const RUNS = [
  { id: 1, title: "Refactor auth module", status: "working" },
  { id: 2, title: "Migrate tests to Vitest", status: "on-watch" },
  { id: 3, title: "Generate API docs", status: "done" },
  { id: 4, title: "Audit dependencies", status: "blocked" },
];

function Tui() {
  const [active, setActive] = React.useState(1);
  const [dialog, setDialog] = React.useState(true);
  const [log, setLog] = React.useState([
    { t: "hachi ▸ run refactor --watch", c: TUI.ink },
    { t: "→ scanning src/auth (12 files)", c: TUI.muted },
    { t: "✓ session.ts — extracted token guard", c: TUI.green },
    { t: "on watch · spent $0.02 of $1.00", c: TUI.muted },
  ]);

  const choose = (label) => {
    setDialog(false);
    const line = label === "Deny"
      ? { t: "✗ denied — Hachi is resting", c: TUI.danger }
      : { t: "✓ allowed — running npm install", c: TUI.green };
    setLog((l) => [...l, line]);
  };

  return (
    <div style={{
      fontFamily: "var(--font-mono)", fontSize: 13, lineHeight: "22px",
      background: TUI.canvas, color: TUI.ink, height: "100%", display: "flex", flexDirection: "column",
    }}>
      {/* header */}
      <div style={{ display: "flex", alignItems: "center", padding: "8px 14px", background: TUI.surface, borderBottom: `1px solid ${TUI.line}` }}>
        <span style={{ color: TUI.brand }}>hachi&nbsp;▸</span>
        <span style={{ color: TUI.muted, marginLeft: 10 }}>on watch</span>
        <span style={{ flex: 1 }} />
        <span style={{ color: TUI.muted }}>spent $0.41 of $5.00</span>
        <span style={{ color: TUI.line, margin: "0 10px" }}>│</span>
        <span style={{ color: TUI.muted }}>14:22</span>
      </div>

      {/* body */}
      <div style={{ flex: 1, display: "flex", gap: 12, padding: 14, minHeight: 0, position: "relative" }}>
        <Panel title=" runs · 4 " accent={TUI.brand} style={{ width: 280, flexShrink: 0 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            {RUNS.map((r) => <RunRow key={r.id} run={r} active={active === r.id} onClick={() => setActive(r.id)} />)}
          </div>
        </Panel>

        <Panel title=" output · refactor auth module " accent={TUI.muted} style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
            {log.map((l, i) => <div key={i} style={{ color: l.c }}>{l.t}</div>)}
            <div style={{ display: "flex", gap: 8, marginTop: 2 }}>
              <span style={{ color: TUI.brand }}>hachi ▸</span>
              <span style={{ width: 8, height: 15, background: TUI.brand, display: "inline-block", animation: "hachi-caret 1s steps(1) infinite" }} />
            </div>
          </div>
        </Panel>

        {dialog && <LeashDialog onChoose={choose} />}
      </div>

      {/* footer */}
      <div style={{ display: "flex", gap: 20, padding: "7px 14px", background: TUI.surface, borderTop: `1px solid ${TUI.line}` }}>
        <FooterKey k="^n" label="new run" />
        <FooterKey k="^p" label="the pack" />
        <FooterKey k="^k" label="the kennel" />
        <FooterKey k="^l" label="leash" />
        <FooterKey k="^q" label="quit" />
      </div>
      <style>{`@keyframes hachi-caret{50%{opacity:0}}`}</style>
    </div>
  );
}

window.Tui = Tui;
