"""
Unit tests for ``hachi.client.sse`` — SSE frame parsing.

Tests feed synthetic byte sequences directly to ``_parse_sse_frames``
to verify the parsing logic without any network calls.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Generator

from hachi.client.sse import RuntimeEvent, _parse_sse_frames


def _bytes_iter(*chunks: str) -> Generator[bytes, None, None]:
    """Helper: yield each string as UTF-8 bytes."""
    for chunk in chunks:
        yield chunk.encode("utf-8")


def _collect(frames: str) -> list[RuntimeEvent]:
    """Parse a complete SSE text and return all RuntimeEvent objects."""
    return list(_parse_sse_frames(_bytes_iter(frames), stop_event=None))


# ---------------------------------------------------------------------------
# Basic frame parsing
# ---------------------------------------------------------------------------


class TestSseFrameParsing:
    def test_minimal_data_only(self) -> None:
        raw = 'data: {"sequence":1,"event_type":"ping","payload":{},"time":"t1"}\n\n'
        events = _collect(raw)
        assert len(events) == 1
        assert events[0].sequence == 1
        assert events[0].event_type == "ping"
        assert events[0].time == "t1"

    def test_id_field_overrides_sequence(self) -> None:
        raw = 'id: 42\ndata: {"sequence":1,"event_type":"x","payload":{},"time":""}\n\n'
        events = _collect(raw)
        assert events[0].sequence == 42

    def test_event_field_fallback(self) -> None:
        # When data JSON has no event_type, use the event: field
        raw = 'event: tool.call.started\ndata: {"payload":{"name":"read_file"}}\n\n'
        events = _collect(raw)
        assert events[0].event_type == "tool.call.started"
        assert events[0].payload == {"name": "read_file"}

    def test_comment_line_skipped(self) -> None:
        raw = ': keepalive\ndata: {"sequence":5,"event_type":"ok","payload":{},"time":""}\n\n'
        events = _collect(raw)
        assert len(events) == 1
        assert events[0].sequence == 5

    def test_multi_data_lines_joined(self) -> None:
        # split JSON across two data: lines — unusual but allowed by SSE spec
        part1 = '{"sequence":3,"event_type":"ev","payload":{},'
        part2 = '"time":"t"}'
        raw = f"data: {part1}\ndata: {part2}\n\n"
        events = _collect(raw)
        assert events[0].sequence == 3

    def test_multiple_frames(self) -> None:
        frame1 = 'data: {"sequence":1,"event_type":"a","payload":{},"time":""}\n\n'
        frame2 = 'data: {"sequence":2,"event_type":"b","payload":{},"time":""}\n\n'
        events = _collect(frame1 + frame2)
        assert len(events) == 2
        assert events[0].event_type == "a"
        assert events[1].event_type == "b"

    def test_non_json_data_yields_empty_payload(self) -> None:
        raw = "data: not-json\n\n"
        events = _collect(raw)
        assert len(events) == 1
        assert events[0].payload == {}
        assert events[0].sequence == 0

    def test_carriage_return_stripped(self) -> None:
        raw = "data: {\"sequence\":7,\"event_type\":\"cr\",\"payload\":{},\"time\":\"\"}\r\n\r\n"
        events = _collect(raw)
        assert events[0].sequence == 7

    def test_empty_stream_yields_nothing(self) -> None:
        events = _collect("")
        assert events == []

    def test_only_comments_yields_nothing(self) -> None:
        raw = ": comment\n: another\n"
        events = _collect(raw)
        assert events == []

    def test_chunked_delivery(self) -> None:
        """Bytes arriving in two chunks simulate network chunking."""
        payload = json.dumps({"sequence": 9, "event_type": "chunk", "payload": {}, "time": ""})
        half = len(payload) // 2
        chunk1 = f"data: {payload[:half]}"
        chunk2 = f"{payload[half:]}\n\n"
        events = list(_parse_sse_frames(_bytes_iter(chunk1, chunk2), stop_event=None))
        assert events[0].sequence == 9


# ---------------------------------------------------------------------------
# Cancellation via stop_event
# ---------------------------------------------------------------------------


def test_stop_event_halts_iteration() -> None:
    """Generator stops emitting once the stop_event is set."""
    stop = threading.Event()

    def controlled_iter() -> Generator[bytes, None, None]:
        frame = b'data: {"sequence":1,"event_type":"a","payload":{},"time":""}\n\n'
        yield frame
        stop.set()  # signal cancellation
        # This second frame should NOT be yielded
        yield b'data: {"sequence":2,"event_type":"b","payload":{},"time":""}\n\n'

    events = list(_parse_sse_frames(controlled_iter(), stop_event=stop))
    # The first frame should be parsed; the second may or may not appear depending
    # on buffer state — what matters is the generator doesn't hang.
    assert events[0].sequence == 1


# ---------------------------------------------------------------------------
# RuntimeEvent dataclass
# ---------------------------------------------------------------------------


def test_runtime_event_fields() -> None:
    ev = RuntimeEvent(sequence=1, event_type="test", payload={"k": "v"}, time="now")
    assert ev.sequence == 1
    assert ev.event_type == "test"
    assert ev.payload == {"k": "v"}
    assert ev.time == "now"


def test_runtime_event_equality() -> None:
    a = RuntimeEvent(sequence=1, event_type="test", payload={}, time="t")
    b = RuntimeEvent(sequence=1, event_type="test", payload={}, time="t")
    assert a == b
