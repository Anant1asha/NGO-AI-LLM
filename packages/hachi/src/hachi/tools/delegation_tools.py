"""
Delegation Tools — Sub-Agent Spawning Interface for the Orchestrator

This module exposes the Sub-Agent Runtime to the LLM as a callable tool.
It is the bridge between the orchestrator's intent ("I need a coder to handle this")
and the isolated execution environment that actually runs the sub-agent.

Architecture:
    Orchestrator LLM
        │
        ▼ calls delegate_task(role="coder", task="...")
    delegation_tools.py
        │ 1. Resolves role → .og file
        │ 2. Builds scoped ToolRegistry (no delegate_task, no memory tools)
        │ 3. Spawns SubAgentRuntime
        ▼ 4. Returns SubAgentReport → orchestrator context
    Sub-Agent (isolated)

Security:
    - Sub-agents do NOT receive the delegate_task tool (no recursive spawning)
    - Sub-agents do NOT receive memory tools (no long-term memory writes)
    - Sub-agents inherit the same PermissionGate as the orchestrator
    - All tool execution is logged via on_event callbacks
"""

import json
import logging
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import wait as futures_wait
from typing import Any

from hachi.core.loop import ToolRegistry
from hachi.core.permissions import PermissionGate
from hachi.core.sub_agent import (
    RoleResolver,
    SubAgentReport,
    SubAgentRuntime,
    SubAgentStatus,
)
from hachi.jobs import Job, JobStatus
from hachi.og_engine.parser import parse_og_file

logger = logging.getLogger(__name__)


# ==========================================
# Tool Schemas (Anthropic Format)
# ==========================================

DELEGATE_TASK_SCHEMA = {
    "name": "delegate_task",
    "description": (
        "Spawn a specialized sub-agent to handle a complex task in isolation. "
        "The sub-agent runs with its own context window, executes the task using "
        "the tools available to it, and returns a short report. "
        "Your context stays clean — you only see the final summary.\n\n"
        "WHEN TO USE:\n"
        "- The task requires 3+ tool calls across multiple domains\n"
        "- The task involves trial-and-error that would pollute your context\n"
        "- The task requires specialized execution (coding, research, email)\n\n"
        "WHEN NOT TO USE:\n"
        "- Simple 1-2 step tasks — just do them directly\n"
        "- Purely conversational questions — answer them yourself\n"
        "- Tasks requiring real-time user interaction"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "role": {
                "type": "string",
                "description": (
                    "The sub-agent role to use. Maps to a .og file in the roles directory. "
                    "Available roles: 'coder' (coding/engineering), 'researcher' (web research), "
                    "'emailer' (email composition/sending), 'analyst' (data analysis), "
                    "'devops' (system administration)."
                ),
            },
            "task": {
                "type": "string",
                "description": (
                    "A detailed, self-contained description of what the sub-agent should "
                    "accomplish. Be specific — the sub-agent has NO access to your conversation "
                    "history. "
                    "Include file paths, URLs, expected output format, and any constraints."
                ),
            },
            "context": {
                "type": "string",
                "description": (
                    "Optional additional context for the sub-agent. Use this to pass "
                    "file contents, prior research results, user preferences, or any "
                    "information the sub-agent needs but can't discover on its own."
                ),
            },
            "write_targets": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "P4-01: Declared write-target prefixes this sub-agent will modify "
                    "(e.g. ['projects/billing', 'drive.write']). "
                    "Prevents two concurrent delegations from writing to the same resource. "
                    "Omit for read-only tasks."
                ),
            },
            "model": {
                "type": "string",
                "description": (
                    "Optional model override for this specific sub-agent. "
                    "When set, the sub-agent will be run with this model instead of the "
                    "session default (e.g. 'claude-opus-4-5' for complex reasoning tasks "
                    "or 'claude-haiku-4-5' for fast, cheap sub-tasks). "
                    "Omit to use the session's configured sub-agent model."
                ),
            },
        },
        "required": ["role", "task"],
    },
}

