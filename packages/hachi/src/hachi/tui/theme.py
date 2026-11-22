"""Hachi TUI theme and semantic palette.

Hachi's terminal surface is **always dark** — warm-dark canvas, hairline slate
borders, and a single Torii-red brand accent used *sparingly* (the ``hachi ▸``
prompt + primary actions only). Cream/bone ink carries the words; navy is the
workhorse secondary. The palette constants are exported so widgets and the pure
``formatters`` builders share exactly one source of truth for role/status colors
(and stay unit-testable without importing Textual styling at call time).

Brand spec (Hachi Design System, dark surface):
  canvas #16151A · surface #201E25 · line #322F38 · ink #FBF7EF · muted #9C968C
  brand(red) #E25A44 · navy #7C9BD1 · amber #E0922E · green #3F9D6B · danger #E0594A
"""

from __future__ import annotations

from textual.theme import Theme

# --- Core surfaces (always dark) -----------------------------------------
BACKGROUND = "#16151A"  # canvas — page/terminal background
SURFACE = "#201E25"  # surface — cards, panels, header, footer
PANEL = "#201E25"  # panels share the surface tone (flat, no elevation)
FOREGROUND = "#FBF7EF"  # ink → bone (the words, the dog's eyes)
MUTED = "#9C968C"  # secondary text
BORDER_MUTED = "#322F38"  # line — hairline borders

# --- Brand + accent families ---------------------------------------------
# Torii red is the single brand accent (the mark + the prompt + primary
# actions). Danger red is deliberately distinct so "destructive" never reads as
# "primary action." Navy is the secondary workhorse (links / on-watch / Deny).
BRAND = "#E25A44"  # torii red (dark lift) — mark, `hachi ▸`, primary
BRAND_HOVER = "#D64933"  # press/hover: settle/darken, never lighten
NAVY = "#7C9BD1"  # trust navy (dark) — links, secondary, "on watch"
AMBER = "#E0922E"  # working / in progress
GREEN = "#3F9D6B"  # done / success
DANGER = "#E0594A"  # blocked / destructive — distinct from brand red

# --- Status-pill tints (tinted bg, same-family text), dark mode -----------
BRAND_TINT = "#3A211C"
NAVY_TINT = "#1E2735"
AMBER_TINT = "#34281A"
GREEN_TINT = "#182A22"
DANGER_TINT = "#321E1C"

# --- Semantic accents (existing names remapped onto the Hachi palette) ----
# Kept as the public surface every widget/formatter already imports; only the
# values move to Hachi. ``PRIMARY`` is the brand-red voice (the hachi prompt,
# focus rings, footer keys, the agent); ``ACCENT`` is navy (the workhorse
# secondary — links, tokens/cost, the "you" voice).
PRIMARY = BRAND  # brand red — primary actions, focus, footer keys, hachi voice
ACCENT = NAVY  # navy — secondary highlights, links, tokens/cost, the user
SECONDARY = "#5E7BB0"  # deeper navy
SUCCESS = GREEN
WARNING = AMBER
ERROR = DANGER

# --- Role colors (used by message widgets) -------------------------------
ROLE_USER = ACCENT  # navy — "you" (you hold the leash)
ROLE_AGENT = BRAND  # torii red — the hachi voice / the `hachi ▸` prompt

# --- Status colors (tool cards, sidebar, jobs, run rows) ------------------
# Generic runtime statuses keep their established semantics (a tool *running*
# is navy/in-flight, distinct from a long *working* run which is amber). The
# Hachi run-state words (working / on watch / done / blocked) are also mapped.
STATUS_COLORS: dict[str, str] = {
    "running": ACCENT,
    "starting": ACCENT,
    "pending": WARNING,
    "completed": SUCCESS,
    "ready": SUCCESS,
    "done": SUCCESS,
    "failed": ERROR,
    "error": ERROR,
    "cancelled": MUTED,
    "idle": MUTED,
    # Hachi run states ---------------------------------------------------
    "working": WARNING,  # amber — in progress
    "on-watch": NAVY,  # navy — background / long-running
    "on_watch": NAVY,
    "blocked": ERROR,  # danger — needs you
}

# Hachi status words, always lowercase: working · on watch · done · blocked.
# Maps generic runtime statuses onto the four product-facing words.
STATUS_WORDS: dict[str, str] = {
    "working": "working",
    "running": "working",
    "starting": "working",
    "pending": "working",
    "on-watch": "on watch",
    "on_watch": "on watch",
    "idle": "on watch",  # Hachi is always quietly listening
    "done": "done",
    "completed": "done",
    "ready": "done",
    "success": "done",
    "blocked": "blocked",
    "failed": "blocked",
    "error": "blocked",
    "cancelled": "blocked",
}

# Glyphs (single source so widgets/formatters agree). Hachi uses line/stroke
# marks, never emoji; the only functional unicode glyph is the `▸` prompt.
GLYPH_PROMPT = "▸"  # the signature `hachi ▸` marker
GLYPH_RUNNING = "⠿"
GLYPH_DONE = "✓"
GLYPH_ERROR = "✗"
GLYPH_USER = "▍"
GLYPH_AGENT = "▸"  # the hachi prompt mark fronts every reply
GLYPH_TOOL = "⚙"
GLYPH_DOT = "●"  # run-status dot (working/on-watch/done/blocked)
GLYPH_LOOP = "∞"  # the loyal loop motif (8 = ∞ = always on; "hachi" = eight)

