"""
Gateway Orchestrator

Binds the LLM client, workspace, skill engine, memory manager, integration runtime,
MCP servers, and all tools into a cohesive agent session.

Phase 2 memory architecture:
    - Session Snapshot: User profile + workspace facts refreshed per turn.
    - Async Prefetch: Background recall starts during the previous turn.
    - Auto-Sync: Facts extracted after every completed turn (via loop.py hook).

Phase 1 Update (Runtime Correctness):
    - Immutable TurnContext per turn (no mutation of shared loop state)
    - Durable job queue for background work (replaces daemon threads)
"""

import importlib.util
import logging
import os
import threading
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hachi.core.approvals import (
    ActionApprover,
    HandlerApprover,
    PolicyApprover,
    RegistryApprover,
    get_approval_registry,
)
from hachi.core.checkpoints import CheckpointManager
from hachi.core.cost import CostTracker, clamp_nonnegative_cost_delta, today_utc_str
from hachi.core.credential_vault import CredentialVault
from hachi.core.integrations import IntegrationRuntime
from hachi.core.llm import Message, create_llm_client
from hachi.core.loop import ExecutionLoop, ToolRegistry
from hachi.core.mcp_client import MCPManager, MCPServerConfig
from hachi.core.memory import MemoryManager
from hachi.core.memory_provider import ChromaMemoryProvider, resolve_provider
from hachi.core.memory_vault import MemoryVault
from hachi.core.obs.trace import TraceContext
from hachi.core.obs.trace import bind as _bind_trace_ctx
from hachi.core.paths import get_hachi_paths
from hachi.core.permissions import (
    InteractivePermissionGate,
    PermissionDecision,
    PermissionGate,
    PermissionRequest,
)
from hachi.core.prompt_composer import build_stable_base
from hachi.core.rest_adapter import UniversalRestAdapter
from hachi.core.runtime_events import (
    BOOT_COMPLETE,
    BOOT_PROGRESS,
    BUDGET_EXCEEDED,
    MCP_SERVER_FAILED,
    MCP_SERVER_READY,
    MCP_SERVER_STARTING,
    MCP_SHUTDOWN,
    SESSION_BUSY,
    SESSION_CHAT_COMPLETED,
    SESSION_CHAT_STARTED,
    SESSION_PERSISTED,
    SESSION_RESUMED,
    SESSION_SHUTDOWN,
    RuntimeEvent,
    adapt_event,
    now_iso,
)
from hachi.core.runtime_read_models import (
    JobFailureSnapshot,
    JobSnapshot,
    MCPInventorySnapshot,
    MCPServerSnapshot,
    MemoryRecallSnapshot,
    PermissionAuditSnapshot,
    RuntimeEventSnapshot,
    RuntimeReadModelStore,
    SessionStateSnapshot,
    SkillSnapshot,
    SubAgentReportSnapshot,
    TaskLedgerItemSnapshot,
    ToolCallSnapshot,
)
from hachi.core.secret_store import create_default_secret_store
from hachi.core.session_store import SessionStore
from hachi.core.session_titler import generate_title
from hachi.core.sub_agent import DEFAULT_SUB_AGENT_MODEL
from hachi.core.tracing import configure_from_env, span
from hachi.core.turn_context import TurnContext
from hachi.gateway.tool_registration import BootDeps, ToolRegistrar, ToolSpec
from hachi.gateway.workspace import (
    get_skills_dir,
    get_workspace_dir,
    install_optional_skill_pack,
    load_brain,
    load_config,
)
from hachi.jobs import (
    Job,
    JobQueue,
    JobRegistry,
    JobStatus,
    JobWorker,
    ResidentWorkerThread,
    SQLiteJobQueue,
)
from hachi.jobs.scheduler import (
    Schedule,
    Scheduler,
    ScheduleRunner,
    ScheduleStore,
    deliver_result,
)
from hachi.og_engine.engine import SkillEngine
from hachi.tools.browser_tools import register_browser_tools
from hachi.tools.config_tools import register_config_tools
from hachi.tools.delegation_tools import register_delegation_tools
from hachi.tools.file_tools import register_file_tools
from hachi.tools.google_tools import GOOGLE_TOOL_NAMES, register_google_tools
from hachi.tools.memory_tools import register_memory_tools, register_session_tools
from hachi.tools.messaging_tools import register_messaging_tools
from hachi.tools.notification_tools import register_notification_tools
from hachi.tools.og_tools import USE_TOOLS_SCHEMA, _make_use_tools, register_og_tools
from hachi.tools.os_tools import register_os_tools
from hachi.tools.presentation_tools import register_presentation_tools
from hachi.tools.sandbox_tools import register_sandbox_tools
from hachi.tools.schedule_tools import register_schedule_tools
from hachi.tools.search_tools import register_search_tools
from hachi.tools.vision_tools import register_vision_tools
from hachi.tools.voice_tools import register_voice_tools
from hachi.tools.workflow_tools import register_workflow_tools

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CapabilityDescriptor:
    id: str
    kind: str
    enabled: bool
    configured: bool
    available: bool
    requires_scopes: tuple[str, ...]
    setup_hint: str
    factory: Callable[[], Any] | None = None


class CapabilityRegistry:
    """Capability state and lazy runtime instantiation for optional components."""

    def __init__(self, descriptors: Iterable[CapabilityDescriptor]):
        self._descriptors: dict[str, CapabilityDescriptor] = {item.id: item for item in descriptors}
        self._instances: dict[str, Any] = {}

    def iter_enabled(self) -> tuple[CapabilityDescriptor, ...]:
        return tuple(item for item in self._descriptors.values() if item.enabled)

    def get(self, capability_id: str) -> CapabilityDescriptor | None:
        return self._descriptors.get(capability_id)

    def status_snapshot(self) -> dict[str, dict[str, Any]]:
        return {
            item.id: {
                "kind": item.kind,
                "enabled": item.enabled,
                "configured": item.configured,
                "available": item.available,
                "requires_scopes": list(item.requires_scopes),
                "setup_hint": item.setup_hint,
            }
            for item in self._descriptors.values()
        }

    def instantiate(self, capability_id: str) -> Any:
        if capability_id in self._instances:
            return self._instances[capability_id]

        descriptor = self._descriptors.get(capability_id)
        if not descriptor:
            raise KeyError(f"Unknown capability: {capability_id}")
        if not descriptor.enabled:
            raise RuntimeError(f"Capability '{capability_id}' is disabled")
        if not descriptor.available:
            raise RuntimeError(f"Capability '{capability_id}' is not available on this system")
        if not descriptor.configured:
            raise RuntimeError(f"Capability '{capability_id}' is not configured")
        if descriptor.factory is None:
            raise RuntimeError(f"Capability '{capability_id}' has no runtime factory")

        instance = descriptor.factory()
        self._instances[capability_id] = instance
        return instance


def _is_module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


# --- Lazy tool-loading taxonomy ------------------------------------------
# Curated "core" tools sent to the model on every turn. Everything else is
# lazily unlocked via use_tools(group) / load_skill (see ToolRegistry.classify).
_CORE_TOOL_NAMES: frozenset[str] = frozenset(
    {
        # filesystem / shell
        "read_file",
        "write_file",
        "run_terminal_command",
        "rollback_changes",
        # ObjectGraph skills (3-pass) + the lazy-loading meta-tool. The skill-routing
        # contract in brain.og requires skill_dependencies / check_skill_assertions to
        # be present right after load_skill, so they stay core. The rarer authoring
        # tools (save_skill, skill_changelog) are lazy under the "authoring" group.
        "search_skills",
        "list_skills",
        "peek_skill",
        "load_skill",
        "skill_dependencies",
        "check_skill_assertions",
        "use_tools",
        # long-term memory / sessions
        "core_save_memory",
        "core_search_memory",
        "core_delete_memory",
        "core_save_user_profile",
        "core_search_user_profile",
        "core_delete_user_profile",
        "core_search_sessions",
        # delegation: delegate_task / list_roles are lazy under the "delegation" group.
        # web (the common case; richer browser actions are gated under "browser")
        "browse_web",
        # BB-33: search tools are always-on when a provider is configured;
        # they're only registered when Tavily (or another SearchProvider) is
        # present, so they cannot appear without a key — but classify() must
        # not reclassify them to "integrations" (which is never activated).
        "web_search",
        "extract_url",
    }
)

# Non-core, statically-known tools → their on-demand group. Per-skill REST tools
# are tagged at registration (group == skill name) and are not listed here.
_GROUP_BY_TOOL_NAME: dict[str, str] = {
    # Flagship-but-occasional tools trimmed out of always-on core to cut the per-turn
    # tool-schema footprint (~1.3K tokens). Discoverable via the system prompt's
    # "OPTIONAL TOOL GROUPS" list; the model unlocks them with use_tools(group=...).
    "delegate_task": "delegation",
    "list_roles": "delegation",
    "save_skill": "authoring",
    "skill_changelog": "authoring",
    "browser_act": "browser",
    "browser_screenshot": "browser",
    "python_sandbox": "sandbox",
    "create_schedule": "schedule",
    "schedule_task": "schedule",
    "list_schedules": "schedule",
    "delete_schedule": "schedule",
    "cancel_schedule": "schedule",
    "core_suspend_workflow": "workflow",
    "send_slack_message": "messaging",
    "send_discord_message": "messaging",
    "send_whatsapp_message": "messaging",
    "send_telegram_message": "messaging",
    "notify_user": "notifications",
    "send_email_digest": "notifications",
    "buffer_notification": "notifications",
    "flush_notification_digest": "notifications",
    "view_image": "vision",
    "transcribe_audio": "voice",
    "transcribe_and_summarize": "voice",
    "speak_text": "voice",
    "play_audio": "voice",
    "get_audio_info": "voice",
    **{name: "google" for name in GOOGLE_TOOL_NAMES},
}


def _coerce_float(*candidates: Any) -> float:
    """Return the first parseable float among candidates (config, then env), else 0.0."""
    for value in candidates:
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _coerce_int(*candidates: Any) -> int:
    """Return the first parseable int among candidates (config, then env), else 0."""
    for value in candidates:
        if value in (None, ""):
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return 0


def _build_capability_registry(config: dict[str, Any]) -> CapabilityRegistry:
    caps_cfg = config.get("capabilities", {})

    def cap_flags(cap_id: str) -> tuple[bool, bool]:
        payload = caps_cfg.get(cap_id, {}) if isinstance(caps_cfg, dict) else {}
        if not isinstance(payload, dict):
            return False, False
        enabled = bool(payload.get("enabled", False))
        # BB-11: if the config flag is off but the user already connected via the web UI
        # (token stored under "oauth2.<cap_id>"), treat the capability as enabled so
        # tools are registered without requiring a manual config edit or re-auth.
        if not enabled:
            try:
                from hachi.integrations.oauth_flow import OAuthTokenStore

                enabled = OAuthTokenStore().is_connected(cap_id)
            except Exception:
                pass
        return enabled, bool(payload.get("configured", False))

    google_enabled, google_configured = cap_flags("google")
    slack_enabled, slack_configured = cap_flags("slack")
    notion_enabled, notion_configured = cap_flags("notion")

    return CapabilityRegistry(
        [
            CapabilityDescriptor(
                id="google",
                kind="native_integration",
                enabled=google_enabled,
                configured=google_configured,
                available=_is_module_available("hachi.integrations.google"),
                requires_scopes=(
                    "openid",
                    "gmail.readonly",
                    "calendar.readonly",
                    "drive.readonly",
                ),
                setup_hint="Run `hachi setup --tier enhanced` then connect Google in setup or "
                "settings.",
                factory=lambda: __import__(
                    "hachi.integrations.google", fromlist=["GoogleIntegrationHub"]
                ).GoogleIntegrationHub(),
            ),
            CapabilityDescriptor(
                id="slack",
                kind="native_integration",
                enabled=slack_enabled,
                configured=slack_configured,
                available=_is_module_available("hachi.integrations.slack"),
                requires_scopes=("channels:history", "chat:write", "users:read"),
                setup_hint="Run `hachi setup --tier enhanced` then connect Slack in setup or "
                "settings.",
                factory=lambda: (
                    __import__(
                        "hachi.integrations.slack", fromlist=["SlackChat", "SlackWorkspace"]
                    ).SlackChat(),
                    __import__(
                        "hachi.integrations.slack", fromlist=["SlackChat", "SlackWorkspace"]
                    ).SlackWorkspace(),
                ),
            ),
            CapabilityDescriptor(
                id="notion",
                kind="native_integration",
                enabled=notion_enabled,
                configured=notion_configured,
                available=_is_module_available("hachi.integrations.notion"),
                requires_scopes=("read:content", "write:content"),
                setup_hint="Run `hachi setup --tier enhanced` then connect Notion in setup or "
                "settings.",
                factory=lambda: (
                    __import__(
                        "hachi.integrations.notion", fromlist=["NotionPages", "NotionDatabases"]
                    ).NotionPages(),
                    __import__(
                        "hachi.integrations.notion", fromlist=["NotionPages", "NotionDatabases"]
                    ).NotionDatabases(),
                ),
            ),
        ]
    )


def _register_search_tools_for(
    provider: Any,
    tool_registry: ToolRegistry,
    gate: Any,
    config: dict[str, Any] | None = None,
) -> None:
    """Register ``web_search`` and ``extract_url`` for *provider* onto *tool_registry*.

    Idempotent: if ``web_search`` is already registered the handlers are updated
    in-place (via :meth:`~hachi.core.loop.ToolRegistry.update_handler`) so schemas
    are never duplicated.  This is safe to call on a live reload path.

    Args:
        provider:      A :class:`~hachi.core.providers.search.SearchProvider`.
        tool_registry: The session's :class:`~hachi.core.loop.ToolRegistry`.
        gate:          The session's permission gate (passed to register_search_tools).
        config:        Optional raw config dict for ``[search]`` settings.
    """
    from hachi.core.rate_limit import OutboundRateLimiter
    from hachi.core.search_cache import SearchCache
    from hachi.core.settings import SearchSettings

    _search_settings = SearchSettings()
    try:
        _raw_cfg = config
        if _raw_cfg is None:
            import hachi.core.settings as _settings_mod  # noqa: PLC0415

            _raw_cfg = getattr(_settings_mod, "_current_config", None)
        if _raw_cfg is not None and hasattr(_raw_cfg, "search"):
            _s = _raw_cfg.search
            if _s is not None:
                _search_settings = _s
    except Exception:
        pass

    cache = SearchCache(ttl_seconds=_search_settings.cache_ttl_seconds)
    limiter = OutboundRateLimiter(
        max_per_window=_search_settings.window_max_calls,
        window_seconds=_search_settings.window_seconds,
        max_per_turn=_search_settings.max_calls_per_turn,
    )

    already = "web_search" in tool_registry._tools
    if already:
        # Rebuild handlers bound to the new provider without duplicating schemas.
        from hachi.tools.search_tools import _make_extract_url, _make_web_search

        tool_registry.update_handler("web_search", _make_web_search(provider, cache, limiter))
        tool_registry.update_handler("extract_url", _make_extract_url(provider, cache, limiter))
        logger.info(
            "search: updated web_search + extract_url handlers via provider=%r", provider.name
        )
    else:
        register_search_tools(tool_registry, provider, cache=cache, limiter=limiter, gate=gate)
        logger.info("search: registered web_search + extract_url via provider=%r", provider.name)


def _register_search_if_available(deps: Any) -> None:
    """Register search tools when a SearchProvider is present in the ProviderRegistry.

    Resolves the provider, builds a cache and rate limiter from ``[search]``
    config, then delegates to :func:`_register_search_tools_for`.
    When no provider is configured this is a silent no-op (graceful degradation).

    Args:
        deps: :class:`~hachi.gateway.tool_registration.BootDeps` bundle.
    """
    registry = deps.provider_registry
    if registry is None:
        logger.warning(
            "search: web_search is UNAVAILABLE (no ProviderRegistry at boot). "
            "browse_web/Playwright is the active fallback. "
            "To enable Tavily: set TAVILY_API_KEY env var or configure "
            '[search] provider = "tavily" in settings.toml, then restart.'
        )
        return

    provider = registry.get_search()
    if provider is None:
        logger.warning(
            "search: web_search is UNAVAILABLE (no SearchProvider registered). "
            "browse_web/Playwright is the active fallback. "
            "To enable Tavily: set TAVILY_API_KEY env var or configure "
            '[search] provider = "tavily" in settings.toml, then restart.'
        )
        return

    _register_search_tools_for(provider, deps.tool_registry, deps.gate)


