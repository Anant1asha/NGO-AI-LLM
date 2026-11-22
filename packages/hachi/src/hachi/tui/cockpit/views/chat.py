"""ChatView — full-altitude chat focus view with live gateway streaming.

Faithful recreation of the Chat (focus) panel from the Hachi Cockpit design
(lines 79–147 of Hachi Cockpit.dc.html), now wired to the live gateway via
REST + SSE.

Layout:
  Horizontal
  ├── Vertical (flex:1) — transcript pane + composer Input
  │     ├── transcript (scrollable Static)
  │     └── composer row: glyph Static + Input
  └── right-rail Static (300-cell wide) — plan + context + approval card

Live behavior:
  1. On first send (if is_live), calls cockpit_data.start_session() once.
  2. Appends the user line, clears the composer, calls cockpit_data.send().
  3. Spins a thread worker that calls cockpit_data.stream() and marshals
     events back via self.app.call_from_thread(_apply_event).
  4. Offline / error path falls back to the local-echo stub (no crash).

Hooks:
  activate_selected() — focuses the composer Input widget.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, Static
from textual.worker import Worker, get_current_worker

from hachi.client.sse import RuntimeEvent
from hachi.core.runtime_events import (
    PERMISSION_REQUESTED,
    SESSION_CANCELLED,
    SESSION_CHAT_COMPLETED,
    SESSION_CHAT_STARTED,
    TEXT_STREAM,
    TOOL_CALL_COMPLETED,
    TOOL_CALL_STARTED,
)
from hachi.tui.cockpit.base import CockpitView
from hachi.tui.theme import (
    AMBER,
    BORDER_MUTED,
    BRAND,
    DANGER,
    FOREGROUND,
    GREEN,
    MUTED,
    NAVY,
    SURFACE,
)

if TYPE_CHECKING:
    from hachi.tui.cockpit.data import CockpitData

_DIM = "#6E6A74"

# Representative plan steps shown only in offline/demo mode (CockpitData(None)).
# There is currently no gateway data model for a live per-turn "plan" — the
# frontend's run.tsx hides its Plan section for the same reason ("live mode
# emits no plan events"). Do NOT show these once a live CockpitData is wired;
# see BB-60.
_DEMO_PLAN_STEPS = [
    (GREEN, "☑", "search sources"),
    (AMBER, "◐", "read top 5 articles"),
    (_DIM, "☐", "extract figures"),
    (_DIM, "☐", "draft one-pager"),
    (_DIM, "☐", "save to Drive"),
]

# Event types sourced from hachi/core/runtime_events.py
_EV_TEXT_DELTA = TEXT_STREAM  # "text.stream.delta"
_EV_TOOL_STARTED = TOOL_CALL_STARTED  # "tool.call.started"
_EV_TOOL_DONE = TOOL_CALL_COMPLETED  # "tool.call.completed"
_EV_PERM_REQUESTED = PERMISSION_REQUESTED  # "permission.requested"
_EV_CHAT_COMPLETED = SESSION_CHAT_COMPLETED  # "session.chat.completed"
_EV_CHAT_STARTED = SESSION_CHAT_STARTED  # "session.chat.started"
_EV_CANCELLED = SESSION_CANCELLED  # "session.turn.cancelled"


class _TranscriptMessage:
    """Mutable transcript entry.  speaker: 'you' | 'hachi' | 'tool'."""

    __slots__ = ("speaker", "text", "is_streaming")

    def __init__(self, speaker: str, text: str, *, is_streaming: bool = False) -> None:
        self.speaker = speaker
        self.text = text
        self.is_streaming = is_streaming


class ChatView(CockpitView):  # type: ignore[misc]
    """Chat / focus-mode view with live gateway streaming.

    Scrollable transcript on the left (you ▸ in navy, hachi ▸ in brand red),
    a right rail with plan checklist + context block + approval card, and a
    focusable composer Input pinned at the bottom of the transcript column.

    Data sources: ``CockpitData.config()``, ``CockpitData.sessions()``.

    Live streaming:
        A Textual thread worker iterates ``CockpitData.stream()`` and marshals
        each ``RuntimeEvent`` back to the main thread via
        ``self.app.call_from_thread(_apply_event)``.

    Hooks:
        activate_selected() — focuses the composer Input.
    """

    view_id: ClassVar[str] = "chat"

    DEFAULT_CSS = f"""
    ChatView {{
        height: 1fr;
        width: 1fr;
        background: $background;
    }}
    ChatView > Horizontal {{
        height: 1fr;
        width: 1fr;
    }}
    ChatView > Horizontal > Vertical {{
        height: 1fr;
        width: 1fr;
    }}
    ChatView #chat-transcript {{
        height: 1fr;
        width: 1fr;
        background: $background;
        padding: 1 2;
        overflow: auto;
    }}
    ChatView #chat-composer-row {{
        height: 3;
        width: 1fr;
        background: {SURFACE};
        border-top: solid {BORDER_MUTED};
        padding: 0 1;
    }}
    ChatView #chat-prompt-glyph {{
        width: 2;
        height: 1fr;
        padding: 1 0 0 0;
    }}
    ChatView #chat-composer {{
        width: 1fr;
        height: 1fr;
        background: transparent;
        color: {FOREGROUND};
    }}
    ChatView #chat-rail {{
        width: 34;
        height: 1fr;
        border-left: solid {BORDER_MUTED};
        background: $background;
        padding: 1 2;
        overflow: auto;
    }}
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._data: CockpitData | None = None

        # Live session state
        self._session_id: str | None = None
        self._last_seq: int = 0
        self._stop = threading.Event()
        self._stream_worker: Worker[None] | None = None

        # In-memory transcript as a list of _TranscriptMessage objects.
        self._messages: list[_TranscriptMessage] = [
            _TranscriptMessage(
                "you", "research the latest AI funding rounds and draft a one-pager"
            ),
            _TranscriptMessage("hachi", "On it — gathering sources, then drafting. Delegating."),
        ]

    def compose(self) -> ComposeResult:
        """Build the split layout: transcript+composer | right rail."""
        with Horizontal():
            with Vertical():
                yield Static("", id="chat-transcript")
                with Horizontal(id="chat-composer-row"):
                    yield Static(
                        f"[{BRAND}]▸[/{BRAND}]",
                        id="chat-prompt-glyph",
                        markup=True,
                    )
                    yield Input(
                        placeholder="ask hachi…  (↵ send · ⎋ interrupt)",
                        id="chat-composer",
                    )
            yield Static("", id="chat-rail")

    def on_mount(self) -> None:
        """Reset stop event on (re)mount."""
        self._stop = threading.Event()

    def on_unmount(self) -> None:
        """Cancel any active stream worker on unmount."""
        self._stop.set()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter in the composer Input."""
        if event.input.id == "chat-composer":
            self._on_composer_submit(event.value)
            event.input.value = ""

    def on_key(self, event: object) -> None:
        """Handle Escape to interrupt the active stream."""
        from textual.events import Key  # local import to avoid circular at module load

        if isinstance(event, Key) and event.key == "escape":
            self._interrupt_stream()

    def populate(self, data: CockpitData) -> None:
        """Render the transcript and right rail with live config/session data."""
        self._data = data
        self._render_transcript()
        self._render_rail()

    # ------------------------------------------------------------------
    # Hook
    # ------------------------------------------------------------------

    def activate_selected(self) -> None:
        """Focus the composer Input (called by the screen on Enter)."""
        self.query_one("#chat-composer", Input).focus()

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------

    def _on_composer_submit(self, text: str) -> None:
        """Append the user message then either stream a live reply or echo locally.

        Live path (is_live):
          1. Lazy-create a session if needed.
          2. POST the message via cockpit_data.send().
          3. Spin a thread worker to stream the reply.

        Offline / error path:
          Appends a local-echo stub reply so demo/offline mode still works.
        """
        stripped = text.strip()
        if not stripped:
            return

        self._messages.append(_TranscriptMessage("you", stripped))
        self._render_transcript()

        data = self._data
        if data is None or not data.is_live:
            # Offline / demo mode — local echo stub
            self._messages.append(_TranscriptMessage("hachi", "Got it — working on that now."))
            self._render_transcript()
            return

        # ── Live path ──────────────────────────────────────────────
        # Lazy session creation
        if self._session_id is None:
            sid = data.start_session()
            if sid is None:
                # start_session failed — fall back to local echo
                self._messages.append(_TranscriptMessage("hachi", "Got it — working on that now."))
                self._render_transcript()
                return
            self._session_id = sid

        # POST the message (fire-and-forget; streaming carries the reply)
        data.send(self._session_id, stripped)

        # Seed an empty streaming hachi line with a caret
        self._messages.append(_TranscriptMessage("hachi", "", is_streaming=True))
        self._render_transcript()

        # Reset stop event and launch worker
        self._stop = threading.Event()
        self._stream_worker = self.run_worker(
            self._stream_thread_worker,
            thread=True,
            exclusive=True,
        )

    # ------------------------------------------------------------------
    # Stream worker (thread)
    # ------------------------------------------------------------------

    def _stream_thread_worker(self) -> None:
        """Thread worker: iterate the SSE stream and push events to the main thread.

        Runs inside a Textual thread worker.  All UI mutations go through
        ``self.app.call_from_thread`` to stay on the main thread.
        """
        worker = get_current_worker()
        data = self._data
        session_id = self._session_id

        if data is None or session_id is None:
            return

        try:
            for ev in data.stream(session_id, after=self._last_seq, stop_event=self._stop):
                if worker.is_cancelled or self._stop.is_set():
                    break
                self._last_seq = max(self._last_seq, ev.sequence)
                self.app.call_from_thread(self._apply_event, ev)
        except Exception:
            # Stream errors (no LLM key, network, etc.) — degrade gracefully
            self.app.call_from_thread(self._on_stream_error)

    # ------------------------------------------------------------------
    # Event application (main thread via call_from_thread)
    # ------------------------------------------------------------------

    def _apply_event(self, ev: RuntimeEvent) -> None:  # noqa: C901
        """Apply a single SSE event to the in-memory transcript.

        Called on the Textual main thread via ``app.call_from_thread``.

        Event types (from hachi/core/runtime_events.py):
          - ``text.stream.delta``    → append text delta to in-progress hachi line
          - ``tool.call.started``    → append a tool-started card
          - ``tool.call.completed``  → append a tool-done card
          - ``permission.requested`` → push ApprovalModal (if request_id present)
          - ``session.chat.completed`` / ``session.turn.cancelled`` → finalize line
          - All others → ignored silently
        """
        et = ev.event_type
        p = ev.payload

        if et == _EV_TEXT_DELTA:
            delta = str(p.get("text") or "")
            self._append_to_streaming_line(delta)

        elif et == _EV_TOOL_STARTED:
            name = str(p.get("name") or "?")
            inp = p.get("input") or {}
            inp_str = str(inp)[:80] if inp else ""
            card = f"◐ {name}"
            if inp_str:
                card += f"  {inp_str}"
            self._messages.append(_TranscriptMessage("tool", card))
            self._render_transcript()

        elif et == _EV_TOOL_DONE:
            name = str(p.get("name") or "?")
            preview = str(p.get("result_preview") or "")[:80]
            card = f"✓ {name}"
            if preview:
                card += f"  {preview}"
            self._messages.append(_TranscriptMessage("tool", card))
            self._render_transcript()

        elif et == _EV_PERM_REQUESTED:
            self._handle_permission_event(p)

        elif et in (_EV_CHAT_COMPLETED, _EV_CANCELLED):
            self._finalize_streaming_line()
            self._stop.set()

        elif et == _EV_CHAT_STARTED:
            # Nothing to render; stream is underway
            pass

        # All other event types are intentionally ignored.

    def _append_to_streaming_line(self, delta: str) -> None:
        """Append *delta* to the last in-progress hachi message."""
        for msg in reversed(self._messages):
            if msg.speaker == "hachi" and msg.is_streaming:
                msg.text += delta
                self._render_transcript()
                return
        # No in-progress line — create one
        self._messages.append(_TranscriptMessage("hachi", delta, is_streaming=True))
        self._render_transcript()

    def _finalize_streaming_line(self) -> None:
        """Mark the last streaming hachi line as complete (remove caret)."""
        for msg in reversed(self._messages):
            if msg.speaker == "hachi" and msg.is_streaming:
                msg.is_streaming = False
                break
        self._render_transcript()

    def _handle_permission_event(self, payload: dict[str, object]) -> None:
        """Push the leash modal if the payload carries a request_id.

        The ``permission.requested`` payload (from hachi/core/approvals.py) always
        carries ``request_id``, ``operation``, ``tool``, ``target``, ``reason``,
        and ``policy_summary`` — verified by reading the emit calls in
        RegistryApprover.require() at approvals.py:328.
        """
        request_id = str(payload.get("request_id") or "")

        if not request_id:
            # GAP: payload did not carry request_id — cannot wire the modal.
            # Degrade gracefully: show an inline card so the user is not blocked.
            op = str(payload.get("operation") or "action")
            tool = str(payload.get("tool") or "?")
            self._messages.append(
                _TranscriptMessage(
                    "tool",
                    f"⚠ approval needed: {op} → {tool}  (no request_id in event payload)",
                )
            )
            self._render_transcript()
            return

        # Build an Approval model from the event payload
        from hachi.client.models import Approval

        approval = Approval.from_api(
            {
                "request_id": request_id,
                "operation": payload.get("operation") or "action",
                "tool": payload.get("tool") or "",
                "target": payload.get("target") or "",
                "reason": payload.get("reason") or "Hachi needs this to continue",
                "policy_summary": payload.get("policy_summary") or "asks first",
            }
        )

        # Push the leash modal
        try:
            from hachi.tui.cockpit.approval import ApprovalModal

            screen = self.app.screen
            self.app.push_screen(ApprovalModal(approval, screen))
        except Exception:
            # Modal push failed (e.g. screen type mismatch) — show inline card
            self._messages.append(
                _TranscriptMessage(
                    "tool",
                    f"⚠ approval needed: {approval.op} → {approval.action}",
                )
            )
            self._render_transcript()

    def _on_stream_error(self) -> None:
        """Handle stream-level errors on the main thread (no LLM key, network, etc.)."""
        self._finalize_streaming_line()
        # If the streaming hachi line is empty, give a minimal feedback message
        for msg in reversed(self._messages):
            if msg.speaker == "hachi":
                if not msg.text:
                    msg.text = "(stream ended — no reply)"
                break
        self._render_transcript()

    def _interrupt_stream(self) -> None:
        """Set the stop event to cancel the active stream worker."""
        self._stop.set()
        self._finalize_streaming_line()

    # ------------------------------------------------------------------
    # Transcript renderer
    # ------------------------------------------------------------------

    def _render_transcript(self) -> None:
        """Re-build the transcript Static from the in-memory message list."""
        t = Text()
        for msg in self._messages:
            if msg.speaker == "you":
                t.append("you ▸", style=NAVY)
                t.append(f" {msg.text}\n", style=FOREGROUND)
            elif msg.speaker == "hachi":
                t.append("hachi ▸", style=BRAND)
                t.append(f" {msg.text}", style=FOREGROUND)
                if msg.is_streaming:
                    t.append("█", style=BRAND)  # streaming caret
                t.append("\n")
            elif msg.speaker == "tool":
                # Tool card — indented, with separator lines
                t.append("━" * 40 + "\n", style=BORDER_MUTED)
                # Parse glyph prefix to pick color
                raw = msg.text
                if raw.startswith("✓"):
                    t.append(f"  {raw}\n", style=GREEN)
                elif raw.startswith("◐"):
                    t.append(f"  {raw}\n", style=AMBER)
                elif raw.startswith("⚠"):
                    t.append(f"  {raw}\n", style=DANGER)
                else:
                    t.append(f"  {raw}\n", style=MUTED)
                t.append("━" * 40 + "\n", style=BORDER_MUTED)

        self.query_one("#chat-transcript", Static).update(t)

    # ------------------------------------------------------------------
    # Right rail
    # ------------------------------------------------------------------

    def _render_rail(self) -> None:
        """Build the right-rail content from live config + session data."""
        t = Text()

        # Plan checklist — no gateway data model backs a live per-turn plan
        # today (see BB-60), so only show the representative steps in
        # offline/demo mode. Live sessions omit the section entirely rather
        # than showing fabricated steps, mirroring frontend run.tsx.
        if self._data is None or not self._data.is_live:
            t.append("plan · what's next\n", style=_DIM)
            for color, glyph, label in _DEMO_PLAN_STEPS:
                t.append(f"{glyph} {label}\n", style=color)

            t.append("\n")
            t.append("─" * 28 + "\n", style=BORDER_MUTED)

        # Context block
        t.append("context\n", style=_DIM)
        cfg = self._data.config() if self._data else None
        sessions = self._data.sessions(limit=1) if self._data else []
        sess = sessions[0] if sessions else None

        # Prefer the live session we created; fall back to sessions list
        active_sid = self._session_id or (sess.id if sess else None)
        turns = sess.turns if sess else 0

        model_name = cfg.model if cfg else "—"
        sess_id_display = (active_sid[:6] if active_sid else "—").upper()

        total_cost = 0.0
        if self._data:
            sp = self._data.spend()
            total_cost = sum(m.cost for m in sp.models)
        in_total = 0
        if self._data:
            sp2 = self._data.spend()
            in_total = sum(tr.in_t for tr in sp2.turns)

        t.append("model   ", style=_DIM)
        t.append(f"{model_name}\n", style=MUTED)

        t.append("tokens  ", style=_DIM)
        tok_k = f"{in_total // 1000}k" if in_total >= 1000 else str(in_total)
        t.append(f"{tok_k}\n", style=MUTED)

        t.append("spend   ", style=_DIM)
        t.append(f"${total_cost:.2f}\n", style=MUTED)

        t.append("session ", style=_DIM)
        t.append(f"0x{sess_id_display[:4]} · t{turns}\n", style=MUTED)

        t.append("\n")
        t.append("─" * 28 + "\n", style=BORDER_MUTED)

        # Approval card — reflects CockpitData.approvals() (real pending
        # approvals when live, representative placeholder data offline).
        # Previously hardcoded to "1 approval waiting / browse_web
        # (researcher)" regardless of actual state; see BB-60.
        approvals = self._data.approvals() if self._data else []
        if approvals:
            first = approvals[0]
            count = len(approvals)
            noun = "approval" if count == 1 else "approvals"
            detail = first.touches[0] if first.touches else first.scope
            t.append(f"⚠ {count} {noun} waiting\n", style=BRAND)
            t.append(f"{first.request} ({detail})\n", style=MUTED)
            t.append("[a] review now", style=NAVY)
        else:
            t.append("✓ no approvals waiting\n", style=MUTED)

        self.query_one("#chat-rail", Static).update(t)
