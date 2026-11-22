// Hachi web app — main Runs workspace. Interactive: start a run → leash prompt → allow → toast.
const { RunCard, LeashPrompt, Button, Toast } = window.HachiDesignSystem_46e488;

const SEED_RUNS = [
  { id: 1, title: "Refactor auth module", status: "working", progress: 0.42, spent: 0.02, budget: 1.0, meta: "Editing session.ts" },
  { id: 2, title: "Migrate test suite to Vitest", status: "on-watch", progress: 0.15, spent: 0.01, budget: 0.5, meta: "Hachi is on watch" },
  { id: 3, title: "Generate API docs", status: "done", progress: 1, spent: 0.18, budget: 1.0, meta: "Hachi is resting" },
  { id: 4, title: "Audit dependencies for CVEs", status: "blocked", progress: 0.6, spent: 0.09, budget: 1.0, meta: "Needs your approval" },
];

function TopBar({ onNewRun }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 16,
      padding: "0 32px", height: 68, flexShrink: 0,
      borderBottom: "0.5px solid var(--hachi-line)", background: "var(--surface-page)",
    }}>
      <div style={{ display: "flex", flexDirection: "column" }}>
        <h1 style={{ font: "var(--text-heading)", fontSize: 22, lineHeight: "26px" }}>Runs</h1>
      </div>
      <div style={{ flex: 1 }} />
      <div style={{
        display: "flex", alignItems: "center", gap: 8, height: 38, padding: "0 12px",
        background: "var(--surface-card)", border: "0.5px solid var(--hachi-line)",
        borderRadius: "var(--radius-md)", color: "var(--text-muted)", width: 220,
      }}>
        <window.Icon name="search" size={16} />
        <span style={{ font: "var(--text-small)" }}>Search runs</span>
      </div>
      <Button variant="primary" onClick={onNewRun} icon={<window.Icon name="plus" size={16} />}>New run</Button>
    </div>
  );
}

function Workspace() {
  const [runs, setRuns] = React.useState(SEED_RUNS);
  const [prompt, setPrompt] = React.useState(null);
  const [toast, setToast] = React.useState(null);

  const flashToast = (message, tone = "success") => {
    setToast({ message, tone });
    setTimeout(() => setToast(null), 3200);
  };

  const newRun = () => {
    setPrompt({
      request: "Hachi wants to run a command",
      action: "npm install && npm run build",
      why: "Set up the workspace for your new run",
    });
  };

  const allow = () => {
    const id = Date.now();
    setRuns((r) => [{ id, title: "Build and test workspace", status: "working", progress: 0.08, spent: 0.0, budget: 1.0, meta: "Hachi is working" }, ...r]);
    setPrompt(null);
    flashToast("On it — Hachi is working", "working");
  };

  const deny = () => {
    setPrompt(null);
    flashToast("Stayed put — Hachi is resting", "success");
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", flex: 1, minWidth: 0, position: "relative" }}>
      <TopBar onNewRun={newRun} />

      <div style={{ flex: 1, overflow: "auto", padding: 32 }}>
        <div style={{ font: "var(--text-small)", color: "var(--text-muted)", marginBottom: 16 }}>
          {runs.length} runs · {runs.filter((r) => r.status === "working").length} working ·{" "}
          {runs.filter((r) => r.status === "blocked").length} need you
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: 16, maxWidth: 1080 }}>
          {runs.map((r) => (
            <RunCard key={r.id} title={r.title} status={r.status} progress={r.progress} spent={r.spent} budget={r.budget} meta={r.meta} />
          ))}
        </div>
      </div>

      {prompt && (
        <div style={{
          position: "absolute", inset: 0, background: "rgba(28,26,32,0.32)",
          display: "grid", placeItems: "center", padding: 24, zIndex: 10,
        }} onClick={deny}>
          <div onClick={(e) => e.stopPropagation()}>
            <LeashPrompt request={prompt.request} action={prompt.action} why={prompt.why}
              onDeny={deny} onAllowOnce={allow} onAlwaysAllow={allow} />
          </div>
        </div>
      )}

      {toast && (
        <div style={{ position: "absolute", bottom: 28, left: "50%", transform: "translateX(-50%)", zIndex: 20 }}>
          <Toast message={toast.message} tone={toast.tone} />
        </div>
      )}
    </div>
  );
}

window.Workspace = Workspace;
