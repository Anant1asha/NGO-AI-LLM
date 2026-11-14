"""AASHA AIOS — Master Luxury Chapter Builder (Gold Standard Engine).

Fuses the best patterns from the user's 4 gold-standard prototypes:
  1. Dark Luxury Educational Theme (--bg0:#070c12, --panel:#121c27, --teal:#31e6c4, --gold:#ffc247, etc.)
  2. Strict Ergonomics: All interactive elements min-height >= 46px, generous touch targets.
  3. High Typography Contrast: Headings 22-30px, Body 17-20px (line-height 1.68), legible on all devices.
  4. Dual-Layer LLE:
     - Word-level tap-to-reveal with Devanagari phonics + Hindi meanings + SpeechSynthesisUtterance audio.
     - Sentence-level Hindi layer (.hiWrap, .hiBtn "अ", .hiBox) on every paragraph, step, and question.
     - Grammatical connectors (because -> क्योंकि, therefore -> इसलिए, etc.).
  5. Acharya Mentor Persona: Warm, conversational Indian teacher voice with real-life Indian analogies.
  6. Live Interactive Procedural Manipulatives on EVERY Concept: Real-time SVG/Canvas models.
  7. Full 25-35 Slide Journeys: Complete chapter coverage (not dummy exercises).
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHAPTERS_DIR = REPO_ROOT / "Aasha-AI" / "chapters"
SCRIPTS_DIR = REPO_ROOT / "scripts"

# Load Master Vocabulary & Phrases extracted from user prototypes
WORDS_PATH = SCRIPTS_DIR / "master_words_lle.json"
PHRASES_PATH = SCRIPTS_DIR / "master_phrases_lle.json"
LLE_JS_PATH = SCRIPTS_DIR / "lle_runtime.js"

MASTER_WORDS = json.loads(WORDS_PATH.read_text(encoding="utf-8")) if WORDS_PATH.exists() else {}
MASTER_PHRASES = json.loads(PHRASES_PATH.read_text(encoding="utf-8")) if PHRASES_PATH.exists() else {}
LLE_RUNTIME_JS = LLE_JS_PATH.read_text(encoding="utf-8") if LLE_JS_PATH.exists() else ""


def get_base_css() -> str:
    return """
:root{
  --bg0:#070c12; --bg1:#0d1620; --panel:#121c27; --panel2:#16222f;
  --ink:#eef5fa; --ink2:#c9d9e6; --muted:#8ba2b6;
  --teal:#31e6c4; --teal2:#19b79e; --gold:#ffc247; --gold2:#ffd98a;
  --red:#ff5f78; --green:#4ade80; --blue:#63a9ff; --violet:#9d7bff;
  --line:rgba(125,185,225,.14); --line2:rgba(125,185,225,.24);
  --r:14px; --r2:18px;
  --safe: env(safe-area-inset-bottom, 0px);
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;height:100%;color:var(--ink);overflow:hidden;
  font-family:system-ui,-apple-system,"Segoe UI",Roboto,"Noto Sans Devanagari",sans-serif;
  background:
    radial-gradient(1100px 620px at 78% -12%, rgba(49,230,196,.10), transparent 62%),
    radial-gradient(900px 520px at 6% 108%, rgba(255,194,71,.08), transparent 60%),
    linear-gradient(180deg,var(--bg1),var(--bg0) 60%);
  background-attachment:fixed;font-size:16px}
.app{max-width:1200px;margin:0 auto;padding:10px 14px 10px;display:flex;flex-direction:column;
  gap:10px;height:100dvh}