LIST_ROLES_SCHEMA = {
    "name": "list_roles",
    "description": (
        "List all available sub-agent roles that can be used with delegate_task. "
        "Each role maps to a .og blueprint file that defines the sub-agent's "
        "persona, constraints, and capabilities."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}


# ==========================================
# Blocked Tools for Sub-Agents
# ==========================================

# These tools are NEVER available to sub-agents.
# This is the security boundary that prevents:
# - Recursive spawning (delegate_task, list_roles)
# - Uncontrolled memory writes (core_save_memory, core_save_user_profile)
# - Memory reads that could leak cross-session data
# - Workflow manipulation (suspend_workflow)
# - Session state corruption (core_search_sessions)
BLOCKED_TOOL_NAMES = frozenset(
    {
        # Delegation (no recursive spawning)
        "delegate_task",
        "delegate_parallel_tasks",
        "list_roles",
        # Core memory (no long-term memory writes from sub-agents)
        "core_save_memory",
        "core_search_memory",
        "core_delete_memory",
        # User profile (sub-agents must never alter user identity)
        "core_save_user_profile",
        "core_search_user_profile",
        "core_delete_user_profile",
        # Agent profile (sub-agents must never alter agent personality)
        "core_save_agent_profile",
        "core_delete_agent_profile",
        # Session persistence (sub-agents don't have sessions)
        "core_search_sessions",
        # Workflow control (registered name is core_suspend_workflow)
        "core_suspend_workflow",
        # Skill authoring + scheduling are privileged main-agent actions
        "save_skill",
        "schedule_task",
        "list_schedules",
        "cancel_schedule",
    }
)


# ==========================================
# Scoped Tool Registry Builder
# ==========================================

# Core tools that are always available to every sub-agent regardless of role
# (these are the minimum required for any useful work)
_CORE_TOOLS = frozenset(
    {
        "run_terminal_command",
        "read_file",
        "write_file",
        "search_skills",
        "peek_skill",
        "load_skill",
    }
)


_OG_SKILL_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "search_skills",
        "list_skills",
        "peek_skill",
        "load_skill",
        "skill_dependencies",
        "check_skill_assertions",
        "skill_changelog",
        "skill_traverse_hints",
        "save_skill",
    }
)
"""OG skill tools that reference the SkillEngine — rebindable per sub-agent role."""


def _build_scoped_registry(
    parent_registry: ToolRegistry,
    gate: PermissionGate | None = None,
    tool_patterns: str = "",
    skill_engine: Any = None,
    sub_agent_role: str = "",
) -> ToolRegistry:
    """Build a restricted ToolRegistry for a sub-agent.

    Three-stage filtering + optional OG tool rebinding:
        1. BLOCK:  Remove tools in BLOCKED_TOOL_NAMES (security boundary).
        2. ALLOW:  If tool_patterns is set, only include tools matching
                   the declared patterns (role-based scoping).
        3. REBIND: If ``skill_engine`` and ``sub_agent_role`` are provided,
                   rebind the OG skill-reading tools to a
                   ``skill_engine.with_role(sub_agent_role)`` view so the
                   sub-agent can only see skill nodes accessible to its role.
                   Without this step sub-agents would inherit the orchestrator's
                   engine and see ``scope=orchestrator`` nodes.

    tool_patterns is a pipe-separated string from the role .og file's
    ``::meta tools:`` field. Each pattern is either an exact name or a
    glob prefix (e.g., ``google_*``).

    If tool_patterns is empty, all non-blocked tools pass through
    (backward compatibility).

    Args:
        parent_registry: The orchestrator's full ToolRegistry.
        gate:            Optional PermissionGate (same as orchestrator's).
        tool_patterns:   Pipe-separated tool name patterns (from role .og meta.tools).
        skill_engine:    Optional SkillEngine; when provided together with
                         ``sub_agent_role``, the OG tools are rebound to a
                         scope-filtered view of this engine.
        sub_agent_role:  The sub-agent's role string (e.g. ``"coder"``).  Used
                         as the ``agent_role`` argument for the engine view.

    Returns:
        A new ToolRegistry with security-blocked and role-filtered tools removed.
    """
    scoped = ToolRegistry()

    # Parse tool patterns into prefix list
    allowed_prefixes = []
    allowed_exact = set()
    if tool_patterns:
        for pattern in tool_patterns.split("|"):
            pattern = pattern.strip()
            if not pattern:
                continue
            if pattern.endswith("*"):
                allowed_prefixes.append(pattern[:-1])  # "google_*" → "google_"
            else:
                allowed_exact.add(pattern)

    has_filter = bool(allowed_prefixes or allowed_exact)

    for schema in parent_registry.get_schemas():
        tool_name = schema.get("name", "")

        # Stage 1: Security block
        if tool_name in BLOCKED_TOOL_NAMES:
            logger.debug("Blocked tool '%s' from sub-agent registry", tool_name)
            continue

        # Stage 2: Role-based filtering (skip if no patterns declared)
        if has_filter:
            # Core tools always pass through
            if tool_name not in _CORE_TOOLS:
                # Check if tool matches any declared pattern
                matched = tool_name in allowed_exact or any(
                    tool_name.startswith(prefix) for prefix in allowed_prefixes
                )
                if not matched:
                    logger.debug("Role-filtered tool '%s' (not in tool_patterns)", tool_name)
                    continue

        # Copy the tool's handler from the parent registry
        handler = parent_registry._tools.get(tool_name)
        if handler:
            scoped.register(schema, handler)

    # Stage 3: Rebind OG skill tools to a scope-filtered engine view.
    # This prevents sub-agents from reading skill nodes outside their scope
    # (e.g. scope=orchestrator nodes in brain.og).
    if skill_engine is not None and sub_agent_role:
        _rebind_og_tools_for_role(scoped, skill_engine, sub_agent_role)

    return scoped


