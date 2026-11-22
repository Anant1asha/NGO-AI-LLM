# Hachi Design System

> **hachi** — a local-first personal AI agent you can actually trust. *You hold the leash.*
> Part of the **Open Gigantic** family. Endorse as **"Hachi by Open Gigantic."**

This is the source of truth for Hachi's brand and product design: tokens, fonts, assets, reusable
components, and full-screen UI kits for the three surfaces (TUI, web app, CLI). An automated compiler
reads this folder and ships `styles.css` + a component bundle to consuming projects.

---

## 1 · Company & product context

Hachi runs long, autonomous tasks **on your own machine** — but only ever within the permissions and
budget you set. The promise is **trust through control**: it acts on its own, never beyond what you
allowed. Named after the famously loyal Akita, Hachi is the quietly capable companion that does the
work and waits at the door.

**Surfaces (priority order):**
1. **TUI** — a Textual terminal UI. Dark, mono, the red `hachi ▸` prompt.
2. **Web app** — React (TanStack Start). Warm cream canvas, run cards, the leash prompt.
3. **CLI** — scriptable command-line entry point.

Prioritise **TUI + web component parity**.

**The leash vocabulary** (used in-product, not just marketing):
| Concept | In-product term |
|---|---|
| Permissions | **the leash** — *you hold it* |
| Background / long-running | **on watch** |
| A finished task | **Hachi is resting** |
| Sub-agents | **the pack** |
| Skill marketplace | **the kennel** |

Status words, always lowercase: **working · on watch · done · blocked**.

### Sources given
- `uploads/hachi-token.css` — the canonical token seed (brand, ink, surfaces, states, radius, motion).
  Expanded into `tokens/` here.
- `uploads/hachi.svg` — the primary mark (geometric two-tone Shiba/Akita head). Copied to
  `assets/hachi-mark.svg`; variants derived in `assets/`.
- `uploads/hachi logo.png` — the logo-system reference board. Copied to `assets/hachi-logo-system.png`.
- No codebase or Figma was provided — components and UI kits here are built to the written brand spec.

---

## 2 · Content fundamentals (voice & tone)

**Calm, loyal, plainspoken, quietly confident.** Never hype, never alarming, respects developers.
Hachi is a good dog: capable, patient, never needy.

- **Casing:** sentence case *everywhere*. Never ALL CAPS — not in buttons, labels, or headings.
  The wordmark is always lowercase **hachi**.
- **Person:** address the user as **you** ("you hold the leash", "Hachi wants to run a command").
  Hachi refers to itself in the third person by name ("Hachi is resting", "Hachi is on watch") —
  this keeps it a companion, not a chatbot saying "I".
- **Emoji:** **no.** The mascot and the ∞/8 motif carry the warmth. No emoji in product or marketing.
- **Length:** short. One plain-language line beats a paragraph. Explain *why* in one clause.
- **Never alarming:** even permission and cost surfaces stay matter-of-fact. The leash prompt is a
  calm question, not an error. Reserve red-as-danger strictly for genuinely destructive actions.

**Voice examples (use these as the reference register):**
- Permission: *"Hachi wants to run a command"* → *"why: install the dependencies for your build"*
- Caption under the leash prompt: *"you hold the leash"*
- Done toast: *"Task complete — Hachi is resting"*
- Idle: *"Hachi is on watch"* · Working: *"Hachi is working"* · Blocked: *"Hachi is blocked — needs you"*
- Budget, always visible: *"spent $0.02 of $1.00"*

**Don't:** "🚀 Supercharge your workflow!", "ERROR: permission denied", "I'll get right on that!",
ALL-CAPS labels, exclamation-heavy hype.

---

## 3 · Visual foundations

**The feel:** warm, premium, flat. Cream and bone carry the warmth; ink carries the words; Torii red
is the single accent, used *rarely and intentionally* — the mark and primary actions only, never body
text or large fills.

### Color
- **One accent.** Torii red `#D64933` (lifts to `#E25A44` on dark). If a screen has more than a few
  red pixels, it's wrong. Cream `#F3E9D2` / bone `#FBF7EF` / surface `#FFFDF8` do the heavy lifting.
- **Navy `#2F4B7C`** is the workhorse secondary — links, secondary buttons, the idle "listening" state.
- **States are their own families:** working = amber `#E0922E`, done = green `#3F9D6B`, blocked/danger
  = `#C0392B`. **Danger red is deliberately distinct from brand red** so "destructive" never reads as
  "primary action."
- **Status pills** = tinted background + dark same-family text (e.g. amber text on `#FBEBD6`).
- Dark mode: canvas `#16151A`, surface `#201E25`, ink becomes bone. Red stays the anchor in both modes.

### Type
- **General Sans** (display/headings) — warm geometric humanist sans. **Inter** (product UI/body).
  **JetBrains Mono** (CLI/TUI/code/terminal, and inline code on a cream chip).
- **Two weights only: 400 regular, 500 medium.** No light, no bold, no black.
- Scale: display 38/42 · heading 24/30 · body 16/26 · small 13/20 · mono 13/22.
- Sentence case. Generous line-height. `text-wrap: pretty` on headings.

