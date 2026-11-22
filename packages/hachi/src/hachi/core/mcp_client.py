"""
MCP (Model Context Protocol) Client

This module implements an MCP client that can connect to MCP servers via three
transport modes:
  - stdio  — spawn a subprocess and communicate via JSON-RPC 2.0 over stdin/stdout
              (industry-standard; original transport)
  - sse    — connect to a remote MCP server over HTTP Server-Sent Events (the MCP
              SSE transport: SSE endpoint for server→client + HTTP POST for client→server)
  - http   — MCP streamable-HTTP transport (single POST endpoint, JSON-RPC body,
              optional streaming response)

How it works (stdio):
    1. An .og file with role=mcp defines the server command (e.g., "npx -y @anthropic/mcp-gmail")
    2. Hachi spawns the server as a subprocess on boot
    3. The MCP client calls `tools/list` to discover what tools the server provides
    4. Each tool is dynamically registered in the ToolRegistry
    5. When the agent calls a tool, the MCP client forwards the call to the subprocess
    6. The MCP server handles all auth (OAuth, tokens, etc.) internally

Protocol: JSON-RPC 2.0 — over stdin/stdout (stdio), SSE (sse), or HTTP POST (http)
Reference: https://modelcontextprotocol.io/
"""

from __future__ import annotations

import json
import logging
import os
import shlex
import subprocess
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from hachi.core.errors import MCPError
from hachi.core.loop import ToolRegistry
from hachi.core.resilience import HealthRecorder, RetryPolicy, resilient_call
from hachi.core.untrusted_content import guard_untrusted

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Private exception for transient MCP transport failures
# ---------------------------------------------------------------------------


class _MCPTimeoutError(TimeoutError):
    """Raised by ``_call_tool_once`` when the server returns no response (timeout or dead
    transport).

    Inherits from ``TimeoutError`` so that ``resilience._is_transient`` recognises it as
    a retryable condition (the name contains "Timeout").  This keeps the retry heuristic
    in resilience.py stable and avoids coupling MCPError (which can also be non-retryable)
    into the transient-detection path.
    """


class _MissingSecretError(ValueError):
    """Raised by :func:`_resolve_secret_refs` when a ``secret:<name>`` reference has no
    matching ``cred:<name>`` entry in the secret store.

    Kept private so callers only need to know about MCP-level errors externally.
    """


# ---------------------------------------------------------------------------
# Secret-reference resolution (BB-9)
# ---------------------------------------------------------------------------

_SECRET_REF_PREFIX: str = "secret:"

_cached_secret_store: Any | None = None
_cached_secret_store_lock = threading.Lock()


def _get_module_secret_store() -> Any:
    """Return a lazily-created, module-level secret store (core→core, layering-clean)."""
    global _cached_secret_store  # noqa: PLW0603
    if _cached_secret_store is None:
        with _cached_secret_store_lock:
            if _cached_secret_store is None:
                from hachi.core.secret_store import create_default_secret_store

                _cached_secret_store = create_default_secret_store()
    return _cached_secret_store


def _resolve_secret_refs(mapping: dict[str, str], store: Any) -> dict[str, str]:
    """Resolve ``secret:<name>`` reference values in *mapping* using the secret store.

    For each value that starts with ``secret:``, the name portion is looked up as
    ``cred:<name>`` in *store*.  A missing credential raises :exc:`_MissingSecretError`.
    Values that do not start with ``secret:`` are passed through unchanged.

    Args:
        mapping: Dict of env-var or header key→value pairs (from :class:`MCPServerConfig`).
        store:   A :class:`~hachi.core.secret_store.SecretStore` instance.

    Returns:
        A new dict with all ``secret:`` values replaced by their resolved credentials.

    Raises:
        _MissingSecretError: When a referenced credential is not found in the store.
    """
    out: dict[str, str] = {}
    for k, v in mapping.items():
        if isinstance(v, str) and v.startswith(_SECRET_REF_PREFIX):
            name = v[len(_SECRET_REF_PREFIX) :]
            resolved = store.get(f"cred:{name}")
            if resolved is None:
                raise _MissingSecretError(
                    f"env/header {k!r} references unknown credential {name!r}. "
                    f"Store it first via POST /runtime/secrets."
                )
            out[k] = resolved
        else:
            out[k] = v
    return out


# MED-004: Hard cap on MCP tool response size to prevent context flooding.
# Responses larger than this are truncated with a visible marker so the LLM
# knows the output was cut and can ask for a narrower query.
_MCP_RESPONSE_MAX_CHARS: int = 64_000
_MCP_TRUNCATION_MARKER: str = (
    "\n\n[TRUNCATED: MCP response exceeded {limit} characters. "
    "Only the first {limit} characters are shown. "
    "Request a smaller result set or filter the output.]\n"
)

# ---------------------------------------------------------------------------
# Transport config schema
# ---------------------------------------------------------------------------

TransportKind = Literal["stdio", "sse", "http"]


@dataclass
class MCPServerConfig:
    """Transport-aware config for a single MCP server.

    Supports three transport kinds:
      - ``stdio``  — subprocess spawn; requires ``command`` and optional ``args``/``env``.
      - ``sse``    — HTTP Server-Sent Events; requires ``url`` and optional ``headers``/``env``.
      - ``http``   — Streamable-HTTP POST; requires ``url`` and optional ``headers``/``env``.

    ``transport`` defaults to ``"stdio"`` for backward compatibility with existing
    ``[mcp_servers]`` config entries that only have ``command``/``args``.
    """

    name: str
    transport: TransportKind = "stdio"

    # stdio fields
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)

    # sse / http fields
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)

    # Optional per-server timeouts
    boot_timeout_seconds: float | None = None
    request_timeout_seconds: float = 30.0

    # The TOML keys that ``to_toml_entry`` owns. On re-registration,
    # ``register_mcp_server`` overwrites these (and prunes any that no longer
    # apply, e.g. a stdio ``command`` after switching to http) but PRESERVES every
    # other key in the ``[mcp_servers.NAME]`` table — notably ``enabled`` (written
    # by ``set_mcp_enabled``) — so a re-register never silently drops a persisted
    # lifecycle field. Keep this in sync with ``to_toml_entry`` (BB-19).
    TOML_MANAGED_KEYS: ClassVar[frozenset[str]] = frozenset(
        {
            "transport",
            "command",
            "args",
            "env",
            "url",
            "headers",
            "boot_timeout_seconds",
            "request_timeout_seconds",
        }
    )

    @classmethod
    def from_toml_entry(cls, name: str, entry: dict[str, Any]) -> MCPServerConfig:
        """Parse an ``[mcp_servers.NAME]`` TOML dict into an ``MCPServerConfig``.

        Supports the old stdio-only format (``command`` + ``args`` + ``env``) as well
        as the new format that includes a ``transport`` key.

        Args:
            name:  Server slug (the TOML sub-table key).
            entry: The raw dict for this server entry.

        Returns:
            A fully populated ``MCPServerConfig``.
        """
        _transport_raw: str = str(entry.get("transport", "stdio"))
        if _transport_raw not in ("stdio", "sse", "http"):
            logger.warning(
                "[mcp] Server '%s': unknown transport '%s'; defaulting to stdio",
                name,
                _transport_raw,
            )
            transport: TransportKind = "stdio"
        else:
            transport = _transport_raw  # type: ignore[assignment]

        args_raw = entry.get("args", "")
        if isinstance(args_raw, list):
            args = [str(a) for a in args_raw]
        else:
            # Legacy: space-separated string
            args = shlex.split(str(args_raw), posix=(os.name != "nt")) if args_raw else []

        env_raw = entry.get("env", {})
        env: dict[str, str] = (
            {str(k): str(v) for k, v in env_raw.items()} if isinstance(env_raw, dict) else {}
        )

        headers_raw = entry.get("headers", {})
        headers: dict[str, str] = (
            {str(k): str(v) for k, v in headers_raw.items()}
            if isinstance(headers_raw, dict)
            else {}
        )

        boot_t = entry.get("boot_timeout_seconds")
        req_t = entry.get("request_timeout_seconds", 30.0)

        try:
            boot_timeout = float(boot_t) if boot_t is not None else None
        except (TypeError, ValueError):
            boot_timeout = None
        try:
            request_timeout = float(req_t)
        except (TypeError, ValueError):
            request_timeout = 30.0

        return cls(
            name=name,
            transport=transport,
            command=str(entry.get("command", "")),
            args=args,
            env=env,
            url=str(entry.get("url", "")),
            headers=headers,
            boot_timeout_seconds=boot_timeout,
            request_timeout_seconds=request_timeout,
        )

    def to_toml_entry(self) -> dict[str, Any]:
        """Serialize back to a plain dict suitable for TOML storage.

        Omits empty/default fields to keep the config file tidy.
        """
        entry: dict[str, Any] = {"transport": self.transport}
        if self.transport == "stdio":
            entry["command"] = self.command
            # Store args as a single space-joined string for human-readable config
            if self.args:
                entry["args"] = " ".join(self.args)
            if self.env:
                entry["env"] = dict(self.env)
        else:
            entry["url"] = self.url
            if self.headers:
                entry["headers"] = dict(self.headers)
            if self.env:
                entry["env"] = dict(self.env)
        if self.boot_timeout_seconds is not None:
            entry["boot_timeout_seconds"] = self.boot_timeout_seconds
        if self.request_timeout_seconds != 30.0:
            entry["request_timeout_seconds"] = self.request_timeout_seconds
        return entry


