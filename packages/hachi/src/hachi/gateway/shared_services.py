"""shared_services.py — P4-02: process-level service singletons.

Rationale (01-architecture-review.md §R13 / TD-8):
  Each gateway session currently boots a *complete* runtime — MCP subprocess
  servers, Chroma client, full .og skill index — even though these are
  read-mostly and fully shareable.  With the 100-session cap that is up to
  100 MCP server sets per process.

Shared across all sessions (one per process):
  - SkillEngine  — indexes all .og files; read-mostly, thread-safe counters.
  - MCPManager   — manages MCP subprocess servers; sessions share the pool.
  - MemoryVault  — Chroma PersistentClient; handles concurrent access natively.
  - MemoryIndex  — FTS5 index over memory/*.og files (when memory.graph=true).

Per-session only:
  - ExecutionLoop, MemoryManager, ConversationMemory, CostTracker, session state.

Usage::

    shared = ProcessSharedServices.get_or_create(config, brain_dir)
    # re-call with same config → returns the same instance (no re-init)
    same  = ProcessSharedServices.get_or_create(config, brain_dir)
    assert shared is same

    # A caller requesting a *different* memory backend gets its own instance,
    # keyed by a (brain_dir, memory_backend, memory_graph) fingerprint.
    other = ProcessSharedServices.get_or_create(alt_config, brain_dir)
    assert other is not shared
"""

from __future__ import annotations

import atexit
import hashlib
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
# ADV-024: keyed by config fingerprint so distinct configs get distinct instances.
_INSTANCES: dict[str, ProcessSharedServices] = {}
# Registered once (lazily, under _LOCK) so the shared vault's Chroma WAL is flushed
# at process exit without any individual session closing the shared vault.
_ATEXIT_REGISTERED = False