def _rebind_og_tools_for_role(
    registry: ToolRegistry,
    skill_engine: Any,
    sub_agent_role: str,
) -> None:
    """Rebind OG skill tools in *registry* to a role-scoped engine view.

    Creates a ``skill_engine.with_role(sub_agent_role)`` lightweight view and
    updates each registered OG tool handler via :meth:`ToolRegistry.update_handler`
    (no schema duplication).

    Args:
        registry:       The sub-agent's scoped ToolRegistry (mutated in-place).
        skill_engine:   The parent SkillEngine (already loaded with skills).
        sub_agent_role: Role to enforce — e.g. ``"coder"``, ``"researcher"``.
                        Nodes whose ``scope`` is not ``"all"``, ``"public"``, or
                        this value will be hidden from the sub-agent.
    """
    from hachi.tools.og_tools import (
        _make_check_skill_assertions,
        _make_list_skills,
        _make_load_skill,
        _make_peek_skill,
        _make_save_skill,
        _make_search_skills,
        _make_skill_changelog,
        _make_skill_dependencies,
        _make_skill_traverse_hints,
    )

    scoped_engine = skill_engine.with_role(sub_agent_role)
    factories = {
        "search_skills": _make_search_skills,
        "list_skills": _make_list_skills,
        "peek_skill": _make_peek_skill,
        "load_skill": _make_load_skill,
        "skill_dependencies": _make_skill_dependencies,
        "check_skill_assertions": _make_check_skill_assertions,
        "skill_changelog": _make_skill_changelog,
        "skill_traverse_hints": _make_skill_traverse_hints,
        "save_skill": _make_save_skill,
    }
    for tool_name, factory in factories.items():
        updated = registry.update_handler(tool_name, factory(scoped_engine))
        if updated:
            logger.debug(
                "Rebound OG tool '%s' to scope-filtered engine (role=%s)",
                tool_name,
                sub_agent_role,
            )


# ==========================================
# Tool Handlers
# ==========================================


_DELEGATION_MAX_DEPTH = 3
"""Maximum allowed delegation nesting depth (inclusive).

At depth 0 the orchestrator calls delegate_task; depth 1 is a child sub-agent.
The ``delegate_task`` tool is already absent from sub-agent registries via
``BLOCKED_TOOL_NAMES``, so in normal operation depth never exceeds 1.  This
cap is a defence-in-depth backstop against bugs that bypass that block (e.g. a
future refactor that forgets to strip the tool).
"""


