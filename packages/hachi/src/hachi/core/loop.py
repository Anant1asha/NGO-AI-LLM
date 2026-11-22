"""
Autonomous Execution Loop (ReAct / Tool-Calling)

This module implements the core reasoning engine for Hachi. It manages the continuous
cycle of observing the environment, reasoning via the LLM, and executing tools until the
assigned task is completed.

Uses the MemoryManager for intelligent context management across skill switches.

Phase 1 Update:
    - Accepts immutable TurnContext per execution instead of mutating base_system_prompt
    - Prevents mutable shared state issues across concurrent sessions/turns

Performance & concurrency improvements (BE-4):
    HIGH-003: ChromaDB writes called by tool callables inside the thread pool can race on the
              embedded SQLite WAL. The vault serializes its own writes via _vault_lock (added in
              memory_vault.py); the tool pool here does not need additional coordination.
              Also: the pool uses max_workers=4 which is conservative; the chat lock from the
              gateway/orchestrator layer is NOT held across tool dispatch so the anyio thread pool
              is not exhausted.
    LOW-016:  Prompt-cache breakpoints are anchored on the stable brain/.og prefix via the
              TurnContext cacheable_system / dynamic_system split (see _system_blocks()).
              When a TurnContext is present the cacheable prefix never changes between turns
              (only the dynamic tail with time/recall varies), so Anthropic's cache hits the
              large stable prefix on every turn after the first.  The fallback path (no
              TurnContext) returns the full prompt as a single cacheable block — correct
              but less efficient; callers should always supply a TurnContext for optimal caching.
"""

import concurrent.futures
import contextlib
import logging
import threading
import time
from collections.abc import Callable, Iterable
from typing import Any

from hachi.core.llm import BaseLLMClient, LLMResponse, Message, ToolCall
from hachi.core.obs.trace import (
    TraceContext,
    attach_otel_context,
    copy_otel_context,
    detach_otel_context,
)
from hachi.core.runtime_events import (
    BUDGET_EXCEEDED,
    LLM_RETRY,
    SESSION_ITERATION_LIMIT,
    SESSION_TIME_LIMIT,
    TOOL_RESULT_PREVIEW_MAX,
)
from hachi.core.tool_results import ToolResultBlocks
from hachi.core.tracing import span
from hachi.core.turn_context import TurnContext

logger = logging.getLogger(__name__)

# Transient HTTP statuses worth retrying on (rate limit, overloaded, gateway errors).
_RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504, 529}
_RETRYABLE_HINTS = ("overloaded", "rate limit", "timeout", "timed out", "temporarily", "connection")
_MAX_LLM_RETRIES = 3
_LLM_RETRY_BASE_DELAY = 1.0

# R5 — Tool-output compression: cap text results before they enter history.
# Large tool outputs (e.g. full file contents, long web pages) are truncated to
# this limit and suffixed with a char-count note so the model knows data was elided.
_TOOL_OUTPUT_MAX_CHARS: int = 8_000

# R9 — Pre-generation context trim: if estimated token count is still above this
# threshold AFTER the standard per-iteration housekeeping (prepare_for_turn), run
# a second, more aggressive clear_stale_tool_results pass before the LLM call.
# Positioned above _TOOL_RESULT_CLEAR_TOKENS (12 000) to avoid redundant sweeps.
_PRE_GEN_TRIM_THRESHOLD: int = 16_000


def _compress_tool_output(text: str, max_chars: int = _TOOL_OUTPUT_MAX_CHARS) -> str:
    """Truncate an oversized text tool result (R5).

    If *text* is within *max_chars*, it is returned unchanged. If it exceeds the
    limit, the excess is dropped and a one-line note is appended so the model
    knows the output was cut. Non-tool (ToolResultBlocks) paths never call this.
    """
    if len(text) <= max_chars:
        return text
    total = len(text)
    return text[:max_chars] + f"\n[truncated: {total} chars total, showing first {max_chars}]"


def _is_retryable_llm_error(exc: Exception) -> bool:
    """Best-effort detection of transient LLM/provider errors (provider-agnostic).

    Checks an HTTP status code (Anthropic/OpenAI SDK exceptions expose
    ``status_code``; httpx exposes ``response.status_code``) and falls back to
    message heuristics for connection/timeout errors that carry no status.
    """
    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    if isinstance(status, int):
        return status in _RETRYABLE_STATUS
    message = str(exc).lower()
    return any(hint in message for hint in _RETRYABLE_HINTS)


class AgentException(Exception):
    """Base exception for agent execution errors."""

    pass


# P1-04: ExecutionLoop.run() does NOT raise when max_iterations is exhausted —
# it returns this prefix in a graceful, partial-summary string instead (see
# run()'s SESSION_ITERATION_LIMIT branch). Callers that need to distinguish
# "the task genuinely finished" from "the loop was cut off mid-task" (e.g.
# SubAgentRuntime mapping this to a non-SUCCESS status) must check for this
# prefix on the returned string — there is no exception to catch.
INCOMPLETE_RESULT_PREFIX = "[INCOMPLETE]"


class SuspendWorkflow(Exception):
    """Signal that the agent loop should suspend and wait for an external trigger.

    The loop catches this exception, ends the current turn cleanly, and surfaces
    the wait condition to the gateway layer for RunState persistence and registry
    arming.
    """

    def __init__(self, reason: str, wait_kind: str = "user", wait_key: str = "") -> None:
        self.reason = reason
        self.wait_kind = wait_kind
        self.wait_key = wait_key
        super().__init__(reason)


class _StreamCancelled(Exception):
    """Internal sentinel: the cancel flag fired during streaming.

    Never propagates beyond _stream_generate / run(); caught immediately to
    commit the partial text and return a user-cancel result.
    """

    def __init__(self, partial_text: str) -> None:
        self.partial_text = partial_text
        super().__init__(partial_text)


class _StreamTimedOut(Exception):
    """Internal sentinel: the wall-clock deadline fired during streaming.

    Never propagates beyond _stream_generate / run(); caught immediately to
    commit the partial text and return a time-limit result.
    """

    def __init__(self, partial_text: str) -> None:
        self.partial_text = partial_text
        super().__init__(partial_text)