def _register_capability_setup_stub(
    tool_registry: ToolRegistry, descriptor: CapabilityDescriptor
) -> None:
    schema = {
        "name": f"setup_{descriptor.id}_capability",
        "description": (
            f"Explain how to finish setup for the optional {descriptor.id} capability."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    }

    def _handler() -> str:
        state_bits = []
        if not descriptor.available:
            state_bits.append("integration SDK is not installed")
        if not descriptor.configured:
            state_bits.append("credentials/scopes are not configured")
        state = "; ".join(state_bits) if state_bits else "capability is disabled"
        return f"{descriptor.id} capability is unavailable: {state}. {descriptor.setup_hint}"

    tool_registry.register(schema, _handler)


class AgentSession:
    """A persistent session wrapping the execution loop.

    Memory architecture (Phase 2):
            - Session Snapshot: User profile + top workspace facts refreshed each
                turn so newly saved profile facts are visible on the next response.
    - Async Prefetch: After each turn, a background thread pre-fetches context
      relevant to the user's latest message. The result is consumed at the START
      of the next turn — zero blocking latency.
    - Auto-Sync: The execution loop calls memory.sync_turn() after every completed
      task, extracting facts in the background without tool calls.
    """

    def __init__(
        self,
        loop: ExecutionLoop,
        skill_engine: SkillEngine,
        memory: MemoryManager,
        integrations: IntegrationRuntime,
        mcp_manager: MCPManager,
        permission_gate: Any,
        model_name: str,
        event_emitter: Callable[[str, dict[str, Any]], None] | None = None,
        read_models: RuntimeReadModelStore | None = None,
        job_queue: JobQueue | None = None,
    ):
        self.loop = loop
        self.skill_engine = skill_engine
        self.memory = memory
        self.integrations = integrations
        self.mcp_manager = mcp_manager
        self.permission_gate = permission_gate
        self.model_name = model_name
        self.vault = None
        self._original_system_prompt = loop.base_system_prompt
        self._event_emitter = event_emitter or (lambda *_a, **_kw: None)
        self._read_models = read_models or RuntimeReadModelStore()
        self._job_queue = job_queue
        self._job_worker = (
            JobWorker(job_queue, on_job_event=self._emit_event) if job_queue else None
        )
        # Set by boot_agent when a SQLiteJobQueue + ResidentWorkerThread are active.
        self._resident_worker: ResidentWorkerThread | None = None

        # Per-session turn serialization: prevents concurrent chat() calls from
        # corrupting interleaved user/assistant/tool-pair message history.
        self._chat_lock = threading.Lock()

        # Phase 2: Session snapshot (rebuilt each turn to keep profile updates visible)
        self._memory_snapshot: str | None = None

        # Phase 2: Queue-backed prefetch pipeline (FIX medium: keyed by turn_id to avoid
        # cross-turn races where a stale prefetch from turn N is consumed by turn N+1)
        self._prefetch_results: dict = {}  # turn_id -> List[dict]
        self._last_prefetch_turn_id: str | None = None  # turn_id most recently enqueued
        self._prefetch_lock = threading.Lock()

        # Phase 3: Session persistence
        self._session_store: SessionStore | None = None
        self._session_id: str | None = None
        # Auto-title is generated once, from the first turn's exchange.
        self._title_generated: bool = False
        # Tracks the cumulative cost after the previous turn so we can compute the
        # per-turn delta for the daily spend ledger (CostTracker is cumulative).
        self._last_recorded_cost_usd: float = 0.0
        # Same idea for tokens, so the interaction_log records a per-turn token count.
        self._last_recorded_tokens: int = 0

        # Rolling calendar-day spend cap (P1-3).  Set by boot_agent from [limits] config /
        # HACHI_MAX_DAILY_COST_USD env.  None means unlimited (default — safe fail-open).
        self._max_daily_cost_usd: float | None = None

        # Resume support: prior-session turns replayed for TUI transcript rendering.
        # (role, content) pairs, oldest first; empty unless booted with resume.
        self._resumed_transcript: list[tuple[str, str]] = []

        # P4-05: scheduler reference — set by boot_agent after ScheduleRunner starts.
        self._scheduler: Any = None

        # Slice 2.2: when True, _enqueue_title_job uses handler_name= instead of
        # func= so the job survives a restart.  Set by boot_agent when
        # [jobs] durable_handlers=true.
        self._durable_title: bool = False

        # M1: number of past-session episodes to inject per turn (0 = disabled).
        # Set by boot_agent from memory settings (episodic_top_k).
        self._episodic_top_k: int = 3

        # Stage-C graph expansion: when True, each turn appends a concise graph-expanded
        # memory section to the recall block.  Set by boot_agent from memory.graph_recall.
        self._graph_recall: bool = True

        # BB-11: stashed by boot_agent so reload_search_provider() can rebuild the
        # ProviderRegistry with fresh credentials without a full restart.
        self._provider_registry: Any = None
        self._secret_store: Any = None

    @property
    def resumed_transcript(self) -> list[tuple[str, str]]:
        """User/assistant turns carried over from a resumed session (oldest first)."""
        return list(self._resumed_transcript)

    def _emit_event(self, event_name: str, payload: dict[str, Any] | None = None) -> None:
        self._event_emitter(event_name, payload or {})

    def set_vault(self, vault: MemoryVault):
        self.vault = vault

    def reload_search_provider(self) -> bool:
        """Re-evaluate search-provider availability after a credential change (BB-11).

        Rebuilds the :class:`~hachi.core.providers.registry.ProviderRegistry` with
        the current process environment (which now includes the newly stored key),
        then registers or updates ``web_search`` / ``extract_url`` on the live tool
        registry.  Returns *True* when a provider is now active, *False* when no
        search key is available yet.

        Must only be called after ``boot_agent`` has stashed ``_secret_store`` on
        this session.  No-op (returns *False*) when the store is not yet attached.
        """
        if self._secret_store is None:
            return False
        try:
            from hachi.core.config_loader import load_effective_config
            from hachi.core.providers.registry import ProviderRegistry

            cfg = load_effective_config()
            self._provider_registry = ProviderRegistry.from_config(cfg, self._secret_store)
            provider = self._provider_registry.get_search()
            if provider is None:
                return False
            _register_search_tools_for(provider, self.loop.registry, self.permission_gate)
            return True
        except Exception:
            logger.debug("reload_search_provider: failed", exc_info=True)
            return False

    def set_session_store(self, store: SessionStore, model: str = "unknown"):
        """Bind a SessionStore and start a new persistent session.

        Args:
            store: The SQLite-backed session store.
            model: The LLM model name for this session's metadata.
        """
        self._session_store = store
        self._session_id = store.start_session(model=model)

    def resume_from_session(self, source_session_id: str, max_messages: int = 40) -> int:
        """Replay a prior session's transcript into active memory (full context reload).

        The bound SessionStore must already be set. Prior user/assistant turns are
        seeded into the MemoryManager so the next LLM call sees the earlier
        conversation, and cached as ``resumed_transcript`` for the UI to render.
        Tool rows are skipped — only the visible dialogue is restored.

        Args:
            source_session_id: The session whose transcript to load.
            max_messages: Cap on how many recent messages to carry over.

        Returns:
            The number of messages seeded into memory.
        """
        if not self._session_store:
            return 0

        rows = self._session_store.get_session_messages(source_session_id, limit=max_messages)
        seeded: list[Message] = []
        transcript: list[tuple[str, str]] = []
        for row in rows:
            role = str(row.get("role", ""))
            content = row.get("content") or ""
            if role not in {"user", "assistant"} or not content:
                continue
            seeded.append(Message(role=role, content=content))
            transcript.append((role, content))

        self._resumed_transcript = transcript
        return self.memory.seed_history(seeded)

    # ==========================================
    # TUI Read-Model Snapshots
    # ==========================================

    def snapshot_session_state(self) -> SessionStateSnapshot:
        """Immutable summary of current session state for UI inspection."""
        tracker = getattr(self.loop, "cost_tracker", None)
        cost = tracker.snapshot() if tracker is not None else None
        return SessionStateSnapshot(
            session_id=self._session_id or "",
            active_skill=self.memory.active_skill,
            last_user_query=getattr(self.memory, "_last_user_query", ""),
            model_name=self.model_name,
            boot_ready=self._read_models.boot_ready(),
            pending_job_count=len(self._read_models.active_jobs()),
            total_tokens=cost.total_tokens if cost else 0,
            estimated_cost_usd=round(cost.estimated_cost_usd, 6) if cost else 0.0,
        )

    def snapshot_usage(self) -> dict[str, Any]:
        """Detailed token/cost breakdown for the Ops dashboard.

        Exposes the full CostSnapshot (input/output/cache-read/cache-creation/total
        tokens, call_count, estimated_cost_usd). Empty dict before the first LLM call.
        """
        tracker = getattr(self.loop, "cost_tracker", None)
        return tracker.snapshot().to_dict() if tracker is not None else {}

    def snapshot_task_ledger(self, limit: int = 50) -> tuple[TaskLedgerItemSnapshot, ...]:
        """Immutable task ledger records for timeline views."""
        records = self.memory.task_ledger[-limit:]
        return tuple(
            TaskLedgerItemSnapshot(
                skill_name=record.skill_name,
                user_query=record.user_query,
                summary=record.summary,
            )
            for record in records
        )

    def snapshot_skills(self, limit: int = 100) -> tuple[SkillSnapshot, ...]:
        """Immutable inventory of loaded .og skills with usage stats.

        Surfaces the ObjectGraph moat in the TUI: which skills are loaded, how
        often each has been used, and when. Sorted by use_count desc (most-used
        first) by the engine.
        """
        rows = self.skill_engine.get_skill_inventory()[:limit]
        return tuple(
            SkillSnapshot(
                name=str(row.get("name", "")),
                role=str(row.get("role", "")),
                keyword_count=int(row.get("keyword_count", 0) or 0),
                use_count=int(row.get("use_count", 0) or 0),
                last_used=row.get("last_used"),
            )
            for row in rows
        )

    def snapshot_gardener_diffs(self) -> list[dict]:
        """Return pending memory-diff proposals from the last gardener run.

        Reads the pending_diffs.json file written by MemoryGardener.run().
        Returns an empty list if the file is missing or unreadable.
        """
        from hachi.core.memory_gardener import GardeningResult

        memory_dir = getattr(self.memory, "memory_dir", None)
        if memory_dir is None:
            return []
        diffs_path = memory_dir / GardeningResult._PENDING_DIFFS_FILE
        result = GardeningResult.load(diffs_path)
        from dataclasses import asdict

        return [asdict(p) for p in result.pending_review]

    def snapshot_og_explorer(self) -> dict:
        """Return data for the OG Explorer TUI screen.

        Includes the full skill inventory with usage stats plus pass-depth
        counters so the explorer can show token-efficiency metrics.
        """
        inventory = self.skill_engine.get_skill_inventory()
        counters = self.skill_engine.get_usage_counters()
        node_count = len(self.skill_engine.get_all_nodes())
        return {
            "skills": inventory,
            "counters": counters,
            "node_count": node_count,
        }

    def list_provider_models(self) -> list[str]:
        """Return model ids — registry-backed when available, else live discovery.

        Tries the :class:`~hachi.core.routing.registry.ModelRegistry` first
        (populated from bundled defaults + provider discovery at boot).  Falls back
        to a live ``list_models()`` call when no registry is wired in.
        """
        # Registry-backed path (Slice 2.1).
        router = getattr(self.loop, "router", None)
        if router is not None:
            try:
                registry = getattr(router, "_registry", None)
                if registry is not None:
                    return [d.id for d in registry.all()]
            except Exception:
                logger.debug("list_provider_models: registry path failed", exc_info=True)

        # Fallback: live discovery via the client (pre-routing path).
        client = getattr(self.loop, "llm_client", None)
        lister = getattr(client, "list_models", None)
        if not callable(lister):
            return []
        try:
            return list(lister())
        except Exception:
            logger.warning("Failed to list provider models", exc_info=True)
            return []

    def query_recent_sessions(self, limit: int = 10) -> tuple[dict[str, Any], ...]:
        """Recent persisted sessions from SessionStore."""
        if not self._session_store:
            return tuple()
        return tuple(self._session_store.get_recent_sessions(limit=limit))

    def query_session_messages(
        self, session_id: str, limit: int = 500
    ) -> tuple[dict[str, Any], ...]:
        """Chronological transcript for a persisted session (resume/history replay)."""
        if not self._session_store:
            return tuple()
        return tuple(self._session_store.get_session_messages(session_id, limit=limit))

    def delete_session(self, session_id: str) -> bool:
        """Permanently delete a persisted session + its messages. True if it existed."""
        if not self._session_store:
            return False
        return self._session_store.delete_session(session_id)

    def query_memory_recall(self, query: str, top_k: int = 8) -> tuple[MemoryRecallSnapshot, ...]:
        """Immutable memory recall search snapshots."""
        if not self.vault:
            return tuple()
        rows = self.vault.semantic_search(query, top_k=top_k)
        return tuple(
            MemoryRecallSnapshot(
                fact_id=row.get("id", ""),
                content=row.get("raw_content") or row.get("content", ""),
                category=row.get("category", "workspace_state"),
                timestamp=row.get("timestamp", ""),
            )
            for row in rows
        )

    def snapshot_permission_audit(self, limit: int = 50) -> tuple[PermissionAuditSnapshot, ...]:
        """Recent permission request/decision audit entries."""
        return self._read_models.permission_audit(limit=limit)

    def snapshot_schedules(self) -> list[dict[str, Any]]:
        """Current schedules serialized for the companion web UI."""
        if self._scheduler is None:
            return []
        return [s.to_dict() for s in self._scheduler.list_schedules()]

    def cancel_schedule(self, schedule_id: str) -> bool:
        """Cancel a schedule by id. Returns True if cancelled."""
        if self._scheduler is None:
            return False
        return self._scheduler.cancel(schedule_id)

    def toggle_schedule_enabled(self, schedule_id: str, *, enabled: bool) -> bool:
        """Enable or disable a schedule. Returns True if updated."""
        if self._scheduler is None:
            return False
        return self._scheduler.set_enabled(schedule_id, enabled)

    def run_schedule_now(self, schedule_id: str) -> bool:
        """Force-trigger a schedule immediately (Work screen "Run now").

        Dispatches the same ``fire`` callback the resident :class:`ScheduleRunner`
        uses (``session.chat(task, surface="schedule")`` + :func:`deliver_result`),
        via the existing background job queue so the HTTP request returns without
        waiting for the agent turn to finish — mirrors ``_enqueue_title_job``'s
        ``func=`` closure path (BB-36).

        Returns:
            ``True`` if the schedule id was found and the run was dispatched (in
            the background); ``False`` if no schedule matches ``schedule_id`` or
            the scheduler/runner is not wired up (never booted, or booted without
            proactive scheduling).
        """
        if self._scheduler is None:
            return False
        runner = getattr(self, "_schedule_runner", None)
        fire = getattr(runner, "_fire", None)
        if fire is None:
            return False
        schedule = self._scheduler.get(schedule_id)
        if schedule is None:
            return False

        def _run() -> None:
            self._scheduler.run_now(schedule.schedule_id, fire)

        if not self._job_queue:
            _run()
            return True

        job = Job(
            job_id="",
            name="schedule_run_now",
            status=JobStatus.PENDING,
            func=_run,
            job_type="background",
            session_id=self._session_id,
        )
        try:
            self._job_queue.enqueue(job)
        except Exception:
            # HIGH-012 pattern: enqueue failures should be visible; fall back to inline.
            logger.warning(
                "run_schedule_now: job queue enqueue failed; running inline",
                exc_info=True,
            )
            _run()
        return True

    def snapshot_mcp_inventory(self) -> MCPInventorySnapshot:
        """Current MCP server and tool inventory."""
        inventory_rows = self.mcp_manager.get_inventory()
        servers = tuple(
            MCPServerSnapshot(
                name=row.get("name", "unknown"),
                status=row.get("status", "unknown"),
                tool_count=int(row.get("tool_count", 0)),
                tools=tuple(row.get("tools", [])),
                transport=row.get("transport", "stdio"),
                err=row.get("err"),
            )
            for row in inventory_rows
        )
        return MCPInventorySnapshot(
            server_count=len(servers),
            total_tool_count=sum(server.tool_count for server in servers),
            servers=servers,
        )

    def add_mcp_server_live(
        self,
        cfg: MCPServerConfig,
        registry: ToolRegistry,
        emit: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        """Connect a newly-registered MCP server without restarting the gateway.

        Persists and connects the server, then registers its tools in the live
        ToolRegistry so they are immediately available to the agent.

        Args:
            cfg:      The transport-aware config for the new server.
            registry: The live ToolRegistry to mount the new tools onto.
            emit:     Optional event emitter (same signature as the runtime emitter).

        Returns:
            A dict with ``ok``, ``tool_count``, and ``status``.
        """
        from hachi.core.runtime_events import (
            MCP_SERVER_FAILED,
            MCP_SERVER_READY,
            MCP_SERVER_STARTING,
        )

        _emit = emit or (lambda *_: None)
        _emit(MCP_SERVER_STARTING, {"server": cfg.name})
        try:
            started = self.mcp_manager.setup_from_config(cfg)
        except Exception as exc:
            logger.warning("[mcp] hot-reload of '%s' failed: %s", cfg.name, exc)
            _emit(MCP_SERVER_FAILED, {"server": cfg.name, "reason": str(exc)})
            return {"ok": False, "tool_count": 0, "status": "failed", "error": str(exc)}

        if not started:
            _emit(MCP_SERVER_FAILED, {"server": cfg.name, "reason": "startup failed"})
            return {"ok": False, "tool_count": 0, "status": "failed"}

        tool_count = self.mcp_manager.get_server_tool_count(cfg.name)
        # Register the new server's tools into the live tool registry
        server = self.mcp_manager._servers.get(cfg.name)
        if server is not None:
            self.mcp_manager._register_server_tools(cfg.name, server, registry)
        # BB-32: reclassify the new server's tools into "mcp" group and ensure
        # the group is always-on for the running loop so the LLM sees them
        # immediately without requiring a use_tools call.
        registry.reclassify_by_prefix({f"{cfg.name}_": "mcp"})
        self.loop._persistent_groups.add("mcp")
        _emit(MCP_SERVER_READY, {"server": cfg.name, "tool_count": tool_count})
        return {"ok": True, "tool_count": tool_count, "status": "ready"}

    def remove_mcp_server_live(self, name: str) -> dict[str, Any]:
        """Tear down a live MCP server without restarting the gateway.

        Stops the connection and unregisters its tools from the live
        ToolRegistry so it disappears from ``GET /runtime/mcp/inventory``
        immediately.  Used by the delete-server control-plane path.

        Args:
            name: The logical name of the server to remove.

        Returns:
            Dict with ``ok`` and ``removed_live`` (whether a live server existed).
        """
        removed = self.mcp_manager.remove_server(name, self.loop.registry)
        return {"ok": True, "name": name, "removed_live": removed}

    def set_mcp_tools_active(self, name: str, active: bool) -> dict[str, Any]:
        """Enable/disable a live MCP server's tools without a gateway restart.

        Disabling unregisters the server's tools from the live ToolRegistry (the
        connection and inventory entry remain, so it can be re-enabled). Enabling
        re-registers them.  When the server is not currently live (e.g. it was
        disabled in a prior session and skipped at boot), this is a no-op live and
        the change takes effect on the next session boot via the persisted flag.

        Args:
            name:   The logical name of the server.
            active: ``True`` to (re-)register tools, ``False`` to unregister them.

        Returns:
            Dict with ``ok``, ``name``, ``active``, and ``live`` (whether the
            server was present and the change was applied in-session).
        """
        if active:
            live = self.mcp_manager.register_server_tools(name, self.loop.registry)
        else:
            live = name in self.mcp_manager._servers
            self.mcp_manager.unregister_server_tools(name, self.loop.registry)
        return {"ok": True, "name": name, "active": active, "live": bool(live)}

    def snapshot_active_jobs(self) -> tuple[JobSnapshot, ...]:
        """Active background jobs (delegations and long-running runtime operations)."""
        return self._read_models.active_jobs()

    def snapshot_failed_jobs(self, limit: int = 20) -> tuple[JobFailureSnapshot, ...]:
        """Recently failed jobs for operator diagnostics."""
        return self._read_models.failed_jobs(limit=limit)

    def query_subagent_reports(
        self, query: str = "recent delegation", top_k: int = 10
    ) -> tuple[SubAgentReportSnapshot, ...]:
        """Sub-agent execution reports from memory vault plus recent runtime events."""
        runtime_reports = list(self._read_models.subagent_reports(limit=top_k))
        if not self.vault:
            return tuple(runtime_reports)

        try:
            vault_rows = self.vault.search_delegations(query=query, top_k=top_k)
        except RuntimeError:
            # Vault closed (e.g. a process-teardown race) — degrade to runtime-only
            # reports instead of surfacing a 500. The shared-vault lifecycle fix makes
            # this rare, but the endpoint must never crash on a closed vault.
            logger.warning("query_subagent_reports: vault closed; returning runtime reports only")
            return tuple(runtime_reports)
        for row in vault_rows:
            runtime_reports.append(
                SubAgentReportSnapshot(
                    role=row.get("role", "unknown"),
                    status=row.get("status", "unknown"),
                    duration_seconds=float(row.get("duration") or 0.0),
                    iterations=int(row.get("iterations") or 0),
                    summary=row.get("content", ""),
                )
            )

        return tuple(runtime_reports[-top_k:])

    def snapshot_tool_calls(self, limit: int = 50) -> tuple[ToolCallSnapshot, ...]:
        """Recent tool-call timeline (start→completion pairs with durations)."""
        return self._read_models.tool_calls(limit=limit)

    def snapshot_runtime_events(self, limit: int = 100) -> tuple[RuntimeEventSnapshot, ...]:
        """Recent normalized runtime events for operator diagnostics."""
        return self._read_models.runtime_events(limit=limit)

    def snapshot_events_since(
        self, after: int, limit: int = 100
    ) -> tuple[RuntimeEventSnapshot, ...]:
        """Sequenced events past ``after`` — the single source for gateway polling."""
        return self._read_models.read_events_since(after, limit=limit)

    def snapshot_memory_facts(self) -> dict:
        """Return grouped memory facts, blocked items, and proposed changes for the web UI.

        Enumerates the three vault collections (user_profile, agent_profile, core_memory)
        and the quarantine collection, building a structured payload for the Memory screen.

        Returns:
            Dict with keys ``groups`` (list of fact groups), ``blocked`` (list of quarantined
            items), and ``proposed`` (always None — no moderation pipeline yet).
        """
        if self.vault is None:
            return {"groups": [], "blocked": [], "proposed": None}

        groups: list[dict] = []

        collection_defs = [
            (self.vault.user_collection, "user_profile", "About you"),
            (self.vault.agent_profile, "agent_profile", "About Hachi"),
            (self.vault.collection, "core_memory", "Workspace"),
        ]

        for coll, group_id, title in collection_defs:
            facts: list[dict] = []
            try:
                rows = coll.get()
                ids = rows.get("ids", [])
                docs = rows.get("documents", [])
                metas = rows.get("metadatas", []) or []
                for i, fact_id in enumerate(ids):
                    doc = docs[i] if i < len(docs) else ""
                    meta = (metas[i] if i < len(metas) else None) or {}
                    facts.append(
                        {
                            "id": fact_id,
                            "text": doc,
                            "source": meta.get("category", ""),
                        }
                    )
            except Exception:
                # HIGH-012: one bad collection must not kill the whole response,
                # but log so ChromaDB/persistence failures are visible.
                logger.warning(
                    "snapshot_memory_facts: failed to enumerate collection %r",
                    group_id,
                    exc_info=True,
                )
            groups.append({"id": group_id, "title": title, "facts": facts})

        blocked: list[dict] = []
        try:
            quarantine_rows = self.vault.get_quarantine_entries()
            for row in quarantine_rows:
                blocked.append(
                    {
                        "id": row.get("id", ""),
                        "text": row.get("content", ""),
                        # Reason sourced from threat metadata fields; tolerate absence.
                        "reason": row.get("threat_id") or row.get("status") or "quarantined",
                    }
                )
        except Exception:
            # HIGH-012: quarantine enumeration errors must not kill the response.
            logger.warning(
                "snapshot_memory_facts: failed to enumerate quarantine entries", exc_info=True
            )

        # proposed: no moderation pipeline yet — always null.
        return {"groups": groups, "blocked": blocked, "proposed": None}

    def snapshot_og_graph(self) -> dict:
        """Return ObjectGraph node graph for the OG Explorer web screen.

        Delegates to :func:`og_graph_from_engine` using this session's skill engine.

        Returns:
            Dict with key ``nodes`` containing a list of node dicts and ``count``
            with the number of nodes.
        """
        return og_graph_from_engine(self.skill_engine)

    # ==========================================
    # Session Memory Snapshot
    # ==========================================

    def _build_frozen_snapshot(self) -> str:
        """Build the memory snapshot used for the current chat turn.

        Called at the start of each chat() call. Combines user profile facts
        with top workspace facts so explicit memory saves are reflected on the
        very next turn.

        Returns:
            A formatted string block, or empty string if no vault/facts exist.
        """
        if not self.vault:
            return ""

        parts = []

        # User profile (bounded, high-value)
        profile = self.vault.get_user_snapshot()
        if profile:
            parts.append(profile)

        # Agent persona (bounded, evolving)
        agent_persona = self.vault.get_agent_snapshot()
        if agent_persona:
            parts.append(agent_persona)

        # Top workspace facts (general context).
        # Issue 10: use get_recent_facts() instead of a biased semantic_search probe so
        # the fixed query "important context" no longer skews which facts surface here.
        # Contract C-RECENT: vault.get_recent_facts(collection="core_memory", limit=8) -> list[str]
        try:
            if hasattr(self.vault, "get_recent_facts"):
                top_fact_texts: list[str] = self.vault.get_recent_facts(
                    collection="core_memory", limit=8
                )
            else:
                # Graceful fallback when another lane has not yet landed the contract.
                raw_facts = self.vault.semantic_search("important context", top_k=8)
                top_fact_texts = [
                    f.get("raw_content", "") for f in raw_facts if f.get("raw_content")
                ]
            if top_fact_texts:
                lines = [f"- {t}" for t in top_fact_texts if t]
                parts.append("## Known Context\n" + "\n".join(lines))
        except Exception:
            # HIGH-012: vault recall failures must be visible, not silently dropped.
            logger.warning(
                "_build_frozen_snapshot: get_recent_facts failed; "
                "workspace context will be absent this turn",
                exc_info=True,
            )

        if not parts:
            return ""

        return (
            "\n\n--- LONG-TERM MEMORY (frozen at session start) ---\n" + "\n\n".join(parts) + "\n"
        )

    # ==========================================
    # Async Prefetch Pipeline
    # ==========================================

    def set_resident_worker(self, worker: ResidentWorkerThread) -> None:
        """Bind a ResidentWorkerThread started by boot_agent."""
        self._resident_worker = worker

    def _drain_job_queue(self) -> None:
        """Fallback synchronous drain — no-op when the resident worker is running."""
        if self._resident_worker and self._resident_worker.is_running:
            return
        if not self._job_worker:
            return
        while self._job_worker.execute_one():
            continue

    def _run_prefetch_job(self, query: str, turn_id: str = "compat") -> list[dict]:
        """Execute vault recall (semantic + episodic) and store the result keyed by *turn_id*.

        B10: episodic recall runs here so it does not block the inline turn path on
        turns 2+.  Trade-off: uses the *previous* turn's query for episodic results —
        accepted heuristic (see docs/DECISIONS.md §B10).
        """
        results: list[dict] = []
        if self.vault:
            try:
                results = self.vault.semantic_search(query, top_k=5)
            except Exception:
                # HIGH-012: prefetch recall failures should be visible.
                logger.warning(
                    "_run_prefetch_job: vault semantic_search failed for query %r",
                    query[:80],
                    exc_info=True,
                )
                results = []

            # B10: episodic recall merged in-place; dedup by id.
            if self._episodic_top_k > 0:
                try:
                    episodic = self.vault.search_episodic(query, top_k=self._episodic_top_k)
                    if episodic:
                        existing_ids = {r.get("id") for r in results}
                        for ep in episodic:
                            if ep.get("id") not in existing_ids:
                                results.append(ep)
                except Exception:
                    logger.debug(
                        "_run_prefetch_job: episodic recall failed for query %r (non-fatal)",
                        query[:80],
                        exc_info=True,
                    )

        with self._prefetch_lock:
            # FIX medium: store under turn_id so _pop_prefetch can validate provenance
            self._prefetch_results[turn_id] = results

        return results

    def _enqueue_prefetch_job(self, query: str, turn_id: str) -> None:
        # FIX medium: record the turn_id so _pop_prefetch can validate provenance
        with self._prefetch_lock:
            self._last_prefetch_turn_id = turn_id

        if not self._job_queue:
            self._run_prefetch_job(query, turn_id)
            return

        job = Job(
            job_id="",
            name="prefetch_recall",
            status=JobStatus.PENDING,
            func=self._run_prefetch_job,
            args=(query, turn_id),  # FIX medium: pass turn_id so result is stored under it
            job_type="prefetch",
            session_id=self._session_id,
            turn_id=turn_id,
        )

        try:
            self._job_queue.enqueue(job)
        except Exception:
            # HIGH-012: queue enqueue failures should be visible; fall back to inline.
            logger.warning(
                "_enqueue_prefetch_job: job queue enqueue failed; running prefetch inline",
                exc_info=True,
            )
            self._run_prefetch_job(query, turn_id)

    def _fire_prefetch(self, query: str) -> None:
        """Compatibility wrapper for the queue-backed prefetch pipeline."""
        self._enqueue_prefetch_job(query, turn_id="compat")  # legacy callers have no turn_id

    def _run_title_job(self, session_id: str, user_input: str, assistant_response: str) -> str:
        """Generate and persist a title for *session_id* from its first exchange.

        Best-effort: a model call produces the title, with a deterministic
        fallback baked into :func:`generate_title`. Persisting is guarded so a
        store hiccup never surfaces as a turn error.
        """
        # Prefer the cheaper sub-agent client (a smaller model on Anthropic);
        # fall back to the main loop client when no sub-agent client is wired.
        client = getattr(self, "_sub_agent_client", None) or getattr(self.loop, "llm_client", None)
        # Issue 11 (contract C-TITLER-COST): pass cost_tracker so title-generation tokens are
        # counted in the session's cumulative spend.  The titler signature gains an optional
        # ``cost_tracker`` kwarg — another lane implements this; guarded with inspect so a
        # missing parameter never breaks title generation.
        _tracker = getattr(self.loop, "cost_tracker", None)
        try:
            import inspect as _inspect

            _sig = _inspect.signature(generate_title)
            if "cost_tracker" in _sig.parameters:
                title = generate_title(
                    user_input, assistant_response, llm_client=client, cost_tracker=_tracker
                )
            else:
                title = generate_title(user_input, assistant_response, llm_client=client)
        except Exception:
            title = generate_title(user_input, assistant_response, llm_client=client)
        if self._session_store:
            try:
                self._session_store.set_session_title(session_id, title)
            except Exception:
                # HIGH-012: title persistence failures must be visible.
                logger.warning(
                    "_run_title_job: failed to persist session title for %s",
                    session_id,
                    exc_info=True,
                )
        return title

    def _enqueue_title_job(self, session_id: str, user_input: str, response: str) -> None:
        """Queue first-turn title generation, or run it inline if no queue exists.

        Slice 2.2: when ``_durable_title=True`` (set by boot_agent when
        ``[jobs] durable_handlers=true``), the job is enqueued with
        ``handler_name="generate_title"`` + serializable payload so it survives a
        process restart.  The durable path uses a deterministic fallback title
        (no LLM call) — see ``handle_generate_title`` in runtime/job_handlers.py.

        When ``_durable_title=False`` (default), the original ``func=`` path runs
        unchanged, preserving LLM-generated titles.
        """
        if not self._job_queue:
            self._run_title_job(session_id, user_input, response)
            return

        if self._durable_title:
            # Durable path: serializable payload, survives restart.
            job = Job(
                job_id="",
                name="session_title",
                status=JobStatus.PENDING,
                handler_name="generate_title",
                payload={
                    "session_id": session_id,
                    "user_message": user_input,
                    "assistant_message": response,
                },
                job_type="background",
                session_id=session_id,
            )
        else:
            # Default path: func= closure with LLM client access.
            job = Job(
                job_id="",
                name="session_title",
                status=JobStatus.PENDING,
                func=self._run_title_job,
                args=(session_id, user_input, response),
                job_type="background",
                session_id=session_id,
            )
        try:
            self._job_queue.enqueue(job)
        except Exception:
            # HIGH-012: queue enqueue failures should be visible; fall back to inline.
            logger.warning(
                "_enqueue_title_job: job queue enqueue failed; running title generation inline",
                exc_info=True,
            )
            self._run_title_job(session_id, user_input, response)

    def _pop_prefetch(self) -> list[dict]:
        """Consume and delete the prefetched results for the last enqueued turn.

        FIX medium: validates the turn_id before consuming so a stale result from a
        previous (or concurrent) turn is never served to the wrong turn.
        Returns an empty list if the result is not yet ready or there is no matching entry.
        """
        with self._prefetch_lock:
            tid = self._last_prefetch_turn_id
            if tid is None:
                return []
            results = self._prefetch_results.pop(tid, [])
            self._last_prefetch_turn_id = None
        return results

    # ==========================================
    # Chat Entry Point
    # ==========================================

    def chat(self, user_input: str, *, surface: str = "cli") -> str:  # always returns str
        """Send a message to the agent and trigger the autonomous loop.

        Architecture (Phase 1 update):
            - Serializes concurrent callers via a per-session lock so history is
              never corrupted by interleaved user/assistant/tool-pair messages.
            - Creates an immutable TurnContext per turn (no shared state mutation)
            - Passes the context to ExecutionLoop.run() for use during execution
            - Previous turns' prefetch results are consumed, not blocking

        Prompt composition (per TurnContext):
            1. Time header        — changes every turn (not cached)
            2. Frozen snapshot    — stable across all turns (prefix-cached)
            3. Recalled context   — from async prefetch (turn-specific addendum)
            4. Original prompt    — brain.og + skills + permissions (stable)

        Args:
            user_input: The user's message for this turn.
            surface: The originating surface for this request, e.g. "cli", "tui",
                     "web", "webhook", or "schedule". Defaults to "cli". (MED-012)
        """
        # Emit session.busy when another turn is already running so UIs can show
        # queued state. The acquire() then blocks until the current turn finishes.
        if not self._chat_lock.acquire(blocking=False):
            self._emit_event(SESSION_BUSY, {"queued_input_preview": user_input[:80]})
            self._chat_lock.acquire()  # blocks until the current turn is done

        try:
            return self._chat_impl(user_input, surface=surface)
        finally:
            self._chat_lock.release()

    def _chat_impl(self, user_input: str, *, surface: str = "cli") -> str:
        """Internal single-turn implementation; must only be called while _chat_lock is held."""
        # 1. Refresh memory snapshot at turn start
        turn_id = str(uuid.uuid4())[:8]

        # Build the TraceContext and open the agent.turn ROOT span.  All child spans
        # (llm.generate, tool.call) will nest under this root via OTel context
        # propagation (thread pool fix in loop.py).  The trace_id == turn_id per ADR-0005.
        _trace_ctx = TraceContext(
            trace_id=turn_id,
            session_id=self._session_id or "unknown",
            # SINGLE-TENANT: "session" is a hardcoded placeholder — account_id is intentionally
            # unplumbed; safe only under one-operator-per-install (AUDIT P1-1). Before supporting
            # a 2nd principal/tenant, plumb the authenticated principal → account_id into BOTH
            # MemoryVault construction AND the ProcessSharedServices fingerprint (see
            # src/hachi/core/memory_vault.py docstring ADV-023 and SECURITY.md "Trust model").
            principal="session",
            surface=surface,
        )

        with (
            _bind_trace_ctx(_trace_ctx),
            span(
                "agent.turn",
                turn_id=turn_id,
                session_id=self._session_id or "unknown",
                surface=surface,
            ),
        ):
            return self._chat_impl_inner(user_input, turn_id=turn_id, surface=surface)

    def _write_interaction_log(
        self,
        *,
        turn_id: str,
        user_input: str,
        response: str,
        recalled: list[dict[str, Any]],
        turn_cost_usd: float,
        turn_tokens: int,
    ) -> None:
        """Append the per-turn ``interaction_log`` row (AUDIT P0-2) — best-effort.

        Maps the live turn's in-scope values (recalled facts → ``memory_hits``, the loop's
        per-turn tool names, the active model, the per-turn cost/token deltas) onto one
        durable eval/audit row. A logging failure is swallowed: it must never break a turn.
        """
        if not (self._session_store and self._session_id):
            return
        try:
            self._session_store.log_interaction(
                session_id=self._session_id,
                turn_id=turn_id,
                user_input=user_input,
                agent_output=response,
                tool_calls=getattr(self.loop, "last_tool_calls", []),
                memory_hits=[r.get("content", "") for r in (recalled or [])],
                model_used=self.model_name or None,
                token_cost=turn_cost_usd,
                tokens=turn_tokens,
            )
        except Exception:
            logger.warning(
                "_chat_impl: failed to write interaction_log for turn %s", turn_id, exc_info=True
            )

    def _persist_suspended_run_if_any(self, *, turn_id: str) -> None:
        """If the turn ended by ``core_suspend_workflow``, record a durable WAITING run and
        arm its wait condition — the producer half of the durable-run subsystem (AUDIT P0-1).

        Before this, the loop returned a ``[WORKFLOW SUSPENDED]`` string and the structured
        wait condition was lost, so no ``RunState(WAITING)`` was ever created: the
        wake/recover/sweep machinery and ``GET /runs`` had zero inputs. Best-effort — a
        persistence failure must never break the turn.
        """
        suspend = getattr(self.loop, "last_suspend", None)
        if suspend is None or not self._session_id:
            return
        try:
            import uuid as _uuid

            from hachi.core.runtime.state import RunState, RunStatus, WaitCondition, WaitKind
            from hachi.core.runtime.store import RunStateStore
            from hachi.core.runtime.waits import get_wait_registry
            from hachi.core.runtime_events import RUN_SUSPENDED, now_iso

            now = now_iso()
            try:
                kind = WaitKind(suspend.wait_kind)
            except ValueError:
                # Unknown wait_kind from the model → safest default is human approval.
                kind = WaitKind.USER
            wait = WaitCondition(kind=kind, key=suspend.wait_key, created_at=now)
            run = RunState(
                run_id=str(_uuid.uuid4()),
                session_id=self._session_id,
                status=RunStatus.WAITING,
                wait=wait,
                # resume_cursor=0: a warm wake resumes the still-live in-memory session.
                # Precise cursor + cold-start replay are the separate deferred resume work.
                resume_cursor=0,
                payload={"reason": suspend.reason},
                updated_at=now,
            )
            RunStateStore().upsert(run)
            get_wait_registry().arm(run.run_id, wait)
            self._emit_event(
                RUN_SUSPENDED,
                {
                    "run_id": run.run_id,
                    "session_id": self._session_id,
                    "turn_id": turn_id,
                    "wait_kind": kind.value,
                    "wait_key": suspend.wait_key,
                    "reason": suspend.reason,
                },
            )
        except Exception:
            logger.warning("failed to persist suspended run for turn %s", turn_id, exc_info=True)

    def _daily_cap_exceeded(self) -> str | None:
        """Return a reason string if today's rolling spend cap is hit, else ``None``.

        Best-effort: if ``_session_store`` is absent or the read fails, returns ``None``
        so the turn always runs rather than crashing (safe fail-open).  The cap is only
        checked when ``_max_daily_cost_usd`` is set to a positive value.
        """
        if not self._max_daily_cost_usd:
            return None
        if self._session_store is None:
            return None
        try:
            # BB-56: key on UTC (matching the write side below), not the host's
            # local date — otherwise spend near midnight is misattributed to the
            # wrong day for any user not in UTC.
            today = today_utc_str()
            spent = self._session_store.get_daily_spend(today)
            if spent >= self._max_daily_cost_usd:
                return f"daily cost cap reached (~${spent:.4f} >= ${self._max_daily_cost_usd:.2f})"
        except Exception:
            logger.warning(
                "_daily_cap_exceeded: failed to read daily spend — skipping cap check",
                exc_info=True,
            )
        return None

    def _chat_impl_inner(self, user_input: str, *, turn_id: str, surface: str) -> str:
        """Inner implementation body (runs inside the agent.turn root span)."""
        self._emit_event(
            SESSION_CHAT_STARTED,
            {
                "turn_id": turn_id,
                "session_id": self._session_id,
                "prompt_preview": user_input[:140],
            },
        )

        self._drain_job_queue()

        # 1b. Enforce the rolling daily spend cap (P1-3) before spending any more tokens.
        #     Best-effort: a store read failure falls through (safe fail-open).
        daily_cap_reason = self._daily_cap_exceeded()
        if daily_cap_reason:
            self._emit_event(BUDGET_EXCEEDED, {"reason": daily_cap_reason})
            return f"[BUDGET LIMIT REACHED] {daily_cap_reason}"

        self._memory_snapshot = self._build_frozen_snapshot()

        # 2. Consume async prefetch from previous turn (or sync-fetch on first turn).
        #    B10: prefetch now includes both semantic + episodic recall so the turn path
        #    is non-blocking on turns 2+.  Turn 1 falls back to inline for both.
        recalled = self._pop_prefetch()
        if not recalled and self.vault:
            # Turn 1 (no prefetch available yet): run semantic + episodic inline.
            try:
                recalled = self.vault.semantic_search(user_input, top_k=5)
            except Exception:
                # HIGH-012: synchronous recall failures should be visible.
                logger.warning(
                    "_chat_impl_inner: synchronous vault recall failed for turn %s",
                    turn_id,
                    exc_info=True,
                )
                recalled = []
            if self._episodic_top_k > 0:
                try:
                    episodic = self.vault.search_episodic(user_input, top_k=self._episodic_top_k)
                    if episodic:
                        existing_ids = {r.get("id") for r in recalled}
                        for ep in episodic:
                            if ep.get("id") not in existing_ids:
                                recalled.append(ep)
                except Exception:
                    logger.debug(
                        "_chat_impl_inner: turn-1 episodic recall failed (non-fatal)",
                        exc_info=True,
                    )

        # 3. Build the dynamic recall injection
        recall_block = ""
        if recalled:
            lines = [f"- {r['content']}" for r in recalled]
            recall_block = (
                "\n[Recalled Context]\nRelevant facts from long-term memory:\n"
                + "\n".join(lines)
                + "\n"
            )

        # 3b. Stage-C graph expansion — appends a graph-traversed section to recall_block.
        #     Additive only; never replaces the semantic/episodic floor.  Wrapped in a
        #     broad try/except so a graph failure never breaks a turn.
        if self._graph_recall:
            try:
                from hachi.core.graph_recall import build_graph_recall_section
                from hachi.core.paths import get_hachi_paths

                _graph_section = build_graph_recall_section(
                    user_input=user_input,
                    memory_dir=getattr(self.memory, "memory_dir", None)
                    or get_hachi_paths().memory_dir,
                    existing_recall=recall_block,
                )
                if _graph_section:
                    recall_block += _graph_section
            except Exception:
                logger.debug(
                    "_chat_impl_inner: graph recall failed for turn %s (non-fatal)",
                    turn_id,
                    exc_info=True,
                )

        # 4. Create immutable TurnContext (Phase 1)
        # This replaces the mutation of loop.base_system_prompt
        turn_context = TurnContext.build(
            turn_id=turn_id,
            session_id=self._session_id or "unknown",
            user_input=user_input,
            system_prompt_base=self._original_system_prompt,
            active_skill=self.memory.active_skill,
            user_profile_snapshot=self._memory_snapshot if self._memory_snapshot else None,
            recalled_context=recall_block if recall_block else None,
            max_iterations=15,
            surface=surface,  # MED-012: derived from the caller's request surface
        )

        # 5. Add user message and run with TurnContext (no mutation)
        self.loop.add_user_message(user_input)
        # FIX medium: loop.run() may return None (e.g. empty content path); normalise to str
        response: str = self.loop.run(turn_context=turn_context) or ""

        # 5b. If the loop suspended this turn, persist a durable WAITING run + arm its wait
        #     condition — the producer that gives the wake/recover/sweep subsystem and
        #     GET /runs their inputs (AUDIT P0-1). No-op on a normal turn.
        self._persist_suspended_run_if_any(turn_id=turn_id)

        # 6. Queue prefetch for the NEXT turn
        self._enqueue_prefetch_job(user_input, turn_id)

        # 7. Log messages to session store (non-critical, fire-and-forget)
        if self._session_store and self._session_id:
            try:
                self._session_store.log_message(self._session_id, "user", user_input)
                self._session_store.log_message(
                    self._session_id, "assistant", response or "", model=self.model_name or None
                )
                self._emit_event(
                    SESSION_PERSISTED,
                    {
                        "turn_id": turn_id,
                        "session_id": self._session_id,
                        "messages_written": 2,
                    },
                )
            except Exception:
                # HIGH-012: session log failures must be visible.
                logger.warning(
                    "_chat_impl: failed to log turn %s to session store", turn_id, exc_info=True
                )

            # Persist cumulative cost/token totals for this session and update the
            # rolling daily spend ledger with the per-turn delta.
            _turn_cost_usd = 0.0
            _turn_tokens = 0
            try:
                tracker = getattr(self.loop, "cost_tracker", None)
                if tracker is not None:
                    snap = tracker.snapshot()
                    self._session_store.record_session_cost(
                        self._session_id,
                        snap.total_tokens,
                        snap.estimated_cost_usd,
                    )
                    # Compute the per-turn delta from the cumulative snapshot so the
                    # daily ledger accumulates exactly what this turn spent.
                    turn_delta = snap.estimated_cost_usd - self._last_recorded_cost_usd
                    self._last_recorded_cost_usd = snap.estimated_cost_usd
                    # BB-56: a negative delta (e.g. a cost_tracker reset mid-session)
                    # is clamped to 0.0 AND logged — never silently dropped with no
                    # trace, so a real anomaly stays visible instead of invisible.
                    _turn_cost_usd = clamp_nonnegative_cost_delta(
                        turn_delta, context=self._session_id or "unknown-session"
                    )
                    _turn_tokens = max(0, snap.total_tokens - self._last_recorded_tokens)
                    self._last_recorded_tokens = snap.total_tokens
                    if _turn_cost_usd > 0:
                        # BB-56: key on UTC (matching _daily_cap_exceeded's read side),
                        # not the host's local date.
                        self._session_store.record_daily_cost(today_utc_str(), _turn_cost_usd)
            except Exception:
                # HIGH-012: cost persistence failures must be visible.
                logger.warning(
                    "_chat_impl: failed to record session cost for %s",
                    self._session_id,
                    exc_info=True,
                )

            # 8. Append the per-turn interaction_log row (AUDIT P0-2): row-level eval/audit
            #    ground truth (rateable, mineable, auditable).
            self._write_interaction_log(
                turn_id=turn_id,
                user_input=user_input,
                response=response or "",
                recalled=recalled,
                turn_cost_usd=_turn_cost_usd,
                turn_tokens=_turn_tokens,
            )

            # Generate a session title once, from the opening exchange. Runs on the
            # job queue so it never blocks this turn (drained at the next turn /
            # shutdown); falls back to inline generation when no queue is wired.
            if not self._title_generated:
                self._title_generated = True
                self._enqueue_title_job(self._session_id, user_input, response or "")

        # Issue 9: populate the ``model`` field (contract C-MODEL) so the frontend
        # can display the "last used model" badge without a separate API call.
        _cost_snap = None
        try:
            _tracker = getattr(self.loop, "cost_tracker", None)
            if _tracker is not None:
                _cost_snap = _tracker.snapshot()
        except Exception:
            pass

        self._emit_event(
            SESSION_CHAT_COMPLETED,
            {
                "turn_id": turn_id,
                "session_id": self._session_id,
                "response_preview": (response or "")[:180],
                # C-MODEL: actual model id for the last turn (None before first turn).
                "model": self.model_name or None,
                # Token split for per-turn usage display.
                "input_tokens": _cost_snap.input_tokens if _cost_snap else None,
                "output_tokens": _cost_snap.output_tokens if _cost_snap else None,
                "total_tokens": _cost_snap.total_tokens if _cost_snap else None,
                "estimated_cost_usd": (
                    round(_cost_snap.estimated_cost_usd, 6) if _cost_snap else None
                ),
            },
        )

        return response  # guaranteed str by the `or ""` normalisation above

    def shutdown(self):
        """Gracefully close all persistent connections, MCP servers, and session store."""
        runner = getattr(self, "_schedule_runner", None)
        if runner is not None:
            runner.stop()

        if self._resident_worker:
            self._resident_worker.stop()
        else:
            self._drain_job_queue()

        # P2-05: write episode node at session close
        if self._session_id and self.memory:
            try:
                _last = self.memory.history[-3:] if self.memory.history else []
                _summary = (
                    " ".join(m.content[:80] for m in _last if isinstance(m.content, str))
                    or "session closed"
                )
                self.memory.write_episode(self._session_id, _summary)
            except Exception:
                # HIGH-012: episode write failures should be visible.
                logger.warning("shutdown: failed to write episode node", exc_info=True)

        # M1: capture rich episodic summary into the ChromaDB episodic_memory collection.
        #     Uses interaction_log rows so the digest reflects actual tool use and content,
        #     not just the last 3 history entries.  Wrapped so it NEVER breaks shutdown.
        if self._session_id and self.vault:
            try:
                from hachi.core.memory import build_episode_summary

                _interactions: list[dict[str, Any]] = []
                if self._session_store:
                    # get_interactions returns newest-first; reverse for chronological order.
                    _interactions = list(
                        reversed(
                            self._session_store.get_interactions(
                                session_id=self._session_id, limit=50
                            )
                        )
                    )
                _ep_summary = build_episode_summary(_interactions)
                if _ep_summary:
                    _started_at = getattr(self._session_store, "_current_started_at", "") or ""
                    self.vault.upsert_episode(
                        session_id=self._session_id,
                        summary=_ep_summary,
                        started_at=_started_at,
                    )
                    logger.debug(
                        "shutdown: episodic summary captured for session %s (%d chars)",
                        self._session_id,
                        len(_ep_summary),
                    )
            except Exception:
                logger.warning("shutdown: failed to capture episodic summary", exc_info=True)

        # End the persistent session
        if self._session_store and self._session_id:
            try:
                self._session_store.end_session(self._session_id)
                self._session_store.shutdown()
            except Exception:
                # HIGH-012: session store shutdown errors should be visible.
                logger.warning(
                    "shutdown: failed to end/shutdown session store for %s",
                    self._session_id,
                    exc_info=True,
                )

        # Shut down the per-session tool-execution thread pool (ExecutionLoop
        # creates its own ThreadPoolExecutor per session; leaving it running
        # after session close leaks 4 worker threads per ended session).
        try:
            self.loop.shutdown(wait=False)
        except Exception:
            # HIGH-012: tool-pool shutdown failures should be visible.
            logger.warning("shutdown: failed to shut down loop tool pool", exc_info=True)

        # Close LLM HTTP clients (OpenAICompatibleClient/ollama hold an httpx.Client;
        # AnthropicClient has no close() — guarded by getattr so both are safe).
        for client in (
            getattr(self.loop, "llm_client", None),
            getattr(self, "_sub_agent_client", None),
        ):
            close = getattr(client, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    # HIGH-012: client close failures should be visible.
                    logger.warning(
                        "shutdown: failed to close LLM client %r",
                        type(client).__name__,
                        exc_info=True,
                    )

        # Shut down the browser worker thread + headless browser if one was started.
        browser = getattr(self, "_browser_controller", None)
        if browser is not None:
            try:
                browser.close()
            except Exception:
                # HIGH-012: browser shutdown failures should be visible.
                logger.warning("shutdown: failed to close browser controller", exc_info=True)

        # P3-07: explicit Chroma close so WAL is flushed before process exits.
        # H-VAULT: the vault is normally a PROCESS-SHARED singleton
        # (ProcessSharedServices) reused by every session. An individual session
        # MUST NOT close it on its own shutdown (session delete or config-driven
        # _reload_agents) — sibling/replacement sessions reuse the same instance
        # and would then raise "MemoryVault is closed". Shared vaults are closed
        # exactly once at process exit by ProcessSharedServices.shutdown_all()
        # (atexit). Only a session-OWNED (non-shared) vault is closed here.
        if (
            self.memory
            and hasattr(self.memory, "vault")
            and self.memory.vault is not None
            and not getattr(self.memory.vault, "is_shared", False)
        ):
            try:
                self.memory.vault.close()
            except Exception:
                # HIGH-012: Chroma close failures should be visible (WAL may not be flushed).
                logger.warning(
                    "shutdown: failed to close memory vault (WAL may not be flushed)",
                    exc_info=True,
                )

        self.integrations.shutdown()
        self._emit_event(MCP_SHUTDOWN, {"server_count": self.mcp_manager.server_count})
        self.mcp_manager.shutdown()
        self._emit_event(
            SESSION_SHUTDOWN,
            {
                "session_id": self._session_id,
                "timestamp": now_iso(),
            },
        )


# ==========================================
# MCP Dynamic Configuration
# ==========================================


def _node_is_community_pack(source_file: str, packs_root: str) -> bool:
    """True if an .og node was loaded from an installed community-pack dir.

    Community packs install under ``<skills_dir>/packs/``; bundled/built-in
    skills live elsewhere (inside the package).  Used to tier-gate untrusted,
    web-installable MCP servers (SEC-005).
    """
    if not source_file:
        return False
    try:
        src = os.path.realpath(source_file)
        root = os.path.realpath(packs_root)
        return os.path.commonpath([src, root]) == root
    except (ValueError, OSError):
        return False


def _configure_mcp_servers(
    skill_engine: SkillEngine,
    mcp_manager: MCPManager,
    gate: PermissionGate,
    emit: Callable[[str, dict[str, Any]], None],
    config: dict[str, Any] | None = None,
):
    """Start MCP servers with permissions-aware configuration.

    Issue 4: in addition to ``.og`` nodes with ``role=mcp``, also boots servers
    declared under ``[mcp_servers]`` in ``settings.toml`` so API-registered
    servers (written by ``POST /runtime/mcp/register``) survive a gateway restart.
    Duplicate names (declared in both sources) are de-duped: the ``.og`` definition
    takes precedence and the TOML entry is skipped.

    The filesystem MCP server's allowed directories are pulled dynamically from
    the PermissionGate instead of being hardcoded in mcp-services.og.
    Non-filesystem MCP servers (Gmail, Calendar, etc.) are started as-is.

    Args:
        skill_engine: The loaded skill engine containing MCP node definitions.
        mcp_manager: The MCP manager to start servers on.
        gate: The PermissionGate loaded from device-permissions.og.
        emit: Event emitter callback for boot-progress events.
        config: Optional raw config dict (the same dict returned by
            :func:`~hachi.gateway.workspace.load_config`).  When provided,
            ``config.get("mcp_servers", {})`` entries are parsed and started
            after the ``.og`` pass, subject to the same permission gate.
    """
    packs_root = str(get_hachi_paths().skills_dir / "packs")

    # An ``enabled = false`` flag under ``[mcp_servers.NAME]`` in settings.toml acts
    # as a per-server kill switch / deletion tombstone (written by the disable and
    # delete control-plane paths). It is honoured for BOTH .og-declared servers and
    # API-registered TOML servers so a disabled/deleted server does not silently come
    # back on the next gateway boot.
    _mcp_enabled_map: dict[str, bool] = {}
    if config is not None:
        _raw_for_enabled = config.get("mcp_servers")
        if isinstance(_raw_for_enabled, dict):
            for _sname, _sentry in _raw_for_enabled.items():
                if isinstance(_sentry, dict):
                    _mcp_enabled_map[str(_sname)] = bool(_sentry.get("enabled", True))

    # Track which server names were launched from .og nodes so TOML entries for
    # the same name are skipped (de-dup: .og wins).
    og_server_names: set[str] = set()
    for node in skill_engine.get_nodes_by_role("mcp"):
        if not _mcp_enabled_map.get(node.name, True):
            logger.info("_configure_mcp_servers: skipping disabled MCP server %r", node.name)
            emit(MCP_SERVER_FAILED, {"server": node.name, "reason": "disabled by operator"})
            continue
        emit(MCP_SERVER_STARTING, {"server": node.name})
        if node.name == "filesystem_mcp":
            # Skip entirely if user disabled MCP filesystem
            if not gate.is_mcp_filesystem_enabled():
                emit(
                    MCP_SERVER_FAILED,
                    {
                        "server": node.name,
                        "reason": "filesystem MCP disabled by permissions",
                    },
                )
                continue

            # Override the hardcoded args with resolved paths from device-permissions.og
            allowed = gate.get_allowed_paths()
            if allowed:
                path_args = " ".join(str(p) for p in allowed)
                node.config["args"] = f"-y @modelcontextprotocol/server-filesystem {path_args}"
        else:
            # SEC-005: a non-filesystem MCP server runs an arbitrary command at boot.
            # Community-pack-sourced servers must be tier-gated / explicitly approved
            # so a web-installed pack cannot silently execute code on next launch.
            trusted = not _node_is_community_pack(node.source_file, packs_root)
            decision = gate.is_mcp_server_allowed(node.name, trusted=trusted)
            if not decision.allowed:
                emit(
                    MCP_SERVER_FAILED,
                    {"server": node.name, "reason": decision.reason},
                )
                continue

        # Start the server (filesystem with dynamic paths, or other MCP servers unchanged)
        started = mcp_manager.setup_from_node(node)
        og_server_names.add(node.name)
        if started:
            emit(
                MCP_SERVER_READY,
                {
                    "server": node.name,
                    "tool_count": mcp_manager.get_server_tool_count(node.name),
                },
            )
        else:
            emit(
                MCP_SERVER_FAILED,
                {
                    "server": node.name,
                    "reason": "startup failed",
                },
            )

    # Issue 4: load TOML [mcp_servers] entries so servers registered via the API
    # (written to settings.toml by POST /runtime/mcp/register) survive a restart.
    toml_mcp_entries: dict[str, Any] = {}
    if config is not None:
        _raw = config.get("mcp_servers")
        if isinstance(_raw, dict):
            toml_mcp_entries = _raw

    for server_name, entry in toml_mcp_entries.items():
        if not isinstance(entry, dict):
            continue
        if not entry.get("enabled", True):
            # Disabled / deleted (tombstone) — do not boot it.
            logger.info("_configure_mcp_servers: skipping disabled MCP server %r", server_name)
            continue
        if server_name in og_server_names:
            # .og definition takes precedence — skip the TOML duplicate.
            logger.debug(
                "_configure_mcp_servers: TOML entry %r skipped (already started from .og)",
                server_name,
            )
            continue
        emit(MCP_SERVER_STARTING, {"server": server_name})
        try:
            cfg = MCPServerConfig.from_toml_entry(server_name, entry)
        except Exception:
            _reason = "invalid TOML config"
            emit(MCP_SERVER_FAILED, {"server": server_name, "reason": _reason})
            mcp_manager.register_boot_failure(server_name, _reason)
            logger.warning(
                "_configure_mcp_servers: failed to parse TOML entry for %r",
                server_name,
                exc_info=True,
            )
            continue

        # TOML [mcp_servers] entries are USER-authored config — added by the user via the
        # UI/CLI or by editing settings.toml directly — so they are trusted by definition,
        # unlike community-pack .og servers (which are web-installed code and must be
        # tier-gated). Without trusted=True, a UI-registered server is silently DENIED under
        # the default "guided" tier and never appears in the conversation (Issue 4).
        decision = gate.is_mcp_server_allowed(server_name, trusted=True)
        if not decision.allowed:
            emit(MCP_SERVER_FAILED, {"server": server_name, "reason": decision.reason})
            mcp_manager.register_boot_failure(server_name, decision.reason)
            continue

        started = mcp_manager.setup_from_config(cfg)
        if started:
            emit(
                MCP_SERVER_READY,
                {
                    "server": server_name,
                    "tool_count": mcp_manager.get_server_tool_count(server_name),
                },
            )
        else:
            emit(MCP_SERVER_FAILED, {"server": server_name, "reason": "startup failed"})


# ==========================================
# Slice 2.2 — Durable execution helpers (A4 / §6)
# ==========================================

_SWEEP_INTERVAL_SECONDS = 30  # how often to check for timed-out WAITING runs


def _boot_recover_runs(
    job_queue: "JobQueue",
    registry: "JobRegistry",
    wait_registry: Any,
    emit: Any,
) -> None:
    """Restart-recovery pass for durable runs (design §6).

    Scans the RunStateStore on boot and:
    - **WAITING** runs: re-arm each WaitCondition in the in-process registry so
      EVENT/TIME/USER wakes can still fire.
    - **RUNNING** runs left by a crash: if a ``resume_cursor`` exists, enqueue a
      ``resume_run`` job to replay from the last turn; otherwise mark as FAILED
      with a clear message so the operator knows work was lost.

    This is best-effort: any exception per run is logged and skipped so one
    corrupt record never blocks a whole boot.
    """
    try:
        from hachi.core.runtime.state import RunStatus
        from hachi.core.runtime.store import RunStateStore
        from hachi.core.runtime_events import now_iso
        from hachi.jobs import Job, JobStatus

        store = RunStateStore()
        waiting_runs = store.waiting()
        for run in waiting_runs:
            try:
                if run.wait is not None:
                    wait_registry.arm(run.run_id, run.wait)
                    logger.info(
                        "_boot_recover_runs: re-armed WAITING run %r (kind=%s key=%s)",
                        run.run_id,
                        run.wait.kind.value if run.wait else "?",
                        run.wait.key if run.wait else "?",
                    )
            except Exception:
                logger.warning(
                    "_boot_recover_runs: failed to re-arm run %r", run.run_id, exc_info=True
                )

        # Recover RUNNING runs (crashed mid-turn).
        all_runs = store.list_all(limit=500)
        for run in all_runs:
            if run.status != RunStatus.RUNNING:
                continue
            try:
                if run.resume_cursor and run.resume_cursor > 0:
                    # Cursor exists → re-enqueue resume so the run can finish.
                    job = Job(
                        job_id="",
                        name="resume_run_recovery",
                        handler_name="resume_run",
                        payload={"run_id": run.run_id, "result": {"reason": "crash_recovery"}},
                        status=JobStatus.PENDING,
                        session_id=run.session_id,
                    )
                    job_queue.enqueue(job)
                    logger.info(
                        "_boot_recover_runs: re-enqueued resume for crashed run %r", run.run_id
                    )
                else:
                    # No cursor — cannot resume cleanly; mark FAILED.
                    run = run.model_copy(
                        update={
                            "status": RunStatus.FAILED,
                            "payload": {
                                **run.payload,
                                "error": "Process crashed while RUNNING; no resume cursor",
                            },
                            "updated_at": now_iso(),
                        }
                    )
                    store.upsert(run)
                    logger.info(
                        "_boot_recover_runs: marked crashed run %r as FAILED (no cursor)",
                        run.run_id,
                    )
            except Exception:
                logger.warning(
                    "_boot_recover_runs: failed to recover RUNNING run %r",
                    run.run_id,
                    exc_info=True,
                )
    except Exception:
        logger.warning("_boot_recover_runs: recovery pass failed", exc_info=True)


def _start_timeout_sweep(
    job_queue: "JobQueue",
    registry: "JobRegistry | None",
    emit: Any,
) -> None:
    """Start a background thread that sweeps WAITING runs past their timeout_at (A4).

    The sweep runs every ``_SWEEP_INTERVAL_SECONDS`` seconds.  For each WAITING
    run with ``wait.timeout_at`` in the past, it enqueues a ``resume_run`` job
    with ``result={"reason": "timeout"}`` so the run wakes and can fail/complete
    gracefully rather than hanging forever.

    The thread is daemonized so it does not prevent process exit.
    """
    import threading as _threading
    import time as _time

    def _sweep_loop() -> None:
        while True:
            _time.sleep(_SWEEP_INTERVAL_SECONDS)
            try:
                _sweep_once(job_queue)
            except Exception:
                logger.debug("_start_timeout_sweep: sweep tick failed", exc_info=True)

    t = _threading.Thread(target=_sweep_loop, name="hachi-timeout-sweep", daemon=True)
    t.start()
    logger.info("_start_timeout_sweep: started (interval=%ds)", _SWEEP_INTERVAL_SECONDS)


# ==========================================
# E5 — Weekly failure-report scheduler
# ==========================================


def _start_eval_report_scheduler(
    store: Any,
    paths: Any,
    settings: Any,
    emit: Any,
) -> None:
    """Start a background daemon thread that generates weekly failure reports (E5).

    Mirrors :func:`_start_timeout_sweep` exactly: daemon thread, sleep loop,
    try/except that logs at debug level and never raises.  The thread wakes at
    most every ``min(interval_seconds, 3600)`` seconds so a 1-week interval does
    not leave the process unkillable for an hour if the thread gets stuck.

    Args:
        store:    :class:`~hachi.core.session_store.SessionStore` already open
                  in the calling ``boot_agent`` scope.
        paths:    :class:`~hachi.core.paths.HachiPaths` from ``get_hachi_paths()``.
        settings: :class:`~hachi.core.settings.EvalReportSettings` validated from
                  config.
        emit:     The ``emit_runtime_event`` callable already in scope in
                  ``boot_agent``.
    """
    import threading as _threading
    import time as _time

    from hachi.core.eval.scheduled_report import maybe_generate_report

    out_dir = paths.state_dir / "eval-reports"
    marker_path = out_dir / ".last_report.json"
    sleep_seconds = min(settings.interval_seconds, 3600)

    def _report_loop() -> None:
        while True:
            _time.sleep(sleep_seconds)
            try:
                maybe_generate_report(
                    store,
                    out_dir=out_dir,
                    marker_path=marker_path,
                    interval_seconds=settings.interval_seconds,
                    limit=settings.limit,
                    emit=lambda name, payload: emit(name, payload),
                )
            except Exception:
                logger.debug("_start_eval_report_scheduler: tick failed", exc_info=True)

    t = _threading.Thread(target=_report_loop, name="hachi-eval-report", daemon=True)
    t.start()
    logger.info(
        "_start_eval_report_scheduler: started (interval=%ds, sleep=%ds)",
        settings.interval_seconds,
        sleep_seconds,
    )


def _sweep_once(
    job_queue: "JobQueue",
    now: "Any | None" = None,
    store: "Any | None" = None,
) -> list[str]:
    """Sweep WAITING runs whose timeout_at is in the past.

    Args:
        job_queue: Queue to enqueue ``resume_run`` wake jobs.
        now:       Override "current time" as a ``datetime.datetime`` (for
                   deterministic tests). When ``None``, uses ``datetime.UTC`` now.
        store:     Optional ``RunStateStore`` override (for testing). When ``None``,
                   uses the default store (platform data dir).

    Returns:
        List of run_ids that were swept (woken with timeout result).
    """
    import datetime

    from hachi.core.runtime.store import RunStateStore
    from hachi.jobs import Job, JobStatus

    _now = now or datetime.datetime.now(datetime.UTC)
    swept: list[str] = []

    try:
        store = store or RunStateStore()
        waiting = store.waiting()
        for run in waiting:
            if run.wait is None or run.wait.timeout_at is None:
                continue
            try:
                timeout_dt = datetime.datetime.fromisoformat(run.wait.timeout_at)
                # Ensure both are offset-aware for comparison.
                if timeout_dt.tzinfo is None:
                    timeout_dt = timeout_dt.replace(tzinfo=datetime.UTC)
            except Exception:
                continue  # malformed timeout_at — skip

            if _now >= timeout_dt:
                try:
                    job = Job(
                        job_id="",
                        name=f"timeout_sweep:{run.run_id[:8]}",
                        handler_name="resume_run",
                        payload={
                            "run_id": run.run_id,
                            "result": {
                                "reason": "timeout",
                                "wait_kind": run.wait.kind.value if run.wait else "unknown",
                                "timeout_at": run.wait.timeout_at if run.wait else None,
                            },
                        },
                        status=JobStatus.PENDING,
                        session_id=run.session_id,
                    )
                    job_queue.enqueue(job)
                    swept.append(run.run_id)
                    logger.info(
                        "_sweep_once: timed-out WAITING run %r swept (timeout_at=%s)",
                        run.run_id,
                        run.wait.timeout_at if run.wait else "?",
                    )
                except Exception:
                    logger.warning(
                        "_sweep_once: failed to enqueue timeout wake for run %r",
                        run.run_id,
                        exc_info=True,
                    )
    except Exception:
        logger.debug("_sweep_once: store read failed", exc_info=True)

    return swept


# ==========================================
# OG Graph helper (used by AgentSession.snapshot_og_graph and the pre-session fallback)
# ==========================================


def og_graph_from_engine(skill_engine: Any) -> dict[str, Any]:
    """Build the ObjectGraph node-graph dict from a :class:`SkillEngine` instance.

    Iterates all parsed OGNode objects from *skill_engine*, computing per-pass
    token estimates (index/dense/full) and classifying each node as ``root``,
    ``skill``, or ``leaf``.

    This is a module-level helper so it can be used both by
    :meth:`AgentSession.snapshot_og_graph` (active session) and by
    :meth:`_InProcessGatewayRuntime.get_og_graph` (pre-session fallback via the
    process-shared services skill engine).

    Args:
        skill_engine: A :class:`~hachi.og_engine.engine.SkillEngine` instance whose
            nodes have already been loaded.

    Returns:
        Dict with key ``nodes`` (list of node dicts) and ``count`` (int).
    """
    from hachi.og_engine.engine import estimate_tokens

    all_nodes = skill_engine.get_all_nodes()

    # Precompute the set of all node names that are referenced by other nodes'
    # ``requires`` lists — used for leaf classification below.
    referenced_names: set[str] = set()
    for node in all_nodes:
        for dep in node.requires:
            referenced_names.add(dep)

    result_nodes: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for node in all_nodes:
        # Multiple skill files can each define a node with the same bare name
        # (e.g. every role brain has an "identity" node). The graph is keyed by
        # bare name and edges reference bare names via ``requires``, so collapse
        # duplicate names to keep node ids unique for the OG Explorer (otherwise
        # the diagram overlaps nodes and React warns about duplicate keys).
        if node.name in seen_names:
            continue
        seen_names.add(node.name)

        # Pass-1 (index) token estimate: name + keywords.
        index_tokens = estimate_tokens(node.name + " " + ", ".join(node.keywords))

        # Pass-2 (dense) token estimate: dense summary block.
        dense_tokens = estimate_tokens(node.dense or node.summary or "")

        # Pass-3 (full) token estimate: sum all heavy content blocks.
        heavy_parts: list[str] = []
        if node.full:
            heavy_parts.append(node.full)
        if node.steps:
            heavy_parts.append("\n".join(node.steps))
        if node.code_blocks:
            heavy_parts.append("\n".join(node.code_blocks.values()))
        if node.table:
            heavy_parts.append(node.table)
        if node.list_items:
            heavy_parts.append("\n".join(node.list_items))
        if node.example:
            heavy_parts.append(node.example)
        if node.assertions:
            heavy_parts.append("\n".join(node.assertions))
        if node.note:
            heavy_parts.append(node.note)
        full_tokens = estimate_tokens("\n".join(heavy_parts))

        # Node kind classification.
        if node.role in {"root", "brain"} or node.name == "brain":
            kind = "root"
        elif not node.requires and node.name not in referenced_names:
            kind = "leaf"
        else:
            kind = "skill"

        result_nodes.append(
            {
                "id": node.name,
                "name": node.name,
                "kind": kind,
                "index": index_tokens,
                "dense": dense_tokens,
                "full": full_tokens,
                "deps": list(node.requires),
            }
        )

    return {"nodes": result_nodes, "count": len(result_nodes)}


# ==========================================
# Boot Sequence
# ==========================================


def _get_or_create_shared_scheduler(shared: Any, schedules_file: "Path") -> Scheduler:
    """Return the one process-wide :class:`Scheduler` over *schedules_file*.

    H3: a private per-session ``Scheduler(ScheduleStore(...))`` meant two
    sessions in the same process each ran their own in-memory copy of the same
    on-disk schedule store — both would independently fire a due schedule
    (double-fire) and each's writes could clobber the other's (lost updates).
    Mirrors the existing ``routing_store``/``event_bus`` lazy-singleton pattern
    on :class:`~hachi.gateway.shared_services.ProcessSharedServices`.
    """
    if getattr(shared, "scheduler", None) is None:
        shared.scheduler = Scheduler(ScheduleStore(schedules_file))
    return shared.scheduler  # type: ignore[no-any-return]


def _apply_observability_settings(
    obs_cfg: Any,
    events_cfg: Any,
) -> None:
    """Wire [observability] config into tracing + metrics at boot (Phase 0 / BB-73).

    Must be called AFTER config is loaded and _events_cfg is parsed — not earlier.
    Never calls load_config() a second time; accepts already-parsed objects.

    Args:
        obs_cfg:    Parsed ObservabilitySettings (enabled, exporter, endpoint, metrics_enabled).
        events_cfg: Parsed EventsSettings (bus_funnel).
    """
    if not obs_cfg.enabled:
        return

    from hachi.core import tracing as _tracing
    from hachi.core.obs import metrics as _metrics

    _tracing.setup_from_config(obs_cfg.exporter, obs_cfg.endpoint)

    if obs_cfg.metrics_enabled:
        _metrics.setup_from_config(obs_cfg.exporter, obs_cfg.endpoint)

    # Phase 5: wire JSON logging when log_format="json".
    log_fmt = getattr(obs_cfg, "log_format", "text")
    if log_fmt == "json":
        from hachi.core.obs.logging_setup import setup_logging as _setup_logging

        _setup_logging(log_format="json")

    if not events_cfg.bus_funnel:
        logger.warning(
            "boot_agent: [observability] enabled=true but [events] bus_funnel=false — "
            "direct spans/metrics/logging still work; sink-based attribute enrichment is "
            "unavailable until bus_funnel is re-enabled."
        )


def boot_agent(
    on_event: Callable[..., None] | None = None,
    on_permission_request: Callable[[PermissionRequest], PermissionDecision] | None = None,
    resume_session_id: str | None = None,
) -> AgentSession:
    """
    Factory function to initialize and boot the Hachi agent.

    Boot Sequence:
        0. Load device permissions (PermissionGate)
        1. Load config and brain.og
        2. Initialize Skill Engine (index all .og files)
        3. Load env credentials + direct integrations
        4. Start MCP servers (with dynamic filesystem paths from permissions)
        5. Build the base system prompt (including permission context)
        6. Register all tools (OS tools gated by PermissionGate)
        7. Initialize Memory
        8. Create the Execution Loop

    Args:
        on_event: Optional callback for real-time UI event rendering.

    Returns:
        An active AgentSession ready to receive user input.
    """
    # Enable OpenTelemetry tracing when HACHI_TRACING is set (no-op otherwise).
    configure_from_env()

    read_models = RuntimeReadModelStore()
    job_queue: JobQueue = SQLiteJobQueue()

    # ------------------------------------------------------------------
    # Slice 2.2 — EventBus funnel (gated behind [events] bus_funnel=true)
    #
    # When the flag is OFF (default): the two closures below are used exactly
    # as before — byte-identical output, zero behavior change.
    #
    # When the flag is ON: an EventBus is instantiated; the same two consumers
    # (read-models append + SSE/TUI surface) are registered as sync subscribers
    # in the same order, so publish() produces identical output by construction.
    # emit_runtime_event / relay_event are then re-bound to publish through the bus.
    # ------------------------------------------------------------------
    _event_bus: Any = None  # EventBus | None; exposed on ProcessSharedServices below

    def emit_runtime_event(name: str, payload: dict[str, Any] | None = None) -> None:
        event = RuntimeEvent(name=name, payload=payload or {}, timestamp=now_iso())
        read_models.append_event(event)
        if on_event:
            on_event(event.name, event.payload)

    def relay_event(event_type: str, payload: dict[str, Any] | None = None) -> None:
        envelopes = adapt_event(event_type, payload)
        for envelope in envelopes:
            event = envelope.primary
            read_models.append_event(event)
            if on_event:
                on_event(event.name, event.payload)
                for alias in envelope.legacy_aliases:
                    on_event(alias, event.payload)

    emit_runtime_event(
        BOOT_PROGRESS,
        {
            "step": "permissions",
            "index": 1,
            "total": 11,
            "message": "Loading device permissions",
        },
    )

    # 0. Load Device Permissions (BEFORE anything else)
    permissions_file = get_workspace_dir() / "device-permissions.og"
    gate = PermissionGate(permissions_file)
    runtime_gate: Any = gate

    if on_permission_request:
        runtime_gate = InteractivePermissionGate(
            base_gate=gate,
            approval_handler=on_permission_request,
            event_emitter=emit_runtime_event,
        )

    # Build the session-scoped ActionApprover for destructive tool actions.
    # Selection priority:
    #   1. TUI path  — on_permission_request is set → HandlerApprover (reuses TUI modal).
    #   2. Gateway/API path — no handler but context exists → RegistryApprover (parks in
    #      the PendingApprovalRegistry so Agent B's /approvals endpoint can resolve it).
    #   3. No human context at all → PolicyApprover (tier-gated: allow unrestricted, deny
    #      guided/sandbox with an actionable message).
    action_approver: ActionApprover
    if on_permission_request is not None:
        action_approver = HandlerApprover(on_permission_request, emit_runtime_event)
    elif isinstance(runtime_gate, InteractivePermissionGate):
        # InteractivePermissionGate without a handler = gateway context.
        action_approver = RegistryApprover(get_approval_registry(), emit_runtime_event)
    else:
        action_approver = PolicyApprover(gate.tier)

    emit_runtime_event(
        BOOT_PROGRESS,
        {
            "step": "config",
            "index": 2,
            "total": 11,
            "message": "Loading config and brain prompt",
        },
    )

    # 1. Load Local Configuration and Brain
    config = load_config()
    brain_prompt = load_brain()

    # Bug 7 boot-reconcile: if settings.toml tier drifts from device-permissions.og tier
    # (e.g. update_permissions() wrote the .og but a crash prevented the in-process gate
    # from being rebuilt), rebuild the gate + approver to match config before any tool
    # registration reads permissions.
    _config_tier = config.get("permissions", {}).get("tier", "")
    if _config_tier and _config_tier != gate.tier:
        try:
            gate = PermissionGate(permissions_file)
            if on_permission_request:
                runtime_gate = InteractivePermissionGate(
                    base_gate=gate,
                    approval_handler=on_permission_request,
                    event_emitter=emit_runtime_event,
                )
            else:
                runtime_gate = gate
            if on_permission_request is not None:
                action_approver = HandlerApprover(on_permission_request, emit_runtime_event)
            elif isinstance(runtime_gate, InteractivePermissionGate):
                action_approver = RegistryApprover(get_approval_registry(), emit_runtime_event)
            else:
                action_approver = PolicyApprover(gate.tier)
            logger.info(
                "boot_agent: rebuilt gate to tier=%r (was %r per .og)",
                gate.tier,
                _config_tier,
            )
        except Exception:
            logger.warning("boot_agent: gate reconcile failed", exc_info=True)

    provider_config = config.get("provider", {})
    model_name = provider_config.get("model") or config.get("agent", {}).get(
        "model", "claude-haiku-4-5"
    )
    max_tokens = config.get("agent", {}).get("max_tokens", 8192)

    # ------------------------------------------------------------------
    # Slice 2.2 — EventBus funnel: rebind emit/relay through the bus when
    # [events] bus_funnel=true.  Back-compat: the two sync subscribers below
    # are identical to the original direct-call code path, registered in the
    # same order, so SSE/TUI output is byte-identical by construction.
    # ------------------------------------------------------------------
    from hachi.core.settings import (
        EvalReportSettings,
        EventsSettings,
        JobsSettings,
        RetentionSettings,
    )

    _events_cfg = EventsSettings.model_validate(config.get("events", {}))
    _jobs_cfg = JobsSettings.model_validate(config.get("jobs", {}))

    # Phase 0 / BB-73: wire [observability] config into tracing + metrics.
    from hachi.core.settings import ObservabilitySettings as _ObsSettings

    _obs_cfg = _ObsSettings.model_validate(config.get("observability", {}))
    _apply_observability_settings(_obs_cfg, _events_cfg)

    if _events_cfg.bus_funnel:
        from hachi.core.event_bus import EventBus

        _event_bus = EventBus(job_queue=job_queue)

        def _read_models_sink(event: RuntimeEvent) -> None:
            read_models.append_event(event)

        def _surface_sink(event: RuntimeEvent) -> None:
            if on_event:
                on_event(event.name, event.payload)

        _event_bus.subscribe("*", _read_models_sink, mode="sync", name="read-models")
        _event_bus.subscribe("*", _surface_sink, mode="sync", name="surface")

        from hachi.core.obs.sink import ObservabilitySink

        _event_bus.subscribe("*", ObservabilitySink().handle, mode="sync", name="observability")

        # Rebind emit_runtime_event to publish through the bus.
        def emit_runtime_event(  # type: ignore[misc]  # noqa: F811
            name: str, payload: dict[str, Any] | None = None
        ) -> None:
            event = RuntimeEvent(name=name, payload=payload or {}, timestamp=now_iso())
            _event_bus.publish(event)

        # Rebind relay_event: publish primary events through the bus (so all
        # subscribers see them) and call on_event directly for legacy aliases
        # (aliases are NOT appended to read_models, matching the original behavior).
        def relay_event(  # type: ignore[misc]  # noqa: F811
            event_type: str, payload: dict[str, Any] | None = None
        ) -> None:
            envelopes = adapt_event(event_type, payload)
            for envelope in envelopes:
                _event_bus.publish(envelope.primary)
                # Aliases: on_event only, never read_models (original behavior preserved).
                if on_event and envelope.legacy_aliases:
                    for alias in envelope.legacy_aliases:
                        on_event(alias, envelope.primary.payload)

        logger.info("boot_agent: EventBus funnel active (bus_funnel=true)")
    # ------------------------------------------------------------------
    # End EventBus funnel wiring
    # ------------------------------------------------------------------

    capability_registry = _build_capability_registry(config)
    enabled_capabilities = [item.id for item in capability_registry.iter_enabled()]
    for capability_id in enabled_capabilities:
        install_optional_skill_pack(capability_id)

    emit_runtime_event(
        BOOT_PROGRESS,
        {
            "step": "skills",
            "index": 3,
            "total": 11,
            "message": "Indexing .og skills",
        },
    )

    # 2. Initialize the Skill Engine (the .og brain).
    # P4-02: reuse the process-level singleton (shared across sessions) if available,
    # to avoid re-indexing all .og files on every session boot.
    from hachi.gateway.shared_services import ProcessSharedServices

    _shared = ProcessSharedServices.get_or_create(config, str(get_hachi_paths().data_dir))
    # Slice 2.2: publish the EventBus on the shared singleton so resume.py and
    # the observability sink (slice 2.3) can find it via ProcessSharedServices.instance().
    if _event_bus is not None:
        _shared.event_bus = _event_bus

    if _shared.skill_engine is not None:
        skill_engine = _shared.skill_engine
    else:
        # Fallback: create a fresh engine (should not happen after the first boot).
        skill_engine = SkillEngine(agent_role="orchestrator")
        skills_dir = get_skills_dir()
        skill_engine.load_directory(skills_dir)

    skill_count = skill_engine.node_count

    emit_runtime_event(
        BOOT_PROGRESS,
        {
            "step": "integrations",
            "index": 4,
            "total": 11,
            "message": "Initializing direct integrations",
        },
    )

    # 3. Initialize the Integration Runtime (direct SMTP/HTTP connections)
    integrations = IntegrationRuntime()
    integration_count = 0

    for node in skill_engine.get_nodes_by_role("env"):
        integrations.load_env_node(node)

    for node in skill_engine.get_nodes_by_role("integration"):
        if integrations.setup_integration(node):
            integration_count += 1

    emit_runtime_event(
        BOOT_PROGRESS,
        {
            "step": "mcp",
            "index": 5,
            "total": 11,
            "message": "Starting MCP servers",
        },
    )

    # 4. Initialize MCP Manager (dynamically configured from permissions)
    # Issue 4: pass the raw config dict so TOML [mcp_servers] entries are also started.
    mcp_manager = MCPManager()
    _configure_mcp_servers(skill_engine, mcp_manager, gate, emit_runtime_event, config=config)
    mcp_tool_count = mcp_manager.total_tool_count

    emit_runtime_event(
        BOOT_PROGRESS,
        {
            "step": "native_integrations",
            "index": 6,
            "total": 11,
            "message": "Resolving optional capabilities",
        },
    )

    emit_runtime_event(
        BOOT_PROGRESS,
        {
            "step": "prompt",
            "index": 7,
            "total": 11,
            "message": "Building system prompt",
        },
    )

    # 5. Collect stable-base ingredients (prompt assembled after tool registration below)
    total_tools = integration_count + mcp_tool_count
    _permission_block = runtime_gate.get_system_prompt_injection()
    capability_snapshot = capability_registry.status_snapshot()
    _capability_block = str(capability_snapshot) if capability_snapshot else ""

    emit_runtime_event(
        BOOT_PROGRESS,
        {
            "step": "llm",
            "index": 8,
            "total": 11,
            "message": "Initializing LLM client",
        },
    )

    # 6. Initialize the LLM Provider
    secret_store = create_default_secret_store()
    client = create_llm_client(provider_config, secret_store=secret_store, max_tokens=max_tokens)

    # Sub-agents reuse the SAME resolved provider credentials as the main agent so
    # delegation never fails with "ANTHROPIC_API_KEY must be provided". For Anthropic
    # we drop to a cheaper model to keep delegation cost-aware; other providers keep
    # the user's configured model.
    sub_agent_provider = dict(provider_config)
    if str(provider_config.get("kind", "anthropic")).lower() == "anthropic":
        sub_agent_provider["model"] = DEFAULT_SUB_AGENT_MODEL
    sub_agent_client = create_llm_client(
        sub_agent_provider, secret_store=secret_store, max_tokens=4096
    )

    # 6b. Build routing infrastructure (behind [routing] flag; absent = back-compat).
    # ProviderRegistry → ModelRegistry → RoutingPolicy → ModelRouter.
    # When [routing] is absent, the policy synthesises a single-model-for-all-caps
    # mapping and default_client() returns the existing `client` unchanged.
    _model_router = None
    _provider_registry = None
    try:
        from hachi.core.providers.registry import ProviderRegistry
        from hachi.core.resilience import RetryPolicy
        from hachi.core.routing.policy import RoutingPolicy
        from hachi.core.routing.registry import ModelRegistry
        from hachi.core.routing.router import ModelRouter
        from hachi.core.settings import ResolvedConfig

        _resolved_cfg = ResolvedConfig.model_validate(config)
        _provider_registry = ProviderRegistry.from_config(_resolved_cfg, secret_store)
        _model_registry = ModelRegistry.build(_resolved_cfg, _provider_registry)
        _routing_policy = RoutingPolicy.from_config(_resolved_cfg)
        # Apply auto-policy if requested (amendment A1).
        if _routing_policy.auto:
            _routing_policy = _routing_policy.derive_auto_policy(_model_registry)
        _retry_policy = RetryPolicy.from_config(_resolved_cfg)
        _model_router = ModelRouter(
            registry=_model_registry,
            policy=_routing_policy,
            providers=_provider_registry,
            resilience=_retry_policy,
        )

        # Phase 3: ensure RoutingConfigStore exists on the shared singleton and holds
        # the boot snapshot so sessions can adopt future hot-reload updates at turn
        # boundaries without a restart.
        if getattr(_shared, "routing_store", None) is None:
            from hachi.core.routing.snapshot import RoutingSnapshot
            from hachi.gateway.routing_store import RoutingConfigStore

            _rcs = RoutingConfigStore()
            _boot_snap = RoutingSnapshot(
                registry=_model_registry,
                policy=_routing_policy,
                resilience=_retry_policy,
                version=0,
                source="boot",
            )
            _rcs.init(_boot_snap)
            _shared.routing_store = _rcs

        logger.info(
            "Routing boot: %d models registered; default=%s; auto=%s",
            len(_model_registry.all()),
            _routing_policy.default_model,
            _routing_policy.auto,
        )
        # Cost-governance guard (BB-30): surface the silent "every chat turn routed to
        # the priciest model" trap loudly at boot instead of letting it hide in the
        # routing table. Never changes routing — an explicit choice is respected.
        for _cost_warning in _routing_policy.costly_capability_warnings(_model_registry):
            logger.warning(_cost_warning)
            emit_runtime_event("cost.routing_warning", {"message": _cost_warning})
    except Exception:
        logger.debug(
            "Routing boot: failed to initialise routing layer; falling back to direct client",
            exc_info=True,
        )
        _model_router = None

    # Shared per-session token/cost tracker — used by the main loop AND threaded
    # into delegated sub-agents so their spend is included in the session total.
    # Pass the model registry so registry-backed pricing is used (registry seeds from
    # cost.py values, so no drift).
    _registry_for_cost = (
        _model_router._registry  # type: ignore[union-attr]
        if _model_router is not None
        else None
    )
    cost_tracker = CostTracker(registry=_registry_for_cost)

    emit_runtime_event(
        BOOT_PROGRESS,
        {
            "step": "memory",
            "index": 9,
            "total": 11,
            "message": "Initializing memory and persistence",
        },
    )

    # 7. Initialize the Memory Manager (Moved up so Vault can bind to it)
    # G3-T6: pass the shared LLM client so background memory ops (fact extraction,
    # sliding-window summary) reuse the already-open HTTP/TLS connection pool
    # instead of constructing a new AnthropicClient on every background job.
    memory = MemoryManager(max_active_messages=30, job_queue=job_queue, llm_client=client)

    emit_runtime_event(
        BOOT_PROGRESS,
        {
            "step": "tools",
            "index": 10,
            "total": 11,
            "message": "Registering tools",
        },
    )

    # 8. Build infrastructure objects needed for tool registration.
    # These are created before the TOOL_SPECS table so BootDeps can reference
    # fully-constructed objects rather than lazy placeholders.
    tool_registry = ToolRegistry()
    # File-change checkpoints give the user an undo for agent edits (rollback_changes tool).
    checkpoint_manager = CheckpointManager(get_hachi_paths().checkpoints_dir)
    # Proactive scheduling (cron/interval/once) — persisted across restarts.
    # H3: shared across sessions in this process (see _get_or_create_shared_scheduler).
    scheduler = _get_or_create_shared_scheduler(_shared, get_hachi_paths().schedules_file)
    # Initialize Session Store (Phase 3: cross-session persistence)
    session_store = SessionStore()

    # Initialize and register the Long-Term Memory Vault (backend-selectable).
    # backend="chroma" (default) — ChromaDB persistent vault, full semantic tools.
    # backend="in_memory" — lightweight in-process store, no ChromaDB required;
    #   semantic memory tools degrade gracefully (return an informational message).
    from hachi.core.settings import MemorySettings

    _raw_memory = config.get("memory", {})
    _memory_settings = MemorySettings.model_validate(_raw_memory)

    # P4-02: reuse shared vault when already initialised (avoids opening a new Chroma
    # PersistentClient per session — up to 100 clients per process before this fix).
    if _shared.vault is not None:
        vault: MemoryVault | None = _shared.vault
        _provider = ChromaMemoryProvider(vault=vault)
    else:
        _provider = resolve_provider(_memory_settings)
        # Issue 10: pass the recall-distance threshold and core-memory cap from the
        # [memory] config into the ChromaDB vault so settings.toml actually controls
        # retrieval behaviour. Non-Chroma backends keep the plain initialize() signature.
        if isinstance(_provider, ChromaMemoryProvider):
            _provider.initialize(
                brain_dir=str(get_hachi_paths().data_dir),
                recall_distance_max=_memory_settings.recall_distance_max,
                core_memory_max_entries=_memory_settings.core_memory_max_entries,
                decay_half_life_days=_memory_settings.decay_half_life_days,
            )
        else:
            _provider.initialize(brain_dir=str(get_hachi_paths().data_dir))
        vault = _provider.vault if isinstance(_provider, ChromaMemoryProvider) else None
    memory.set_vault(vault)

    # P4-06: M4 — fts5_only backend forces graph=True (files are canonical; no Chroma needed)
    from hachi.core.memory_provider import FTS5MemoryProvider

    _is_fts5_only = isinstance(_provider, FTS5MemoryProvider)
    _use_graph = _memory_settings.graph or _is_fts5_only

    # P2-04: M0 — attach FTS5 graph index when memory.graph=true (or fts5_only backend)
    # P4-02: reuse the shared graph_index when the process singleton already has one.
    _graph_index = None
    if _use_graph and (vault is not None or _is_fts5_only):
        if _shared.graph_index is not None:
            _graph_index = _shared.graph_index
            # Attach to vault if not already attached (idempotent guard).
            if vault is not None and getattr(vault, "_graph_index", None) is None:
                vault.attach_graph_index(_graph_index)
            if _is_fts5_only:
                _provider.attach_graph_index(_graph_index)
        else:
            try:
                from hachi.core.memory_index import MemoryIndex

                _paths = get_hachi_paths()
                _graph_index = MemoryIndex(
                    memory_dir=_paths.memory_dir,
                    db_path=_paths.memory_index_db,
                )
                _graph_index.refresh()
                if vault is not None:
                    vault.attach_graph_index(_graph_index)
                if _is_fts5_only:
                    _provider.attach_graph_index(_graph_index)
                logger.info(
                    "MemoryIndex: %d nodes indexed from %s",
                    _graph_index.node_count,
                    _paths.memory_dir,
                )
            except Exception:
                logger.debug("P2-04: MemoryIndex init failed; graph recall disabled", exc_info=True)

    # P2-05: M1 — MemoryWriter for typed-node write path (always on when graph flag set)
    # P4-02: reuse the shared memory_writer when available.
    if _use_graph:
        if _shared.memory_writer is not None:
            memory.set_memory_writer(_shared.memory_writer)
            if _is_fts5_only:
                _provider.attach_memory_writer(_shared.memory_writer)
        else:
            try:
                from hachi.core.memory_writer import MemoryWriter

                _paths = get_hachi_paths()
                _memory_writer = MemoryWriter(
                    memory_dir=_paths.memory_dir,
                    graph_index=_graph_index,
                )
                memory.set_memory_writer(_memory_writer)
                if _is_fts5_only:
                    _provider.attach_memory_writer(_memory_writer)
                logger.info("MemoryWriter: M1 write path active (memory_dir=%s)", _paths.memory_dir)
            except Exception:
                logger.debug(
                    "P2-05: MemoryWriter init failed; falling back to Chroma-only", exc_info=True
                )

    # Universal REST adapter for .og-defined APIs; built here so the rest_apis spec
    # can close over it without a circular BootDeps reference.
    credential_vault = CredentialVault(secret_store=secret_store)
    rest_adapter = UniversalRestAdapter(tool_registry, credential_vault)

    # 8b. Declarative tool registration — ordering constraints are explicit in the
    # table below, not buried in prose comments.
    # P4-01: per-session write-target lease manager (prevents concurrent delegation conflicts).
    from hachi.core.lease_manager import LeaseManager

    _lease_manager = LeaseManager()

    # Per-session safety caps (0 = unlimited): stop a runaway loop from draining the
    # user's API budget. Read from the optional [limits] config section, else env vars.
    # Computed here (before _make_deps/registration) so S2 can thread the SAME caps
    # down to register_delegation_tools -> every sub-agent's own ExecutionLoop —
    # a delegated sub-agent must never be able to silently outspend what the user
    # configured for the parent session.
    limits_cfg = config.get("limits", {}) if isinstance(config.get("limits"), dict) else {}
    max_daily_cost_usd = _coerce_float(
        limits_cfg.get("max_daily_cost_usd"), os.environ.get("HACHI_MAX_DAILY_COST_USD")
    )
    max_session_cost_usd = _coerce_float(
        limits_cfg.get("max_session_cost_usd"), os.environ.get("HACHI_MAX_SESSION_COST_USD")
    )
    max_session_tokens = _coerce_int(
        limits_cfg.get("max_session_tokens"), os.environ.get("HACHI_MAX_SESSION_TOKENS")
    )
    max_turn_cost_usd = _coerce_float(
        limits_cfg.get("max_turn_cost_usd"), os.environ.get("HACHI_MAX_TURN_COST_USD")
    )
    max_turn_tokens = _coerce_int(
        limits_cfg.get("max_turn_tokens"), os.environ.get("HACHI_MAX_TURN_TOKENS")
    )

    def _make_deps() -> BootDeps:
        return BootDeps(
            gate=runtime_gate,
            skill_engine=skill_engine,
            checkpoint_manager=checkpoint_manager,
            vault=vault,
            job_queue=job_queue,
            session_store=session_store,
            integrations=integrations,
            mcp_manager=mcp_manager,
            scheduler=scheduler,
            relay_event=relay_event,
            sub_agent_llm=sub_agent_client,
            cost_tracker=cost_tracker,
            provider_kind=str(provider_config.get("kind", "anthropic")),
            secret_store=secret_store,
            tool_registry=tool_registry,
            lease_manager=_lease_manager,
            router=_model_router,
            provider_registry=_provider_registry,
            session_llm=client,
        )

    TOOL_SPECS: list[ToolSpec] = [
        ToolSpec(
            name="os",
            register_fn=lambda d: register_os_tools(
                d.tool_registry, d.gate, checkpoints=d.checkpoint_manager
            ),
        ),
        ToolSpec(
            name="og",
            register_fn=lambda d: register_og_tools(d.tool_registry, d.skill_engine),
        ),
        ToolSpec(
            # Lazy tool-loading meta-tool (core): lets the model unlock optional groups.
            name="use_tools",
            register_fn=lambda d: d.tool_registry.register(
                USE_TOOLS_SCHEMA, _make_use_tools(d.tool_registry), group="core"
            ),
        ),
        ToolSpec(name="workflow", register_fn=lambda d: register_workflow_tools(d.tool_registry)),
        ToolSpec(
            name="sandbox",
            register_fn=lambda d: register_sandbox_tools(d.tool_registry, d.gate),
        ),
        ToolSpec(
            # Headless browser automation (optional: needs `hachi-og[browser]` + a browser
            # binary). The controller is lazy — no browser launches until the agent first calls
            # browse_web. Return value is captured from registration_results["browser"].
            name="browser",
            register_fn=lambda d: register_browser_tools(d.tool_registry, d.gate),
        ),
        ToolSpec(
            # Outbound messaging (Slack/Discord/WhatsApp). Credentials resolve lazily at call
            # time, so these register cleanly even with no token set (return a "not configured"
            # hint until then).
            name="messaging",
            register_fn=lambda d: register_messaging_tools(d.tool_registry),
        ),
        ToolSpec(
            # Desktop push notifications + SMTP email digests. Zero config for desktop;
            # email requires HACHI_SMTP_* env vars (degrades gracefully if unset).
            name="notifications",
            register_fn=lambda d: register_notification_tools(d.tool_registry),
        ),
        ToolSpec(
            # Vision input — view local images.  Capability-routed (doc 20 §3):
            # session model with VISION → inline; else router.select(VISION) → routed;
            # else graceful text fallback.
            name="vision",
            register_fn=lambda d: register_vision_tools(
                d.tool_registry,
                d.gate,
                provider_kind=d.provider_kind,
                session_client=d.session_llm,
                router=d.router,
            ),
        ),
        ToolSpec(
            # Voice input — transcribe/synthesize audio.  Provider resolved via
            # ProviderRegistry.get_speech() (doc 19 §3); falls back to SpeechToText.from_env()
            # when registry is unavailable (back-compat).
            name="voice",
            register_fn=lambda d: register_voice_tools(
                d.tool_registry, d.gate, provider_registry=d.provider_registry
            ),
        ),
        ToolSpec(
            # Web search + URL extraction (Initiative A — Search Platform, doc 17).
            # Registered only when a SearchProvider is available in the ProviderRegistry.
            # Degrades gracefully to a no-op when no provider / key is configured.
            name="search",
            register_fn=lambda d: _register_search_if_available(d),
        ),
        ToolSpec(
            # File / attachment platform (Initiative E, Slice 2.4).
            # attach_file, list_attachments, read_attachment, search_attachments.
            # Permission-gated like os_tools; extraction runs as durable job handler.
            name="files",
            register_fn=lambda d: register_file_tools(d.tool_registry, d.gate),
        ),
        ToolSpec(
            # Google Workspace (Gmail, Calendar, Drive, Docs, Sheets, Contacts, Meet, Tasks).
            # Only mounted when GOOGLE_CLIENT_ID is set; degrades to a friendly stub otherwise.
            # The session-scoped action_approver gates destructive leaf tools (send_email,
            # trash_file, etc.) through the appropriate human-approval path.
            name="google",
            register_fn=lambda d: register_google_tools(d.tool_registry, approver=action_approver),
        ),
        ToolSpec(
            # Presentation generation — build .pptx from natural language.
            name="presentation",
            register_fn=lambda d: register_presentation_tools(d.tool_registry, d.gate),
        ),
        ToolSpec(
            name="schedule",
            register_fn=lambda d: register_schedule_tools(d.tool_registry, d.scheduler),
        ),
        ToolSpec(
            # Register Universal REST APIs parsed from .og files.
            name="rest_apis",
            register_fn=lambda d: [
                rest_adapter.register_node_apis(node) for node in d.skill_engine.get_all_nodes()
            ],
        ),
        ToolSpec(
            name="memory",
            register_fn=lambda d: register_memory_tools(
                d.tool_registry, d.vault, job_queue=d.job_queue
            ),
        ),
        ToolSpec(
            name="session",
            register_fn=lambda d: register_session_tools(d.tool_registry, d.session_store),
        ),
        ToolSpec(
            name="integration_tools",
            register_fn=lambda d: d.integrations.register_tools(d.tool_registry),
        ),
        ToolSpec(
            name="mcp_tools",
            register_fn=lambda d: d.mcp_manager.register_tools(d.tool_registry),
        ),
        ToolSpec(
            # Agent-accessible configuration + MCP management tools.
            # Registered AFTER MCP manager so list_mcp_servers sees all nodes.
            name="config",
            after={"mcp_tools"},
            register_fn=lambda d: register_config_tools(d.tool_registry, gate=d.gate),
        ),
        ToolSpec(
            # MUST be LAST — needs full parent registry.
            # Pass skill_engine so sub-agent OG tools are rebound to a role-scoped
            # engine view, preventing sub-agents from reading scope=orchestrator nodes.
            name="delegation",
            last=True,
            register_fn=lambda d: register_delegation_tools(
                d.tool_registry,
                d.gate,
                d.relay_event,
                d.vault,
                job_queue=d.job_queue,
                sub_agent_llm=d.sub_agent_llm,
                cost_tracker=d.cost_tracker,
                skill_engine=d.skill_engine,
                lease_manager=d.lease_manager,
                # S2: sub-agents inherit the parent session's configured budget caps
                # by default so a delegated task can never silently outspend them.
                max_cost_usd=max_session_cost_usd,
                max_tokens=max_session_tokens,
                max_cost_per_turn=max_turn_cost_usd,
                max_tokens_per_turn=max_turn_tokens,
            ),
        ),
    ]

    deps = _make_deps()
    registrar = ToolRegistrar()
    registration_results = registrar.install(TOOL_SPECS, deps)
    browser_controller = registration_results.get("browser")

    # Register native capability tools lazily, with setup stubs for incomplete states.
    native_registration_count = 0
    for descriptor in capability_registry.iter_enabled():
        if descriptor.kind != "native_integration":
            continue
        if not descriptor.available or not descriptor.configured:
            _register_capability_setup_stub(tool_registry, descriptor)
            continue

        try:
            instance = capability_registry.instantiate(descriptor.id)
        except Exception as exc:
            _register_capability_setup_stub(tool_registry, descriptor)
            emit_runtime_event(
                MCP_SERVER_FAILED,
                {
                    "server": descriptor.id,
                    "reason": f"capability init failed: {exc}",
                },
            )
            continue

        if isinstance(instance, tuple):
            for sub_instance in instance:
                if hasattr(sub_instance, "register_tools"):
                    sub_instance.register_tools(tool_registry)
                    native_registration_count += 1
        elif hasattr(instance, "register_tools"):
            instance.register_tools(tool_registry)
            native_registration_count += 1

    # Classify tools into lazy-loading groups now that every tool is registered.
    # Per-skill REST tools were already tagged at registration (group == skill name);
    # classify() leaves those intact and stamps the rest.
    tool_registry.classify(
        core_names=set(_CORE_TOOL_NAMES),
        group_by_name=_GROUP_BY_TOOL_NAME,
        # Google integration tools all share the "google_" prefix → lazy "google" group.
        prefix_groups={"google_": "google"},
        default="integrations",
    )

    # BB-32: MCP tools land in "integrations" (never activated) because classify()
    # doesn't know MCP server names at call time.  Reclassify them into "mcp" so
    # activating that group exposes them to the LLM.
    _mcp_prefixes = {f"{name}_": "mcp" for name in mcp_manager._servers}
    _has_live_mcp = bool(_mcp_prefixes)
    if _has_live_mcp:
        tool_registry.reclassify_by_prefix(_mcp_prefixes)

    # Tell the model which optional domain groups it can unlock on demand. Skill
    # groups are omitted here — load_skill auto-activates those — so this lists only
    # the static domain groups (e.g. schedule, sandbox, browser, workflow).
    skill_group_names = {node.name for node in skill_engine.get_all_nodes()}
    domain_groups = sorted(tool_registry.available_groups() - {"core"} - skill_group_names)

    # 5.5 Assemble the stable base system prompt via PromptComposer (single call site).
    system_prompt = build_stable_base(
        brain_text=brain_prompt,
        skill_count=skill_count,
        integration_count=total_tools,
        permission_block=_permission_block,
        capability_block=_capability_block,
        tool_groups=list(domain_groups) if domain_groups else None,
    )

    emit_runtime_event(
        BOOT_PROGRESS,
        {
            "step": "loop",
            "index": 11,
            "total": 11,
            "message": "Finalizing execution loop",
        },
    )

    # 9. Instantiate the Brain Loop (cost_tracker created earlier, shared with sub-agents)
    # (max_daily_cost_usd / max_session_cost_usd / max_session_tokens / max_turn_cost_usd /
    # max_turn_tokens were computed earlier, before _make_deps, so S2 could thread them
    # into register_delegation_tools as well.)
    # When the router is available, default_client() returns the configured model's
    # resilient client; the loop's llm_client is unchanged (back-compat).
    _loop_client = client
    if _model_router is not None:
        try:
            _loop_client = _model_router.default_client()
            # Issue 11/9: routing succeeded — report the routed default model as the
            # session model so the "last used model" badge and /spend reflect what
            # actually runs (previously these reported provider.model = the primary).
            model_name = _routing_policy.default_model or model_name
        except Exception as _route_exc:
            # The routed default model's provider is not usable (missing API key,
            # unknown/misspelled model id, etc.). Fall back to the primary client but
            # do NOT misreport the model — keep model_name as the primary provider's
            # model and warn loudly so the user learns their selection didn't take effect.
            logger.warning(
                "Routing: requested default model %r is not usable (%s) — falling back "
                "to %r. Configure that provider's API key or fix the model id in "
                "[routing]/[providers].",
                getattr(_routing_policy, "default_model", "?"),
                _route_exc,
                model_name,
            )
            _loop_client = client

    loop = ExecutionLoop(
        llm_client=_loop_client,
        registry=tool_registry,
        memory=memory,
        base_system_prompt=system_prompt,
        on_event=relay_event,
        skill_engine=skill_engine,
        cost_tracker=cost_tracker,
        max_cost_usd=max_session_cost_usd,
        max_tokens=max_session_tokens,
        max_cost_per_turn=max_turn_cost_usd,
        max_tokens_per_turn=max_turn_tokens,
        router=_model_router,
        routing_store=getattr(_shared, "routing_store", None),
    )

    # BB-32: if live MCP servers were present at boot, persist "mcp" as an
    # always-on group so MCP tools are visible to the LLM every turn without
    # requiring a use_tools call.
    if _has_live_mcp:
        loop._persistent_groups.add("mcp")

    # 10. Create the Session
    session = AgentSession(
        loop,
        skill_engine,
        memory,
        integrations,
        mcp_manager,
        runtime_gate,
        model_name=model_name,
        event_emitter=emit_runtime_event,
        read_models=read_models,
        job_queue=job_queue,
    )
    session.set_vault(vault)
    session.set_session_store(session_store, model=model_name)
    # P1-3: propagate the daily cap to the session so _daily_cap_exceeded() can enforce it.
    if max_daily_cost_usd:
        session._max_daily_cost_usd = max_daily_cost_usd
    if resume_session_id:
        try:
            seeded = session.resume_from_session(resume_session_id)
            emit_runtime_event(
                SESSION_RESUMED,
                {
                    "source_session_id": resume_session_id,
                    "messages_restored": seeded,
                },
            )
        except Exception:
            # HIGH-012: resume failures must be visible even though boot continues.
            logger.warning(
                "boot_agent: session resume from %s failed; starting fresh",
                resume_session_id,
                exc_info=True,
            )
    session._sub_agent_client = sub_agent_client  # closed on shutdown alongside the main client
    session._browser_controller = browser_controller  # closed on shutdown (no-op if never used)
    # M1: episodic recall top-k from memory settings (0 = disabled).
    session._episodic_top_k = _memory_settings.episodic_top_k
    # Stage-C: graph recall enabled flag from memory settings (default True).
    session._graph_recall = _memory_settings.graph_recall
    # Slice 2.2: activate durable title job path when the flag is on.
    if _jobs_cfg.durable_handlers:
        session._durable_title = True
    # BB-11: stash for live search-tool reload without restart.
    session._provider_registry = _provider_registry
    session._secret_store = secret_store

    # ------------------------------------------------------------------
    # JobRegistry activation
    #
    # The four named handlers are pure, self-contained, and degrade gracefully
    # (they return a "skipped:..."/"error:..." status instead of raising when a
    # service is unavailable).  MemoryManager ALWAYS enqueues fact extraction via
    # handler_name="extract_fact" (see memory.py), so the registry MUST exist even
    # when durable_handlers is off — otherwise every fact-extraction job fails with
    # "no callable func and handler_name 'extract_fact' is not in registry".
    #
    # Handler registration is therefore unconditional.  Only the durable-RUN
    # machinery (the WaitConditionRegistry + restart recovery + timeout sweep)
    # stays gated behind [jobs] durable_handlers=true.
    # ------------------------------------------------------------------
    from hachi.core.runtime.job_handlers import (
        handle_auto_extract,
        handle_extract_fact,
        handle_generate_title,
        handle_resume_run,
    )

    _job_registry: JobRegistry = JobRegistry()
    _job_registry.register("extract_fact", handle_extract_fact)
    _job_registry.register("generate_title", handle_generate_title)
    _job_registry.register("resume_run", handle_resume_run)
    _job_registry.register("auto_extract", handle_auto_extract)

    if _jobs_cfg.durable_handlers:
        from hachi.core.runtime.waits import get_wait_registry

        # Expose the WaitConditionRegistry on the process singleton so the
        # scheduler sweep and /runs/{id}/wake endpoint share one registry.
        _wait_registry = get_wait_registry()
        _shared.wait_registry = _wait_registry

        # A6 (§6): restart recovery — re-arm WAITING runs; transition crash-RUNNING runs.
        _boot_recover_runs(job_queue, _job_registry, _wait_registry, emit_runtime_event)

        logger.info("boot_agent: durable-run machinery active (durable_handlers=true)")
    else:
        logger.info("boot_agent: JobRegistry active with 4 handlers (durable-run machinery off)")

    # Initiative E: wire reactive file.uploaded → auto_extract via EventBus.
    #
    # Decoupled from durable_handlers so reactive extraction fires whenever the
    # bus is active, regardless of whether the durable job registry is on.
    #
    # Dispatch mode:
    #   async  — when durable_handlers is on: runs as a durable JobRegistry job
    #            (survives restarts; the handler name "auto_extract" is registered
    #            above in _job_registry).
    #   sync   — when durable_handlers is off: runs inline on the file-upload
    #            thread.  NOT on the turn hot path; acceptable for light workloads.
    #            The handler degrades gracefully (returns a status string on error).
    #
    # When the bus is off (_event_bus is None) no subscription is created; the
    # FilePipeline event fires into the void and extraction is triggered manually
    # or via the standalone gateway POST /files route.
    if _event_bus is not None:
        from hachi.core.runtime.job_handlers import handle_auto_extract as _handle_auto_extract
        from hachi.core.runtime_events import FILE_UPLOADED as _FILE_UPLOADED_EVT

        if _jobs_cfg.durable_handlers:
            # Async: JobRegistry routes handler_name="auto_extract" to the callable.
            _event_bus.subscribe(
                _FILE_UPLOADED_EVT,
                _handle_auto_extract,  # type: ignore[arg-type]
                mode="async",
                name="auto_extract",
            )
            _auto_extract_mode = "async (durable)"
        else:
            # Sync inline: wrap the event into kwargs the handler expects.
            def _auto_extract_sync_wrapper(event: RuntimeEvent) -> None:  # noqa: E306
                """Inline sync adapter: unpacks RuntimeEvent into handle_auto_extract kwargs."""
                _handle_auto_extract(
                    event_name=event.name,
                    event_payload=event.payload,
                    event_timestamp=event.timestamp,
                    event_sequence=0,
                )

            _event_bus.subscribe(
                _FILE_UPLOADED_EVT,
                _auto_extract_sync_wrapper,
                mode="sync",
                name="auto_extract",
            )
            _auto_extract_mode = "sync (inline)"

        logger.info(
            "boot_agent: file.uploaded → auto_extract subscription registered (mode=%s)",
            _auto_extract_mode,
        )

    # Start the resident job worker so background jobs (fact extraction, prefetch,
    # title generation) execute without blocking the turn path.
    # BB-72: also pass session_store + checkpoint_manager so the idle sweep can
    # prune idempotency keys, interaction_log, daily_spend, and checkpoint files.
    _retention_cfg = RetentionSettings.model_validate(config.get("retention") or {})
    _job_worker_for_session = JobWorker(
        job_queue, on_job_event=emit_runtime_event, registry=_job_registry
    )
    _resident_worker = ResidentWorkerThread(
        _job_worker_for_session,
        session_store=session_store,
        checkpoint_manager=checkpoint_manager,
        sweep_interval_seconds=_retention_cfg.sweep_interval_seconds,
        jobs_retention_hours=_retention_cfg.jobs_retention_hours,
        interaction_log_retention_days=_retention_cfg.interaction_log_retention_days,
        idempotency_key_retention_hours=_retention_cfg.idempotency_key_retention_hours,
        daily_spend_retention_days=_retention_cfg.daily_spend_retention_days,
        checkpoint_retention_days=_retention_cfg.checkpoint_retention_days,
    )
    _resident_worker.start()
    session.set_resident_worker(_resident_worker)

    # Start the background schedule runner now that session.chat() is available.
    # The fire callback calls session.chat() so the agent executes the task and
    # delivers the result via the session's normal event pipeline.
    def _fire_schedule(s: Schedule) -> None:
        job_id = f"schedule:{s.schedule_id}:{uuid.uuid4().hex[:8]}"
        emit_runtime_event(
            "job.started",
            {"job_id": job_id, "job_name": s.name, "kind": "schedule", "label": s.name},
        )
        try:
            result_text = session.chat(s.task, surface="schedule")
            # UC-RSCH-002: the resident runner must honor deliver_to/webhook_url too
            # (previously only `hachi schedule run-due` delivered). deliver_result
            # redacts outbound secrets before any webhook POST.
            deliver_result(s, result_text)
            emit_runtime_event(
                "job.completed",
                {"job_id": job_id, "job_name": s.name, "kind": "schedule", "label": s.name},
            )
        except Exception:
            import logging as _logging

            _logging.getLogger(__name__).exception("Schedule fire error for '%s'", s.name)
            emit_runtime_event(
                "job.failed",
                {
                    "job_id": job_id,
                    "job_name": s.name,
                    "kind": "schedule",
                    "label": s.name,
                    "status": "failed",
                },
            )

    _schedule_runner = ScheduleRunner(scheduler, fire=_fire_schedule)
    # H3: the shared Scheduler object still races if two independent runner
    # threads tick it concurrently — only the first session in this process
    # starts the runner; later sessions reuse it without a second thread.
    if not getattr(_shared, "scheduler_runner_started", False):
        _schedule_runner.start()
        _shared.scheduler_runner_started = True
    session._schedule_runner = _schedule_runner  # stopped in shutdown()
    session._scheduler = scheduler  # P4-05: exposed for companion web UI

    # ------------------------------------------------------------------
    # Slice 2.2 — A4: scheduler timeout sweep for WAITING runs.
    # When durable_handlers=true, attach a periodic sweep to the existing
    # ScheduleRunner tick by enqueuing a "sweep_waiting_runs" job on each tick.
    # The sweep is implemented as a standalone function (not a Schedule entry)
    # so it runs every ScheduleRunner interval without cluttering the user's
    # schedule list.  Implementation: a resident helper thread that wakes every
    # SWEEP_INTERVAL seconds and sweeps timed-out runs.
    # ------------------------------------------------------------------
    if _jobs_cfg.durable_handlers:
        _start_timeout_sweep(job_queue, _job_registry, emit_runtime_event)

    # ------------------------------------------------------------------
    # E5 — Weekly failure-report scheduler (opt-in, default off).
    # Mirrors _start_timeout_sweep: daemon thread, sleep loop, never raises.
    # Gated by [eval_reports] enabled = true in settings.toml.
    # ------------------------------------------------------------------
    _eval_cfg = EvalReportSettings.model_validate(config.get("eval_reports", {}))
    if _eval_cfg.enabled:
        _start_eval_report_scheduler(
            session_store, get_hachi_paths(), _eval_cfg, emit_runtime_event
        )

    emit_runtime_event(
        BOOT_COMPLETE,
        {
            "skills": skill_count,
            "integrations": integration_count,
            "native_integrations": native_registration_count,
            "capabilities": capability_snapshot,
            "mcp_servers": mcp_manager.server_count,
            "mcp_tools": mcp_tool_count,
        },
    )

    return session