def _make_delegate_task(
    parent_registry: ToolRegistry,
    gate: PermissionGate | None = None,
    on_event: Callable[..., None] | None = None,
    vault=None,
    job_queue=None,
    sub_agent_llm=None,
    cost_tracker=None,
    skill_engine: Any = None,
    lease_manager: Any = None,
    # S2: parent session's configured budget caps (0 = unlimited), inherited by
    # every sub-agent this factory spawns UNLESS a future caller passes larger
    # explicit values — see SubAgentRuntime's docstring for the same fields.
    max_cost_usd: float = 0.0,
    max_tokens: int = 0,
    max_cost_per_turn: float = 0.0,
    max_tokens_per_turn: int = 0,
    # --- ADV-012: depth / cycle tracking (internal, not exposed in schema) ---
    _depth: int = 0,
    _ancestry: tuple[str, ...] = (),
) -> Callable[..., str]:
    """Factory: creates the delegate_task tool handler.

    The handler is a closure that captures the parent_registry, gate, and vault,
    ensuring each sub-agent gets a properly scoped copy of the tools and
    every delegation result is persisted to long-term memory.

    Args:
        parent_registry: The orchestrator's full ToolRegistry.
        gate:            The device permission gate.
        on_event:        Optional progress callback for the CLI/UI.
        vault:           Optional MemoryVault for persisting delegation results.
        job_queue:       Optional job queue for persistence work.
        skill_engine:    Optional SkillEngine; when provided, OG skill tools in
                         the sub-agent registry are rebound to a
                         ``skill_engine.with_role(role)`` view, preventing the
                         sub-agent from reading ``scope=orchestrator`` nodes.
        lease_manager:   P4-01 optional LeaseManager for write-target leases.
        max_cost_usd:        S2 — parent session's per-session cost cap, inherited
                             by every spawned sub-agent by default (0 = unlimited).
        max_tokens:          S2 — parent session's per-session token cap.
        max_cost_per_turn:   S2 — parent session's per-turn cost cap.
        max_tokens_per_turn: S2 — parent session's per-turn token cap.
        _depth:          ADV-012 internal — current nesting depth (0 = orchestrator).
        _ancestry:       ADV-012 internal — tuple of role names already in the call
                         chain, used to detect cycles.

    Returns:
        A callable that accepts (role, task, context, write_targets) and returns a report string.
    """

    def delegate_task(
        role: str,
        task: str,
        context: str = "",
        write_targets: list[str] | None = None,
        model: str | None = None,
    ) -> str:
        """Spawn an isolated sub-agent and return its execution report.

        This function:
            1. Guards against depth / cycle violations (ADV-012).
            2. Resolves the role .og file and ABORTS if it cannot be loaded (ADV-006).
            3. Builds a scoped ToolRegistry (no delegate_task, no memory tools).
            4. Creates a SubAgentRuntime with the role's .og file.
            5. Runs the sub-agent to completion.
            6. Enqueues persistence work for the delegation log.
            7. Returns a compact report for the orchestrator.

        Args:
            role:    Sub-agent role name (e.g., 'coder', 'researcher').
            task:    Self-contained task description.
            context: Optional additional context string.
            write_targets: Optional list of write-target prefixes (P4-01).
            model:   Optional model override for this sub-agent (HIGH-013).

        Returns:
            A structured report string for the orchestrator's context.
        """
        targets: list[str] = write_targets or []

        # ------------------------------------------------------------------
        # ADV-012: depth / cycle backstop
        # ------------------------------------------------------------------
        if _depth >= _DELEGATION_MAX_DEPTH:
            abort_msg = (
                f"⛔ Delegation aborted: maximum delegation depth ({_DELEGATION_MAX_DEPTH}) "
                f"reached (current depth={_depth}). "
                f"Ancestry chain: {' → '.join(_ancestry) or '(orchestrator)'}. "
                "Sub-agent not started."
            )
            logger.warning(
                "delegate_task depth limit reached: depth=%d ancestry=%s role=%s",
                _depth,
                _ancestry,
                role,
            )
            if on_event:
                on_event(
                    "delegation_complete",
                    {"role": role, "status": "aborted", "task": task[:100]},
                )
            return abort_msg

        if role in _ancestry:
            abort_msg = (
                f"⛔ Delegation aborted: cyclic role detected — '{role}' already "
                f"appears in ancestry chain: {' → '.join(_ancestry)}. "
                "Sub-agent not started."
            )
            logger.warning(
                "delegate_task cycle detected: role=%s ancestry=%s",
                role,
                _ancestry,
            )
            if on_event:
                on_event(
                    "delegation_complete",
                    {"role": role, "status": "aborted", "task": task[:100]},
                )
            return abort_msg

        # ------------------------------------------------------------------
        # P4-01: acquire write-target leases before starting
        # ------------------------------------------------------------------
        if lease_manager is not None and targets:
            ok, conflict = lease_manager.acquire(role, targets)
            if not ok:
                return (
                    f"[Sub-Agent Report: {role}]\n"
                    f"Status: error\n"
                    f"Result: Delegation blocked — {conflict}\n"
                    "[Execution: 0 steps, 0.0s]"
                )

        # Emit progress event for CLI display
        if on_event:
            on_event(
                "delegation_start",
                {
                    "role": role,
                    "task": task[:100],
                    "write_targets": targets,
                },
            )

        try:
            # ------------------------------------------------------------------
            # ADV-006: resolve role .og file — FAIL CLOSED on any parse/resolve error.
            # An empty tool_patterns would cause _build_scoped_registry to grant the
            # UNFILTERED tool set, so we must never proceed without a valid .og file.
            # ------------------------------------------------------------------
            try:
                resolver = RoleResolver()
                role_path = resolver.resolve(role)
                role_og = parse_og_file(str(role_path))
                tool_patterns: str = role_og.meta.tools
            except Exception as og_exc:
                abort_msg = (
                    f"⛔ Delegation aborted: could not load role '{role}' "
                    f"('{og_exc}'). "
                    "Sub-agent not started (failing closed for safety)."
                )
                logger.error(
                    "delegate_task: role .og load failed for '%s', failing closed: %s",
                    role,
                    og_exc,
                )
                if on_event:
                    on_event(
                        "delegation_complete",
                        {"role": role, "status": "aborted", "task": task[:100]},
                    )
                # Leases are released by the outer `finally` block — do not release here.
                return abort_msg

            # Build the scoped tool registry (filtered by role + security).
            # Pass skill_engine so OG tools are rebound to the sub-agent's
            # scope-filtered engine view (hides scope=orchestrator nodes).
            scoped_registry = _build_scoped_registry(
                parent_registry,
                gate,
                tool_patterns,
                skill_engine=skill_engine,
                sub_agent_role=role,
            )

            # Create and run the sub-agent. Pass the credential-resolved LLM client
            # down so the sub-agent uses the SAME working provider/key as the main
            # agent (otherwise it would build a bare client that only reads the env
            # var and fails with "ANTHROPIC_API_KEY must be provided").
            # HIGH-013: when an explicit model is provided, SubAgentRuntime builds a
            # fresh client with that model; otherwise the injected client is used.
            if model:
                logger.info(
                    "delegate_task: explicit model override for role=%s → model=%s", role, model
                )
            runtime = SubAgentRuntime(
                role=role,
                task=task,
                context=context or None,
                tool_registry=scoped_registry,
                llm_client=sub_agent_llm,
                model=model or None,
                on_event=on_event,
                cost_tracker=cost_tracker,
                max_cost_usd=max_cost_usd,
                max_tokens=max_tokens,
                max_cost_per_turn=max_cost_per_turn,
                max_tokens_per_turn=max_tokens_per_turn,
            )
            report = runtime.run()

            # Emit completion event
            if on_event:
                on_event(
                    "delegation_complete",
                    {
                        "role": role,
                        "status": report.status.value,
                        "duration": report.duration_seconds,
                        "iterations": report.iterations,
                        # Carry the task so adapt_event() can rebuild the JOB_STARTED
                        # job_id and clear this sub-agent from the Active Jobs table.
                        "task": task[:100],
                    },
                )

            _enqueue_delegation_persistence(job_queue, vault, report)

            # Return the compact orchestrator string (not raw JSON)
            return report.to_orchestrator_string()

        except FileNotFoundError as exc:
            # Role .og file not found — provide helpful error
            logger.warning("delegate_task failed: %s", exc)
            error_report = SubAgentReport(
                status=SubAgentStatus.ERROR,
                summary=str(exc),
                role=role,
                task=task,
            )
            _enqueue_delegation_persistence(job_queue, vault, error_report)
            return error_report.to_orchestrator_string()

        except Exception as exc:
            # Unexpected error — still return a structured report
            logger.error("delegate_task failed unexpectedly: %s", exc, exc_info=True)
            error_report = SubAgentReport(
                status=SubAgentStatus.ERROR,
                summary=f"Delegation failed: {exc}",
                role=role,
                task=task,
            )
            _enqueue_delegation_persistence(job_queue, vault, error_report)
            return error_report.to_orchestrator_string()

        finally:
            # P4-01: always release leases on exit (success, error, or exception).
            if lease_manager is not None and targets:
                lease_manager.release(role, targets)

    return delegate_task