def _config_fingerprint(config: dict[str, Any], brain_dir: str) -> str:
    """Return a stable cache key for a (config, brain_dir) pair.

    Only the fields that affect *shared* service construction are included:
    ``memory.backend``, ``memory.graph``, and ``brain_dir``.  All other
    per-session config keys are irrelevant to the singleton.
    """
    memory = config.get("memory", {}) if isinstance(config.get("memory"), dict) else {}
    backend = str(memory.get("backend", "chroma"))
    graph = str(bool(memory.get("graph", False)))
    raw = f"{brain_dir}|{backend}|{graph}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class ProcessSharedServices:
    """Container for process-level singleton services.

    Obtain via ``ProcessSharedServices.get_or_create()`` — never construct
    directly, to avoid bypassing the singleton guard.

    Instances are keyed by a fingerprint derived from ``brain_dir`` and the
    memory-backend fields of ``config``.  A caller that requests a different
    memory backend always gets a distinct instance — it is never silently
    handed the wrong backend (ADV-024).

    Slice 2.2 additions:
        event_bus:     Optional :class:`~hachi.core.event_bus.EventBus`.  Set by
                       ``boot_agent`` when ``[events] bus_funnel=true``; used by
                       ``resume.py._get_process_bus()`` and the observability sink.
        wait_registry: Optional :class:`~hachi.core.runtime.waits.WaitConditionRegistry`.
                       Set by ``boot_agent`` when ``[jobs] durable_handlers=true``
                       so the scheduler sweep and wake endpoint share one registry.
    """

    skill_engine: Any  # SkillEngine
    mcp_manager: Any  # MCPManager
    vault: Any  # MemoryVault | None
    graph_index: Any  # MemoryIndex | None
    memory_writer: Any  # MemoryWriter | None
    brain_dir: str
    _fingerprint: str = field(default="", repr=False)
    initialized_at: float = field(default_factory=time.monotonic)
    # Slice 2.2: process-level EventBus (None when bus_funnel flag is off).
    event_bus: Any = field(default=None)  # EventBus | None
    # Slice 2.2: process-level WaitConditionRegistry (None when durable_handlers off).
    wait_registry: Any = field(default=None)  # WaitConditionRegistry | None
    # Phase 3: hot-reload routing store (None until first session boots with routing).
    routing_store: Any = field(default=None)  # RoutingConfigStore | None
    # H3: one Scheduler per process (was a private per-session instance over the
    # same schedules_file, causing double-fires and clobbered writes when two
    # sessions in one process each ran their own Scheduler+ScheduleRunner pair).
    scheduler: Any = field(default=None)  # Scheduler | None
    scheduler_runner_started: bool = field(default=False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def instance(cls) -> ProcessSharedServices | None:
        """Return the most-recently-created singleton, or ``None`` if none exists yet.

        Used by ``resume.py`` and other internal callers that need the process bus
        or wait registry without knowing which config fingerprint was used at boot.
        Returns the *first* (usually only) cached instance; multi-config processes
        are single-user/single-boot, so this is always the correct one in practice.
        """
        with _LOCK:
            if not _INSTANCES:
                return None
            # Return the most recently created instance (last insertion in dict order,
            # Python 3.7+ guaranteed).
            return next(reversed(_INSTANCES.values()))

    @classmethod
    def get_or_create(
        cls,
        config: dict[str, Any],
        brain_dir: str,
        *,
        force_reinit: bool = False,
    ) -> ProcessSharedServices:
        """Return the singleton for this (config, brain_dir) combination.

        FIX ADV-024 — config fingerprint check:
          Instances are keyed by a fingerprint of ``(brain_dir, memory.backend,
          memory.graph)``.  A caller requesting a different memory backend gets a
          distinct instance; it never silently inherits the first session's client.

        FIX UC-INT-004 — MCP health check:
          Before returning a cached instance the MCP manager is health-checked.
          If any server in the pool is dead the entire instance is torn down and
          re-initialised so sessions never inherit a broken pool.

        Args:
            config:       Full agent config dict (used for memory-backend selection).
            brain_dir:    Base data directory (platformdirs).
            force_reinit: If True, destroy the cached instance for this fingerprint
                          and create a fresh one.  Pass this in tests that need a
                          clean slate.
        """
        global _INSTANCES, _ATEXIT_REGISTERED
        fp = _config_fingerprint(config, brain_dir)

        # Fast-path: check without the lock first (double-checked locking).
        if not force_reinit:
            existing = _INSTANCES.get(fp)
            if existing is not None:
                # UC-INT-004: health-check before handing back a cached instance.
                if cls._mcp_pool_healthy(existing.mcp_manager):
                    return existing
                else:
                    logger.warning(
                        "ProcessSharedServices[%s]: MCP pool is unhealthy — "
                        "tearing down and re-initialising (UC-INT-004).",
                        fp,
                    )
                    force_reinit = True

        with _LOCK:
            # Re-check under the lock to avoid double-init races.
            if not force_reinit:
                existing = _INSTANCES.get(fp)
                if existing is not None:
                    if cls._mcp_pool_healthy(existing.mcp_manager):
                        return existing
                    logger.warning(
                        "ProcessSharedServices[%s]: MCP pool unhealthy under lock — "
                        "re-initialising.",
                        fp,
                    )

            new_instance = cls._init(config, brain_dir, fingerprint=fp)
            _INSTANCES[fp] = new_instance
            if not _ATEXIT_REGISTERED:
                # Flush the shared Chroma WAL on process exit (P3-07) without letting
                # any single AgentSession.shutdown() close the shared vault.
                atexit.register(cls.shutdown_all)
                _ATEXIT_REGISTERED = True

        return new_instance

    @classmethod
    def _mcp_pool_healthy(cls, mcp_manager: Any) -> bool:
        """Return True if the MCP manager has no dead server connections.

        A dead pool is detected when at least one previously-started server is
        no longer alive.  An empty pool (no servers configured) is considered
        healthy because there is nothing to revive.
        """
        try:
            servers: dict[str, Any] = mcp_manager._servers  # type: ignore[attr-defined]
        except AttributeError:
            return True  # unknown manager type — assume healthy

        for server in servers.values():
            try:
                if not server.is_alive:
                    return False
            except Exception:
                return False  # unexpected error → treat as dead
        return True

    @classmethod
    def clear(cls) -> None:
        """Destroy all cached singletons (for testing only)."""
        global _INSTANCES
        with _LOCK:
            _INSTANCES.clear()

    @classmethod
    def clear_fingerprint(cls, config: dict[str, Any], brain_dir: str) -> None:
        """Destroy the singleton for a specific (config, brain_dir) pair (for testing only)."""
        global _INSTANCES
        fp = _config_fingerprint(config, brain_dir)
        with _LOCK:
            _INSTANCES.pop(fp, None)

    @classmethod
    def shutdown_all(cls) -> None:
        """Close shared resources for every cached singleton (process exit).

        Closes each instance's MemoryVault exactly once so the Chroma WAL is
        flushed (P3-07), then clears the instance cache. Registered as an
        ``atexit`` handler the first time a singleton is created, so the shared
        vault is flushed on process exit without any individual AgentSession
        closing it (which would break sibling sessions — see ``is_shared``).
        Idempotent and exception-safe.
        """
        global _INSTANCES
        with _LOCK:
            instances = list(_INSTANCES.values())
            _INSTANCES.clear()
        for inst in instances:
            vault = getattr(inst, "vault", None)
            close = getattr(vault, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    logger.warning(
                        "ProcessSharedServices.shutdown_all: vault close failed "
                        "(WAL may not be flushed)",
                        exc_info=True,
                    )

    def uptime_seconds(self) -> float:
        """How long (seconds) since this singleton was first created."""
        return time.monotonic() - self.initialized_at

    # ------------------------------------------------------------------
    # Private initialisation
    # ------------------------------------------------------------------

    @classmethod
    def _init(
        cls, config: dict[str, Any], brain_dir: str, *, fingerprint: str = ""
    ) -> ProcessSharedServices:
        """One-time creation of all shared services."""
        from hachi.core.mcp_client import MCPManager
        from hachi.core.memory_provider import ChromaMemoryProvider, resolve_provider
        from hachi.core.paths import get_hachi_paths
        from hachi.core.settings import MemorySettings
        from hachi.og_engine.engine import SkillEngine

        paths = get_hachi_paths()

        # --- SkillEngine (shared read-mostly index) ---
        skill_engine = SkillEngine(agent_role="orchestrator")
        default_skills_dir = Path(__file__).parent.parent / "default_skills"
        try:
            skill_engine.load_directory(paths.skills_dir)
        except OSError:
            logger.warning("ProcessSharedServices: workspace skill indexing failed", exc_info=True)
        try:
            if default_skills_dir.exists():
                skill_engine.load_directory(default_skills_dir)
        except OSError:
            logger.warning("ProcessSharedServices: default-skills indexing failed", exc_info=True)

        # --- MCPManager (shared MCP subprocess pool) ---
        mcp_manager = MCPManager()

        # --- MemoryVault (shared Chroma client) ---
        vault: Any = None
        _raw_memory = config.get("memory", {})
        _memory_settings = MemorySettings.model_validate(_raw_memory)
        _provider = resolve_provider(_memory_settings)
        _provider.initialize(brain_dir=brain_dir)
        if isinstance(_provider, ChromaMemoryProvider):
            vault = _provider.vault
            # Mark as the process-shared vault so an individual AgentSession never
            # closes it on shutdown — only shutdown_all() (atexit) closes it once.
            if vault is not None:
                vault.is_shared = True

        # --- MemoryIndex / MemoryWriter (when memory.graph=true) ---
        graph_index: Any = None
        memory_writer: Any = None
        if _memory_settings.graph or _memory_settings.backend == "fts5_only":
            try:
                from hachi.core.memory_index import MemoryIndex
                from hachi.core.memory_writer import MemoryWriter

                graph_index = MemoryIndex(
                    memory_dir=paths.memory_dir,
                    db_path=paths.memory_index_db,
                )
                graph_index.refresh()
                memory_writer = MemoryWriter(
                    memory_dir=paths.memory_dir,
                    graph_index=graph_index,
                )
                logger.info(
                    "ProcessSharedServices: MemoryIndex %d nodes; MemoryWriter ready",
                    graph_index.node_count,
                )
            except Exception:
                logger.debug("ProcessSharedServices: graph index init failed", exc_info=True)

        logger.info(
            "ProcessSharedServices[%s]: initialised (skills=%d, mcp=%s, vault=%s, graph=%s)",
            fingerprint or "default",
            len(skill_engine.get_all_nodes()),
            "ok",
            "ok" if vault else "none",
            "ok" if graph_index else "none",
        )

        return cls(
            skill_engine=skill_engine,
            mcp_manager=mcp_manager,
            vault=vault,
            graph_index=graph_index,
            memory_writer=memory_writer,
            brain_dir=brain_dir,
            _fingerprint=fingerprint,
        )
