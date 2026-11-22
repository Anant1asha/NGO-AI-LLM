"""Structured (multimodal) tool-result support.

Most tools return a string, which the execution loop drops verbatim into the
``tool_result`` block's ``content`` field. That is correct for text, but it makes
it impossible to hand richer content — most importantly **images** — back to the
model, because Anthropic's ``tool_result`` ``content`` accepts *either* a string
*or* a list of content blocks (``text``/``image``), never an arbitrary dict.

:class:`ToolResultBlocks` is the opt-in escape hatch. A tool that wants the model
to *see* an image returns ``ToolResultBlocks([...image/text blocks...])`` and the
loop passes those blocks straight through instead of calling ``str()`` on the
result. Every other tool is unaffected — only this exact type triggers
pass-through, so tools that legitimately return plain dicts keep being stringified.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolResultBlocks:
    """A tool result expressed as raw provider content blocks.

    Attributes:
        blocks: A list of provider content-block dicts (e.g.
            ``{"type": "image", "source": {...}}`` and/or
            ``{"type": "text", "text": "..."}``). Passed through to the
            ``tool_result`` ``content`` field unchanged.
        summary: A short plain-text description used for event logging and
            transcripts (where rendering a base64 image would be useless/huge).
    """

    blocks: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