# ---------------------------------------------------------------------------
# Transport interface
# ---------------------------------------------------------------------------


class MCPTransport(ABC):
    """Abstract transport for JSON-RPC 2.0 exchange with an MCP server.

    Implementations must support the MCP initialize / tools/list handshake.
    """

    @abstractmethod
    def start(self) -> bool:
        """Establish the transport connection.

        Returns:
            True if the connection was established successfully.
        """

    @abstractmethod
    def send(self, message: dict[str, Any]) -> None:
        """Send a JSON-RPC message (fire-and-forget; thread-safe).

        Args:
            message: A JSON-serialisable JSON-RPC 2.0 object.
        """

    @abstractmethod
    def receive(self, request_id: Any, timeout_seconds: float) -> dict[str, Any] | None:
        """Wait for a JSON-RPC response matching ``request_id``.

        Args:
            request_id: The id from the outgoing request.
            timeout_seconds: Maximum wall-clock seconds to block.

        Returns:
            The response dict, or ``None`` on timeout.
        """

    @abstractmethod
    def close(self) -> None:
        """Shut down the transport and release resources."""

    @property
    @abstractmethod
    def is_alive(self) -> bool:
        """True if the transport is still usable."""


# ---------------------------------------------------------------------------
# stdio transport
# ---------------------------------------------------------------------------


class StdioTransport(MCPTransport):
    """JSON-RPC 2.0 over subprocess stdin/stdout (the original MCP stdio transport).

    This wraps the existing subprocess-spawn logic that was previously embedded
    directly in ``MCPServerConnection``, keeping the byte-for-byte behaviour.
    """

    # Default timeout for the entire boot sequence (subprocess spawn → initialize → tools/list).
    DEFAULT_BOOT_TIMEOUT_SECONDS: float = 60.0

    def __init__(
        self,
        name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        request_timeout_seconds: float = 30.0,
        boot_timeout_seconds: float | None = None,
    ) -> None:
        self._name = name
        self._command = command
        self._args = list(args or [])
        self._env = dict(env or {})
        self._request_timeout_seconds = max(1.0, float(request_timeout_seconds))
        self._boot_timeout_seconds = (
            float(boot_timeout_seconds)
            if boot_timeout_seconds is not None
            else self.DEFAULT_BOOT_TIMEOUT_SECONDS
        )
        self._process: subprocess.Popen | None = None  # type: ignore[type-arg]
        self._request_id_counter = 0
        self._lock = threading.Lock()
        self._response_cv = threading.Condition(self._lock)
        self._responses: dict[Any, dict[str, Any]] = {}
        self._reader_thread: threading.Thread | None = None
        # LOW-014: sentinel set by reader when the read loop exits unexpectedly.
        self._reader_dead: bool = False

    # --- internal helpers ---------------------------------------------------

    def _build_subprocess_env(self) -> dict[str, str]:
        """Build a minimal environment to avoid leaking host secrets to MCP servers."""
        base_keys = [
            "PATH",
            "HOME",
            "TMPDIR",
            "XDG_RUNTIME_DIR",
            "USER",
            "SHELL",
            "SYSTEMROOT",
            "WINDIR",
            "COMSPEC",
            "TMP",
            "TEMP",
            "APPDATA",
            "LOCALAPPDATA",
            "ProgramData",
            "ProgramFiles",
            "ProgramFiles(x86)",
        ]
        env: dict[str, str] = {}
        for key in base_keys:
            value = os.environ.get(key)
            if value:
                env[key] = value
        env.update(self._env)
        return env

    def _stdout_reader(self) -> None:
        """Continuously read MCP stdout and route JSON-RPC responses by request ID.

        LOW-014: If the read loop exits for any reason (EOF, subprocess death, I/O error)
        we log a warning, set ``_reader_dead``, and wake all waiting threads so they
        detect the failure promptly rather than sitting out the full timeout.
        """
        process = self._process
        if not process or not process.stdout:
            logger.warning("[mcp] %s: _stdout_reader: no process/stdout on entry", self._name)
            self._reader_dead = True
            with self._response_cv:
                self._response_cv.notify_all()
            return

        try:
            while True:
                try:
                    line = process.stdout.readline()
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "[mcp] %s: _stdout_reader: read error — %s; thread exiting",
                        self._name,
                        exc,
                    )
                    break

                if not line:
                    logger.warning(
                        "[mcp] %s: _stdout_reader: EOF on stdout (subprocess exited?); "
                        "thread exiting",
                        self._name,
                    )
                    break

                decoded = line.decode("utf-8", errors="replace").strip()
                if not decoded:
                    continue

                try:
                    response = json.loads(decoded)
                except json.JSONDecodeError:
                    continue

                if not isinstance(response, dict) or "id" not in response:
                    continue

                with self._response_cv:
                    self._responses[response.get("id")] = response
                    self._response_cv.notify_all()
        finally:
            self._reader_dead = True
            with self._response_cv:
                self._response_cv.notify_all()

    # --- MCPTransport interface ---------------------------------------------

    def start(self) -> bool:
        """Spawn the subprocess and initialise the transport connection.

        Note: The overall boot timeout (UC-DEV-001) is enforced by the outer
        :class:`MCPServerConnection` timed thread.  This method runs directly
        without an additional wrapper.

        Returns:
            True if the subprocess started successfully.
        """
        return self._start_inner()

    def _start_inner(self) -> bool:
        """Perform the actual MCP server boot (runs inside a timed daemon thread)."""
        try:
            import shutil

            merged_env = self._build_subprocess_env()

            resolved_command = shutil.which(self._command, path=os.environ.get("PATH", ""))
            if not resolved_command:
                resolved_command = self._command

            full_command = [resolved_command] + self._args

            self._process = subprocess.Popen(
                full_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=merged_env,
                shell=False,
                bufsize=0,
            )

            # FIX 2: Drain stderr in a daemon thread to prevent pipe-buffer deadlock.
            def _drain_stderr(proc: subprocess.Popen[bytes]) -> None:
                try:
                    if proc.stderr is not None:
                        for _ in iter(proc.stderr.readline, b""):
                            pass
                except Exception:
                    pass

            threading.Thread(
                target=_drain_stderr,
                args=(self._process,),
                daemon=True,
                name="mcp-stderr-drain",
            ).start()

            # FIX 3: Poll for up to 5 s (10 x 0.5 s) rather than breaking after one iteration.
            for _ in range(10):
                time.sleep(0.5)
                if self._process.poll() is not None:
                    print(f"  [mcp] {self._name} exited during startup.")
                    self._process = None
                    return False

            self._reader_thread = threading.Thread(
                target=self._stdout_reader,
                name=f"mcp-reader-{self._name}",
                daemon=True,
            )
            self._reader_thread.start()

            # Extra wait for npx to finish downloading on first run
            time.sleep(2)
            return True

        except FileNotFoundError:
            return False
        except Exception:
            self.close()
            return False

    def send(self, message: dict[str, Any]) -> None:
        """Write a JSON-RPC message to the subprocess stdin.

        Args:
            message: A JSON-serialisable JSON-RPC 2.0 object.
        """
        process = self._process
        if not process or not process.stdin:
            return
        try:
            payload = json.dumps(message) + "\n"
            process.stdin.write(payload.encode("utf-8"))
            process.stdin.flush()
        except Exception:  # noqa: BLE001
            pass

    def receive(self, request_id: Any, timeout_seconds: float) -> dict[str, Any] | None:
        """Wait for the JSON-RPC response with ``request_id`` from the subprocess.

        Args:
            request_id:      The id from the outgoing request.
            timeout_seconds: Maximum wall-clock seconds to block.

        Returns:
            The response dict, or ``None`` on timeout.
        """
        with self._response_cv:
            arrived = self._response_cv.wait_for(
                lambda: request_id in self._responses or self._reader_dead,
                timeout=timeout_seconds,
            )
            if not arrived:
                return None
            if request_id not in self._responses:
                logger.warning(
                    "[mcp] %s: reader died before response for request %s arrived",
                    self._name,
                    request_id,
                )
                return {"error": {"message": f"MCP server '{self._name}' reader thread died"}}
            return self._responses.pop(request_id)

    def store_response(self, response: dict[str, Any]) -> None:
        """Route an already-parsed JSON-RPC response into the waiting table.

        Used by the reader thread only.

        Args:
            response: The parsed JSON-RPC response dict (must have an ``id`` key).
        """
        with self._response_cv:
            self._responses[response.get("id")] = response
            self._response_cv.notify_all()

    def close(self) -> None:
        """Terminate the subprocess and release resources."""
        process = self._process
        if process:
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
        self._process = None
        with self._response_cv:
            self._responses.clear()
            self._response_cv.notify_all()
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=0.5)
        self._reader_thread = None

    @property
    def is_alive(self) -> bool:
        """True if the subprocess is still running."""
        return self._process is not None and self._process.poll() is None


