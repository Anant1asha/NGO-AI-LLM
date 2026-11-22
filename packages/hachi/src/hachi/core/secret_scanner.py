"""Outbound secret-leak guard.

Detects and redacts common credential formats (API keys, tokens, private keys)
so the agent can't accidentally exfiltrate a secret it happened to read — e.g. by
posting a config file's contents to a Slack/Discord channel. The patterns are
deliberately specific (provider-prefixed keys, PEM blocks) to keep false positives
low; generic high-entropy heuristics are intentionally avoided.

Pure and dependency-free so it's trivially testable and reusable across any
outbound surface (messaging now; REST/browser are natural follow-ups).
"""

from __future__ import annotations

import os
import re

REDACTION_PLACEHOLDER = "[REDACTED SECRET]"

# (kind, compiled pattern). Order matters: the multi-line PEM block runs first so
# its body is redacted as a unit, and the more specific anthropic key precedes the
# generic openai-style key.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "private_key",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    ),
    ("anthropic_key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("openai_key", re.compile(r"sk-(?:proj-)?[A-Za-z0-9]{20,}")),
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("github_fine_grained_pat", re.compile(r"github_pat_[A-Za-z0-9_]{40,}")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("google_api_key", re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("google_oauth_secret", re.compile(r"GOCSPX-[A-Za-z0-9_\-]{20,}")),
    ("stripe_key", re.compile(r"(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{20,}")),
    ("sendgrid_key", re.compile(r"SG\.[A-Za-z0-9_\-]{16,}\.[A-Za-z0-9_\-]{16,}")),
    ("npm_token", re.compile(r"npm_[A-Za-z0-9]{36}")),
    # JWT bearer token: three base64url segments, header begins `eyJ` (= base64 `{"`).
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}")),
]


def find_secret_kinds(text: str) -> list[str]:
    """Return the kinds of secret detected in ``text`` (deduped, in pattern order)."""
    return [kind for kind, pat in _PATTERNS if pat.search(text)]


def contains_secret(text: str) -> bool:
    """True if ``text`` contains at least one recognized secret."""
    return any(pat.search(text) for _kind, pat in _PATTERNS)


def redact_secrets(text: str, placeholder: str = REDACTION_PLACEHOLDER) -> tuple[str, int]:
    """Replace every recognized secret in ``text`` with ``placeholder``.

    Args:
        text: The text to scrub.
        placeholder: The replacement string.

    Returns:
        ``(redacted_text, count)`` where ``count`` is how many secrets were replaced.
    """
    total = 0
    redacted = text
    for _kind, pat in _PATTERNS:
        redacted, n = pat.subn(placeholder, redacted)
        total += n
    return redacted, total


def outbound_redaction_disabled() -> bool:
    """True if the user opted out of outbound secret redaction (power-user escape hatch).

    Controlled by ``HACHI_ALLOW_OUTBOUND_SECRETS`` — the single env var honored by
    every outbound surface (messaging, REST, scheduled-webhook delivery).
    """
    return os.environ.get("HACHI_ALLOW_OUTBOUND_SECRETS", "").lower() in {"1", "true", "yes"}


def redact_outbound(text: str) -> tuple[str, int]:
    """Redact secrets from outbound text unless the user opted out. Returns ``(text, count)``."""
    if outbound_redaction_disabled():
        return text, 0
    return redact_secrets(text)


def redact_structure(obj: object) -> object:
    """Recursively walk *obj* and redact secrets from every string leaf.

    Handles ``str``, ``dict``, ``list``, and ``tuple`` inputs. All other types
    are returned unchanged. Dicts are rebuilt with both keys and values walked;
    keys that are strings are also redacted (unusual but defensive).

    Args:
        obj: Any Python value — typically a tool-input dict or result preview.

    Returns:
        A new object of the same type with all string leaves scrubbed.
    """
    if isinstance(obj, str):
        redacted, _ = redact_secrets(obj)
        return redacted
    if isinstance(obj, dict):
        return {redact_structure(k): redact_structure(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_structure(item) for item in obj]
    if isinstance(obj, tuple):
        return tuple(redact_structure(item) for item in obj)
    return obj
