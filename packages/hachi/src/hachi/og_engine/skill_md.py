"""SKILL.md → ObjectGraph bridge.

The wider agent ecosystem has standardized on ``SKILL.md`` (Agent Skills): a
markdown file with YAML-ish frontmatter (``name`` / ``description``) and a
markdown body. Hachi's ``.og`` format is more token-efficient but isolated;
this module imports a SKILL.md into an :class:`OGFile` so existing community
skills become usable through the 3-pass engine (search → peek → load).

The converter is pure (no I/O) so it is fully unit-testable; the engine wraps it
with file writing + hot-loading (see ``SkillEngine.import_skill_md``).
"""

from __future__ import annotations

import re

from hachi.og_engine.parser import OGFile, OGFileMeta, OGNode
from hachi.og_engine.serializer import index_entry_for_node

_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "of",
    "for",
    "in",
    "on",
    "with",
    "this",
    "that",
    "from",
    "your",
    "you",
    "it",
    "is",
    "are",
    "be",
    "as",
    "by",
    "at",
    "use",
    "using",
    "used",
    "can",
    "will",
    "into",
    "when",
    "how",
    "what",
    "skill",
}
_NUMBERED_STEP = re.compile(r"^\s*\d+[.)]\s+(.*)$")
_DENSE_MAX_CHARS = 160


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (name or "").strip().lower()).strip("_")
    return slug or "imported_skill"


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Split leading ``---`` YAML frontmatter (simple key: value) from the body."""
    if not text.startswith("---"):
        return {}, text.strip()

    lines = text.split("\n")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text.strip()

    front: dict[str, str] = {}
    for line in lines[1:end]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        front[key.strip().lower()] = value.strip().strip('"').strip("'")
    body = "\n".join(lines[end + 1 :]).strip()
    return front, body


def _derive_keywords(name: str, description: str, body: str, limit: int = 10) -> list[str]:
    """Pick routing keywords from the name + description (Pass-1 search terms)."""
    source = f"{name} {description}".lower()
    seen: list[str] = []
    for token in re.findall(r"[a-z0-9]{3,}", source):
        if token in _STOPWORDS or token in seen:
            continue
        seen.append(token)
        if len(seen) >= limit:
            break
    if not seen:  # fall back to body terms if name/description were empty
        for token in re.findall(r"[a-z0-9]{3,}", body.lower()):
            if token not in _STOPWORDS and token not in seen:
                seen.append(token)
            if len(seen) >= limit:
                break
    return seen


def _extract_steps(body: str) -> list[str]:
    """Pull a leading numbered list out of the body, if present."""
    steps: list[str] = []
    for line in body.split("\n"):
        match = _NUMBERED_STEP.match(line)
        if match:
            steps.append(match.group(1).strip())
        elif steps and not line.strip():
            continue
        elif steps:
            break  # the numbered list ended
    return steps


def skill_md_to_og(text: str, *, fallback_name: str = "imported_skill") -> OGFile:
    """Convert SKILL.md text into a single-node :class:`OGFile`."""
    front, body = _parse_frontmatter(text)
    name = front.get("name") or fallback_name
    slug = _slugify(name)
    description = front.get("description", "")

    dense = (description or body[:_DENSE_MAX_CHARS]).strip()
    if len(dense) > _DENSE_MAX_CHARS:
        dense = dense[: _DENSE_MAX_CHARS - 1].rstrip() + "…"

    node = OGNode(
        name=slug,
        role="skill",
        scope="all",
        keywords=_derive_keywords(name, description, body),
        dense=dense,
        full=body,
        steps=_extract_steps(body),
    )
    meta = OGFileMeta(
        title=name,
        version="1.0.0",
        author="skill-md-import",
        domain="imported",
        scope="all",
    )
    return OGFile(meta=meta, index=[index_entry_for_node(node)], nodes=[node])