class ToolRegistry:
    """
    Manages the registration and execution of agentic tools.
    Separates the tool schemas (for the LLM) from the actual Python implementations.
    """

    def __init__(self):
        self._tools: dict[str, Callable[..., Any]] = {}
        self._schemas: list[dict[str, Any]] = []
        # tool_name -> lazy-loading group. Default "core" means a tool is always
        # sent unless the orchestrator explicitly reclassifies it, so a forgotten
        # tool fails safe (visible/callable) rather than silently hidden.
        self._groups: dict[str, str] = {}

    def register(self, schema: dict[str, Any], func: Callable[..., Any], group: str = "core"):
        """
        Register a new tool.

        Args:
            schema: The JSON Schema definition of the tool (Anthropic/OpenAI format).
            func: The actual Python callable that executes the tool.
            group: Lazy-loading group; "core" tools are always sent to the model,
                   others are sent only when their group is active for the turn.
        """
        tool_name = schema.get("name")
        if not tool_name:
            raise ValueError("Tool schema must contain a 'name' field.")

        self._tools[tool_name] = func
        self._schemas.append(schema)
        self._groups[tool_name] = group

    def update_handler(self, tool_name: str, func: Callable[..., Any]) -> bool:
        """Replace the callable for an already-registered tool without touching its schema.

        Used by sub-agent builders to rebind a tool to a scoped resource (e.g. a
        role-filtered ``SkillEngine``) without duplicating the schema in
        ``_schemas``.  Calling :meth:`register` for an already-registered tool
        would append the schema a second time, causing the model to see duplicate
        tool definitions.

        Args:
            tool_name: The ``name`` field of the tool to update.
            func:      The new callable to bind.

        Returns:
            ``True`` if the tool was found and updated; ``False`` if it was not
            registered (no-op in that case).
        """
        if tool_name not in self._tools:
            return False
        self._tools[tool_name] = func
        return True

    def unregister(self, tool_names: Iterable[str]) -> int:
        """Remove the named tools from the registry (handlers, schemas, groups).

        Used to tear down an MCP server's tools when that server is disabled or
        deleted at runtime, so the model can no longer call them without a
        gateway restart.  Unknown names are ignored (no-op per name).

        Args:
            tool_names: The exact (namespaced) tool names to remove, e.g.
                ``{"gmail_send_email", "gmail_list_inbox"}``.

        Returns:
            The number of tools actually removed.
        """
        targets = set(tool_names)
        if not targets:
            return 0
        removed = 0
        for name in targets:
            if self._tools.pop(name, None) is not None:
                removed += 1
            self._groups.pop(name, None)
        if removed:
            self._schemas = [s for s in self._schemas if s.get("name") not in targets]
        return removed

    def classify(
        self,
        core_names: set[str],
        group_by_name: dict[str, str],
        prefix_groups: dict[str, str] | None = None,
        default: str = "core",
    ) -> None:
        """Stamp lazy-loading groups by tool name, applied once after registration.

        Resolution order (first match wins):
        1. ``core_names`` → ``"core"``
        2. ``group_by_name`` exact match → mapped group
        3. ``prefix_groups`` prefix match → mapped group (longest prefix wins)
        4. Tools already tagged with an explicit non-core group are left intact
        5. Everything else (or tools still at the ``register`` default of "core") → ``default``

        Args:
            core_names: Tool names that should be in the "core" (always-on) group.
            group_by_name: Exact name → group mapping for statically-known tools.
            prefix_groups: Prefix → group mapping, e.g. ``{"google_": "google"}``.
            default: Group assigned to any otherwise-unclassified tool.
        """
        for name in self._tools:
            if name in core_names:
                self._groups[name] = "core"
            elif name in group_by_name:
                self._groups[name] = group_by_name[name]
            elif self._groups.get(name, "core") == "core":
                # Only reclassify tools that haven't been given an explicit group.
                if prefix_groups:
                    # Longest matching prefix wins to avoid ambiguity.
                    match = max(
                        (p for p in prefix_groups if name.startswith(p)),
                        key=len,
                        default=None,
                    )
                    if match:
                        self._groups[name] = prefix_groups[match]
                        continue
                self._groups[name] = default

    def reclassify_by_prefix(self, prefix_groups: dict[str, str]) -> None:
        """Move tools whose names match a given prefix into a new group.

        Designed as a post-``classify`` step for dynamically-discovered tool
        namespaces (e.g. MCP servers) whose prefixes are not known at boot-classify
        time.  Longest prefix wins when multiple prefixes match the same name.

        BB-32: MCP tools land in the ``"integrations"`` default group (never
        activated), making them invisible to the LLM.  This method lets the
        orchestrator relocate them into the ``"mcp"`` group immediately after
        classify, so ``get_schemas(active_groups={"mcp"})`` exposes them.

        Args:
            prefix_groups: Mapping of prefix string → group name, e.g.
                ``{"demo_": "mcp", "context7_": "mcp"}``.  An empty dict is a
                no-op.
        """
        if not prefix_groups:
            return
        for name in self._tools:
            match = max(
                (p for p in prefix_groups if name.startswith(p)),
                key=len,
                default=None,
            )
            if match is not None:
                self._groups[name] = prefix_groups[match]

    def available_groups(self) -> set[str]:
        """Return the set of groups currently in use (for system-prompt listing)."""
        return set(self._groups.values())

    def get_schemas(self, active_groups: set[str] | None = None) -> list[dict[str, Any]]:
        """Retrieve tool schemas.

        ``active_groups=None`` returns every schema (backward-compatible default used
        by sub-agents and existing callers). Otherwise returns "core" plus the active
        groups, so the model only sees the lazily-loaded tools it has unlocked.

        Duplicates by tool name are dropped (first registration wins) so the
        Anthropic API never receives a ``tools: Tool names must be unique`` error.
        """
        if active_groups is None:
            candidates = self._schemas
        else:
            allowed = {"core"} | active_groups
            candidates = [
                s for s in self._schemas if self._groups.get(s.get("name"), "core") in allowed
            ]
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        for schema in candidates:
            name = schema.get("name")
            if name and name not in seen:
                seen.add(name)
                result.append(schema)
        return result

    def execute(self, tool_call: ToolCall) -> Any:
        """
        Execute a tool requested by the LLM.

        Args:
            tool_call: The ToolCall object containing the name and arguments.

        Returns:
            The execution result (stringified for LLM ingestion).

        Raises:
            ValueError: If ``tool_call.parse_error`` is set (BB-54) — the
                provider's tool-call argument JSON was malformed or truncated
                (e.g. a max_tokens cutoff mid-tool-call), so ``input`` is not a
                trustworthy reconstruction of the model's intent. Raising here
                (instead of running the tool with empty/partial args) routes
                through the existing is_error=True tool_result path in
                ``ExecutionLoop.run`` / ``_execute_single_tool``.
        """
        if tool_call.parse_error:
            raise ValueError(f"Tool call '{tool_call.name}' rejected: {tool_call.parse_error}")

        if tool_call.name not in self._tools:
            return f"Error: Tool '{tool_call.name}' is not registered."

        func = self._tools[tool_call.name]
        try:
            result = func(**tool_call.input)
            return result
        except SuspendWorkflow as e:
            raise e  # Let the execution loop handle suspension
        except Exception:
            raise  # FIX H6: re-raise so run() can set is_error on the tool_result block