# ---------------------------------------------------------------------------
# SSE transport
# ---------------------------------------------------------------------------


class SseTransport(MCPTransport):
    """JSON-RPC 2.0 over HTTP Server-Sent Events (MCP SSE transport).

    The MCP SSE transport splits the channel:
      - Server→client:  a persistent SSE connection (``GET <url>/sse`` or the base URL
                        if the server uses path-based routing).
      - Client→server:  individual HTTP POST requests to the server's message endpoint,
                        which the server returns via the SSE stream.

    This implementation uses ``httpx`` (already a Hachi dependency) with a background
    reader thread that consumes the SSE stream and routes JSON-RPC responses by id.
    """

    def __init__(
        self,
        name: str,
        url: str,
        headers: dict[str, str] | None = None,
        env: dict[str, str] | None = None,
        request_timeout_seconds: float = 30.0,
        boot_timeout_seconds: float | None = None,
    ) -> None:
        """Initialise the SSE transport.

        Args:
            name:                    Logical server name for logging.
            url:                     Base URL of the MCP SSE server.
            headers:                 Optional HTTP headers added to every request.
            env:                     Ignored for SSE (kept for API symmetry).
            request_timeout_seconds: Per-request JSON-RPC timeout.
            boot_timeout_seconds:    Max seconds for the initial SSE handshake + initialize.
        """
        self._name = name
        self._base_url = url.rstrip("/")
        self._headers = dict(headers or {})
        self._request_timeout_seconds = max(1.0, float(request_timeout_seconds))
        self._boot_timeout_seconds = float(boot_timeout_seconds or 60.0)

        self._lock = threading.Lock()
        self._response_cv = threading.Condition(self._lock)
        self._responses: dict[Any, dict[str, Any]] = {}
        self._reader_dead: bool = False
        self._reader_thread: threading.Thread | None = None
        self._message_endpoint: str | None = None  # discovered from SSE handshake
        self._sse_response: Any = None  # httpx streaming response
        self._client: Any = None  # httpx.Client

    # --- MCPTransport interface ---------------------------------------------

    def start(self) -> bool:
        """Open the SSE connection (transport level only — no MCP handshake here).

        The MCP handshake (initialize / tools/list) is performed by the outer
        :class:`MCPServerConnection` after this returns True.

        Returns:
            True if the SSE stream was opened successfully.
        """
        return self._start_inner()

    def _start_inner(self) -> bool:
        try:
            import httpx  # lazy import — keeps cold-start light for stdio-only deployments

            self._client = httpx.Client(
                headers=self._headers, timeout=self._request_timeout_seconds
            )

            # Try the conventional SSE endpoint first, then the base URL.
            sse_url = f"{self._base_url}/sse"
            try:
                self._sse_response = self._client.stream("GET", sse_url)
                self._sse_response.__enter__()
            except Exception:
                # Fall back to the base URL as the SSE endpoint.
                sse_url = self._base_url
                self._sse_response = self._client.stream("GET", sse_url)
                self._sse_response.__enter__()

            # The MCP SSE handshake sends an ``endpoint`` event first with the POST URL.
            endpoint_discovered = threading.Event()

            def _reader() -> None:
                try:
                    for raw_line in self._sse_response.iter_lines():
                        if isinstance(raw_line, str):
                            line = raw_line.strip()
                        else:
                            line = raw_line.decode("utf-8", errors="replace").strip()
                        if not line:
                            continue
                        if line.startswith("data:"):
                            data_str = line[5:].strip()
                            if data_str.startswith("{"):
                                try:
                                    msg = json.loads(data_str)
                                except json.JSONDecodeError:
                                    continue
                                if "id" in msg:
                                    with self._response_cv:
                                        self._responses[msg["id"]] = msg
                                        self._response_cv.notify_all()
                        elif line.startswith("event: endpoint"):
                            # Next data line will carry the POST endpoint URL.
                            pass
                        elif line.startswith("data:") and self._message_endpoint is None:
                            candidate = line[5:].strip()
                            if candidate.startswith("http") or candidate.startswith("/"):
                                if not candidate.startswith("http"):
                                    candidate = self._base_url + candidate
                                self._message_endpoint = candidate
                                endpoint_discovered.set()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("[mcp/sse] %s: SSE reader error: %s", self._name, exc)
                finally:
                    self._reader_dead = True
                    with self._response_cv:
                        self._response_cv.notify_all()

            self._reader_thread = threading.Thread(
                target=_reader, name=f"mcp-sse-reader-{self._name}", daemon=True
            )
            self._reader_thread.start()

            # Give the reader a moment to discover the endpoint event.
            endpoint_discovered.wait(timeout=5.0)
            if self._message_endpoint is None:
                # Many SSE MCP servers use the base URL for both SSE and POST.
                self._message_endpoint = f"{self._base_url}/message"

            return True

        except Exception as exc:
            logger.warning("[mcp/sse] %s: failed to start: %s", self._name, exc)
            self.close()
            return False

    def send(self, message: dict[str, Any]) -> None:
        """POST a JSON-RPC message to the server's message endpoint.

        Args:
            message: A JSON-serialisable JSON-RPC 2.0 object.
        """
        if not self._client or not self._message_endpoint:
            return
        try:
            self._client.post(
                self._message_endpoint,
                json=message,
                headers={"Content-Type": "application/json"},
                timeout=self._request_timeout_seconds,
            )
        except Exception as exc:
            logger.warning("[mcp/sse] %s: send error: %s", self._name, exc)

    def receive(self, request_id: Any, timeout_seconds: float) -> dict[str, Any] | None:
        """Wait for the JSON-RPC response with ``request_id`` from the SSE stream.

        Args:
            request_id:      The id from the outgoing request.
            timeout_seconds: Maximum wall-clock seconds to block.

        Returns:
            The response dict, or ``None`` on timeout.
        """
        with self._response_cv:
            arrived = self._response_cv.wait_for(
                lambda: request_id in self._responses or self._reader_dead,
                timeout=timeout_seconds,
            )
            if not arrived:
                return None
            if request_id not in self._responses:
                return {"error": {"message": f"MCP SSE connection '{self._name}' lost"}}
            return self._responses.pop(request_id)

    def close(self) -> None:
        """Close the SSE connection and HTTP client."""
        self._reader_dead = True
        with self._response_cv:
            self._response_cv.notify_all()
        try:
            if self._sse_response is not None:
                self._sse_response.__exit__(None, None, None)
        except Exception:
            pass
        try:
            if self._client is not None:
                self._client.close()
        except Exception:
            pass
        self._sse_response = None
        self._client = None
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=0.5)

    @property
    def is_alive(self) -> bool:
        """True if the SSE reader thread is still alive."""
        return (
            not self._reader_dead
            and self._reader_thread is not None
            and self._reader_thread.is_alive()
        )