_PARALLEL_MAX_WORKERS = 3  # matches Hermes' "3 parallel sub-agents"
_PARALLEL_DEFAULT_TIMEOUT = 300  # seconds per sub-agent


def _make_delegate_parallel_tasks(
    parent_registry: ToolRegistry,
    gate: PermissionGate | None = None,
    on_event: Callable[..., None] | None = None,
    vault: Any = None,
    job_queue: Any = None,
    sub_agent_llm: Any = None,
    cost_tracker: Any = None,
    max_cost_usd: float = 0.0,
    max_tokens: int = 0,
    max_cost_per_turn: float = 0.0,
    max_tokens_per_turn: int = 0,
) -> Callable[..., str]:
    """Factory: creates the delegate_parallel_tasks tool handler.

    Each task in the list is dispatched to a separate sub-agent thread,
    up to :data:`_PARALLEL_MAX_WORKERS` concurrently.  All results are
    collected before returning.

    Args:
        parent_registry: The orchestrator's full ToolRegistry.
        gate:            The device permission gate.
        on_event:        Optional progress callback.
        vault:           Optional MemoryVault for delegation persistence.
        job_queue:       Optional job queue.
        sub_agent_llm:   Credential-resolved LLM client for sub-agents.
        cost_tracker:    Shared cost tracker (thread-safe).
        max_cost_usd:        S2 — parent session's per-session cost cap, inherited
                             by every spawned sub-agent (0 = unlimited).
        max_tokens:          S2 — parent session's per-session token cap.
        max_cost_per_turn:   S2 — parent session's per-turn cost cap.
        max_tokens_per_turn: S2 — parent session's per-turn token cap.

    Returns:
        A callable that accepts ``tasks`` and returns a JSON result string.
    """
    # Build a single-task dispatcher we can call from threads.
    _single = _make_delegate_task(
        parent_registry,
        gate,
        on_event,
        vault,
        job_queue,
        sub_agent_llm,
        cost_tracker,
        max_cost_usd=max_cost_usd,
        max_tokens=max_tokens,
        max_cost_per_turn=max_cost_per_turn,
        max_tokens_per_turn=max_tokens_per_turn,
    )

    def delegate_parallel_tasks(
        tasks: list[dict[str, str]],
        timeout_sec: int = _PARALLEL_DEFAULT_TIMEOUT,
    ) -> str:
        """Run up to 3 sub-agent tasks in parallel and return all results.

        Each item in ``tasks`` must have ``role`` and ``task`` keys and may have
        an optional ``context`` key.  Sub-agents run concurrently (max 3 at a
        time).  Slower tasks do not block faster ones from completing.

        Args:
            tasks: List of ``{"role": "...", "task": "...", "context": "..."}``
                   dicts — at most 10 items.
            timeout_sec: Per-task timeout in seconds (default 300).

        Returns:
            JSON string with ``results`` list (one entry per task), each with
            ``role``, ``task``, ``status`` ("ok" | "timeout" | "error"),
            ``output``, and ``index``.
        """
        if not tasks:
            return json.dumps({"results": [], "message": "No tasks provided."})

        items = tasks[:10]  # cap at 10 to avoid runaway spawning

        if on_event:
            on_event(
                "delegation_parallel_start",
                {"count": len(items), "roles": [t.get("role", "?") for t in items]},
            )

        results: list[dict[str, Any]] = [{}] * len(items)
        futures: list[Future[str]] = []

        with ThreadPoolExecutor(
            max_workers=min(_PARALLEL_MAX_WORKERS, len(items)),
            thread_name_prefix="hachi-subagent",
        ) as pool:
            for idx, task_spec in enumerate(items):
                role = str(task_spec.get("role", "researcher"))
                task = str(task_spec.get("task", ""))
                context = str(task_spec.get("context", ""))
                fut: Future[str] = pool.submit(_single, role, task, context)
                # Attach metadata to retrieve later
                fut._hachi_idx = idx  # type: ignore[attr-defined]
                fut._hachi_role = role  # type: ignore[attr-defined]
                fut._hachi_task = task  # type: ignore[attr-defined]
                futures.append(fut)

            done, timed_out = futures_wait(futures, timeout=timeout_sec)

        for fut in futures:
            idx = fut._hachi_idx  # type: ignore[attr-defined]
            role = fut._hachi_role  # type: ignore[attr-defined]
            task = fut._hachi_task  # type: ignore[attr-defined]
            if fut in done:
                exc = fut.exception()
                if exc is not None:
                    results[idx] = {
                        "index": idx,
                        "role": role,
                        "task": task[:100],
                        "status": "error",
                        "output": f"Sub-agent error: {exc}",
                    }
                else:
                    results[idx] = {
                        "index": idx,
                        "role": role,
                        "task": task[:100],
                        "status": "ok",
                        "output": fut.result(),
                    }
            else:
                # Timed out — cancel the future (best-effort)
                fut.cancel()
                results[idx] = {
                    "index": idx,
                    "role": role,
                    "task": task[:100],
                    "status": "timeout",
                    "output": (
                        f"Sub-agent did not complete within {timeout_sec}s. "
                        "Consider breaking the task into smaller steps."
                    ),
                }

        ok_count = sum(1 for r in results if r.get("status") == "ok")
        if on_event:
            on_event(
                "delegation_parallel_complete",
                {"total": len(items), "ok": ok_count},
            )

        return json.dumps(
            {
                "results": results,
                "summary": f"{ok_count}/{len(items)} tasks completed successfully.",
            },
            indent=2,
        )

    return delegate_parallel_tasks