class ExecutionLoop:
    """The main autonomous execution orchestrator.

    Manages the conversation state via MemoryManager and handles the LLM's
    multi-step tool interactions with automatic context compaction.
    """

    # Hard token ceiling applied even when max_tokens=0 (unlimited opt-in budget).
    # Prevents true runaway generation; intentionally large so it never fires in
    # normal use but caps an undetected infinite tool-loop before real damage is done.
    _TOKEN_SAFETY_CEILING: int = 2_000_000

    def __init__(
        self,
        llm_client: BaseLLMClient,
        registry: ToolRegistry,
        memory,
        base_system_prompt: str = "",
        on_event: Callable[..., None] | None = None,
        skill_engine=None,
        cost_tracker=None,
        max_cost_usd: float = 0.0,
        max_tokens: int = 0,
        max_cost_per_turn: float = 0.0,
        max_tokens_per_turn: int = 0,
        max_wall_seconds: float = 600.0,
        router=None,
        routing_store=None,
    ):
        """Initialize the execution loop.

        Args:
            llm_client: The LLM provider (e.g., AnthropicClient).
            registry: The registry containing all available tools.
            memory: The MemoryManager for intelligent history management.
            base_system_prompt: The base system instructions (from brain.og + skill awareness).
            on_event: Optional callback invoked during execution for UI rendering.
                      Signature: on_event(event_type: str, data: dict)
                      Event types: "thinking", "tool_call", "tool_result", "text_chunk",
                      "compaction"
            skill_engine: Optional SkillEngine for usage tracking on load_skill calls.
            max_cost_usd: Per-session cost cap in USD (0 = unlimited).
            max_tokens: Per-session token cap (0 = unlimited).
            max_cost_per_turn: Per-turn cost cap in USD (0 = unlimited). Stops the
                agent mid-turn if a single user message would cost more than this.
            max_tokens_per_turn: Per-turn token cap (0 = unlimited). Stops the agent
                mid-turn if a single user message would consume more than this.
            max_wall_seconds: Wall-clock timeout for a single run() call in seconds.
                Always on (default 600 s = 10 min). Set to a positive value to cap
                long-running turns independent of iteration count or token budgets.
                Set to 0 to disable (not recommended; leaves only the iteration cap).
            router: Optional :class:`~hachi.core.routing.router.ModelRouter`.  When
                provided, tools and future slices may call ``router.select(capability)``
                for capability-aware routing.  When ``None`` (default), the loop behaves
                exactly as today — ``llm_client`` is the only client used.
            routing_store: Optional :class:`~hachi.gateway.routing_store.RoutingConfigStore`.
                When provided, the loop pulls a new :class:`RoutingSnapshot` from the
                store at each turn boundary if the store's version is newer than the
                last-applied version.  ``None`` disables hot-reload (back-compat).
        """
        self.llm_client = llm_client
        self.registry = registry
        self.memory = memory
        self.base_system_prompt = base_system_prompt
        self.on_event = on_event or (lambda *a, **kw: None)
        self.skill_engine = skill_engine
        self.cost_tracker = cost_tracker
        # Optional ModelRouter — when None, loop uses llm_client directly (back-compat).
        self.router = router
        # Phase 3: optional hot-reload store; None disables snapshot polling.
        self.routing_store = routing_store
        # Phase 3: version of the last routing snapshot adopted; 0 = boot state.
        self._applied_routing_version: int = 0
        # Per-turn LLM client: resolved at run() start via router.select() when a router
        # is present; falls back to llm_client for back-compat when router is None.
        self._turn_client: BaseLLMClient = llm_client
        # Per-session safety caps (0 = unlimited). Enforced between iterations so a
        # runaway tool-calling loop can't silently drain the user's API budget.
        self.max_cost_usd = max_cost_usd
        self.max_tokens = max_tokens
        # Per-turn safety caps (0 = unlimited). Enforced after each LLM call within
        # a single run() invocation so a runaway tool-calling sequence within one
        # user message can't exhaust the user's API budget.
        self.max_cost_per_turn = max_cost_per_turn
        self.max_tokens_per_turn = max_tokens_per_turn
        # Wall-clock timeout per run() call (always on; 0 disables).
        self.max_wall_seconds: float = max_wall_seconds
        # Baseline snapshot taken at the start of each run(); used to compute deltas.
        self._turn_tokens_start: int = 0
        self._turn_cost_start: float = 0.0
        self._current_turn_context: TurnContext | None = None
        # Tool groups unlocked for the current turn (besides always-on "core").
        # Reset each run(); mutated when the model calls use_tools / load_skill.
        self._active_groups: set[str] = set()
        # BB-32: groups that are ALWAYS active for this session (e.g. "mcp").
        # They are merged into _active_groups at the top of every run() so the
        # LLM never loses sight of them between turns.
        self._persistent_groups: set[str] = set()
        # Cooperative cancel: set by cancel(); checked at the top of each iteration.
        self._cancel_event: threading.Event = threading.Event()
        # Text accumulated across iterations (for partial output on cancel).
        self._partial_text: list[str] = []
        # P4-03: thread pool for parallel tool execution within a batch.
        # max_workers=4 is conservative for I/O-bound tools; does not starve other
        # concurrent sessions since each session's loop uses its own pool.
        self._tool_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="hachi-tool"
        )
        # Emitted once per ExecutionLoop instance when no budget is configured (MR-6 nudge).
        self._nudge_emitted: bool = False
        # Per-run wall-clock deadline (monotonic); set at the top of run(), cleared at end.
        self._wall_deadline: float | None = None

    def _execute_single_tool(
        self,
        tool_call: ToolCall,
        _otel_ctx: Any = None,
        _trace_ctx: "TraceContext | None" = None,
    ) -> tuple[Any, bool, "SuspendWorkflow | None"]:
        """Execute one tool call and return (result, is_error, suspend_exc_or_None).

        Designed to run inside the thread pool.  ``SuspendWorkflow`` is returned
        as a value (not re-raised) so the caller can collect all futures before
        deciding whether to suspend.

        Args:
            tool_call:   The tool invocation to execute.
            _otel_ctx:   OTel context captured on the calling thread (before
                         submit) so ``tool.call`` spans nest UNDER ``agent.turn``
                         across the thread boundary — the critical propagation fix.
            _trace_ctx:  :class:`~hachi.core.obs.trace.TraceContext` to re-bind
                         inside the worker so correlated logging and event-stamping
                         work even after the hand-off.
        """
        # Re-attach the OTel context captured on the submitting thread so spans
        # opened inside the pool are children of the agent.turn root span.
        otel_token = attach_otel_context(_otel_ctx)
        # Re-bind the TraceContext so contextvar-backed lookups work in the worker.
        from hachi.core.obs.trace import bind as _bind_trace

        try:
            with _bind_trace(_trace_ctx) if _trace_ctx is not None else contextlib.nullcontext():
                try:
                    with span("tool.call", tool=tool_call.name):
                        result = self.registry.execute(tool_call)
                    return (result, False, None)
                except SuspendWorkflow as exc:
                    return (None, False, exc)
                except Exception as exc:
                    # Only the stringified message goes back to the model (it needs
                    # a compact error to reason about), but the original exception
                    # + traceback must not vanish — log it with exc_info so the
                    # chain survives for debugging.
                    logger.error(
                        "Tool %s raised during execution: %s",
                        tool_call.name,
                        exc,
                        exc_info=exc,
                    )
                    return (f"Tool Execution Error: {str(exc)}", True, None)
        finally:
            detach_otel_context(otel_token)

    def add_user_message(self, text: str):
        """Add a user query to the active session history via the MemoryManager."""
        self.memory.add_message(Message(role="user", content=text))

    def _build_system_prompt(self) -> str:
        """
        Construct the full system prompt by combining the base prompt
        with the task ledger context header.

        If a TurnContext is active, uses the composed system_prompt from it.
        Otherwise, falls back to base_system_prompt + context_header.
        """
        if self._current_turn_context:
            # Use the frozen system prompt from the TurnContext
            # (already includes time header, memory snapshot, recall, and base prompt)
            return self._current_turn_context.system_prompt

        # Fallback for compatibility: build from base_system_prompt + task ledger.
        # get_context_header() is a legacy helper not in the ConversationMemory Protocol;
        # guard with getattr so minimal backends (tests, sub-agents) remain unaffected.
        _get_header = getattr(self.memory, "get_context_header", None)
        context_header = _get_header() if callable(_get_header) else ""
        if context_header:
            return f"{self.base_system_prompt}\n\n{context_header}"
        return self.base_system_prompt

    def _system_blocks(self) -> tuple[str, str | None]:
        """Return ``(cacheable prefix, per-turn tail)`` for the system prompt.

        Uses the frozen TurnContext's precomputed cache-aware split when present
        so the stable brain/.og prefix carries the cache breakpoint and the
        volatile time/recall tail stays after it. Falls back to the full prompt as
        a single (cacheable) block when there is no split — same as before.
        """
        tc = self._current_turn_context
        if tc is not None and tc.cacheable_system:
            return tc.cacheable_system, (tc.dynamic_system or None)
        return self._build_system_prompt(), None

    def _maybe_apply_routing_snapshot(self) -> None:
        """Pull a newer routing snapshot from the store if one is available.

        Called at the start of each turn boundary (inside ``_resolve_turn_client``
        or directly from ``run()`` when ``router`` is ``None``).  Safe to call
        from any single-session thread — no lock needed because each router is
        per-session and is only accessed from that session's own turn thread.

        No-op when:
          - ``routing_store`` is ``None`` (hot-reload not configured).
          - ``router`` is ``None`` (no router to update).
          - The store version equals the last-applied version (already current).
          - The store has no snapshot yet (``current_snapshot is None``).
        """
        if self.routing_store is None or self.router is None:
            return
        store_version = self.routing_store.version
        if store_version <= self._applied_routing_version:
            return
        snap = self.routing_store.current_snapshot
        if snap is None:
            return
        self.router.apply_snapshot(snap)
        self._applied_routing_version = store_version

    def _resolve_turn_client(self, user_input: str) -> None:
        """Classify *user_input* and resolve a capability-tiered client via the router.

        Sets :attr:`_turn_client` for this turn.  Falls back to :attr:`llm_client`
        if the router raises (e.g. :class:`~hachi.core.routing.router.NoRouteError`
        or any unexpected error) so the turn always completes.

        Called at the start of :meth:`run` only when :attr:`router` is not ``None``.
        """
        from hachi.core.routing.classifier import classify_turn_capability
        from hachi.core.routing.router import NoRouteError

        # Phase 3: pull a newer routing snapshot before this turn's select() calls.
        self._maybe_apply_routing_snapshot()

        # Reset the sticky cache so this turn re-selects independently.
        self.router.new_turn()

        capability = classify_turn_capability(user_input)
        try:
            resolved = self.router.select(capability)
            self._turn_client = resolved.client
            logger.debug(
                "hot-path routing: capability=%s primary=%s",
                capability,
                resolved.descriptor.id,
            )
        except NoRouteError as exc:
            # S3: a router falling back to the default client is operationally
            # visible (the model actually used for this turn silently changed) —
            # WARNING, not DEBUG, so it isn't invisible in normal operation.
            logger.warning(
                "hot-path routing: no route for capability=%s — falling back to "
                "llm_client (%s): %s",
                capability,
                getattr(self.llm_client, "model", "unknown"),
                exc,
            )
            self._turn_client = self.llm_client
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "hot-path routing: unexpected error for capability=%s — falling back to "
                "llm_client (%s): %s",
                capability,
                getattr(self.llm_client, "model", "unknown"),
                exc,
            )
            self._turn_client = self.llm_client

    def cancel(self) -> None:
        """Signal the loop to stop at the start of the next iteration.

        Thread-safe. The current LLM call and any in-progress tool execution
        finish normally; the loop exits cleanly at the top of the following
        iteration, preserving well-formed history (all tool_use blocks have
        matching tool_result blocks).
        """
        self._cancel_event.set()

    def shutdown(self, wait: bool = True) -> None:
        """Shut down the internal thread pool. Call on session close."""
        self._tool_pool.shutdown(wait=wait)

    def _stream_generate(self, on_delta: Callable[[str], None], **kwargs: Any) -> LLMResponse:
        """Drive generate_stream(), emit per-chunk callbacks, return the LLMResponse.

        Retries on pre-stream transient errors (bounded exponential backoff,
        same retry/backoff constants used elsewhere in this module). Does NOT
        retry mid-stream failures to avoid emitting duplicate output.

        Checks the cancel flag and wall-clock deadline after each chunk so an
        in-flight generation can be interrupted promptly by cancel() or a timeout.
        Raises ``_StreamCancelled`` or ``_StreamTimedOut`` (both internal-only;
        caught immediately in ``run()``) when interrupted mid-stream so the caller
        can commit partial text and return a clean result without touching LLMResponse.
        """
        delay = _LLM_RETRY_BASE_DELAY
        for attempt in range(1, _MAX_LLM_RETRIES + 1):
            chunks_yielded = 0
            streamed_parts: list[str] = []
            try:
                gen = self._turn_client.generate_stream(**kwargs)
                while True:
                    try:
                        chunk = next(gen)
                    except StopIteration as si:
                        return si.value
                    chunks_yielded += 1
                    streamed_parts.append(chunk)
                    on_delta(chunk)
                    # Cooperative mid-stream cancel: check after each chunk so an
                    # in-flight generation stops as soon as the next chunk arrives.
                    if self._cancel_event.is_set():
                        raise _StreamCancelled("".join(streamed_parts))
                    # Wall-clock deadline check inside the stream loop.
                    if self._wall_deadline is not None and time.monotonic() >= self._wall_deadline:
                        raise _StreamTimedOut("".join(streamed_parts))
            except (_StreamCancelled, _StreamTimedOut):
                raise  # propagate to run() without retry
            except Exception as exc:
                if (
                    chunks_yielded > 0
                    or attempt >= _MAX_LLM_RETRIES
                    or not _is_retryable_llm_error(exc)
                ):
                    raise
                logger.warning(
                    "LLM stream failed pre-output (attempt %d/%d): %s — retrying in %.1fs",
                    attempt,
                    _MAX_LLM_RETRIES,
                    exc,
                    delay,
                )
                self.on_event(LLM_RETRY, {"attempt": attempt, "error": str(exc)})
                time.sleep(delay)
                delay *= 2
        return LLMResponse()  # unreachable; satisfies type checker

    def _budget_exceeded(self) -> str | None:
        """Return a reason string if a per-session budget cap is hit, else None."""
        if self.cost_tracker is None or (self.max_cost_usd <= 0 and self.max_tokens <= 0):
            return None
        snap = self.cost_tracker.snapshot()
        if self.max_tokens > 0 and snap.total_tokens >= self.max_tokens:
            return f"token budget reached ({snap.total_tokens:,} >= {self.max_tokens:,})"
        if self.max_cost_usd > 0 and snap.estimated_cost_usd >= self.max_cost_usd:
            return (
                f"cost budget reached (~${snap.estimated_cost_usd:.4f} >= ${self.max_cost_usd:.2f})"
            )
        return None

    def _safety_ceiling_exceeded(self) -> str | None:
        """Return a reason string if the hard token safety ceiling is hit — or would be
        crossed by the upcoming LLM call — else None.

        This ceiling is always checked when a cost_tracker is present, regardless of
        whether the user configured any opt-in budget.  It prevents true runaway
        token consumption when no other cap is active.

        S1: checked PRE-FLIGHT, not just post-hoc. A pure ``snapshot >= ceiling``
        check only ever catches an overrun *after* a call has already happened —
        a single generation can cross the ceiling by its own full token cost before
        the next iteration's check notices. We instead add the upcoming call's
        worst-case token cost (bounded by ``_turn_client.max_tokens``, the
        provider's configured output-token cap) to the current snapshot, so a call
        that *would* cross the ceiling is refused before it starts.
        """
        if self.cost_tracker is None:
            return None
        snap = self.cost_tracker.snapshot()
        # Worst-case tokens the upcoming call could add: its bounded max output
        # tokens (0 if the client doesn't expose one — no client-based estimate
        # possible, falls back to the pure post-hoc check for that call).
        worst_case_next_call = getattr(self, "_turn_client", None)
        next_call_ceiling_tokens = getattr(worst_case_next_call, "max_tokens", 0) or 0
        projected = snap.total_tokens + next_call_ceiling_tokens
        if projected >= self._TOKEN_SAFETY_CEILING:
            return (
                f"token safety ceiling reached ({snap.total_tokens:,} "
                f"+ up to {next_call_ceiling_tokens:,} for the next call "
                f">= {self._TOKEN_SAFETY_CEILING:,})"
            )
        return None

    def _emit_budget_nudge(self) -> None:
        """Emit a one-time informational nudge when no spend budget is configured.

        The nudge fires at most once per ExecutionLoop instance so it is not
        repeated every turn.  It is informational only — the loop continues.
        """
        if self._nudge_emitted:
            return
        if self.max_cost_usd > 0 or self.max_tokens > 0:
            # A budget is set; no nudge needed.
            return
        self._nudge_emitted = True
        logger.info(
            "[hachi] No spend budget configured.  Consider setting max_cost_usd or "
            "max_tokens to guard against unexpected API costs."
        )
        self.on_event(
            "budget_nudge",
            {
                "message": (
                    "No spend budget is configured for this session.  "
                    "Set max_cost_usd or max_tokens to add a spend guardrail."
                )
            },
        )

    def _turn_budget_exceeded(self) -> str | None:
        """Return a reason string if a per-turn budget cap is hit, else None.

        Compares the current cumulative snapshot against the baseline recorded at
        the start of this ``run()`` call, so only the spend incurred by the current
        user message is counted — not earlier turns in the same session.
        """
        if self.cost_tracker is None or (
            self.max_cost_per_turn <= 0 and self.max_tokens_per_turn <= 0
        ):
            return None
        snap = self.cost_tracker.snapshot()
        turn_tokens = snap.total_tokens - self._turn_tokens_start
        turn_cost = snap.estimated_cost_usd - self._turn_cost_start
        if self.max_tokens_per_turn > 0 and turn_tokens >= self.max_tokens_per_turn:
            return f"per-turn token limit reached ({turn_tokens:,} >= {self.max_tokens_per_turn:,})"
        if self.max_cost_per_turn > 0 and turn_cost >= self.max_cost_per_turn:
            return (
                f"per-turn cost limit reached (~${turn_cost:.4f} >= ${self.max_cost_per_turn:.2f})"
            )
        return None

    @property
    def last_tool_calls(self) -> list[str]:
        """Tool names invoked during the most recent ``run()``, in call order.

        Powers the per-turn ``interaction_log`` (P0-2). Returns an empty list before the
        first run. A copy, so callers can't mutate loop state.
        """
        return list(getattr(self, "_last_tool_calls", []))

    @property
    def last_suspend(self) -> "SuspendWorkflow | None":
        """The ``SuspendWorkflow`` if the most recent ``run()`` ended by suspension, else None.

        Lets the caller persist a durable WAITING run + arm the wait registry (P0-1).
        Reset at the start of every ``run()``.
        """
        return getattr(self, "_last_suspend", None)

    def run(self, max_iterations: int = 15, turn_context: TurnContext | None = None) -> str:
        """
        Execute the autonomous loop until the model stops calling tools or hits the limit.

        Args:
            max_iterations: Safety threshold to prevent infinite tool-calling loops.
            turn_context: Optional immutable context for this turn (Phase 1 feature).
                         If provided, uses the composed system_prompt from the context
                         instead of mutating base_system_prompt. Prevents shared state issues.

        Returns:
            The final textual response from the agent.
        """
        # Set the turn context for this execution (used by _build_system_prompt)
        prev_context = self._current_turn_context
        self._current_turn_context = turn_context

        # Capture the user query for complete_task() calls later in the turn.
        # TurnContext is the authoritative source when present; fall back to the
        # memory attribute for callers that don't supply a TurnContext (sub-agents,
        # tests, legacy code paths).
        if turn_context is not None:
            user_input_for_turn: str = turn_context.user_input
        else:
            user_input_for_turn = getattr(self.memory, "_last_user_query", "")

        # P1-2: Classify the turn and resolve a (possibly tiered) client via the router.
        # Runs once per turn; sticky-per-turn caching inside ModelRouter means subsequent
        # select() calls for the same capability within this turn hit the cache.
        # When router is None, _turn_client stays as llm_client (byte-for-byte back-compat).
        self._turn_client = self.llm_client
        if self.router is not None:
            self._resolve_turn_client(user_input_for_turn)

        # Only "core" tools are sent until the model unlocks groups this turn.
        # BB-32: seed with persistent groups (e.g. "mcp") so MCP tools are
        # always visible to the LLM without an explicit use_tools call.
        self._active_groups = set(self._persistent_groups)
        # Reset per-run state.
        self._cancel_event.clear()
        self._partial_text = []
        # Per-turn tool-call record (names, in call order) for the interaction_log (P0-2).
        self._last_tool_calls: list[str] = []
        # Set when this run() ends by suspension, so the caller (AgentSession) can persist
        # a durable WAITING run + arm the wait registry (P0-1). None on a normal turn.
        self._last_suspend: SuspendWorkflow | None = None

        # Wall-clock deadline for this run() call (None when disabled).
        # Set before anything else so the streaming helper can read it.
        if self.max_wall_seconds > 0:
            self._wall_deadline: float | None = time.monotonic() + self.max_wall_seconds
        else:
            self._wall_deadline = None

        # One-time nudge when no spend budget is configured (MR-6 / ADV-013).
        self._emit_budget_nudge()

        # Record the cost/token baseline at turn start so _turn_budget_exceeded()
        # can compute deltas rather than checking cumulative session totals.
        if self.cost_tracker is not None:
            _snap = self.cost_tracker.snapshot()
            self._turn_tokens_start = _snap.total_tokens
            self._turn_cost_start = _snap.estimated_cost_usd

        # FIX H5: honour max_iterations declared on the TurnContext (overrides default)
        if turn_context is not None:
            tc_max = getattr(turn_context, "max_iterations", None)
            if tc_max is not None:
                max_iterations = tc_max

        try:
            iterations = 0

            while iterations < max_iterations:
                iterations += 1

                # Cooperative cancel: check before each LLM call so a cancel()
                # call from another thread stops the loop at the iteration boundary
                # without interrupting a running LLM call or leaving orphaned
                # tool_use blocks in history.
                if self._cancel_event.is_set():
                    partial = "".join(self._partial_text)
                    self.on_event(
                        "session_cancelled",
                        {"partial_text": partial, "status": "user_cancel"},
                    )
                    self.memory.complete_task(user_input_for_turn, f"Cancelled: {partial[:80]}")
                    return f"[CANCELLED] {partial}" if partial else "[CANCELLED]"

                # Wall-clock deadline check at iteration boundary (belt-and-suspenders;
                # also checked inside the stream loop for faster response).
                if self._wall_deadline is not None and time.monotonic() >= self._wall_deadline:
                    partial = "".join(self._partial_text)
                    self.on_event(
                        SESSION_TIME_LIMIT,
                        {
                            "elapsed_s": self.max_wall_seconds,
                            "partial_text": partial,
                            "status": "time_limit",
                        },
                    )
                    self.memory.complete_task(
                        user_input_for_turn,
                        f"Partial (time limit): {partial[:80]}",
                    )
                    partial_suffix = f" Partial: {partial}" if partial else ""
                    return (
                        f"[TIME LIMIT REACHED] Turn exceeded "
                        f"{self.max_wall_seconds:.0f}s wall-clock limit.{partial_suffix}"
                    )

                # Stop before spending more if a per-session budget cap was hit.
                budget_reason = self._budget_exceeded()
                if budget_reason:
                    self.on_event(BUDGET_EXCEEDED, {"reason": budget_reason})
                    self.memory.complete_task(user_input_for_turn, f"Stopped: {budget_reason}")
                    return f"[BUDGET LIMIT REACHED] {budget_reason}"

                # Always-on token safety ceiling (independent of opt-in budgets).
                ceiling_reason = self._safety_ceiling_exceeded()
                if ceiling_reason:
                    self.on_event(
                        BUDGET_EXCEEDED,
                        {"reason": ceiling_reason, "status": "safety_ceiling"},
                    )
                    self.memory.complete_task(user_input_for_turn, f"Stopped: {ceiling_reason}")
                    return f"[BUDGET LIMIT REACHED] {ceiling_reason}"

                # Apply compaction, clearing, and repair — all behind the memory seam.
                iter_state = self.memory.prepare_for_turn()
                if iter_state.compacted:
                    self.on_event(
                        "compaction",
                        {"old_skill": iter_state.old_skill, "new_skill": self.memory.active_skill},
                    )
                if iter_state.tool_results_cleared:
                    self.on_event(
                        "tool_results_cleared", {"count": iter_state.tool_results_cleared}
                    )
                if iter_state.history_repaired:
                    self.on_event(
                        "history_repaired", {"orphaned_tool_uses": iter_state.history_repaired}
                    )

                # Repair any orphaned tool_use blocks before sending to the API.
                # Edge cases (mid-loop errors, compaction races) can leave tool_use
                # blocks without a matching tool_result, causing Anthropic 400s.
                _repair = getattr(self.memory, "repair_tool_pairs", None)
                if callable(_repair):
                    fixed = _repair()
                    if fixed:
                        self.on_event("history_repaired", {"orphaned_tool_uses": fixed})

                # R9 — pre-generation context trim: if history is still large after the
                # standard housekeeping, do an extra tool-result sweep with aggressive
                # settings (smaller keep window, lower min_chars) before the LLM call so
                # fewer tokens are sent to the provider.  Guard with getattr: SubAgentMemory
                # is a lightweight stand-in that skips all compaction housekeeping.
                _estimate_fn = getattr(self.memory, "estimate_token_count", None)
                _clear_fn = getattr(self.memory, "clear_stale_tool_results", None)
                if callable(_estimate_fn) and callable(_clear_fn):
                    _pre_gen_tokens = _estimate_fn()
                    if _pre_gen_tokens > _PRE_GEN_TRIM_THRESHOLD:
                        _extra_cleared = _clear_fn(keep_recent_messages=3, min_chars=200)
                        if _extra_cleared:
                            self.on_event(
                                "context_trimmed",
                                {"cleared": _extra_cleared, "tokens_before": _pre_gen_tokens},
                            )

                self.on_event("thinking", {"iteration": iterations})

                # Build the system prompt split into a stable cacheable prefix and a
                # per-turn tail, so prompt caching reads the brain/.og prefix instead
                # of rewriting it every turn (time/recall live in the dynamic tail).
                cacheable_system, dynamic_system = self._system_blocks()
                gen_kwargs: dict[str, Any] = {
                    "messages": self.memory.history,
                    "system_prompt": cacheable_system,
                    "tools": self.registry.get_schemas(self._active_groups),
                }
                # Only pass the dynamic block when there is one, so clients without
                # the cache-split parameter keep working unchanged.
                if dynamic_system is not None:
                    gen_kwargs["dynamic_system"] = dynamic_system

                # 1. Ask the LLM to generate the next step (streaming; emits text_delta
                #    events per chunk so TUI / SSE surfaces can render incrementally).
                delta_parts: list[str] = []

                def _on_delta(chunk: str, _parts: list[str] = delta_parts) -> None:
                    _parts.append(chunk)
                    self.on_event("text_delta", {"text": chunk})

                try:
                    _llm_model = getattr(self._turn_client, "model", "unknown")
                    with span("llm.generate", model=_llm_model):
                        response = self._stream_generate(on_delta=_on_delta, **gen_kwargs)
                        if response is None:
                            # Defence-in-depth: a resilient/streaming provider path can
                            # complete with a None value instead of raising when the
                            # upstream call fails (commonly: out of API credits, invalid
                            # key, or model unavailable). Surface a clear, logged error
                            # instead of crashing below on `response.usage` with an opaque
                            # AttributeError that masks the real cause.
                            raise RuntimeError(
                                "LLM returned no response — the AI provider call failed "
                                "(check API credits, key, and model configuration)."
                            )
                        # Enrich the span with token/cost telemetry while still inside
                        # the span context so attributes land on the correct span.
                        from hachi.core.tracing import add_span_attributes

                        # ``usage`` can be absent on a degraded/empty provider response
                        # (e.g. a swallowed upstream failure); guard so telemetry never
                        # crashes the turn with an opaque AttributeError.
                        if response.usage is not None:
                            add_span_attributes(
                                llm_input_tokens=response.usage.input_tokens,
                                llm_output_tokens=response.usage.output_tokens,
                                llm_cache_read_tokens=response.usage.cache_read_tokens,
                                llm_cache_creation_tokens=response.usage.cache_creation_tokens,
                                llm_model=_llm_model,
                            )
                except _StreamCancelled as exc:
                    # Mid-stream cancel: partial text is in exc.partial_text plus whatever
                    # was already flushed into _partial_text from prior iterations.
                    partial = "".join(self._partial_text) + exc.partial_text
                    self.on_event(
                        "session_cancelled",
                        {"partial_text": partial, "status": "user_cancel"},
                    )
                    self.memory.complete_task(
                        user_input_for_turn, f"Cancelled (mid-stream): {partial[:80]}"
                    )
                    return f"[CANCELLED] {partial}" if partial else "[CANCELLED]"
                except _StreamTimedOut as exc:
                    partial = "".join(self._partial_text) + exc.partial_text
                    self.on_event(
                        SESSION_TIME_LIMIT,
                        {
                            "elapsed_s": self.max_wall_seconds,
                            "partial_text": partial,
                            "status": "time_limit",
                        },
                    )
                    self.memory.complete_task(
                        user_input_for_turn,
                        f"Partial (time limit, mid-stream): {partial[:80]}",
                    )
                    return (
                        f"[TIME LIMIT REACHED] Turn exceeded {self.max_wall_seconds:.0f}s "
                        f"wall-clock limit."
                        f"{(' Partial: ' + partial) if partial else ''}"
                    )

                # Account for token usage / estimated cost and surface it live.
                if self.cost_tracker is not None:
                    model_name = getattr(self._turn_client, "model", "unknown")
                    self.cost_tracker.record(model_name, response.usage, feature="chat")
                    self.on_event("usage", self.cost_tracker.snapshot().to_dict())
                    # Per-call cache/cost breakdown (hit-rate + fresh/cached/no-cache
                    # spread) so cache effectiveness is observable per request, not just
                    # buried in the aggregate. Guarded — observability never breaks a turn.
                    try:
                        self.on_event(
                            "cache_metrics",
                            self.cost_tracker.cache_metrics(model_name, response.usage),
                        )
                    except Exception:
                        pass

                # Stop this turn if a per-turn budget cap is now exceeded.
                turn_budget_reason = self._turn_budget_exceeded()
                if turn_budget_reason:
                    self.on_event(BUDGET_EXCEEDED, {"reason": turn_budget_reason})
                    self.memory.complete_task(user_input_for_turn, f"Stopped: {turn_budget_reason}")
                    return f"[BUDGET LIMIT REACHED] {turn_budget_reason}"

                # Record the assistant's generation in history
                assistant_content: list[dict[str, Any]] = []

                if response.content:
                    assistant_content.append({"type": "text", "text": response.content})
                    # Emit the full text as a single text_chunk ONLY when streaming
                    # produced no incremental deltas (a non-streaming client/fallback).
                    # Delta listeners (TUI transcript, gateway SSE) accumulate
                    # text.stream.delta events; emitting BOTH the per-chunk deltas and
                    # the full chunk made them render the reply twice — the full chunk
                    # appended on top of the text already built from the deltas.
                    if not delta_parts:
                        self.on_event("text_chunk", {"text": response.content})
                    self._partial_text.append(response.content)

                for tc in response.tool_calls:
                    assistant_content.append(
                        {"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.input}
                    )

                if not assistant_content:
                    # Empty response with no tool calls means the LLM stopped
                    # cleanly (e.g. max_tokens reached mid-token). Treat it as a
                    # graceful finish rather than falling through to the misleading
                    # "exceeded maximum iterations" error.
                    self.memory.complete_task(user_input_for_turn, "")
                    return response.content or ""

                self.memory.add_message(Message(role="assistant", content=assistant_content))

                # 2. If no tools were called, the agent has finished its task
                if not response.tool_calls:
                    # Sync facts and log the completed task via the memory seam.
                    self.memory.complete_task(user_input_for_turn, response.content or "")
                    return response.content

                # 3. Execute requested tools and detect skill switches
                # P4-03: Pre-pass — apply control-flow side-effects for all calls before
                # dispatching to the thread pool.  use_tools/load_skill mutate shared state
                # (active_groups, active_skill) that downstream tools may rely on, so they
                # must run before any tool is submitted.
                tool_results: list[dict[str, Any]] = []
                suspend_exc: SuspendWorkflow | None = None

                for tool_call in response.tool_calls:
                    self.on_event("tool_call", {"name": tool_call.name, "input": tool_call.input})
                    # Record for the per-turn interaction_log (sequential pre-pass — safe
                    # before the thread-pool dispatch below).
                    self._last_tool_calls.append(tool_call.name)

                    # Lazy tool loading: the model unlocks an optional group for the
                    # rest of this turn; the handler only confirms — state lives here.
                    if tool_call.name == "use_tools":
                        group = tool_call.input.get("group", "")
                        if group:
                            self._active_groups.add(group)

                    # Detect skill switch via load_skill calls (compaction deferred to next
                    # iteration)
                    if tool_call.name == "load_skill":
                        new_skill = tool_call.input.get("name", "")
                        if new_skill:
                            # Auto-unlock the skill's own tool group (its REST APIs are
                            # registered under group == skill name) so the model rarely
                            # needs an explicit use_tools call after loading a skill.
                            self._active_groups.add(new_skill)
                            # Phase 4: Track skill usage
                            if self.skill_engine:
                                self.skill_engine.record_use(new_skill)
                            if new_skill != self.memory.active_skill:
                                self.memory.signal_skill_switch(new_skill)

                # P4-03: Submit all tool calls to the thread pool concurrently.
                # Results are collected in original order so the API receives a
                # well-ordered tool_result block list (Anthropic requires it).
                #
                # OTel context propagation (the critical fix, 21-observability.md §3):
                # The OTel context and TraceContext are captured HERE (on the turn
                # thread, inside the agent.turn root span) and forwarded into each
                # worker so tool.call spans are children of agent.turn across the
                # thread boundary.  Without this capture the pool workers start with a
                # fresh empty context and spans cannot be correlated.
                from hachi.core.obs.trace import current as _current_trace_ctx

                _otel_ctx = copy_otel_context()
                _trace_ctx = _current_trace_ctx()
                _futures: dict[str, concurrent.futures.Future] = {}
                for tool_call in response.tool_calls:
                    _futures[tool_call.id] = self._tool_pool.submit(
                        self._execute_single_tool, tool_call, _otel_ctx, _trace_ctx
                    )

                for tool_call in response.tool_calls:
                    if suspend_exc is not None:
                        break
                    raw_result, tool_error, _suspend = _futures[tool_call.id].result()
                    if _suspend is not None:
                        suspend_exc = _suspend
                        break

                    # Most tools return text (stringified here). A tool that needs
                    # the model to *see* richer content (e.g. an image) returns a
                    # ToolResultBlocks, whose blocks pass through to the tool_result
                    # content untouched. Only this exact type opts into pass-through,
                    # so tools that return plain dicts keep being stringified.
                    if isinstance(raw_result, ToolResultBlocks):
                        result_content: Any = list(raw_result.blocks)
                        result_summary = raw_result.summary or "[multimodal content]"
                    else:
                        result_content = _compress_tool_output(str(raw_result))
                        result_summary = result_content

                    self.on_event(
                        "tool_result",
                        {
                            "name": tool_call.name,
                            "result": result_summary[:TOOL_RESULT_PREVIEW_MAX],
                        },
                    )

                    tr: dict[str, Any] = {
                        "type": "tool_result",
                        "tool_use_id": tool_call.id,
                        "content": result_content,
                    }
                    if tool_error:
                        tr["is_error"] = True  # FIX H6: signal failure to the Anthropic API
                    tool_results.append(tr)

                # Every tool_use block in the assistant message MUST have a matching
                # tool_result, or the next turn's history is rejected by the Anthropic
                # API (400). On suspend we break early, so synthesize results for the
                # suspending tool and any that never ran.
                answered_ids = {tr["tool_use_id"] for tr in tool_results}
                for tool_call in response.tool_calls:
                    if tool_call.id not in answered_ids:
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_call.id,
                                "content": "[not executed: workflow suspended]",
                            }
                        )

                if tool_results:
                    self.memory.add_message(Message(role="user", content=tool_results))

                if suspend_exc is not None:
                    self.memory.complete_task(
                        user_input_for_turn, f"Suspended: {suspend_exc.reason}"
                    )
                    # Surface the structured wait condition to the caller so the gateway
                    # can persist RunState(WAITING) + arm the registry (P0-1). Without this
                    # the wait_kind/wait_key were lost inside the return string.
                    self._last_suspend = suspend_exc
                    return f"[WORKFLOW SUSPENDED] {suspend_exc.reason}"

            self.on_event(
                SESSION_ITERATION_LIMIT,
                {"iterations": max_iterations, "status": "incomplete"},
            )
            self.memory.complete_task(
                user_input_for_turn,
                f"Partial: iteration limit reached ({max_iterations})",
            )
            return (
                f"{INCOMPLETE_RESULT_PREFIX} The task reached the {max_iterations}-iteration "
                "limit and could not be fully completed. Reply 'continue' to pick up where "
                "it left off."
            )

        finally:
            # Restore previous context
            self._current_turn_context = prev_context