/* ---------- header ---------- */
header{display:flex;align-items:center;gap:10px;flex:0 0 auto}
.logo{width:32px;height:32px;border-radius:9px;flex:0 0 auto;
  background:linear-gradient(135deg,var(--teal),var(--gold));
  display:grid;place-items:center;color:#06231f;font-weight:900;font-size:16px}
.brand{font-weight:800;letter-spacing:.2px;font-size:15px;line-height:1.15}
.brand em{font-style:normal;color:var(--teal)}
.brand small{display:block;font-size:11px;color:var(--muted);font-weight:600;letter-spacing:.05em;margin-top:2px}
.chip{margin-left:auto;font-size:12.5px;color:var(--ink2);background:rgba(255,255,255,.05);
  border:1px solid var(--line);border-radius:999px;padding:6px 12px;white-space:nowrap;font-weight:700}
.chip b{color:var(--gold)}

/* ---------- progress bar ---------- */
.bar{height:6px;background:rgba(255,255,255,.07);border-radius:99px;overflow:hidden;flex:0 0 auto}
.bar i{display:block;height:100%;width:0;border-radius:99px;
  background:linear-gradient(90deg,var(--teal),var(--gold));transition:width .35s cubic-bezier(.4,0,.2,1)}

/* ---------- card ---------- */
.card{flex:1 1 auto;min-height:0;overflow:hidden;border-radius:var(--r2);
  background:linear-gradient(168deg,var(--panel2),var(--panel) 55%,#101a24);
  border:1px solid var(--line2);
  box-shadow:0 18px 44px -20px rgba(0,0,0,.85), inset 0 1px 0 rgba(255,255,255,.045);
  padding:16px 20px;display:grid;gap:12px;
  grid-template-columns:minmax(0,1fr);
  grid-template-rows:auto auto minmax(0,1fr) auto;
  grid-template-areas:"head" "txt" "vis" "ctl"}
.card .head{grid-area:head}
.card .txt{grid-area:txt;min-height:0;overflow-y:auto;display:flex;flex-direction:column;gap:10px;padding-right:4px}
.card .visual{grid-area:vis;min-height:0;overflow:hidden;border-radius:14px;
  background:radial-gradient(120% 100% at 50% 0%, rgba(49,230,196,.07), rgba(10,17,24,.55));
  border:1px solid rgba(125,185,225,.10);display:grid;place-items:center;padding:6px}
.card .visual svg{width:100%;height:100%;max-height:340px;display:block}
.card .ctl{grid-area:ctl}

@media (min-width:900px){
  .card.split{grid-template-columns:minmax(0,1fr) minmax(0,1.15fr);
    grid-template-rows:auto minmax(0,1fr) auto;
    grid-template-areas:"head head" "txt vis" "txt ctl"}
  .card.split .txt{padding-right:12px}
}

/* ---------- typography ---------- */
.kindrow{display:flex;align-items:center;gap:9px;flex:0 0 auto;margin-bottom:4px}
.kind{font-size:11px;letter-spacing:.14em;text-transform:uppercase;font-weight:800;
  color:var(--teal);background:rgba(49,230,196,.10);border:1px solid rgba(49,230,196,.24);
  padding:3px 10px;border-radius:999px}
h1{font-size:clamp(23px,3.2vw,31px);line-height:1.22;margin:0;letter-spacing:-.015em;font-weight:800;color:#fff}
h2{font-size:clamp(19.5px,2.6vw,25px);line-height:1.26;margin:0;letter-spacing:-.01em;font-weight:800;color:#fff}
p.b{font-size:clamp(16.5px,2vw,19.5px);line-height:1.68;margin:0;color:var(--ink2)}
p.b strong{color:#fff;font-weight:750}
.sub{color:var(--muted);font-size:clamp(14.5px,1.7vw,17px);margin:0;font-weight:600}
.em{vertical-align:-4px;margin-right:6px}

/* Acharya Mentor Bubble */
.mentor-bubble{display:flex;gap:10px;align-items:flex-start;background:rgba(255,255,255,.03);
  border:1px solid var(--line);border-radius:13px;padding:11px 14px;margin-top:4px}
.mentor-av{width:36px;height:36px;border-radius:10px;display:grid;place-items:center;
  background:linear-gradient(135deg,var(--gold),#c07a12);color:#221501;font-size:18px;font-weight:900;flex:none}
.mentor-msg{flex:1;font-size:clamp(15px,1.8vw,17.5px);line-height:1.6;color:#ffe6a8}
.mentor-name{font-size:10.5px;font-weight:800;color:var(--gold);text-transform:uppercase;letter-spacing:.06em;margin-bottom:2px}

/* ---------- footer & buttons ---------- */
.tapline{display:flex;gap:10px;align-items:center;flex:0 0 auto}
.taphint{font-size:12.5px;color:var(--muted);white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis;display:flex;align-items:center;gap:5px}
.taphint b{color:var(--gold);font-weight:700}
@media (max-width:560px){.taphint{display:none}}

button{font:inherit;font-size:15px;font-weight:700;cursor:pointer;border-radius:12px;
  border:1px solid var(--line2);background:rgba(255,255,255,.05);color:var(--ink);
  padding:11px 20px;min-height:46px;transition:transform .08s ease, background .15s ease}
button:active{transform:scale(.97)}
button:disabled{opacity:.35;cursor:default}
button.pri{background:linear-gradient(180deg,#37ebca,#16a98f);color:#052a24;border:0;font-weight:800;
  box-shadow:0 8px 20px -8px rgba(49,230,196,.75)}
button.gho{background:transparent}

/* quiet Hindi toggle pill */
.hiWrap{display:inline}
.hiBox{display:block}
.hiBox[hidden]{display:none}
.hiBtn{display:inline-flex;align-items:center;justify-content:center;
  min-width:44px;min-height:44px;padding:6px 14px;margin-left:8px;vertical-align:middle;
  font-size:13px;font-weight:800;line-height:1;border-radius:999px;
  color:var(--gold);background:rgba(255,194,71,.12);
  border:1.5px solid rgba(255,194,71,.35);cursor:pointer;transition:all .15s ease}
.hiBtn:hover{opacity:1;background:rgba(255,194,71,.25)}
.hiBtn.on{background:var(--gold);color:#2a1d00;border-color:transparent}
.hiBox{margin-top:9px;padding:12px 16px;border-left:3.5px solid var(--gold);
  background:linear-gradient(90deg,rgba(255,194,71,.12),rgba(255,194,71,.04));
  border-radius:0 12px 12px 0;font-size:clamp(15.5px,1.85vw,18.5px);line-height:1.64;color:#ffe6a8}

/* ---------- tapable word ---------- */
.tapable{cursor:pointer;border-bottom:1.5px dotted rgba(49,230,196,.6);transition:background .12s}
.tapable:hover{background:rgba(49,230,196,.12);border-radius:3px}
.tapable:active{background:rgba(49,230,196,.25)}
.conn{color:var(--teal);font-weight:600}

/* ---------- tables ---------- */
table{border-collapse:separate;border-spacing:0;width:100%;font-size:clamp(15px,1.7vw,17.5px);
  border-radius:12px;overflow:hidden;border:1px solid var(--line)}
th,td{border-bottom:1px solid var(--line);padding:10px 12px;text-align:center}
tr:last-child td{border-bottom:0}
th{background:rgba(49,230,196,.09);font-weight:800;color:#d9f7f1}
td:first-child,th:first-child{text-align:left}
tbody tr:nth-child(even){background:rgba(255,255,255,.02)}

/* ---------- steps ---------- */
.steps{display:flex;flex-direction:column;gap:8px}
.step{display:flex;gap:11px;align-items:flex-start;background:rgba(255,255,255,.035);
  border:1px solid var(--line);border-left:3px solid var(--teal);
  border-radius:10px;padding:11px 13px;font-size:clamp(15.5px,1.85vw,18.5px);line-height:1.55}
.step .n{flex:0 0 24px;height:24px;border-radius:50%;background:var(--teal);color:#06231f;
  font-weight:900;font-size:12.5px;display:grid;place-items:center;margin-top:1px}

/* ---------- quiz options ---------- */
.opts{display:flex;flex-direction:column;gap:8px}
.opt{border:1px solid var(--line);border-radius:12px;padding:12px 14px;background:rgba(255,255,255,.035);
  font-size:clamp(15.5px,1.85vw,18.5px);cursor:pointer;min-height:50px;display:flex;align-items:center;gap:11px;
  transition:border-color .15s,background .15s}
.opt:hover{border-color:var(--line2);background:rgba(255,255,255,.06)}
.opt .k{width:26px;height:26px;border-radius:8px;background:rgba(255,255,255,.09);display:grid;
  place-items:center;font-size:12.5px;font-weight:800;color:var(--ink2);flex:0 0 auto}
.opt.ok{border-color:var(--green);background:rgba(74,222,128,.14)}
.opt.ok .k{background:var(--green);color:#06231f}
.opt.no{border-color:var(--red);background:rgba(255,95,120,.14)}
.opt.no .k{background:var(--red);color:#2a0009}
.fb{font-size:clamp(15px,1.8vw,18px);line-height:1.58;padding:12px 14px;border-radius:10px;display:none}
.fb.show{display:block}
.fb.ok{background:rgba(74,222,128,.12);border:1px solid rgba(74,222,128,.40);color:#baf4d0}
.fb.no{background:rgba(255,95,120,.12);border:1px solid rgba(255,95,120,.40);color:#ffc4cb}

/* ---------- rows & cards ---------- */
.mrow{display:flex;gap:11px;align-items:flex-start;background:rgba(255,255,255,.035);
  border:1px solid var(--line);border-radius:10px;padding:11px 13px}
.mrow b{display:block;font-size:clamp(16px,1.9vw,19px);margin-bottom:2px;color:#fff}
.mrow span{font-size:clamp(14.5px,1.75vw,17.5px);color:var(--ink2);line-height:1.52}

/* ---------- sim controls ---------- */
.simctl{display:flex;flex-direction:column;gap:10px}
.simctl input[type=range]{width:100%;accent-color:var(--teal);height:44px;min-height:44px;margin:2px 0;cursor:pointer}
.readout{display:flex;gap:16px;flex-wrap:wrap;font-size:clamp(14.5px,1.75vw,17.5px);color:var(--ink2)}
.readout b{color:var(--teal);font-size:clamp(16.5px,2vw,19.5px);font-weight:800}
.hint{font-size:clamp(14px,1.7vw,17px);color:var(--gold);line-height:1.52;
  background:rgba(255,194,71,.07);border-left:3px solid var(--gold);
  padding:10px 14px;border-radius:0 10px 10px 0}
.switch{display:flex;gap:8px}
.switch button{flex:1;font-size:14px;padding:10px;min-height:46px}
.switch button.on{background:var(--teal);color:#052a24;border-color:transparent;font-weight:800}

/* ---------- word panel ---------- */
#wp{position:fixed;left:0;right:0;bottom:0;transform:translateY(130%);
  transition:transform .26s cubic-bezier(.32,.72,0,1);
  background:linear-gradient(180deg,#162536,#0d1822);
  border-top:1px solid var(--line2);
  padding:16px 20px calc(16px + var(--safe));
  z-index:100;box-shadow:0 -18px 46px rgba(0,0,0,.75);border-radius:18px 18px 0 0;max-width:1200px;margin:0 auto}
#wp.up{transform:translateY(0)}
#wp .r1{display:flex;align-items:center;gap:14px;flex-wrap:wrap}
#wpWord{font-weight:800;font-size:22px;letter-spacing:-.01em;color:#fff}
#wpHindi{color:var(--gold);font-size:20px;font-weight:700}
#wpPron{color:var(--muted);font-size:15px}
.spk{background:rgba(255,255,255,.08);border:1px solid var(--line2);border-radius:999px;
  padding:11px 20px;min-height:46px;min-width:46px;font-size:14.5px;font-weight:700;color:var(--ink);cursor:pointer}
.spk:hover{background:var(--teal);color:#052a24}
.spk.cls{margin-left:auto;background:rgba(255,95,120,.12);border-color:rgba(255,95,120,.35);color:#ffc2cb}
"""


def build_lle_script(words_dict: dict, phrases_dict: dict) -> str:
    """Builds the comprehensive LLE client engine script by injecting dictionaries into lle_runtime.js."""
    wm_json = json.dumps(words_dict, ensure_ascii=False)
    ph_json = json.dumps(phrases_dict, ensure_ascii=False)

    return f"""
<script>
const WM2 = {wm_json};
const PH = {ph_json};
{LLE_RUNTIME_JS}
</script>
"""


print("Gold standard builder base module ready.")