DELEGATE_PARALLEL_TASKS_SCHEMA: dict[str, Any] = {
    "name": "delegate_parallel_tasks",
    "description": (
        "Dispatch up to 3 sub-agent tasks in parallel and wait for all results. "
        "Use this when you have multiple INDEPENDENT work items that do not depend on "
        "each other — e.g. researching 3 different APIs concurrently, running "
        "separate code audits in parallel, or generating multiple content drafts at once. "
        "Do NOT use for tasks that must run in sequence. "
        "Each task runs in full isolation with its own tool scope and context. "
        "Returns a JSON object with `results` (one per task) and a `summary`."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "description": "List of tasks to run in parallel (max 10).",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {
                            "type": "string",
                            "description": (
                                "Sub-agent role (e.g. 'researcher', 'coder'). "
                                "Use list_roles to see available roles."
                            ),
                        },
                        "task": {
                            "type": "string",
                            "description": "Self-contained task description for this sub-agent.",
                        },
                        "context": {
                            "type": "string",
                            "description": "Optional background context string.",
                        },
                    },
                    "required": ["role", "task"],
                },
                "maxItems": 10,
            },
            "timeout_sec": {
                "type": "integer",
                "description": (
                    "Maximum seconds to wait per sub-agent (default 300). "
                    "Timed-out tasks are marked with status='timeout'."
                ),
                "default": 300,
            },
        },
        "required": ["tasks"],
    },
}