### Surfaces, borders, radius
- **Cards:** surface `#FFFDF8` on bone canvas, **0.5px hairline border** in Line `#E2D9C9`, radius
  **16px**. **No shadow** (or a barely-there functional one only when elevation is truly needed).
- **Radius scale:** sm 6 (chips/inputs) · md 10 (buttons/inputs) · lg 16 (cards) · pill 999 (status,
  avatars). Friendly, rounded, never sharp.
- **Borders are hairlines** — 0.5px, Line color. They define structure instead of shadows.
- **Flat:** no gradients, no glows, no drop shadows beyond a functional focus ring
  (`2px solid brand`, 2px offset).

### Motion
- Durations **120 / 200 / 320ms**, one shared ease **`cubic-bezier(.2,.7,.3,1)`**.
- Calm fades and short slides. No bounces, no springy overshoot, no infinite decorative loops on
  content. **Hover:** darken the fill (brand → `#C23E2C`) or tint the bg; don't lighten. **Press:**
  settle/darken, no large scale jumps.
- **The loyal loop** — the loading spinner is an **infinity / figure-8 in Torii red** (8 = ∞ = always
  on; "hachi" means eight). `assets/hachi-loop.svg`.

### Layout
- Warm canvas, comfortable whitespace, hairline-bordered cards. **Cost and permissions are always
  visible** — they're features, not settings to hide. Budget lives on the run card; the leash prompt
  is a first-class surface, not a modal afterthought.

---

## 4 · Iconography

- **No bundled icon font shipped with the brand spec.** Hachi uses **Lucide** (https://lucide.dev) as
  its product icon set — a clean, consistent 1.5–2px stroke line set that matches the calm, flat,
  rounded feel. Linked from CDN in components/kits (`lucide@latest`). **This is a substitution choice**
  flagged for the user: if Hachi has its own icon set, drop it into `assets/icons/` and update here.
- **Stroke, not fill.** Icons are line icons at ~1.75px stroke, `currentColor`, sized 16–20px in UI.
  They inherit ink or muted; **icons are never Torii red** unless they're the brand mark itself.
- **The mascot is the one illustration.** `assets/hachi-mark.svg` (two-tone), `hachi-app-icon.svg`
  (cream face on red square), `hachi-mark-knockout.svg` (one-colour, `currentColor`, holds at 16px).
  **Never recolour the dog per screen.**
- **The ∞/8 (`hachi-loop.svg`)** is the secondary motif — loading, "always on", connective moments.
- **No emoji as icons. No unicode-glyph icons** except the functional `▸` in the terminal prompt and
  arrows/check where typographically appropriate.

---

## 5 · Index — what's in this system

**Foundations / tokens**
- `styles.css` — global entry (imports only). Consumers link this.
- `tokens/colors.css` · `typography.css` · `spacing.css` · `motion.css` · `fonts.css` · `base.css`

**Assets** (`assets/`)
- `hachi-mark.svg` · `hachi-app-icon.svg` · `hachi-mark-knockout.svg` · `hachi-loop.svg`
- `hachi-logo-system.png` (reference board)

**Specimen cards** (`guidelines/`) — populate the Design System tab (Type, Colors, Spacing, Brand).

**Components** (`components/`) — namespace `window.HachiDesignSystem_46e488`. Each has a `.prompt.md`.
- `core/` — `Button`, `StatusPill`, `Input`, `Switch`, `Badge`, `Card`
- `feedback/` — `Toast`, `LoyalLoop`
- `hachi/` — `HachiMark`, **`LeashPrompt`** (signature), `RunCard`, `Terminal`

**UI kits** (`ui_kits/`) — full-screen recreations per surface.
- `webapp/` — React / TanStack Start runs workspace (sidebar, run cards, interactive leash prompt → toast). Composes the bundle primitives.
- `tui/` — Textual terminal UI (runs panel, output log, leash dialog, key bindings). Self-contained.
- `cli/` — scriptable CLI session transcript with the inline text leash prompt. Self-contained.

**SKILL.md** — Agent-Skills-compatible entry for using this system in Claude Code.

---

## 6 · Caveats & substitutions
- **Fonts are CDN-linked, not self-hosted.** General Sans (Fontshare) is the *specified* brand face, so
  this is not a substitution — but no `@font-face`/binary lives in the repo, so the compiler reports 0
  fonts. If you want self-hosted webfonts, upload the `.woff2` files and I'll write real `@font-face`
  rules. Inter + JetBrains Mono come from Google Fonts.
- **Icons use Lucide** (real path data, inline at stroke 1.75). No Hachi-specific icon set was provided
  — if one exists, drop it into `assets/` and I'll swap the kit's `Icon` helper.
- **Mascot variants** (`hachi-app-icon.svg`, `hachi-mark-knockout.svg`, `hachi-loop.svg`) were derived
  from the supplied `hachi.svg` geometry to match the reference board, not delivered as files.
- The `webapp` kit renders only once the compiler has built `_ds_bundle.js` (it composes bundled
  primitives); the `tui` and `cli` kits are self-contained.

*Tokens namespace for `@dsCard` HTML: `window.HachiDesignSystem_46e488`.*
