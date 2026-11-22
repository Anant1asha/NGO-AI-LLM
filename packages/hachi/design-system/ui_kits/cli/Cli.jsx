// Hachi CLI — a realistic terminal transcript in a window frame. Self-contained dark surface.
const C = {
  canvas: "#16151A", bar: "#201E25", line: "#322F38",
  ink: "#FBF7EF", muted: "#9C968C", brand: "#E25A44",
  amber: "#E0922E", green: "#3F9D6B", navy: "#7C9BD1", danger: "#E0594A",
};

function L({ children, color = C.ink, style = {} }) {
  return <div style={{ color, whiteSpace: "pre-wrap", ...style }}>{children}</div>;
}
function Prompt({ children }) {
  return <div><span style={{ color: C.green }}>~/acme/api</span> <span style={{ color: C.muted }}>$</span> {children}</div>;
}

function Cli() {
  return (
    <div style={{ height: "100%", display: "grid", placeItems: "center", padding: 28, boxSizing: "border-box", background: "var(--surface-page)" }}>
      <div style={{ width: 760, maxWidth: "100%", borderRadius: "var(--radius-lg)", overflow: "hidden", border: "0.5px solid var(--hachi-line)", background: C.canvas }}>
        {/* window chrome */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 14px", background: C.bar, borderBottom: `1px solid ${C.line}` }}>
          <span style={{ width: 11, height: 11, borderRadius: "50%", background: "#E0594A" }} />
          <span style={{ width: 11, height: 11, borderRadius: "50%", background: "#E0922E" }} />
          <span style={{ width: 11, height: 11, borderRadius: "50%", background: "#3F9D6B" }} />
          <span style={{ flex: 1, textAlign: "center", color: C.muted, fontFamily: "var(--font-mono)", fontSize: 12 }}>hachi — zsh</span>
        </div>

        {/* transcript */}
        <div style={{ fontFamily: "var(--font-mono)", fontSize: 13, lineHeight: "22px", padding: 18, display: "flex", flexDirection: "column", gap: 2 }}>
          <Prompt><span style={{ color: C.brand }}>hachi</span> run "refactor auth module" --budget 1.00</Prompt>
          <L color={C.muted}>hachi ▸ on watch · budget $1.00</L>
          <L color={C.muted}>→ scanning src/auth (12 files)</L>
          <div style={{ height: 8 }} />

          <L color={C.brand}>▸ Hachi wants to run a command</L>
          <L color={C.ink}>{"  "}npm install</L>
          <L color={C.muted}>{"  "}why: install the dependencies for your build</L>
          <L style={{ marginTop: 2 }}>
            {"  "}<span style={{ color: C.navy }}>[d]</span><span style={{ color: C.muted }}>eny  </span>
            <span style={{ color: C.brand }}>[a]</span><span style={{ color: C.muted }}>llow once  </span>
            <span style={{ color: C.muted }}>[A]lways</span>
            <span style={{ color: C.muted }}>{"     "}you hold the leash</span>
          </L>
          <div><span style={{ color: C.brand }}>❯</span> <span style={{ color: C.ink }}>a</span></div>
          <div style={{ height: 8 }} />

          <L color={C.green}>✓ allowed — running npm install</L>
          <L color={C.muted}>→ added 214 packages in 3.1s</L>
          <L color={C.green}>✓ session.ts — extracted token guard</L>
          <L color={C.green}>✓ tests passing (28/28)</L>
          <div style={{ height: 8 }} />

          <L color={C.ink}>Task complete — Hachi is resting.</L>
          <L color={C.muted}>spent $0.21 of $1.00 · 1m 04s</L>
          <div style={{ height: 6 }} />
          <Prompt><span style={{ width: 8, height: 15, background: C.brand, display: "inline-block", verticalAlign: "middle", animation: "hachi-caret 1s steps(1) infinite" }} /></Prompt>
        </div>
      </div>
      <style>{`@keyframes hachi-caret{50%{opacity:0}}`}</style>
    </div>
  );
}

window.Cli = Cli;
