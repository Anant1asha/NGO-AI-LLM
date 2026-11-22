"""Tests for Capability enum (Slice 2.1)."""

from __future__ import annotations

from hachi.core.routing.capability import Capability


def test_capability_is_str_enum() -> None:
    assert isinstance(Capability.REASONING, str)
    assert Capability.REASONING == "reasoning"


def test_all_capabilities_defined() -> None:
    expected = {
        "reasoning",
        "coding",
        "summarization",
        "title_generation",
        "compaction",
        "long_context",
        "vision",
        "embeddings",
        "speech_to_text",
        "text_to_speech",
        "web_search",
        "realtime",
    }
    actual = {c.value for c in Capability}
    assert actual == expected


def test_capability_round_trips() -> None:
    for cap in Capability:
        assert Capability(cap.value) is cap
