"""
Hachi Cockpit — synchronous SSE stream reader.

Provides ``stream_events``, a generator that consumes the gateway's
Server-Sent Events stream at ``GET /sessions/{session_id}/stream``
and yields typed ``RuntimeEvent`` objects.

The generator is cancellable via a ``threading.Event``::

    stop = threading.Event()
    for event in stream_events(client, session_id, stop_event=stop):
        handle(event)
    # In another thread: stop.set()

The generator stops cleanly when:
  - The server closes the connection (stream ends).
  - ``stop_event`` is set before or during streaming.
  - The generator is garbage-collected / ``.close()`` is called.

Mirror of ``frontend/src/lib/data/sse.ts`` parsing logic:
  - Lines starting with ``:`` are comments/keepalives — skipped.
  - Blank lines dispatch the current accumulated frame.
  - Fields: ``id``, ``event``, ``data``, ``retry`` (others ignored).
  - Multi-line ``data:`` values are joined with ``\\n``.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Generator, Iterator
from dataclasses import dataclass
from typing import Any

import httpx

from .gateway import GatewayClient, GatewayError


@dataclass(frozen=True, slots=True)
class RuntimeEvent:
    """
    A parsed runtime event from the SSE stream.

    ``sequence``   — monotonically increasing gateway event id.
    ``event_type`` — domain event name, e.g. ``text.stream.delta``.
    ``payload``    — raw event payload dict.
    ``time``       — ISO-8601 timestamp string from the gateway envelope.
    """

    sequence: int
    event_type: str
    payload: dict[str, Any]
    time: str


def _parse_sse_frames(
    byte_iter: Generator[bytes, None, None],
    stop_event: threading.Event | None,
) -> Iterator[RuntimeEvent]:
    """
    Parse SSE byte stream into ``RuntimeEvent`` objects.

    Mirrors the TypeScript ``streamSSE`` parser exactly:
    - Comment lines (starting with ``:``) are ignored.
    - Blank lines dispatch the accumulated frame.
    - ``id``, ``event``, ``data`` fields are accumulated per frame.
    - The ``data`` field is assumed to contain a JSON envelope with shape
      ``{sequence, event_type, payload, time}`` (the gateway's
      ``GatewayEventPayload``).
    """
    buffer = ""
    ev_id: str | None = None
    ev_name = "message"
    ev_data_parts: list[str] = []

    for chunk in byte_iter:
        if stop_event and stop_event.is_set():
            return

        buffer += chunk.decode("utf-8", errors="replace")

        while "\n" in buffer:
            nl_pos = buffer.index("\n")
            line = buffer[:nl_pos]
            buffer = buffer[nl_pos + 1 :]

            # Strip trailing \r
            if line.endswith("\r"):
                line = line[:-1]

            if line == "":
                # Blank line — dispatch accumulated frame
                if ev_data_parts or ev_name != "message" or ev_id is not None:
                    raw_data = "\n".join(ev_data_parts)
                    # Try to parse the JSON envelope from data:
                    seq = 0
                    event_type = ev_name
                    payload: dict[str, Any] = {}
                    ts = ""
                    try:
                        envelope = json.loads(raw_data)
                        seq = int(envelope.get("sequence") or 0)
                        event_type = str(envelope.get("event_type") or ev_name)
                        payload = dict(envelope.get("payload") or {})
                        ts = str(envelope.get("time") or "")
                    except (json.JSONDecodeError, ValueError):
                        pass

                    # Prefer id: field as sequence if available
                    if ev_id is not None:
                        try:
                            seq = int(ev_id)
                        except ValueError:
                            pass

                    yield RuntimeEvent(
                        sequence=seq,
                        event_type=event_type,
                        payload=payload,
                        time=ts,
                    )

                # Reset accumulators
                ev_id = None
                ev_name = "message"
                ev_data_parts = []
                continue

            if line.startswith(":"):
                # Comment / keepalive — ignore
                continue

            colon_pos = line.find(":")
            if colon_pos == -1:
                field = line
                val = ""
            else:
                field = line[:colon_pos]
                val = line[colon_pos + 1 :]
                if val.startswith(" "):
                    val = val[1:]

            if field == "id":
                ev_id = val
            elif field == "event":
                ev_name = val
            elif field == "data":
                ev_data_parts.append(val)
            # Unknown fields (e.g. retry) are intentionally ignored

    # Flush trailing frame (mirrors TS dispatch() at end of stream)
    if ev_data_parts or ev_name != "message" or ev_id is not None:
        raw_data = "\n".join(ev_data_parts)
        seq = 0
        event_type = ev_name
        payload = {}
        ts = ""
        try:
            envelope = json.loads(raw_data)
            seq = int(envelope.get("sequence") or 0)
            event_type = str(envelope.get("event_type") or ev_name)
            payload = dict(envelope.get("payload") or {})
            ts = str(envelope.get("time") or "")
        except (json.JSONDecodeError, ValueError):
            pass
        if ev_id is not None:
            try:
                seq = int(ev_id)
            except ValueError:
                pass
        yield RuntimeEvent(sequence=seq, event_type=event_type, payload=payload, time=ts)


def stream_events(
    client: GatewayClient,
    session_id: str,
    after: int = 0,
    stop_event: threading.Event | None = None,
    poll_interval: float = 1.0,
    max_idle_cycles: int = 30,
) -> Iterator[RuntimeEvent]:
    """
    Stream typed ``RuntimeEvent`` objects from the gateway SSE endpoint.

    ``GET /sessions/{session_id}/stream`` with optional ``after`` cursor.

    Parameters
    ----------
    client:
        A configured ``GatewayClient``.  The underlying ``httpx.Client``
        is used directly for streaming — no timeout is applied to the
        stream itself (only the connection timeout from the client).
    session_id:
        The gateway session to subscribe to.
    after:
        Sequence number to resume from (last seen event id).
    stop_event:
        When set, the generator stops cleanly at the next frame boundary.
    poll_interval:
        Passed to the gateway as the SSE poll interval.
    max_idle_cycles:
        Passed to the gateway; controls server-side stream lifetime.

    Raises
    ------
    GatewayError
        On HTTP errors or transport failures.
    """
    http_client = client._get_client()  # noqa: SLF001 — friend access pattern
    url = f"/sessions/{session_id}/stream"
    params: dict[str, str | int | float] = {
        "after": after,
        "poll_interval": poll_interval,
        "max_idle_cycles": max_idle_cycles,
    }

    try:
        with http_client.stream(
            "GET",
            url,
            params=params,
            headers={"Accept": "text/event-stream"},
            timeout=None,  # streaming — no read timeout
        ) as response:
            if response.status_code != 200:
                raise GatewayError(
                    f"SSE {url} → {response.status_code}", response.status_code
                )
            yield from _parse_sse_frames(
                _iter_chunks(response, stop_event), stop_event
            )
    except GatewayError:
        raise
    except httpx.TransportError as exc:
        raise GatewayError(f"SSE {url} transport error: {exc}") from exc


def _iter_chunks(
    response: httpx.Response,
    stop_event: threading.Event | None,
) -> Generator[bytes, None, None]:
    """Yield raw byte chunks from an httpx streaming response."""
    for chunk in response.iter_bytes():
        if stop_event and stop_event.is_set():
            return
        if chunk:
            yield chunk