# ---------------------------------------------------------------------------
# HTTP (streamable-HTTP) transport
# ---------------------------------------------------------------------------


class HttpTransport(MCPTransport):
    """JSON-RPC 2.0 over HTTP POST (MCP streamable-HTTP transport).

    This is the simplest transport: each JSON-RPC request is a synchronous HTTP
    POST to the server's endpoint.  Responses may be streaming (NDJSON) or a
    single JSON body — both are handled.
    """

    def __init__(
        self,
        name: str,
        url: str,
        headers: dict[str, str] | None = None,
        env: dict[str, str] | None = None,
        request_timeout_seconds: float = 30.0,
        boot_timeout_seconds: float | None = None,
    ) -> None:
        """Initialise the HTTP transport.

        Args:
            name:                    Logical server name for logging.
            url:                     Full URL to POST JSON-RPC messages to.
            headers:                 Optional HTTP headers added to every request.
            env:                     Ignored for HTTP (kept for API symmetry).
            request_timeout_seconds: Per-request HTTP timeout.
            boot_timeout_seconds:    Max seconds for the MCP initialize handshake.
        """
        self._name = name
        self._url = url
        self._headers = dict(headers or {})
        self._request_timeout_seconds = max(1.0, float(request_timeout_seconds))
        self._boot_timeout_seconds = float(boot_timeout_seconds or 30.0)
        self._client: Any = None
        self._alive: bool = False
        # Streamable-HTTP: the server assigns a session id on initialize (returned in
        # the Mcp-Session-Id response header) that must be echoed on later requests.
        self._session_id: str | None = None

    def start(self) -> bool:
        """Verify the endpoint is reachable (HEAD/GET probe).

        Returns:
            True if the server responded successfully.
        """
        try:
            import httpx

            self._client = httpx.Client(
                headers={
                    "Content-Type": "application/json",
                    # MCP streamable-HTTP requires the client to accept BOTH a single
                    # JSON response and an SSE stream. Hosted servers (e.g. Tavily's
                    # mcp.tavily.com) return 406 Not Acceptable without text/event-stream.
                    "Accept": "application/json, text/event-stream",
                    **self._headers,
                },
                timeout=self._request_timeout_seconds,
            )
            self._alive = True
            return True
        except Exception as exc:
            logger.warning("[mcp/http] %s: failed to initialise client: %s", self._name, exc)
            return False

    def send(self, message: dict[str, Any]) -> None:
        """Send a JSON-RPC notification (no response expected) via HTTP POST.

        For request-response pairs use :meth:`send_request` directly through
        :meth:`receive` by calling :meth:`MCPServerConnection._send_request`.

        Args:
            message: A JSON-serialisable JSON-RPC 2.0 notification (no ``id``).
        """
        if not self._client:
            return
        try:
            _headers = {"Mcp-Session-Id": self._session_id} if self._session_id else None
            self._client.post(
                self._url, json=message, timeout=self._request_timeout_seconds, headers=_headers
            )
        except Exception as exc:
            logger.warning("[mcp/http] %s: send error: %s", self._name, exc)

    def receive(self, request_id: Any, timeout_seconds: float) -> dict[str, Any] | None:
        """Not used directly — HTTP transport is synchronous; see ``send_and_receive``.

        For the HTTP transport the request and response happen in the same POST call,
        so the MCPServerConnection calls ``send_and_receive`` directly instead of
        splitting into send + receive.

        Args:
            request_id:      Unused (kept for interface compliance).
            timeout_seconds: Unused.

        Returns:
            Always ``None`` — callers must use ``send_and_receive``.
        """
        return None

    def send_and_receive(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """Send a JSON-RPC request and return the response synchronously via HTTP POST.

        Handles both single-object JSON responses and NDJSON streaming responses
        (takes the last complete JSON line).

        Args:
            message: A JSON-serialisable JSON-RPC 2.0 request with an ``id``.

        Returns:
            The parsed JSON-RPC response dict, or ``None`` on error.
        """
        if not self._client:
            return None
        try:
            _headers = {"Mcp-Session-Id": self._session_id} if self._session_id else None
            resp = self._client.post(
                self._url, json=message, timeout=self._request_timeout_seconds, headers=_headers
            )
            resp.raise_for_status()
            # Capture the session id assigned on initialize for subsequent requests.
            _sid = resp.headers.get("Mcp-Session-Id") or resp.headers.get("mcp-session-id")
            if _sid:
                self._session_id = _sid
            return self._parse_response_body(resp.text)
        except Exception as exc:
            logger.warning("[mcp/http] %s: send_and_receive error: %s", self._name, exc)
            return {"error": {"message": str(exc)}}

    @staticmethod
    def _parse_response_body(text: str) -> dict[str, Any] | None:
        """Parse a streamable-HTTP response body.

        The body may be a single JSON object, NDJSON, or an SSE stream
        (``event: message\\ndata: {json}\\n\\n``). Scan lines from the end for the
        last JSON-RPC object, stripping an optional ``data:`` SSE prefix and skipping
        SSE control lines.
        """
        text = (text or "").strip()
        if not text:
            return None
        if "\n" in text or text.startswith("data:"):
            for raw in reversed(text.splitlines()):
                line = raw.strip()
                if not line or line.startswith((":", "event:", "id:", "retry:")):
                    continue
                if line.startswith("data:"):
                    line = line[len("data:") :].strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    return obj
            return None
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            return None
        return obj if isinstance(obj, dict) else None

    def close(self) -> None:
        """Close the HTTP client."""
        self._alive = False
        try:
            if self._client is not None:
                self._client.close()
        except Exception:
            pass
        self._client = None

    @property
    def is_alive(self) -> bool:
        """True if the HTTP client is initialised."""
        return self._alive and self._client is not None


# ---------------------------------------------------------------------------
# MCPServerConnection — unified connection using the transport layer
# ---------------------------------------------------------------------------


class MCPServerConnection:
    """Manages a persistent connection to a single MCP server via any transport.

    The transport (stdio / sse / http) is selected at construction time; the
    higher-level protocol (JSON-RPC initialize / tools/list / tools/call) is
    the same for all transports.
    """

    # Default timeout for the full boot sequence (UC-DEV-001).
    DEFAULT_BOOT_TIMEOUT_SECONDS: float = 60.0

    def __init__(
        self,
        name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        request_timeout_seconds: float = 30.0,
        boot_timeout_seconds: float | None = None,
        # New transport-aware parameters (all optional for backward compatibility)
        transport: TransportKind = "stdio",
        url: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialise an MCP server connection.

        Args:
            name:                    Logical name (e.g. ``'gmail'``).
            command:                 Subprocess command (stdio only).
            args:                    Subprocess args (stdio only).
            env:                     Extra environment variables.
            request_timeout_seconds: Per-request JSON-RPC timeout.
            boot_timeout_seconds:    Max seconds for the full boot sequence (UC-DEV-001).
            transport:               ``"stdio"``, ``"sse"``, or ``"http"``.
            url:                     Remote server URL (sse / http only).
            headers:                 HTTP headers (sse / http only).
        """
        self.name = name
        self.command = command
        self.args = list(args or [])
        self.env = dict(env or {})
        self._request_timeout_seconds = max(1.0, float(request_timeout_seconds))
        # Store the boot timeout in a plain backing attribute BEFORE creating the transport
        # so the _boot_timeout_seconds property (which reads from the transport) doesn't
        # try to access self._transport before it exists.
        self.__boot_timeout: float = (
            float(boot_timeout_seconds)
            if boot_timeout_seconds is not None
            else self.DEFAULT_BOOT_TIMEOUT_SECONDS
        )
        self.transport_kind = transport
        self._url = url
        self._headers = dict(headers or {})

        self._request_id = 0
        self._id_lock = threading.Lock()
        self._tools: list[dict[str, Any]] = []

        # Issue 4: per-server error tracking and transient loading state.
        # _last_error is set when a server fails to start; status is exposed
        # via get_inventory() so operator views can surface the failure reason.
        self._last_error: str | None = None
        # _loading is True while setup_from_config's boot thread is running.
        self._loading: bool = False

        # P1-8: per-server resilience — one HealthRecorder + RetryPolicy per connection
        # so one dead server's breaker never affects peers.
        self._retry_policy: RetryPolicy = RetryPolicy(
            max_attempts=3,
            backoff_base_s=0.25,
            timeout_s=float(request_timeout_seconds),
            breaker_threshold=5,
            breaker_cooldown_s=30.0,
        )
        self._health_recorder: HealthRecorder = HealthRecorder(name, self._retry_policy)
        # Serialise reconnect attempts so parallel tool calls don't all reconnect.
        self._reconnect_lock: threading.Lock = threading.Lock()

        self._transport: MCPTransport = self._make_transport()

    def _make_transport(self) -> MCPTransport:
        """Instantiate the correct transport based on ``transport_kind``."""
        boot_t = self.__boot_timeout
        if self.transport_kind == "sse":
            return SseTransport(
                name=self.name,
                url=self._url,
                headers=self._headers,
                env=self.env,
                request_timeout_seconds=self._request_timeout_seconds,
                boot_timeout_seconds=boot_t,
            )
        if self.transport_kind == "http":
            return HttpTransport(
                name=self.name,
                url=self._url,
                headers=self._headers,
                env=self.env,
                request_timeout_seconds=self._request_timeout_seconds,
                boot_timeout_seconds=boot_t,
            )
        # Default: stdio
        return StdioTransport(
            name=self.name,
            command=self.command,
            args=self.args,
            env=self.env,
            request_timeout_seconds=self._request_timeout_seconds,
            boot_timeout_seconds=boot_t,
        )

    @staticmethod
    def _normalize_tools_payload(raw_tools: Any) -> list[dict[str, Any]]:
        """Normalize tool-discovery payload to a stable list with unique named tools."""
        if not isinstance(raw_tools, list):
            return []

        normalized: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        for item in raw_tools:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            if name in seen_names:
                continue
            seen_names.add(name)
            normalized.append(item)
        return normalized

    def start(self) -> bool:
        """Start the transport and complete the MCP initialize handshake.

        The full sequence (transport boot → JSON-RPC initialize → tools/list) is
        executed inside a timed thread so a hanging server doesn't block the agent.

        Returns:
            True if the server started and the tool list was fetched successfully.
        """
        result_holder: list[bool] = []
        exc_holder: list[BaseException] = []

        boot_timeout = self._boot_timeout_seconds

        def _do_start() -> None:
            try:
                ok = self._start_inner()
                result_holder.append(ok)
            except BaseException as exc:  # noqa: BLE001
                exc_holder.append(exc)
                result_holder.append(False)

        t = threading.Thread(target=_do_start, name=f"mcp-boot-{self.name}", daemon=True)
        t.start()
        t.join(timeout=boot_timeout)

        if t.is_alive():
            msg = f"boot timed out after {boot_timeout:.1f}s (UC-DEV-001)"
            logger.warning("[mcp] %s: %s", self.name, msg)
            self._last_error = msg
            # Kill subprocess if one was spawned
            try:
                proc = self._process
                if proc:
                    proc.kill()
            except Exception:  # noqa: BLE001
                pass
            if isinstance(self._transport, StdioTransport):
                self._transport._process = None
            return False

        if exc_holder:
            msg = str(exc_holder[0])
            logger.warning("[mcp] %s: unexpected error during boot: %s", self.name, msg)
            self._last_error = msg
            return False

        success = result_holder[0] if result_holder else False
        if not success and self._last_error is None:
            self._last_error = "server failed to start (check command/url and server logs)"
        return success

    def _start_inner(self) -> bool:
        """Run the MCP boot sequence (called inside the timed boot thread).

        Exposed so tests can monkey-patch this method to bypass the actual
        transport without touching transport internals.  The default implementation
        starts the underlying transport and performs the JSON-RPC handshake.

        Returns:
            True if the server started and the tool list was fetched successfully.
        """
        if not self._transport.start():
            return False

        # Send the MCP initialize request
        init_response = self._send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "hachi", "version": "1.0.0"},
            },
        )

        if not init_response or "error" in init_response:
            self.stop()
            return False

        # Send initialized notification (fire-and-forget)
        self._send_notification("notifications/initialized", {})

        # Discover available tools
        tools_response = self._send_request("tools/list", {})
        if tools_response and "result" in tools_response:
            tools = tools_response["result"].get("tools", [])
            self._tools = self._normalize_tools_payload(tools)

        return True

    def stop(self) -> None:
        """Shut down the transport."""
        self._transport.close()

    @property
    def tools(self) -> list[dict[str, Any]]:
        """The list of tools discovered from this MCP server."""
        return self._tools

    @property
    def is_alive(self) -> bool:
        """True if the transport is still usable."""
        return self._transport.is_alive

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Call a tool on this MCP server with retry, circuit-breaker, and reconnect.

        Wraps the raw transport call in the shared ``resilient_call`` / ``HealthRecorder``
        machinery (P1-8) so that:

        - Transient I/O failures are retried with exponential backoff.
        - A dead server trips the per-server circuit breaker; subsequent calls
          fast-fail without hammering the transport.
        - If the transport is detected as dead on the first attempt, exactly ONE
          reconnect is attempted before the retry loop gives up.

        Args:
            tool_name:  The name of the tool to call.
            arguments:  The arguments to pass to the tool.

        Returns:
            The tool's response as a string.  On unrecoverable failure, returns an
            ``[MCP ERROR]``-prefixed string so the LLM can see the failure reason
            (the loop sets ``is_error`` on tool exceptions; callers that catch
            exceptions should expect ``MCPError``).

        Raises:
            MCPError: When the circuit breaker is open (fast-fail path), so the loop
                sets ``is_error=True`` on the tool_result block.
        """
        # Fast-fail when the breaker is open: surface a typed MCPError so the
        # execution loop marks is_error=True on the tool_result block.
        health = self._health_recorder.snapshot()
        if not health.is_usable():
            raise MCPError(
                f"MCP server '{self.name}' circuit breaker is open "
                f"(too many consecutive failures); will retry after cooldown",
                context={"server": self.name},
            )

        # Reconnect-on-dead: if the transport is already known-dead before we
        # even try, attempt one reconnect so a mid-session restart succeeds.
        if not self._transport.is_alive:
            self._try_reconnect()

        def _attempt() -> str:
            # Inner reconnect: if the transport died between the outer liveness
            # check and now (e.g. a prior call killed it), reconnect once.
            if not self._transport.is_alive:
                self._try_reconnect()
                if not self._transport.is_alive:
                    raise MCPError(
                        f"MCP server '{self.name}' transport is not alive and reconnect failed",
                        context={"server": self.name},
                    )
            return self._call_tool_once(tool_name, arguments)

        try:
            result: str = resilient_call(
                _attempt,
                self._retry_policy,
                self._health_recorder,
                on_failover=lambda attempt, exc: logger.warning(
                    "[mcp] %s: tool '%s' attempt %d failed (%s); retrying",
                    self.name,
                    tool_name,
                    attempt,
                    type(exc).__name__,
                ),
            )
            return result
        except MCPError:
            raise
        except Exception as exc:
            raise MCPError(
                f"MCP server '{self.name}' tool '{tool_name}' failed: {exc}",
                context={"server": self.name, "tool": tool_name},
            ) from exc

    def _try_reconnect(self) -> None:
        """Attempt a single transport reconnect (serialised; idempotent if transport is alive).

        Called when the transport is detected as dead before or during a ``call_tool``
        invocation.  Uses a lock so concurrent callers don't all spawn a reconnect
        simultaneously — only the first thread reconnects; subsequent threads re-check
        ``is_alive`` after acquiring the lock.
        """
        with self._reconnect_lock:
            if self._transport.is_alive:
                return  # Another thread already reconnected.
            logger.info("[mcp] %s: transport dead; attempting reconnect", self.name)
            try:
                self._transport.close()
            except Exception:
                pass
            self._transport = self._make_transport()
            ok = self._start_inner()
            if ok:
                logger.info("[mcp] %s: reconnect succeeded", self.name)
            else:
                logger.warning("[mcp] %s: reconnect failed", self.name)

    def _call_tool_once(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Single-shot tool invocation (no retry).  Called by ``call_tool`` via resilient_call.

        Args:
            tool_name:  The name of the tool to call.
            arguments:  The arguments to pass to the tool.

        Returns:
            The tool's response as a string.

        Raises:
            _MCPTimeoutError: When the server returns no response (transient; will be retried).
            MCPError: On a JSON-RPC error response (non-transient; will NOT be retried).
        """
        response = self._send_request("tools/call", {"name": tool_name, "arguments": arguments})

        if not response:
            # Raise a TimeoutError subclass so resilience._is_transient recognises it as
            # retryable (name contains "Timeout").  MCPError alone is NOT transient.
            raise _MCPTimeoutError(
                f"No response from MCP server '{self.name}' (timeout or dead transport)",
            )

        if "error" in response:
            error = response["error"]
            raise MCPError(
                f"MCP server '{self.name}' returned error: {error.get('message', 'Unknown error')}",
                context={"server": self.name, "tool": tool_name, "rpc_error": error},
            )

        result = response.get("result", {})
        content = result.get("content", [])

        text_parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif isinstance(block, str):
                text_parts.append(block)

        raw = "\n".join(text_parts) if text_parts else json.dumps(result)

        # MED-004: Cap response size to prevent context flooding.
        if len(raw) > _MCP_RESPONSE_MAX_CHARS:
            marker = _MCP_TRUNCATION_MARKER.format(limit=_MCP_RESPONSE_MAX_CHARS)
            raw = raw[:_MCP_RESPONSE_MAX_CHARS] + marker

        return raw

    def _next_request_id(self) -> int:
        """Allocate a unique request ID (thread-safe)."""
        with self._id_lock:
            self._request_id += 1
            return self._request_id

    def _send_request(self, method: str, params: dict[str, Any]) -> dict[str, Any] | None:
        """Send a JSON-RPC request and wait for the response.

        Dispatches to the correct transport strategy:
          - stdio / sse: allocate id, call transport.send(), then transport.receive()
          - http:        call HttpTransport.send_and_receive() (synchronous round-trip)

        Args:
            method: JSON-RPC method name.
            params: JSON-RPC params dict.

        Returns:
            The response dict, or ``None`` on timeout/error.
        """
        request_id = self._next_request_id()

        message = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

        # HTTP transport: single synchronous POST round-trip
        if isinstance(self._transport, HttpTransport):
            return self._transport.send_and_receive(message)

        # stdio / SSE: send then wait
        self._transport.send(message)
        return self._transport.receive(request_id, self._request_timeout_seconds)

    def _send_notification(self, method: str, params: dict[str, Any]) -> None:
        """Send a JSON-RPC notification (no response expected).

        Args:
            method: JSON-RPC method name.
            params: JSON-RPC params dict.
        """
        message = {"jsonrpc": "2.0", "method": method, "params": params}
        self._transport.send(message)

    # -------------------------------------------------------------------------
    # Backward-compatibility shims — keep existing tests passing without changes.
    # -------------------------------------------------------------------------

    def _build_subprocess_env(self) -> dict[str, str]:
        """Proxy to the StdioTransport env builder (backward compat for tests).

        Returns:
            The merged environment dict, or an empty dict for non-stdio transports.
        """
        if isinstance(self._transport, StdioTransport):
            return self._transport._build_subprocess_env()
        return {}

    def _stdout_reader(self) -> None:
        """Proxy to the StdioTransport stdout reader (backward compat for tests)."""
        if isinstance(self._transport, StdioTransport):
            self._transport._stdout_reader()

    @property
    def _response_cv(self) -> threading.Condition:
        """Proxy to the StdioTransport response condition (backward compat for tests)."""
        if isinstance(self._transport, StdioTransport):
            return self._transport._response_cv
        # Fallback condition variable (should not be needed outside tests)
        return threading.Condition()

    @property
    def _responses(self) -> dict[Any, dict[str, Any]]:
        """Proxy to the StdioTransport response store (backward compat for tests)."""
        if isinstance(self._transport, StdioTransport):
            return self._transport._responses
        return {}

    @property
    def _process(self) -> Any:
        """Expose the underlying subprocess (stdio transport only)."""
        if isinstance(self._transport, StdioTransport):
            return self._transport._process
        return None

    @_process.setter
    def _process(self, value: Any) -> None:
        if isinstance(self._transport, StdioTransport):
            self._transport._process = value

    @property
    def _boot_timeout_seconds(self) -> float:
        """The boot timeout (read from backing store; syncs to transport after init)."""
        return self.__boot_timeout

    @_boot_timeout_seconds.setter
    def _boot_timeout_seconds(self, value: float) -> None:
        self.__boot_timeout = value
        # Sync to the transport if it has already been created.
        transport = self.__dict__.get("_transport")
        if transport is not None and isinstance(
            transport, (StdioTransport, SseTransport, HttpTransport)
        ):
            transport._boot_timeout_seconds = value


# ---------------------------------------------------------------------------
# MCPManager
# ---------------------------------------------------------------------------


class MCPManager:
    """Manages the lifecycle of all MCP server connections.

    Loads MCP definitions from .og nodes or ``MCPServerConfig`` objects, starts
    servers, and registers their tools in the Hachi ToolRegistry.
    """

    def __init__(self) -> None:
        self._servers: dict[str, MCPServerConnection] = {}
        # Boot failures for servers that failed before entering _servers (e.g. bad
        # TOML config or gate denial). These appear in get_inventory() as "failed"
        # entries so the operator UI always shows a complete picture (Bug 4).
        self._boot_failures: dict[str, str] = {}

    def setup_from_node(self, node: Any) -> bool:
        """Create and start an MCP server from a role=mcp .og node.

        Expected ``::config`` format::

            command=npx
            args=-y @anthropic/mcp-gmail
            env_KEY=VALUE       # optional env vars, prefixed with ``env_``
            transport=stdio     # optional; defaults to stdio

        Args:
            node: An OGNode with ``role='mcp'``.

        Returns:
            True if the server started successfully.
        """
        _node_transport = str(node.config.get("transport", "stdio"))
        if _node_transport == "sse":
            transport: TransportKind = "sse"
        elif _node_transport == "http":
            transport = "http"
        else:
            transport = "stdio"

        if transport in ("sse", "http"):
            url = node.config.get("url", "")
            if not url:
                print(f"  [mcp] No url specified for {node.name} (transport={transport})")
                return False

            headers: dict[str, str] = {}
            for key, value in node.config.items():
                if key.startswith("header_"):
                    headers[key[7:]] = str(value)

            env: dict[str, str] = {}
            for key, value in node.config.items():
                if key.startswith("env_"):
                    env[key[4:]] = str(value)

            boot_timeout = node.config.get("boot_timeout_seconds")
            request_timeout = node.config.get("request_timeout_seconds")
            kwargs: dict[str, Any] = {}
            if boot_timeout is not None:
                try:
                    kwargs["boot_timeout_seconds"] = float(boot_timeout)
                except (ValueError, TypeError):
                    pass
            if request_timeout is not None:
                try:
                    kwargs["request_timeout_seconds"] = float(request_timeout)
                except (ValueError, TypeError):
                    pass

            server = MCPServerConnection(
                name=node.name,
                command="",
                transport=transport,
                url=url,
                headers=headers,
                env=env,
                **kwargs,
            )

        else:
            # stdio (default)
            command = node.config.get("command", "")
            if not command:
                print(f"  [mcp] No command specified for {node.name}")
                return False

            args_raw = node.config.get("args", "")
            args = shlex.split(args_raw, posix=(os.name != "nt")) if args_raw else []

            env = {}
            for key, value in node.config.items():
                if key.startswith("env_"):
                    env[key[4:]] = str(value)

            boot_timeout = node.config.get("boot_timeout_seconds")
            request_timeout = node.config.get("request_timeout_seconds")
            kwargs = {}
            if boot_timeout is not None:
                try:
                    kwargs["boot_timeout_seconds"] = float(boot_timeout)
                except (ValueError, TypeError):
                    pass
            if request_timeout is not None:
                try:
                    kwargs["request_timeout_seconds"] = float(request_timeout)
                except (ValueError, TypeError):
                    pass

            server = MCPServerConnection(
                name=node.name,
                command=command,
                args=args,
                env=env,
                transport="stdio",
                **kwargs,
            )

        if server.start():
            self._servers[node.name] = server
            return True
        return False

    def setup_from_config(self, cfg: MCPServerConfig) -> bool:
        """Create and start an MCP server from an ``MCPServerConfig``.

        This is the hot-reload path: when a new server is registered via the REST
        API, the config is persisted and then this method is called to bring the
        server online without a gateway restart.

        The server is registered immediately with ``_loading=True`` so that
        :meth:`get_inventory` surfaces a transient "starting" status while the
        boot thread runs.  Once boot completes the flag is cleared and the status
        reflects the real outcome.

        ``secret:<name>`` references in ``cfg.env`` and ``cfg.headers`` are resolved
        to their ``cred:<name>`` values before the connection is created.  If a
        referenced credential is absent the server is registered with status "failed"
        and *False* is returned (fail-soft — boot continues; BB-9).

        Args:
            cfg: A fully populated :class:`MCPServerConfig`.

        Returns:
            True if the server started successfully.
        """
        # Resolve secret: references before constructing the connection so the
        # real credential reaches the subprocess/transport without touching TOML.
        from dataclasses import replace as _dc_replace

        try:
            store = _get_module_secret_store()
            resolved_env = _resolve_secret_refs(cfg.env, store)
            resolved_headers = _resolve_secret_refs(cfg.headers, store)
            cfg = _dc_replace(cfg, env=resolved_env, headers=resolved_headers)
        except _MissingSecretError as exc:
            placeholder = MCPServerConnection(
                name=cfg.name,
                command=cfg.command,
                args=cfg.args,
                env={},
                transport=cfg.transport,
                url=cfg.url,
                headers={},
            )
            placeholder._last_error = str(exc)
            self._servers[cfg.name] = placeholder
            logger.warning("[mcp] %s: missing secret — %s", cfg.name, exc)
            return False

        server = MCPServerConnection(
            name=cfg.name,
            command=cfg.command,
            args=cfg.args,
            env=cfg.env,
            request_timeout_seconds=cfg.request_timeout_seconds,
            boot_timeout_seconds=cfg.boot_timeout_seconds,
            transport=cfg.transport,
            url=cfg.url,
            headers=cfg.headers,
        )
        # Mark as loading so inventory shows "starting" during boot.
        server._loading = True
        # Optimistically register so get_inventory returns an entry immediately.
        self._servers[cfg.name] = server
        try:
            ok = server.start()
        finally:
            server._loading = False
        if not ok:
            # Keep the failed entry in _servers so get_inventory can surface the
            # error; the gateway can call shutdown() to remove it if desired.
            pass
        return ok

    def register_tools(self, registry: ToolRegistry) -> None:
        """Register all discovered MCP tools into the Hachi ToolRegistry.

        Each MCP tool becomes a native LLM tool the agent can call directly.
        Tools are namespaced as ``{server_name}_{tool_name}`` to prevent collisions.

        Args:
            registry: The ToolRegistry to mount tools onto.
        """
        for server_name, server in self._servers.items():
            self._register_server_tools(server_name, server, registry)

    def _register_server_tools(
        self,
        server_name: str,
        server: MCPServerConnection,
        registry: ToolRegistry,
    ) -> None:
        """Register the tools from a single server into the registry.

        Args:
            server_name: The logical name of the MCP server.
            server:      The active :class:`MCPServerConnection`.
            registry:    The ToolRegistry to mount tools onto.
        """
        for tool in server.tools:
            tool_name = tool.get("name", "")
            if not tool_name:
                continue

            namespaced_name = f"{server_name}_{tool_name}"

            schema = {
                "name": namespaced_name,
                "description": tool.get("description", f"Tool from MCP server '{server_name}'"),
                "input_schema": tool.get(
                    "inputSchema", {"type": "object", "properties": {}, "required": []}
                ),
            }

            def make_handler(srv: MCPServerConnection, original_name: str) -> Any:
                def handler(**kwargs: Any) -> str:
                    raw = srv.call_tool(original_name, kwargs)
                    guarded, _flagged = guard_untrusted(
                        raw,
                        source=f"MCP tool '{original_name}' (server '{srv.name}')",
                    )
                    return str(guarded)

                return handler

            registry.register(schema, make_handler(server, tool_name))

    def _namespaced_tool_names(self, server_name: str) -> list[str]:
        """Return the registry tool names (``{server}_{tool}``) for a server."""
        server = self._servers.get(server_name)
        if server is None:
            return []
        return [f"{server_name}_{t.get('name', '')}" for t in server.tools if t.get("name")]

    def register_server_tools(self, server_name: str, registry: ToolRegistry) -> bool:
        """(Re-)register a single live server's tools into ``registry``.

        Idempotent: any existing registration for the server's tools is removed
        first so re-enabling a server never produces duplicate tool schemas.
        Used by the runtime to bring a disabled server's tools back online
        without a gateway restart.

        Args:
            server_name: The logical name of an active MCP server.
            registry:    The live ToolRegistry to mount the tools onto.

        Returns:
            ``True`` if the server is present and its tools were registered.
        """
        server = self._servers.get(server_name)
        if server is None:
            return False
        registry.unregister(self._namespaced_tool_names(server_name))
        self._register_server_tools(server_name, server, registry)
        return True

    def unregister_server_tools(self, server_name: str, registry: ToolRegistry) -> int:
        """Remove a single live server's tools from ``registry`` (server kept).

        Used to disable a server in-session: its tools stop being offered to the
        model immediately, but the connection and inventory entry remain so the
        operator can re-enable it.  Returns the number of tools removed.
        """
        removed: int = registry.unregister(self._namespaced_tool_names(server_name))
        return removed

    def remove_server(self, server_name: str, registry: ToolRegistry | None = None) -> bool:
        """Tear down a server completely: unregister tools, stop it, drop it.

        Used to delete a server at runtime so it disappears from the live
        inventory (``get_inventory``) immediately.  Best-effort: transport
        shutdown errors are logged, not raised.

        Args:
            server_name: The logical name of the server to remove.
            registry:    Optional live ToolRegistry to unregister the tools from.

        Returns:
            ``True`` if the server was present and removed; ``False`` otherwise.
        """
        server = self._servers.get(server_name)
        if server is None:
            return False
        if registry is not None:
            try:
                registry.unregister(self._namespaced_tool_names(server_name))
            except Exception:
                logger.warning(
                    "[mcp] failed to unregister tools for %r", server_name, exc_info=True
                )
        try:
            server.stop()
        except Exception:
            logger.warning("[mcp] failed to stop server %r", server_name, exc_info=True)
        self._servers.pop(server_name, None)
        return True

    def get_server_tool_count(self, server_name: str) -> int:
        """Return the discovered tool count for a given server.

        Args:
            server_name: The logical name of the MCP server.

        Returns:
            Number of tools discovered, or 0 if the server is not registered.
        """
        server = self._servers.get(server_name)
        if not server:
            return 0
        return len(server.tools)

    def register_boot_failure(self, name: str, reason: str) -> None:
        """Record a server that failed before entering _servers (e.g. bad config, gate denial).

        These entries appear in get_inventory() with status="failed" so the
        operator UI shows the full picture, not only successfully started servers.
        """
        self._boot_failures[name] = reason

    def get_inventory(self) -> list[dict[str, Any]]:
        """Return a structured MCP inventory snapshot for operator views.

        Each entry includes the server ``name``, ``transport``, ``status``,
        ``tool_count``, the list of tool names (``tools``), and an optional
        ``err`` string populated when the server failed to start (Issue 4).

        Status values:
          - ``"starting"`` — boot thread is still running (transient).
          - ``"ready"``    — transport is alive and tools were discovered.
          - ``"failed"``   — server failed to start; see ``err`` for reason.
          - ``"stopped"``  — previously alive but transport is no longer alive.

        Boot failures (servers that failed before transport setup, e.g. invalid TOML
        or gate denial) are also returned as "failed" entries even though they were
        never added to ``_servers``.

        Returns:
            List of inventory dicts, one per registered or attempted server.
        """
        rows: list[dict[str, Any]] = []
        for name, server in self._servers.items():
            loading = getattr(server, "_loading", False)
            last_err: str | None = getattr(server, "_last_error", None)
            if loading:
                status = "starting"
            elif server.is_alive:
                status = "ready"
            elif last_err is not None:
                status = "failed"
            else:
                status = "stopped"

            entry: dict[str, Any] = {
                "name": name,
                "transport": server.transport_kind,
                "status": status,
                "tool_count": len(server.tools),
                "tools": [tool.get("name", "") for tool in server.tools if tool.get("name")],
                "err": last_err,
            }
            rows.append(entry)

        # Include pre-registration failures (bad TOML, gate denial) that never
        # entered _servers. Skip if the server was later successfully added.
        for name, reason in self._boot_failures.items():
            if name not in self._servers:
                rows.append(
                    {
                        "name": name,
                        "transport": "unknown",
                        "status": "failed",
                        "tool_count": 0,
                        "tools": [],
                        "err": reason,
                    }
                )
        return rows

    @property
    def server_count(self) -> int:
        """Number of active MCP server connections."""
        return len(self._servers)

    @property
    def total_tool_count(self) -> int:
        """Total number of tools across all MCP servers."""
        return sum(len(s.tools) for s in self._servers.values())

    def shutdown(self) -> None:
        """Terminate all MCP server connections."""
        for _name, server in self._servers.items():
            server.stop()
        self._servers.clear()