def _enqueue_delegation_persistence(job_queue, vault, report: SubAgentReport) -> None:
    """Persist a delegation result through the job queue when available.

    When no queue is configured, the persistence work runs inline so tests and
    development workflows still retain delegation history.
    """
    if not vault:
        return

    if job_queue:
        job = Job(
            job_id="",
            name="persist_delegation",
            status=JobStatus.PENDING,
            func=_persist_delegation_result,
            args=(vault, report),
            job_type="persist",
        )

        try:
            job_queue.enqueue(job)
            return
        except Exception:
            logger.debug("Failed to enqueue delegation persistence job", exc_info=True)

    _persist_delegation_result(vault, report)


def _persist_delegation_result(vault, report: SubAgentReport) -> str:
    """Persist a delegation result to long-term memory.

    Two writes happen:
        1. delegation_log: The full delegation record (searchable by role, task, status)
        2. core_memory: Key workspace facts extracted from the sub-agent's summary
           (e.g., files created, commands run, configurations applied)

    This function is queue-friendly and returns the delegation log ID.

    Args:
        vault:  The MemoryVault instance (may be None if vault is not configured).
        report: The SubAgentReport to persist.
    """
    if not vault:
        return ""

    try:
        entry_id = vault.log_delegation(
            role=report.role,
            task=report.task,
            status=report.status.value,
            summary=report.summary,
            duration_seconds=report.duration_seconds,
            iterations=report.iterations,
            token_estimate=report.token_estimate,
        )

        if report.status == SubAgentStatus.SUCCESS and len(report.summary) > 30:
            vault.upsert_fact(
                f"[delegation:{report.role}] {report.summary[:500]}",
                category="delegation_result",
            )

        return entry_id
    except Exception:
        logger.debug("Failed to persist delegation result", exc_info=True)
        return ""


