"""
Memory Importer — portable conversation history ingestion

Parses exported conversation files from ChatGPT, Gemini, and Hermes (and
generic JSON chat logs) and loads them into Hachi as:

  1. SessionStore transcript rows — so imported conversations are searchable
     via ``hachi session search`` and resumable.
  2. MemoryVault core_memory facts — each conversation produces a compact
     summary fact indexed for semantic retrieval.

The importer never writes directly to the DB; it goes through the normal
``SessionStore`` and ``MemoryVault`` APIs so MemoryGuard, WAL locking, and
capacity checks are all respected.

Supported formats
-----------------
chatgpt   - conversations.json from OpenAI's data export.
gemini    - Bard/Gemini conversations.json or myactivity.json (Google Takeout).
hermes    - Generic Hermes/open-source agent JSON logs.
auto      - Sniff the structure and pick the right parser.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from hachi.core.memory_vault import MemoryVault
    from hachi.core.session_store import SessionStore

logger = logging.getLogger(__name__)

# Sentinel returned by MemoryVault when the user_profile cap is hit.
_LIMIT_REACHED = "LIMIT_REACHED"

# Max characters of a conversation we feed to the summary fact.
_SUMMARY_SNIPPET_CHARS = 600


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Turn:
    """A single user/assistant exchange."""

    role: str  # "user" | "assistant" | "tool"
    content: str


@dataclass
class Conversation:
    """A parsed conversation ready for ingestion."""

    title: str
    turns: list[Turn] = field(default_factory=list)
    source: str = ""  # "chatgpt" | "gemini" | "hermes" | …


@dataclass
class ImportResult:
    """Summary of a completed import operation."""

    format_detected: str
    conversations_parsed: int
    sessions_created: int
    memory_facts_added: int
    skipped: int  # empty / unparseable conversations


# ---------------------------------------------------------------------------
# Format parsers
# ---------------------------------------------------------------------------


def _parse_chatgpt(data: Any) -> list[Conversation]:
    """Parse OpenAI ChatGPT export (conversations.json).

    Structure::

        [
          {
            "title": "...",
            "mapping": {
              "<uuid>": {
                "message": {
                  "author": {"role": "user"|"assistant"},
                  "content": {"content_type": "text", "parts": ["..."]}
                }
              }
            }
          }
        ]
    """
    if not isinstance(data, list):
        raise ValueError("ChatGPT export must be a JSON array of conversations.")

    convos: list[Conversation] = []
    for item in data:
        title = str(item.get("title") or "Untitled")
        mapping = item.get("mapping") or {}

        # Build a turn list ordered by the message tree (breadth-first via parent links).
        # For simplicity we sort by insertion order and skip None messages.
        turns: list[Turn] = []
        for node in mapping.values():
            msg = node.get("message")
            if not msg:
                continue
            role = msg.get("author", {}).get("role", "")
            if role not in {"user", "assistant"}:
                continue
            content_obj = msg.get("content") or {}
            parts = content_obj.get("parts") or []
            text = " ".join(str(p) for p in parts if isinstance(p, str)).strip()
            if text:
                turns.append(Turn(role=role, content=text))

        if turns:
            convos.append(Conversation(title=title, turns=turns, source="chatgpt"))

    return convos


def _parse_gemini(data: Any) -> list[Conversation]:
    """Parse Google Gemini / Bard export.

    Google Takeout produces two possible structures:

    1. ``conversations.json`` — ``[{title, conversations: [{role, text}]}]``
    2. ``myactivity.json``   — ``[{title, subtitles: [{text}], details: [{activityControls}]}]``
       (activity log, very limited — we treat each activity as a one-turn conversation)

    We handle both gracefully.
    """
    if not isinstance(data, list):
        raise ValueError("Gemini export must be a JSON array.")

    convos: list[Conversation] = []
    for item in data:
        title = str(item.get("title") or "Untitled")

        # Format 1: conversationsData / conversations array
        raw_turns = item.get("conversationsData") or item.get("conversations") or []
        if raw_turns and isinstance(raw_turns, list):
            turns: list[Turn] = []
            for t in raw_turns:
                role = str(t.get("role") or t.get("author") or "").lower()
                text = str(t.get("text") or t.get("content") or "").strip()
                if role in {"user", "human"}:
                    role = "user"
                elif role in {"model", "assistant", "bard", "gemini"}:
                    role = "assistant"
                else:
                    continue
                if text:
                    turns.append(Turn(role=role, content=text))
            if turns:
                convos.append(Conversation(title=title, turns=turns, source="gemini"))
            continue

        # Format 2: activity log (subtitles)
        subtitles = item.get("subtitles") or []
        text_parts = [s.get("text", "") for s in subtitles if isinstance(s, dict)]
        text = " ".join(text_parts).strip()
        if text:
            convos.append(
                Conversation(
                    title=title,
                    turns=[Turn(role="user", content=text)],
                    source="gemini",
                )
            )

    return convos


def _parse_hermes(data: Any) -> list[Conversation]:
    """Parse Hermes/generic open-source agent JSON.

    Accepts two shapes:

    1. A list of conversations: ``[{title?, messages: [{role, content}]}]``
    2. A flat message list (single conversation): ``[{role, content}]``
    """
    if not isinstance(data, list):
        raise ValueError("Hermes export must be a JSON array.")

    if not data:
        return []

    first = data[0]

    # Shape 2: flat turn list
    if isinstance(first, dict) and "role" in first and "content" in first:
        turns = [
            Turn(role=t["role"], content=str(t.get("content") or "").strip())
            for t in data
            if isinstance(t, dict)
            and t.get("role") in {"user", "assistant", "tool"}
            and t.get("content")
        ]
        if not turns:
            return []
        return [Conversation(title="Imported Hermes session", turns=turns, source="hermes")]

    # Shape 1: list of conversations
    convos: list[Conversation] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("name") or "Untitled")
        raw = item.get("messages") or item.get("turns") or item.get("history") or []
        turns = [
            Turn(role=t["role"], content=str(t.get("content") or "").strip())
            for t in raw
            if isinstance(t, dict)
            and t.get("role") in {"user", "assistant", "tool"}
            and t.get("content")
        ]
        if turns:
            convos.append(Conversation(title=title, turns=turns, source="hermes"))
    return convos


def _sniff_format(data: Any) -> str:
    """Heuristically detect which format *data* is from."""
    if not isinstance(data, list) or not data:
        return "hermes"  # fallback

    first = data[0]
    if not isinstance(first, dict):
        return "hermes"

    # ChatGPT: has "mapping" key with UUID sub-nodes
    if "mapping" in first:
        return "chatgpt"

    # Gemini: has "conversationsData" / "conversations" / "subtitles"
    if any(k in first for k in ("conversationsData", "conversations", "subtitles")):
        return "gemini"

    # Flat turn list (Hermes shape 2)
    if "role" in first and "content" in first:
        return "hermes"

    # Conversation list (Hermes shape 1)
    if any(k in first for k in ("messages", "turns", "history")):
        return "hermes"

    return "hermes"


def parse_file(path: Path, format: str = "auto") -> tuple[list[Conversation], str]:
    """Load and parse an export file.

    Args:
        path: Path to the JSON export file.
        format: "chatgpt" | "gemini" | "hermes" | "auto".

    Returns:
        (conversations, detected_format)

    Raises:
        ValueError: If the file cannot be parsed as the declared format.
        FileNotFoundError: If the path doesn't exist.
    """
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)

    if format == "auto":
        format = _sniff_format(data)

    parsers = {"chatgpt": _parse_chatgpt, "gemini": _parse_gemini, "hermes": _parse_hermes}
    parser = parsers.get(format)
    if parser is None:
        raise ValueError(f"Unknown format: {format!r}. Choose from: {list(parsers)}")

    return parser(data), format


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------


def _make_summary_fact(convo: Conversation) -> str:
    """Build a short core_memory fact summarising the imported conversation."""
    first_user = next((t.content for t in convo.turns if t.role == "user"), "")
    snippet = first_user[:_SUMMARY_SNIPPET_CHARS]
    return f"[imported:{convo.source}] Conversation titled '{convo.title}'. Opening: {snippet}"


def ingest(
    conversations: list[Conversation],
    session_store: SessionStore,
    memory_vault: MemoryVault | None = None,
    model_label: str = "imported",
) -> ImportResult:
    """Load parsed conversations into SessionStore and optionally MemoryVault.

    Each conversation becomes:
    - One new session in SessionStore (title pre-set, all turns logged).
    - One core_memory fact in MemoryVault (the opening exchange as a snippet).

    Args:
        conversations: Output of :func:`parse_file`.
        session_store: The target session store.
        memory_vault: Optional vault; memory facts skipped when None.
        model_label: Value stored in sessions.model for imported sessions.

    Returns:
        :class:`ImportResult` summary.
    """
    sessions_created = 0
    facts_added = 0
    skipped = 0

    for convo in conversations:
        if not convo.turns:
            skipped += 1
            continue

        # Create session
        sid = session_store.start_session(model=model_label)
        session_store.set_session_title(sid, convo.title[:72])
        for turn in convo.turns:
            session_store.log_message(sid, turn.role, turn.content)
        session_store.end_session(sid)
        sessions_created += 1

        # Persist summary fact
        if memory_vault is not None:
            fact = _make_summary_fact(convo)
            result = memory_vault.upsert_fact(fact, category="imported_conversation")
            if not result.startswith("BLOCKED"):
                facts_added += 1

    return ImportResult(
        format_detected="",  # filled in by caller
        conversations_parsed=len(conversations),
        sessions_created=sessions_created,
        memory_facts_added=facts_added,
        skipped=skipped,
    )
