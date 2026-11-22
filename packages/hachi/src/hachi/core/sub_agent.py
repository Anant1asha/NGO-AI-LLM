"""
Sub-Agent Runtime — Isolated Execution Engine for Delegated Tasks

This module implements the core Sub-Agent Runtime for the Hachi Delegation
Architecture. It enables the Main Orchestrator to spawn fire-and-forget sub-agents
that execute complex tasks in total isolation, returning only a structured report.

Architecture:
    ┌─────────────────────────────────────────────────────────────┐
    │  SubAgentRuntime                                            │
    │  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐  │
    │  │  OGFile      │  │  PromptBuilder│  │  ExecutionLoop    │  │
    │  │  (role .og)  │→ │  (5 layers)  │→ │  (isolated ctx)   │  │
    │  └─────────────┘  └──────────────┘  └───────────────────┘  │
    │                                            │                │
    │                                     SubAgentReport          │
    └─────────────────────────────────────────────────────────────┘

Design Principles:
    P1 — Context Isolation:  Sub-agent history NEVER touches the orchestrator.
    P2 — .og Native:         Every sub-agent persona is defined by a .og file.
    P3 — Cost Aware:         Defaults to a cheaper model (Haiku) for sub-agents.
    P4 — Deterministic Exit: Strict iteration + wall-clock timeout guards.
    P5 — Structured Handoff: Returns SubAgentReport, not freeform LLM text.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hachi.core.llm import AnthropicClient, BaseLLMClient, Message
from hachi.core.loop import (
    INCOMPLETE_RESULT_PREFIX,
    AgentException,
    ExecutionLoop,
    ToolRegistry,
)
from hachi.core.paths import get_hachi_paths
from hachi.og_engine.parser import OGFile, parse_og_file

if TYPE_CHECKING:
    from hachi.core.conversation_memory import IterationState

logger = logging.getLogger(__name__)


# ==========================================
# Constants
# ==========================================

DEFAULT_SUB_AGENT_MODEL = "claude-haiku-4-5"
DEFAULT_MAX_ITERATIONS = 10
DEFAULT_TIMEOUT_SECONDS = 120.0
ROLES_DIRECTORY_NAME = "roles"


# ==========================================
# Data Models
# ==========================================


class SubAgentStatus(StrEnum):
    """Terminal status of a completed sub-agent execution.

    Values:
        SUCCESS:  Sub-agent completed the task normally.
        ERROR:    Sub-agent encountered an unrecoverable error during execution.
        TIMEOUT:  Sub-agent exceeded the wall-clock timeout or iteration limit.
    """

    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass(frozen=True, slots=True)
class SubAgentReport:
    """Immutable, structured result of a sub-agent execution.

    This is the ONLY data that flows back to the orchestrator. It keeps
    the orchestrator's context window pristine — no intermediate tool calls,
    no error logs, no retry noise.

    Attributes:
        status:           Terminal execution status (success/error/timeout).
        summary:          The sub-agent's final textual response or error message.
        role:             The role name that was used (maps to the .og file).
        task:             The original task description that was delegated.
        iterations:       Number of ReAct loop iterations consumed.
        duration_seconds: Wall-clock execution time in seconds.
        token_estimate:   Rough estimate of total tokens consumed.
        metadata:         Optional structured data extracted from the sub-agent's output.
        needs:            P4-01 continuation hint — if set, the sub-agent is requesting
                          a follow-up delegation: ``{"role": "analyst", "task": "..."}``.
                          The orchestrator decides whether to spawn it; it is never automatic.
    """

    status: SubAgentStatus
    summary: str
    role: str
    task: str
    iterations: int = 0
    duration_seconds: float = 0.0
    token_estimate: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    # P4-01: continuation request from the sub-agent (never auto-spawned).
    needs: dict[str, Any] | None = None

    def to_orchestrator_string(self) -> str:
        """Format the report as a concise string for injection into the orchestrator's context.

        This is what the orchestrator's LLM actually sees. It contains everything
        needed to understand the result without any of the intermediate noise.

        Returns:
            A compact, structured string (typically 50-200 tokens).
        """
        lines = [
            f"[Sub-Agent Report: {self.role}]",
            f"Status: {self.status.value}",
            f"Task: {self.task[:200]}",
            f"Result: {self.summary[:1000]}",
        ]
        if self.metadata:
            for key, value in self.metadata.items():
                lines.append(f"{key}: {value}")
        # P4-01: surface continuation request so the orchestrator can decide to spawn it.
        if self.needs:
            next_role = self.needs.get("role", "?")
            next_task = str(self.needs.get("task", ""))[:200]
            lines.append(f"[Continuation requested: role={next_role}, task={next_task}]")
            lines.append(
                "Note: The above continuation is a REQUEST, not automatic. "
                "Decide whether to delegate_task with those parameters."
            )
        lines.append(f"[Execution: {self.iterations} steps, {self.duration_seconds:.1f}s]")
        return "\n".join(lines)


# ==========================================
# Lightweight Memory for Sub-Agents
# ==========================================


class SubAgentMemory:
    """Minimal, zero-overhead memory manager for isolated sub-agent execution.

    Unlike the full MemoryManager (which handles compaction, skill-switching,
    task ledgers, and long-term memory syncing), this class is a thin wrapper
    around a message list. Sub-agents are short-lived and disposable — they
    don't need any of the sophisticated memory management features.

    Implements the ConversationMemory protocol consumed by ExecutionLoop:
        - history (property)
        - active_skill (property)
        - add_message(msg)
        - prepare_for_turn() -> IterationState
        - complete_task(user_query, result)
        - signal_skill_switch(name)

    Legacy attributes kept for backward compatibility:
        - get_context_header() -> str
        - apply_pending_compaction() -> bool
        - sync_turn(query, response)
        - complete_current_task(summary)
        - _last_user_query (attribute)
    """

    __slots__ = ("_history", "_last_user_query", "_active_skill")

    def __init__(self) -> None:
        self._history: list[Message] = []
        self._last_user_query: str = ""
        self._active_skill: str | None = None

    @property
    def history(self) -> list[Message]:
        """The raw conversation history sent to the LLM on every turn."""
        return self._history

    @property
    def active_skill(self) -> str | None:
        """Currently active skill name (always None for sub-agents)."""
        return self._active_skill

    def add_message(self, message: Message) -> None:
        """Append a message to the history. Captures user queries for reference."""
        if message.role == "user" and isinstance(message.content, str):
            self._last_user_query = message.content
        self._history.append(message)

    def get_context_header(self) -> str:
        """Sub-agents have no task ledger — always returns empty string."""
        return ""

    def apply_pending_compaction(self) -> bool:
        """Sub-agents never compact — always returns False."""
        return False

    def sync_turn(self, user_content: str, assistant_content: str) -> None:
        """Sub-agents do not sync facts to long-term memory. No-op."""
        pass

    def complete_current_task(self, result_summary: str) -> None:
        """Sub-agents do not maintain a task ledger. No-op."""
        pass

    def signal_skill_switch(self, new_skill_name: str) -> None:
        """Sub-agents do not switch skills. No-op."""
        self._active_skill = new_skill_name

    def prepare_for_turn(self) -> IterationState:
        """Sub-agents perform no housekeeping — return a zero-state snapshot."""
        from hachi.core.conversation_memory import IterationState

        return IterationState(
            compacted=False, old_skill="", tool_results_cleared=0, history_repaired=0
        )

    def complete_task(self, user_query: str, result: str) -> None:
        """Sub-agents do not maintain a task ledger or sync facts. No-op."""
        pass


# ==========================================
# System Prompt Builder
# ==========================================


class PromptBuilder:
    """Constructs a layered system prompt from an OGFile's rich tags.

    The prompt is assembled from 5 distinct layers, each sourced from specific
    ObjectGraph tags. This ensures the sub-agent receives a perfectly curated,
    minimal prompt — no bloat, no ambiguity.

    Layer Architecture:
        Layer 1 — Identity:     WHO the sub-agent is (from ::dense + ::full of persona nodes)
        Layer 2 — Warnings:     Critical constraints (from ::warning blocks — ALWAYS included)
        Layer 3 — Instructions: HOW to behave (from ::steps + ::assertion of rule nodes)
        Layer 4 — Index Map:    WHAT exists in the file (from ::index — compact routing table)
        Layer 5 — Task:         WHAT to do (from the delegate_task call — task + context)
    """

    @staticmethod
    def build(og_file: OGFile, task: str, context: str | None = None) -> str:
        """Assemble the complete system prompt from the .og file and task parameters.

        Args:
            og_file:  The parsed OGFile for the sub-agent's role.
            task:     The task description delegated by the orchestrator.
            context:  Optional context string (file paths, prior results, etc.).

        Returns:
            A complete system prompt string, typically 200-800 tokens.
        """
        sections: list[str] = []

        # Layer 1 — Identity
        identity = PromptBuilder._extract_identity(og_file)
        if identity:
            sections.append(identity)

        # Layer 2 — Warnings (always included, high priority)
        warnings = PromptBuilder._extract_warnings(og_file)
        if warnings:
            sections.append(warnings)

        # Layer 3 — Instructions & Constraints
        instructions = PromptBuilder._extract_instructions(og_file)
        if instructions:
            sections.append(instructions)

        # Layer 4 — Index Map (compact navigation table)
        index_map = og_file.get_index_prompt()
        if index_map:
            sections.append(f"--- Available Capabilities ---\n{index_map}")

        # Layer 5 — Task Assignment
        sections.append(PromptBuilder._build_task_section(task, context))

        return "\n\n".join(sections)

    @staticmethod
    def _extract_identity(og_file: OGFile) -> str:
        """Extract the sub-agent's identity from persona/identity nodes.

        Searches for nodes with role='persona', role='identity', or role='core_agent'.
        Uses ::dense for compressed identity, ::full for detailed instructions,
        and ::summary as a fallback.

        Returns:
            A formatted identity section, or empty string if no identity nodes exist.
        """
        identity_roles = {"persona", "identity", "core_agent"}
        parts: list[str] = []

        for node in og_file.nodes:
            if node.role not in identity_roles:
                continue

            if node.dense:
                parts.append(node.dense)
            if node.full:
                parts.append(node.full)
            elif node.summary:
                parts.append(node.summary)

        if not parts:
            # Fallback: use the file's meta title + first node's dense block
            if og_file.meta.title:
                parts.append(f"You are a specialized sub-agent: {og_file.meta.title}")
            if og_file.nodes and og_file.nodes[0].dense:
                parts.append(og_file.nodes[0].dense)

        return "\n".join(parts) if parts else ""

    @staticmethod
    def _extract_warnings(og_file: OGFile) -> str:
        """Extract all ::warning blocks from every node in the file.

        Warnings are ALWAYS included regardless of scope or priority.
        They represent hard constraints that the sub-agent must obey.

        Returns:
            A formatted warnings section, or empty string if none exist.
        """
        warnings: list[str] = []
        for node in og_file.nodes:
            if node.warning:
                warnings.append(f"⚠️ {node.warning}")

        if not warnings:
            return ""
        return "--- CRITICAL CONSTRAINTS ---\n" + "\n".join(warnings)

    @staticmethod
    def _extract_instructions(og_file: OGFile) -> str:
        """Extract structured instructions from rule/constraint nodes.

        Pulls ::steps blocks for ordered execution sequences and ::assertion
        blocks for validation conditions. Also includes ::code blocks that
        define expected command patterns.

        Returns:
            A formatted instructions section.
        """
        parts: list[str] = []
        rule_roles = {"rule", "constraint", "procedure"}

        for node in og_file.nodes:
            if node.role not in rule_roles:
                continue

            if node.steps:
                parts.append("Steps:")
                for i, step in enumerate(node.steps, 1):
                    parts.append(f"  {i}. {step}")

            if node.assertions:
                parts.append("Validation:")
                for assertion in node.assertions:
                    parts.append(f"  ✓ {assertion}")

            # Include code examples as reference patterns
            for lang, code in node.code_blocks.items():
                parts.append(f"Reference [{lang}]:\n{code}")

        return "\n".join(parts) if parts else ""

    @staticmethod
    def _build_task_section(task: str, context: str | None = None) -> str:
        """Build the task assignment section from the delegate_task parameters.

        This is always the final section of the prompt, ensuring the sub-agent
        reads it last and gives it the highest attention weight.

        Args:
            task:    The task description.
            context: Optional additional context.

        Returns:
            A formatted task section.
        """
        parts = [
            "--- YOUR ASSIGNED TASK ---",
            task,
        ]

        if context and context.strip():
            parts.append(f"\n--- CONTEXT ---\n{context}")

        parts.append(
            "\n--- OUTPUT REQUIREMENTS ---\n"
            "When finished, provide a SINGLE concise summary of:\n"
            "- What you accomplished\n"
            "- Any files created or modified (full paths)\n"
            "- Any issues encountered\n"
            "Do NOT repeat yourself. Do NOT run verification commands after successful operations."
        )

        return "\n".join(parts)


# ==========================================
# Role File Resolver
# ==========================================


class RoleResolver:
    """Resolves a role name to its corresponding .og file path.

    Search Order:
        1. ~/.hachi/skills/roles/<role>.og        (user-defined roles)
        2. ~/.hachi/skills/roles/<role>/<role>.og  (directory-based roles)
        3. Built-in default_skills/roles/<role>.og     (shipped with Hachi)

    This separation allows users to override built-in roles by placing a
    custom .og file in their local roles directory.
    """

    def __init__(self, workspace_dir: Path | None = None) -> None:
        """Initialize the role resolver.

        Args:
            workspace_dir: Path to the workspace data dir. If None, resolved via platformdirs.
        """
        _using_default = workspace_dir is None
        self._workspace_dir = workspace_dir or get_hachi_paths().data_dir
        self._roles_dir = self._workspace_dir / "skills" / ROLES_DIRECTORY_NAME
        # Legacy shim: if caller didn't override, also check ~/.hachi/skills/roles/
        self._legacy_roles_dir: Path | None = (
            Path.home() / ".hachi" / "skills" / ROLES_DIRECTORY_NAME if _using_default else None
        )
        self._builtin_dir = Path(__file__).parent.parent / "default_skills" / ROLES_DIRECTORY_NAME

    def resolve(self, role: str) -> Path:
        """Resolve a role name to its absolute .og file path.

        Args:
            role: The role name (e.g., 'coder', 'researcher', 'emailer').

        Returns:
            The absolute Path to the role's .og file.

        Raises:
            FileNotFoundError: If no .og file exists for the given role.
        """
        candidates = [
            self._roles_dir / f"{role}.og",
            self._roles_dir / role / f"{role}.og",
        ]
        if self._legacy_roles_dir is not None:
            candidates += [
                self._legacy_roles_dir / f"{role}.og",
                self._legacy_roles_dir / role / f"{role}.og",
            ]
        candidates += [
            self._builtin_dir / f"{role}.og",
            self._builtin_dir / role / f"{role}.og",
        ]

        for path in candidates:
            if path.exists():
                logger.debug("Resolved role '%s' → %s", role, path)
                return path

        searched = "\n  ".join(str(p) for p in candidates)
        raise FileNotFoundError(
            f"No .og file found for role '{role}'. Searched:\n  {searched}\n"
            f"Create one at: {self._roles_dir / f'{role}.og'}"
        )

    def list_available_roles(self) -> list[str]:
        """List all available role names from both user and built-in directories.

        Returns:
            A sorted, deduplicated list of role names.
        """
        roles: set[str] = set()

        dirs_to_check: list[Path] = [self._roles_dir]
        if self._legacy_roles_dir is not None:
            dirs_to_check.append(self._legacy_roles_dir)
        dirs_to_check.append(self._builtin_dir)

        for directory in dirs_to_check:
            if not directory.exists():
                continue
            for og_file in directory.glob("**/*.og"):
                roles.add(og_file.stem)

        return sorted(roles)


# ==========================================
# Sub-Agent Runtime
# ==========================================


class SubAgentRuntime:
    """Isolated execution environment for a delegated sub-agent.

    Creates a completely independent agent with its own context window,
    tools, and system prompt — all derived from a role .og file. The
    orchestrator's context is never touched.

    Lifecycle:
        1. __init__:  Configure the runtime (role, task, tools, model)
        2. run():     Execute the sub-agent loop → SubAgentReport

    Usage:
        runtime = SubAgentRuntime(
            role="coder",
            task="Build a REST API with FastAPI",
            context="Use Python 3.12, output to /tmp/api/",
            tool_registry=scoped_registry,
        )
        report = runtime.run()
        print(report.to_orchestrator_string())

    Thread Safety:
        Each SubAgentRuntime instance is independent and can be executed
        in a thread. However, tool implementations must be thread-safe
        if parallel execution is desired.
    """

    def __init__(
        self,
        role: str,
        task: str,
        context: str | None = None,
        tool_registry: ToolRegistry | None = None,
        llm_client: BaseLLMClient | None = None,
        model: str | None = None,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        workspace_dir: Path | None = None,
        on_event: Callable[..., None] | None = None,
        cost_tracker: Any = None,
        max_cost_usd: float = 0.0,
        max_tokens: int = 0,
        max_cost_per_turn: float = 0.0,
        max_tokens_per_turn: int = 0,
    ) -> None:
        """Initialize the sub-agent runtime.

        Args:
            role:             Role name mapping to a .og file (e.g., 'coder').
            task:             The task description to execute.
            context:          Optional context string for the sub-agent.
            tool_registry:    Pre-built ToolRegistry with scoped tools. If None,
                              the sub-agent runs with NO tools (pure reasoning).
            llm_client:       Pre-configured LLM client. Used as the default when
                              ``model`` is not explicitly provided.  When ``model``
                              is provided, a fresh client is built with that model
                              even if ``llm_client`` is non-None (HIGH-013).
            model:            Optional model identifier override.  When provided,
                              always takes precedence over the injected client so
                              the caller can select a specific model for a
                              delegation without changing the session-level client.
                              When None, ``llm_client`` is used if given, otherwise
                              the DEFAULT_SUB_AGENT_MODEL is used.
            max_iterations:   Maximum ReAct loop iterations before forced termination.
            timeout_seconds:  Wall-clock timeout in seconds.
            workspace_dir:    Path to ~/.hachi/ (auto-resolved if None).
            on_event:         Optional callback for execution progress events.
            max_cost_usd:         S2: per-session cost cap passed straight through to the
                                  sub-agent's own ExecutionLoop.  Callers (delegate_task)
                                  should default this to the PARENT session's configured
                                  cap so a sub-agent can never silently outspend its
                                  parent — 0 (unlimited) only when the caller has no cap
                                  to inherit or explicitly wants an uncapped sub-agent.
            max_tokens:           Same as max_cost_usd but for the token budget.
            max_cost_per_turn:    Per-turn cost cap forwarded to the sub-agent's loop.
            max_tokens_per_turn:  Per-turn token cap forwarded to the sub-agent's loop.

        Raises:
            FileNotFoundError: If the role .og file does not exist.
        """
        self._role = role
        self._task = task
        self._context = context
        self._max_iterations = max_iterations
        self._timeout_seconds = timeout_seconds
        self._max_cost_usd = max_cost_usd
        self._max_tokens = max_tokens
        self._max_cost_per_turn = max_cost_per_turn
        self._max_tokens_per_turn = max_tokens_per_turn
        self._on_event = on_event or (lambda *a, **kw: None)
        self._cost_tracker = cost_tracker

        # Resolve the role .og file
        resolver = RoleResolver(workspace_dir)
        role_path = resolver.resolve(role)
        self._og_file = parse_og_file(str(role_path))

        # HIGH-013: configure LLM client.
        # • model explicitly provided → always build a fresh client with that model
        #   (the injected llm_client is only used for credentials/config if needed
        #   by the concrete client implementation — here we just call _create_client
        #   so the factory picks up env-var credentials automatically).
        # • no model, llm_client provided → use the injected client (preserves the
        #   credential-resolved session client for delegation, which is the common
        #   case and the previous behaviour).
        # • neither → build a fresh DEFAULT_SUB_AGENT_MODEL client.
        if model is not None:
            # D2 fix: pass session client so provider kind is preserved.
            self._llm_client = self._create_client(model, session_client=llm_client)
            logger.info(
                "SubAgentRuntime: explicit model override for role=%s → model=%s",
                role,
                model,
            )
        elif llm_client is not None:
            self._llm_client = llm_client
        else:
            self._llm_client = self._create_client(DEFAULT_SUB_AGENT_MODEL)

        # Configure tool registry (empty if not provided)
        self._tool_registry = tool_registry or ToolRegistry()

        # Build the system prompt from .og layers
        self._system_prompt = PromptBuilder.build(self._og_file, self._task, self._context)

        logger.info(
            "SubAgentRuntime initialized: role=%s, model=%s, max_iter=%d, timeout=%.0fs",
            self._role,
            getattr(self._llm_client, "model", "unknown"),
            self._max_iterations,
            self._timeout_seconds,
        )

    @staticmethod
    def _create_client(
        model: str,
        session_client: BaseLLMClient | None = None,
    ) -> BaseLLMClient:
        """Create a lightweight LLM client for the sub-agent.

        D2 fix: respects the session provider instead of always building an
        AnthropicClient.  When *session_client* is provided its provider kind
        is reused so OpenAI/Groq/etc. delegations build the correct client type.

        Args:
            model: The model identifier.
            session_client: The parent session's LLM client.  Used to detect
                the provider kind so the sub-agent stays on the same provider.

        Returns:
            A configured :class:`~hachi.core.llm.BaseLLMClient` instance.
        """
        from hachi.core.llm import OpenAICompatibleClient, create_llm_client

        # Detect provider kind from the injected session client.
        if session_client is not None and isinstance(session_client, OpenAICompatibleClient):
            # OpenAI-compatible session: build a matching client.
            provider_config: dict[str, Any] = {
                "kind": "openai-compatible",
                "model": model,
                "base_url": session_client.base_url,
                "api_key_env": None,
            }
            # Pass the already-resolved API key directly so we don't need env vars.
            if session_client.api_key:
                provider_config["api_key_env"] = None
                # create_llm_client accepts explicit api_key via api_key_ref path only;
                # easier to build directly for the compat case.
                return OpenAICompatibleClient(
                    base_url=session_client.base_url,
                    model=model,
                    api_key=session_client.api_key,
                    max_tokens=4096,
                )
            return create_llm_client(provider_config, max_tokens=4096)

        # Default: Anthropic (preserves back-compat for Anthropic sessions and when
        # session_client is None or an AnthropicClient).
        return AnthropicClient(model=model, max_tokens=4096)

    def run(self) -> SubAgentReport:
        """Execute the sub-agent and return a structured report.

        This is the main entry point. It:
            1. Creates an isolated ExecutionLoop with fresh memory
            2. Injects the task as the initial user message
            3. Runs the loop with timeout and iteration guards
            4. Captures the result (or error) into a SubAgentReport

        Returns:
            An immutable SubAgentReport containing the execution result.
            The status field indicates success, error, or timeout.
        """
        start_time = time.monotonic()

        # Create isolated memory (no compaction, no vault, no ledger)
        memory = SubAgentMemory()

        # Create the execution loop.
        # S2: thread the (parent-inherited, by default) cost/token caps down so the
        # sub-agent's OWN loop can stop itself early instead of always running
        # unchecked to max_iterations — the shared cost_tracker alone only records
        # spend, it doesn't stop this loop from spending it.
        loop = ExecutionLoop(
            llm_client=self._llm_client,
            registry=self._tool_registry,
            memory=memory,
            base_system_prompt=self._system_prompt,
            on_event=self._on_event,
            cost_tracker=self._cost_tracker,
            max_cost_usd=self._max_cost_usd,
            max_tokens=self._max_tokens,
            max_cost_per_turn=self._max_cost_per_turn,
            max_tokens_per_turn=self._max_tokens_per_turn,
        )

        # Inject the task as the initial user message
        loop.add_user_message(self._task)

        # Execute with guards
        try:
            result = self._execute_with_timeout(loop, start_time)
            elapsed = time.monotonic() - start_time
            token_estimate = self._estimate_tokens_from_memory(memory)

            # S2: ExecutionLoop.run() never raises AgentException when max_iterations
            # is exhausted (P1-04 made it a graceful [INCOMPLETE] string return, not
            # a raised exception) — so the `except AgentException` branch below is
            # unreachable for this case. Detect the prefix directly so an
            # incomplete/cut-off sub-agent is never reported as SUCCESS.
            if result.startswith(INCOMPLETE_RESULT_PREFIX):
                logger.warning(
                    "Sub-agent '%s' hit iteration limit after %.1fs (%d iterations)",
                    self._role,
                    elapsed,
                    self._max_iterations,
                )
                return SubAgentReport(
                    status=SubAgentStatus.TIMEOUT,
                    summary=result,
                    role=self._role,
                    task=self._task,
                    iterations=self._count_iterations(memory),
                    duration_seconds=round(elapsed, 2),
                    token_estimate=token_estimate,
                )

            logger.info(
                "Sub-agent '%s' completed: %.1fs, ~%d tokens",
                self._role,
                elapsed,
                token_estimate,
            )

            return SubAgentReport(
                status=SubAgentStatus.SUCCESS,
                summary=result,
                role=self._role,
                task=self._task,
                iterations=self._count_iterations(memory),
                duration_seconds=round(elapsed, 2),
                token_estimate=token_estimate,
            )

        except AgentException as exc:
            elapsed = time.monotonic() - start_time
            logger.warning(
                "Sub-agent '%s' hit iteration limit after %.1fs: %s",
                self._role,
                elapsed,
                exc,
            )
            return SubAgentReport(
                status=SubAgentStatus.TIMEOUT,
                summary=f"Sub-agent exceeded iteration limit: {exc}",
                role=self._role,
                task=self._task,
                iterations=self._max_iterations,
                duration_seconds=round(elapsed, 2),
                token_estimate=self._estimate_tokens_from_memory(memory),
            )

        except TimeoutError:
            elapsed = time.monotonic() - start_time
            logger.warning(
                "Sub-agent '%s' timed out after %.1fs",
                self._role,
                elapsed,
            )
            return SubAgentReport(
                status=SubAgentStatus.TIMEOUT,
                summary=f"Sub-agent timed out after {self._timeout_seconds:.0f} seconds.",
                role=self._role,
                task=self._task,
                duration_seconds=round(elapsed, 2),
                token_estimate=self._estimate_tokens_from_memory(memory),
            )

        except Exception as exc:
            elapsed = time.monotonic() - start_time
            logger.error(
                "Sub-agent '%s' failed after %.1fs: %s",
                self._role,
                elapsed,
                exc,
                exc_info=True,
            )
            return SubAgentReport(
                status=SubAgentStatus.ERROR,
                summary=f"Sub-agent execution failed: {exc}",
                role=self._role,
                task=self._task,
                duration_seconds=round(elapsed, 2),
                token_estimate=self._estimate_tokens_from_memory(memory),
            )

    def _execute_with_timeout(self, loop: ExecutionLoop, start_time: float) -> str:
        """Run the execution loop with a wall-clock timeout check.

        The timeout is checked between iterations by the ExecutionLoop's
        natural pausing points. This avoids threading complexity while still
        providing a hard ceiling on sub-agent runtime.

        Args:
            loop:       The configured ExecutionLoop instance.
            start_time: The monotonic timestamp when execution began.

        Returns:
            The final textual response from the sub-agent.

        Raises:
            TimeoutError: If wall-clock time exceeds timeout_seconds.
            AgentException: If the iteration limit is exceeded.
        """
        # Wrap the on_event callback to inject timeout checks
        original_event = self._on_event

        def _timeout_aware_event(*args: Any, **kwargs: Any) -> None:
            elapsed = time.monotonic() - start_time
            if elapsed > self._timeout_seconds:
                raise TimeoutError(
                    f"Sub-agent '{self._role}' exceeded timeout: "
                    f"{elapsed:.1f}s > {self._timeout_seconds:.0f}s"
                )
            original_event(*args, **kwargs)

        loop.on_event = _timeout_aware_event

        return loop.run(max_iterations=self._max_iterations)

    @staticmethod
    def _count_iterations(memory: SubAgentMemory) -> int:
        """Count the number of ReAct iterations from the message history.

        Each iteration corresponds to one assistant message in the history.

        Args:
            memory: The sub-agent's memory manager.

        Returns:
            The number of assistant turns (iterations).
        """
        return sum(1 for msg in memory.history if msg.role == "assistant")

    @staticmethod
    def _estimate_tokens_from_memory(memory: SubAgentMemory) -> int:
        """Estimate total token consumption from the message history.

        Uses the standard ~4 characters per token heuristic.

        Args:
            memory: The sub-agent's memory manager.

        Returns:
            Estimated token count.
        """
        total_chars = 0
        for msg in memory.history:
            if isinstance(msg.content, str):
                total_chars += len(msg.content)
            elif isinstance(msg.content, list):
                for block in msg.content:
                    if isinstance(block, dict):
                        total_chars += len(str(block))
        return total_chars // 4
