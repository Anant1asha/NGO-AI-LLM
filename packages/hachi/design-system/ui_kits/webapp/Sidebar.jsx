// Hachi web app — left navigation rail. Wordmark, nav, and always-visible budget summary.
const { HachiMark } = window.HachiDesignSystem_46e488;

function NavItem({ icon, label, active, hint, onClick }) {
  const [hover, setHover] = React.useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: "flex", alignItems: "center", gap: 12, width: "100%",
        padding: "9px 12px", borderRadius: "var(--radius-md)", border: "none",
        background: active ? "var(--hachi-cream)" : hover ? "var(--hachi-cream)" : "transparent",
        color: active ? "var(--text-default)" : "var(--text-muted)",
        font: "var(--text-body)", fontSize: 14, fontWeight: active ? 500 : 400,
        cursor: "pointer", textAlign: "left",
        transition: "background var(--dur) var(--ease)",
      }}
    >
      <window.Icon name={icon} size={18} style={{ color: active ? "var(--hachi-brand)" : "currentColor" }} />
      <span style={{ flex: 1 }}>{label}</span>
      {hint != null && (
        <span style={{ font: "var(--text-small)", color: "var(--text-muted)", fontVariantNumeric: "tabular-nums" }}>{hint}</span>
      )}
    </button>
  );
}

function Sidebar({ active = "runs", onNavigate = () => {} }) {
  return (
    <aside style={{
      width: 248, flexShrink: 0, background: "var(--surface-card)",
      borderRight: "0.5px solid var(--hachi-line)", height: "100%",
      display: "flex", flexDirection: "column", padding: 16, boxSizing: "border-box",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 8px 18px" }}>
        <HachiMark size={30} />
        <span style={{ fontFamily: "var(--font-display)", fontWeight: 500, fontSize: 22, color: "var(--text-default)" }}>hachi</span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <NavItem icon="list-checks" label="Runs" hint="3" active={active === "runs"} onClick={() => onNavigate("runs")} />
        <NavItem icon="layers" label="The pack" hint="2" active={active === "pack"} onClick={() => onNavigate("pack")} />
        <NavItem icon="shopping-bag" label="The kennel" active={active === "kennel"} onClick={() => onNavigate("kennel")} />
        <NavItem icon="terminal" label="Terminal" active={active === "terminal"} onClick={() => onNavigate("terminal")} />
        <NavItem icon="settings" label="Settings" active={active === "settings"} onClick={() => onNavigate("settings")} />
      </div>

      <div style={{ flex: 1 }} />

      <div style={{
        background: "var(--hachi-cream)", border: "0.5px solid var(--hachi-line)",
        borderRadius: "var(--radius-md)", padding: 14,
      }}>
        <div style={{ font: "var(--text-small)", color: "var(--text-muted)", marginBottom: 8 }}>Today's budget</div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 6, marginBottom: 10 }}>
          <span style={{ fontFamily: "var(--font-display)", fontWeight: 500, fontSize: 22, color: "var(--text-default)" }}>$0.41</span>
          <span style={{ font: "var(--text-small)", color: "var(--text-muted)" }}>of $5.00</span>
        </div>
        <div style={{ height: 4, borderRadius: 999, background: "var(--hachi-line)", overflow: "hidden" }}>
          <div style={{ width: "8%", height: "100%", background: "var(--hachi-brand)", borderRadius: 999 }} />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 7, marginTop: 12, font: "var(--text-small)", color: "var(--text-muted)" }}>
          <HachiMark size={15} variant="knockout" style={{ color: "var(--hachi-muted)" }} />
          you hold the leash
        </div>
      </div>
    </aside>
  );
}

window.Sidebar = Sidebar;