def _make_list_roles() -> Callable[..., str]:
    """Factory: creates the list_roles tool handler.

    Returns:
        A callable that returns a JSON list of available role names.
    """

    def list_roles() -> str:
        """List all available sub-agent roles.

        Returns:
            A JSON string with available role names and their source paths.
        """
        try:
            resolver = RoleResolver()
            roles = resolver.list_available_roles()
            if not roles:
                return json.dumps(
                    {
                        "roles": [],
                        "message": (
                            "No role .og files found. Create one at ~/.hachi/skills/roles/<name>.og"
                        ),
                    }
                )
            return json.dumps({"roles": roles})
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    return list_roles


# ==========================================
# Registration Helper
# ==========================================


def register_delegation_tools(
    registry: ToolRegistry,
    gate: PermissionGate | None = None,
    on_event: Callable[..., None] | None = None,
    vault=None,
    job_queue=None,
    sub_agent_llm=None,
    cost_tracker=None,
    skill_engine: Any = None,
    lease_manager: Any = None,
    max_cost_usd: float = 0.0,
    max_tokens: int = 0,
    max_cost_per_turn: float = 0.0,
    max_tokens_per_turn: int = 0,
) -> None:
    """Mount delegation tools onto the provided ToolRegistry.

    This must be called AFTER all other tools are registered, because
    delegate_task needs access to the full parent registry to build
    scoped copies for sub-agents.

    Args:
        registry:     The orchestrator's tool registry (will be the parent for sub-agents).
        gate:         The device PermissionGate instance.
        on_event:     Optional callback for delegation progress events.
        vault:        Optional MemoryVault for persisting delegation results.
        job_queue:    Optional job queue for delegation persistence.
        skill_engine: Optional SkillEngine passed from the orchestrator.  When
                      provided, sub-agent OG tools are rebound to a
                      ``skill_engine.with_role(role)`` view so each sub-agent
                      only sees skill nodes within its declared scope
                      (closes the scope=orchestrator information-leak).
        lease_manager: P4-01 optional LeaseManager for write-target leases.
        max_cost_usd:        S2 — the orchestrator session's configured per-session
                             cost cap (0 = unlimited).  Passed down to every
                             sub-agent's own ExecutionLoop so a delegated task can
                             never silently outspend the caps the user configured
                             for the parent session.
        max_tokens:          S2 — the orchestrator session's per-session token cap.
        max_cost_per_turn:   S2 — the orchestrator session's per-turn cost cap.
        max_tokens_per_turn: S2 — the orchestrator session's per-turn token cap.
    """
    registry.register(
        DELEGATE_TASK_SCHEMA,
        _make_delegate_task(
            registry,
            gate,
            on_event,
            vault,
            job_queue,
            sub_agent_llm,
            cost_tracker,
            skill_engine=skill_engine,
            lease_manager=lease_manager,
            max_cost_usd=max_cost_usd,
            max_tokens=max_tokens,
            max_cost_per_turn=max_cost_per_turn,
            max_tokens_per_turn=max_tokens_per_turn,
        ),
    )
    registry.register(
        DELEGATE_PARALLEL_TASKS_SCHEMA,
        _make_delegate_parallel_tasks(
            registry,
            gate,
            on_event,
            vault,
            job_queue,
            sub_agent_llm,
            cost_tracker,
            max_cost_usd=max_cost_usd,
            max_tokens=max_tokens,
            max_cost_per_turn=max_cost_per_turn,
            max_tokens_per_turn=max_tokens_per_turn,
        ),
    )
    registry.register(
        LIST_ROLES_SCHEMA,
        _make_list_roles(),
    )
