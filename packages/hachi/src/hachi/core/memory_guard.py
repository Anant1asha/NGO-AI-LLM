"""Memory Content Security Scanner.

Scans inbound memory content for prompt-injection and role-hijack patterns
before it reaches long-term storage. The scanner uses layered checks:

1. Unicode hygiene (invisible/control characters)
2. Canonical normalization (NFKC) so some obfuscated variants still match
3. Weighted threat scoring across a small set of English-language indicator
   families (see ``_THREAT_SIGNALS``)

This is a fast, deterministic, defense-in-depth heuristic — a handful of
regexes, not a comprehensive prompt-injection classifier. It is NOT
resistant to non-English phrasing, homoglyph substitution beyond NFKC
normalization, or encoded payloads (e.g. base64). Do not treat a clean
``scan()`` result as a guarantee that content is safe; it is one signal
among several (see M8 in ``docs/audit/2026-07-03/PRODUCTION_READINESS.md``).

The public API remains ``scan(content) -> (is_safe, threat_id)``.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class _ThreatSignal:
    pattern: re.Pattern[str]
    threat_id: str
    score: int


# Higher score means stronger confidence that the text is instructional abuse.
_THREAT_SIGNALS: tuple[_ThreatSignal, ...] = (
    _ThreatSignal(
        re.compile(
            r"(?:ignore|forget|disregard|override)\s+(?:all|any|the|previous|prior|above)?\s*"
            r"(?:system|safety|policy|rules?|instructions?)",
            re.IGNORECASE,
        ),
        "instruction_override",
        5,
    ),
    _ThreatSignal(
        re.compile(
            r"(?:you\s+are\s+now|act\s+as|assume\s+the\s+role\s+of|behave\s+as)",
            re.IGNORECASE,
        ),
        "role_hijack",
        4,
    ),
    _ThreatSignal(
        re.compile(
            r"(?:do\s+not\s+tell\s+the\s+user|hide\s+this\s+from\s+the\s+user)", re.IGNORECASE
        ),
        "deception",
        4,
    ),
    _ThreatSignal(
        re.compile(r"(?:developer|system)\s+prompt\s*[:=]", re.IGNORECASE),
        "prompt_leak_priming",
        3,
    ),
    _ThreatSignal(
        re.compile(r"<\s*/?\s*(?:system|prompt|instruction|policy)\s*>", re.IGNORECASE),
        "xml_injection",
        3,
    ),
    _ThreatSignal(
        re.compile(r"(?:tool\s*:\s*|function\s*call\s*:\s*|json\s*tool\s*payload)", re.IGNORECASE),
        "tool_call_injection",
        2,
    ),
)

# Zero-width and invisible Unicode characters that can be used to hide
# injections inside seemingly benign text.
_INVISIBLE_CHARS = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff\u00ad\u200e\u200f]")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")

_THREAT_SCORE_THRESHOLD = 5


def _normalize_for_scan(content: str) -> str:
    """Normalize content so obfuscated variants still match threat signals."""
    normalized = unicodedata.normalize("NFKC", content)
    normalized = _INVISIBLE_CHARS.sub("", normalized)
    normalized = _CONTROL_CHARS.sub("", normalized)
    return normalized


def _score_threats(content: str) -> tuple[int, str | None, int]:
    """Return cumulative score, strongest threat ID, and strongest signal score."""
    score = 0
    strongest: str | None = None
    strongest_score = 0

    for signal in _THREAT_SIGNALS:
        if signal.pattern.search(content):
            score += signal.score
            if signal.score > strongest_score:
                strongest = signal.threat_id
                strongest_score = signal.score

    return score, strongest, strongest_score


def scan(content: str) -> tuple[bool, str | None]:
    """Scan memory content for security threats.

    Args:
        content: The raw fact string to validate.

    Returns:
        A tuple of (is_safe, threat_id).
        is_safe is True when the content passes all checks.
        threat_id is None when safe, otherwise a short identifier
        like "prompt_injection" or "invisible_unicode".
    """
    if not content or not isinstance(content, str):
        return True, None

    # Invisible Unicode is blocked directly and tagged for quarantine/review.
    if _INVISIBLE_CHARS.search(content):
        return False, "invisible_unicode"

    # Control characters frequently indicate encoded/obfuscated payload attempts.
    if _CONTROL_CHARS.search(content):
        return False, "control_chars"

    normalized = _normalize_for_scan(content)
    threat_score, strongest_signal, strongest_score = _score_threats(normalized)

    if threat_score >= _THREAT_SCORE_THRESHOLD:
        return False, strongest_signal or "composite_injection"

    # Keep backward compatibility for strong, single-signal matches.
    if strongest_signal and strongest_score >= 4:
        return False, strongest_signal

    return True, None