# --- Brand: hachi, the loyal companion -----------------------------------
# Terminal companion to the SVG mark in the Hachi Design System. The `▸` prompt
# is the persistent brand atom; its color encodes the live runtime state, so the
# header doubles as a status readout (on watch / working / done / blocked).
HACHI_WORDMARK = "hachi"

# state -> (prompt glyph, color). The `▸` stays the mark; the color carries state.
HACHI_STATE_EYES: dict[str, tuple[str, str]] = {
    "idle": (GLYPH_PROMPT, MUTED),  # resting / on watch
    "thinking": (GLYPH_PROMPT, BRAND),  # the red prompt
    "working": (GLYPH_PROMPT, AMBER),
    "success": (GLYPH_PROMPT, GREEN),
    "error": (GLYPH_PROMPT, DANGER),
}

# Loop palette for the ASCII "loyal loop" splash (tui/art.py). Brand red is the
# anchor; the loop is the figure-8/∞ motif.
HACHI_BODY = BRAND  # the loop body — torii red
HACHI_BODY_BRIGHT = "#EC6F5A"  # brighter red lobe
HACHI_EYE_CREAM = FOREGROUND  # bone ink highlight
HACHI_TONGUE = AMBER  # warm accent flick

# Animated frames cycled by the header on a timer — the loyal loop turning over.
# States not listed here render the static glyph from HACHI_STATE_EYES.
HACHI_EYE_FRAMES: dict[str, list[str]] = {
    "thinking": ["◜", "◝", "◞", "◟"],
    "working": ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
}

# runtime event -> hachi state (None = leave the glyph unchanged)
_HACHI_EVENT_STATES: dict[str, str] = {
    "session.chat.started": "thinking",
    "thinking.step": "thinking",
    "permission.requested": "thinking",
    "permission.decided": "thinking",
    "tool.call.started": "working",
    "session.chat.completed": "success",
    "job.completed": "success",
    "boot.complete": "idle",
    "session.ready": "idle",
    "gateway.connect.completed": "idle",
    "boot.failed": "error",
    "job.failed": "error",
    "gateway.events.error": "error",
}


def status_color(status: str | None) -> str:
    """Return the semantic color for a status label (falls back to muted)."""
    return STATUS_COLORS.get(str(status or "").lower(), MUTED)


def status_word(status: str | None) -> str:
    """Return the Hachi status word (working/on watch/done/blocked) for a status."""
    label = str(status or "").lower()
    return STATUS_WORDS.get(label, label)


def status_glyph(status: str | None) -> str:
    """Return the glyph for a status label (done/error/running)."""
    label = str(status or "").lower()
    if label in {"completed", "done", "ready", "success"}:
        return GLYPH_DONE
    if label in {"failed", "error", "blocked"}:
        return GLYPH_ERROR
    return GLYPH_RUNNING


def status_dot_color(status: str | None) -> str:
    """Return the run-row dot color (working=amber, on-watch=navy, done=green, blocked=danger)."""
    return status_color(status)


def hachi_eye(state: str | None) -> tuple[str, str]:
    """Return the ``(prompt glyph, color)`` for a hachi runtime state."""
    return HACHI_STATE_EYES.get(str(state or "idle").lower(), HACHI_STATE_EYES["idle"])


def hachi_state_for_event(event_type: str, *, is_error: bool = False) -> str | None:
    """Map a runtime event to a hachi state, or ``None`` to leave it unchanged.

    ``tool.call.completed`` resolves to ``error`` when the result looks like a
    failure (caller passes ``is_error``) and otherwise back to ``thinking``,
    since the agent resumes reasoning after a successful tool call.
    """
    if event_type == "tool.call.completed":
        return "error" if is_error else "thinking"
    return _HACHI_EVENT_STATES.get(event_type)


HACHI_THEME = Theme(
    name="hachi",
    primary=PRIMARY,
    secondary=SECONDARY,
    accent=ACCENT,
    warning=WARNING,
    error=ERROR,
    success=SUCCESS,
    foreground=FOREGROUND,
    background=BACKGROUND,
    surface=SURFACE,
    panel=PANEL,
    dark=True,
    variables={
        # Custom CSS variables ($name) consumed by APP_CSS. Brand-red focus
        # rings + footer keys are the Hachi signature; navy is the secondary.
        "border-muted": BORDER_MUTED,
        "text-muted": MUTED,
        "role-user": ROLE_USER,
        "role-agent": ROLE_AGENT,
        "brand": BRAND,
        "brand-hover": BRAND_HOVER,
        "brand-tint": BRAND_TINT,
        "navy": NAVY,
        "amber": AMBER,
        "green": GREEN,
        "danger": DANGER,
        "line": BORDER_MUTED,
        "footer-key-foreground": BRAND,
        "block-cursor-background": BRAND,
        "input-cursor-background": BRAND,
    },
)
