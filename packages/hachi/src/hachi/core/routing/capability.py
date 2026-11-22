"""Capability vocabulary shared by the model registry and provider protocols.

All capability strings are declared here — neither provider adapters nor tool code
should hard-code vendor-specific capability strings.
"""

from __future__ import annotations

from enum import StrEnum


class Capability(StrEnum):
    """A named capability that a model or service provider may advertise.

    Used by :class:`~hachi.core.routing.descriptor.ModelDescriptor`,
    :class:`~hachi.core.providers.base.AIProvider`, and
    :class:`~hachi.core.routing.router.ModelRouter` to route by capability
    rather than by vendor name.
    """

    REASONING = "reasoning"
    CODING = "coding"
    SUMMARIZATION = "summarization"
    TITLE_GENERATION = "title_generation"
    COMPACTION = "compaction"
    LONG_CONTEXT = "long_context"
    VISION = "vision"
    EMBEDDINGS = "embeddings"
    SPEECH_TO_TEXT = "speech_to_text"
    TEXT_TO_SPEECH = "text_to_speech"
    WEB_SEARCH = "web_search"
    REALTIME = "realtime"
