from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ConfigVersion = Literal[1]
ProviderKind = Literal[
    "anthropic", "openai-compatible", "openrouter", "groq", "together", "deepseek", "ollama"
]
PermissionTier = Literal["sandbox", "guided", "unrestricted"]


class ConfigMeta(BaseModel):
    model_config = ConfigDict(extra="ignore")

    config_version: ConfigVersion = 1
    imported_from_legacy: bool = False


class AgentSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = ""
    persona: str = ""
    max_tokens: int = 8192
    temperature: float = 0.0


class ProviderSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    kind: ProviderKind = "anthropic"
    model: str = "claude-haiku-4-5"
    base_url: str | None = None
    api_key_ref: str | None = None
    api_key_env: str | None = None
    # Hard guardrail: when non-empty, ONLY these models may be selected via
    # `/model` / `--model`. Empty (default) = no restriction (any model the
    # provider exposes is allowed).
    allowed_models: list[str] = Field(default_factory=list)
    # Custom HTTP headers for OpenAI-compatible / self-hosted endpoints (e.g. an
    # ``Authorization`` bearer for a gateway placed in front of the model, or a
    # tenant header). Empty (default) = none. Applied by the OpenAI-compat provider.
    headers: dict[str, str] = Field(default_factory=dict)


class AskBeforeSettings(BaseModel):
    """User-facing "Ask before…" confirmation preferences.

    Each flag controls whether the agent must pause and ask for confirmation
    before a class of sensitive action. These are surfaced in the web UI
    (Settings → Permissions & safety) and persisted to ``settings.toml`` so they
    survive a reload. ``True`` = ask first (safer); ``False`` = proceed silently.

    The keys mirror the toggle ids the frontend sends, so a single
    ``PUT /config/permissions`` round-trips the panel state.
    """

    model_config = ConfigDict(extra="ignore")

    # Ask before a single task spends over the per-task cost cap.
    spend_over_threshold: bool = True
    # Ask before any tool sends data off the local machine (network egress).
    network_egress: bool = True
    # Ask before deleting files.
    delete_files: bool = True


class PermissionsSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tier: PermissionTier = "guided"
    ask_before: AskBeforeSettings = Field(default_factory=AskBeforeSettings)


MemoryBackend = Literal["chroma", "in_memory", "fts5_only"]


class MemorySettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enable_session_history: bool = True
    enable_semantic_memory: bool = True
    backend: MemoryBackend = "chroma"
    # P2-04: M0 — FTS5 index over memory/*.og files, merged via RRF with Chroma.
    graph: bool = False
    # Issue 10 — retrieval-quality controls, consumed by MemoryVault:
    #   recall_distance_max: cosine-distance ceiling in [0, 2]; per-turn recall results
    #     above it are dropped so unrelated facts are never injected into context.
    #     Set to None to disable the filter (legacy "top-k always" behaviour). Default 0.85.
    #   core_memory_max_entries: soft cap on the core_memory collection; oldest entries
    #     are pruned once exceeded so the store cannot grow unbounded. Default 1000.
    recall_distance_max: float | None = 0.85
    core_memory_max_entries: int = 1000
    # M1: number of past-session episodes to inject into each turn's recall block.
    #     Set to 0 to disable episodic recall entirely.
    episodic_top_k: int = 3
    # M2: optional recency weighting for recall. Half-life in DAYS — a fact this old
    #     ranks as if twice as cosine-distant. None disables (pure relevance order).
    #     Only re-ranks relevance-gated core/episodic recall; NEVER user_profile or
    #     get_recent_facts. A reasonable starting value if enabled is ~30.0.
    decay_half_life_days: float | None = None
    # Stage-C graph expansion: when True, each turn appends a concise graph-expanded
    # memory section to the recall block (≤400 tokens, additive, gracefully degrades
    # to empty on any error).  Default True (enabled).  Set False to opt out entirely.
    graph_recall: bool = True


class LimitsSettings(BaseModel):
    """Per-session / per-turn / per-day safety caps (None = unlimited).

    Mirrors the optional ``[limits]`` TOML section that the gateway orchestrator
    reads and the execution loop enforces, so a cap set via
    ``hachi config-set session_cost_cap_usd`` is actually honoured at runtime
    (rather than written to a key nothing reads).

    Field semantics:
        max_daily_cost_usd:   Rolling calendar-day total spend cap (local date).
                              Exposed to the frontend as ``daily_cap_usd``.
        max_session_cost_usd: Per-individual-session cumulative cap.
        max_turn_cost_usd:    Per-turn cap (frontend: ``per_task_cap_usd``).
        max_session_tokens:   Per-session token limit.
        max_turn_tokens:      Per-turn token limit.
    """

    model_config = ConfigDict(extra="ignore")

    max_daily_cost_usd: float | None = None
    max_session_cost_usd: float | None = None
    max_session_tokens: int | None = None
    max_turn_cost_usd: float | None = None
    max_turn_tokens: int | None = None


class CapabilityState(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    configured: bool = False
    secret_ref: str | None = None


class TelegramChannelSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # Telegram chat ids allowed to talk to the agent. Empty = no restriction
    # (the bot answers anyone who messages it — only sensible for a private bot).
    allowlist: list[str] = Field(default_factory=list)


class ChannelSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    telegram: TelegramChannelSettings = Field(default_factory=TelegramChannelSettings)


class ResilienceSettings(BaseModel):
    """Retry and circuit-breaker parameters for the routing resilience layer.

    Maps to ``[routing.resilience]`` in ``settings.toml``.  All fields are
    optional — absent section uses the :class:`~hachi.core.resilience.RetryPolicy`
    defaults.
    """

    model_config = ConfigDict(extra="ignore")

    max_attempts: int = 3
    backoff_base_s: float = 0.5
    timeout_s: float = 60.0
    breaker_threshold: int = 5
    breaker_cooldown_s: float = 30.0


class EventsSettings(BaseModel):
    """Optional ``[events]`` config section (Slice 2.2 — EventBus funnel).

    The EventBus is the **default** event path.  ``emit_runtime_event`` /
    ``relay_event`` publish through the ``EventBus`` singleton, which fans out
    to all registered subscribers (read-models, SSE surface, observability sink,
    and any reactive handlers such as ``file.uploaded → auto_extract``).

    Back-compat: the two primary sync subscribers (read-models append + SSE
    surface) are registered in the same order as the old direct-call path, so
    output is byte-identical by construction.

    Set ``bus_funnel = false`` in the ``[events]`` config section to opt out of
    the bus and fall back to the legacy direct-call path.
    """

    model_config = ConfigDict(extra="ignore")

    bus_funnel: bool = True


class ObservabilitySettings(BaseModel):
    """Optional ``[observability]`` config section (Phase 0 — tracing / metrics).

    When ``enabled=True``, ``boot_agent`` calls
    :func:`~hachi.core.tracing.setup_from_config` and (when
    ``metrics_enabled=True``) :func:`~hachi.core.obs.metrics.setup_metrics`
    immediately after the EventBus config is parsed — see
    ``gateway.orchestrator._apply_observability_settings``.

    Attributes:
        enabled:           Master switch.  Default ``False`` so default runtime is
                           unchanged (tracing stays dormant unless opted in).
        exporter:          One of ``"console"`` (default), ``"otlp"``, ``"langfuse"``.
        endpoint:          OTLP endpoint URL (optional; falls back to
                           ``OTEL_EXPORTER_OTLP_ENDPOINT`` env var).
        metrics_enabled:   When ``True``, also initialise the metrics facade.
    """

    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    exporter: str = "console"
    endpoint: str | None = None
    metrics_enabled: bool = False
    log_format: str = "text"  # "text" | "json"


class JobsSettings(BaseModel):
    """Optional ``[jobs]`` config section (Slice 2.2 — durable job handlers).

    When ``durable_handlers=true``:
      - A ``JobRegistry`` is built at boot with the four named handlers.
      - ``_enqueue_title_job`` converts to ``handler_name=`` so titles survive
        restarts (fact-extraction jobs are converted inside ``MemoryManager``
        when this flag is in the env; see memory.py comment).
      - The scheduler sweeps WAITING runs past ``wait.timeout_at`` (A4).
      - On boot, WAITING runs are re-armed and RUNNING crashes are resolved (§6).

    Default is ``False`` so the old func= path stays active.

    ``worker_count`` is wired but not enforced (single worker pool is sufficient
    for single-node/single-user; seam for future throughput).
    """

    model_config = ConfigDict(extra="ignore")

    durable_handlers: bool = False
    worker_count: int = 1


class EvalReportSettings(BaseModel):
    """Optional ``[eval_reports]`` config section — weekly failure-report automation.

    When ``enabled=True`` the gateway boots a resident daemon thread that wakes
    every ``interval_seconds`` (default: one week), reads the interaction_log via
    the live :class:`~hachi.core.session_store.SessionStore`, builds a failure
    report, and writes both ``eval-report-<stamp>.md`` and
    ``eval-report-<stamp>.json`` to ``state_dir/eval-reports/``.

    Default is ``False`` so the feature is completely dormant unless the operator
    opts in by setting ``[eval_reports] enabled = true`` in ``settings.toml``.

    Attributes:
        enabled:          Master switch.  Defaults to ``False`` (opt-in).
        interval_seconds: Seconds between report runs.  Default 604800 (1 week).
        limit:            Maximum interaction rows loaded per run.  Default 1000.
    """

    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    interval_seconds: int = 604800  # 1 week
    limit: int = 1000


class VoiceSettings(BaseModel):
    """Optional ``[voice]`` config section (Initiative F — Voice Platform).

    Provides STT/TTS configuration with the established HACHI_STT_* / HACHI_TTS_*
    env-var precedence as the fallback.  All fields are optional; when absent the
    :class:`~hachi.core.providers.speech.OpenAICompatibleSpeechProvider` reads
    directly from the env vars (same precedence order, back-compat guaranteed).

    Attributes:
        stt_model: Whisper model name (e.g. ``"whisper-1"``).
        stt_base_url: Base URL for the STT endpoint (OpenAI-compat).
        stt_api_key_env: Name of the env var that holds the STT API key.
        tts_model: TTS model name (e.g. ``"tts-1"``).
        tts_base_url: Base URL for the TTS endpoint (OpenAI-compat).
        tts_api_key_env: Name of the env var that holds the TTS API key.
        tts_voice: Default TTS voice name (e.g. ``"alloy"``).
    """

    model_config = ConfigDict(extra="ignore")

    stt_model: str = "whisper-1"
    stt_base_url: str | None = None
    stt_api_key_env: str | None = None
    tts_model: str = "tts-1"
    tts_base_url: str | None = None
    tts_api_key_env: str | None = None
    tts_voice: str | None = None
    # Provider selection. "openai" = OpenAI-compatible /audio endpoints (default,
    # back-compat — covers OpenAI Whisper/TTS and self-hosted compatible servers);
    # "elevenlabs" = ElevenLabs TTS.
    stt_provider: Literal["openai"] = "openai"
    tts_provider: Literal["openai", "elevenlabs"] = "openai"
    # ElevenLabs (TTS only) — used when ``tts_provider == "elevenlabs"``.
    elevenlabs_api_key_env: str | None = None
    elevenlabs_voice_id: str | None = None
    # ElevenLabs model id. Defaults to eleven_turbo_v2_5 (low-latency, high quality).
    elevenlabs_model: str = "eleven_turbo_v2_5"


class RoutingSettings(BaseModel):
    """Optional ``[routing]`` config section.

    When absent from ``settings.toml``, :class:`~hachi.core.routing.policy.RoutingPolicy`
    synthesises back-compat behaviour (single model for every capability).

    Attributes:
        default_model: The fallback / session model id.
        auto: When ``True``, derive smart-default policy from the registry (A1).
        capabilities: Explicit ordered candidate list per capability name.
        model_overrides: Extra :class:`~hachi.core.routing.descriptor.ModelDescriptor`
            dicts to register (highest precedence in the registry).
        resilience: Retry / circuit-breaker settings.
    """

    model_config = ConfigDict(extra="ignore")

    default_model: str = "claude-haiku-4-5"
    auto: bool = False
    capabilities: dict[str, list[str]] = Field(default_factory=dict)
    model_overrides: list[Any] = Field(default_factory=list)
    resilience: ResilienceSettings = Field(default_factory=ResilienceSettings)


class FileSettings(BaseModel):
    """Optional ``[files]`` config section (Initiative E — File Attachment Platform).

    Controls the file ingest pipeline: size cap, allowed MIME types, storage
    backend, scan hook, and whether extracted text is indexed into the
    ``attachments`` Chroma collection for RAG.

    Attributes:
        max_size_bytes:  Hard upload ceiling in bytes.  Default 50 MB.
        allowed_types:   Explicit allowlist of MIME base types (e.g. ``["text/plain",
                         "application/pdf"]``).  Empty (default) = allow everything.
        storage_backend: ``"local"`` (default).  ``"s3"`` / ``"gcs"`` are seams for
                         future :class:`~hachi.core.files.store.StorageProvider`
                         implementations.
        scan_hook:       ``"noop"`` (default).  ``"clamav"`` / ``"cloudmersive"`` are
                         future :class:`~hachi.core.files.store.VirusScanHook` impls.
        index_on_extract: When ``True``, extracted text chunks are indexed into the
                         ``attachments`` Chroma collection via the RRF fusion seam
                         so ``search_attachments`` merges through ``semantic_search``.
    """

    model_config = ConfigDict(extra="ignore")

    max_size_bytes: int = 50 * 1024 * 1024  # 50 MB
    allowed_types: list[str] = Field(default_factory=list)
    storage_backend: str = "local"
    scan_hook: str = "noop"
    index_on_extract: bool = True


class SearchSettings(BaseModel):
    """Optional ``[search]`` config section (Initiative A — Search Platform).

    When ``provider`` is set to a known provider name (e.g. ``"tavily"``) and
    the corresponding API key is available (env var or SecretStore), the search
    tools (``web_search``, ``extract_url``) are registered automatically.

    Attributes:
        provider:          Provider name.  ``"tavily"`` is the only built-in.
                           ``None`` (default) = search tools not registered.
        max_calls_per_turn: Hard cap on outbound search/extract calls per agent turn.
                           ``0`` = disabled (no per-turn cap).
        cache_ttl_seconds: TTL for the in-session search cache in seconds.
                           ``0`` = cache disabled.
        window_max_calls:  Maximum calls within ``window_seconds`` (sliding window).
        window_seconds:    Duration of the sliding-window rate limit in seconds.
    """

    model_config = ConfigDict(extra="ignore")

    provider: str | None = None
    max_calls_per_turn: int = 10
    cache_ttl_seconds: float = 300.0
    window_max_calls: int = 60
    window_seconds: float = 3600.0


class RetentionSettings(BaseModel):
    """Data-retention TTLs for the periodic maintenance sweep.

    Maps to the optional ``[retention]`` section in ``settings.toml``.
    Defaults are conservative — nothing is deleted aggressively; operators can
    tighten them for storage-constrained installs.

    Field semantics:
        jobs_retention_hours:           Delete completed/failed/cancelled jobs
                                        older than this many hours.  24 h keeps
                                        one day of job history.
        interaction_log_retention_days: Delete ``interaction_log`` rows older than
                                        this many days.  90 days is the default
                                        for eval/audit usage.
        idempotency_key_retention_hours: Delete ``idempotency_keys`` rows older
                                        than this many hours.  48 h covers any
                                        realistic replay window.
        daily_spend_retention_days:     Delete ``daily_spend`` rows older than
                                        this many days.  365 keeps a year of
                                        cost history.
        checkpoint_retention_days:      Delete file-edit checkpoint snapshots
                                        older than this many days.  30 is safe
                                        since they're only needed for undo.
        sweep_interval_seconds:         How often the idle ResidentWorkerThread
                                        runs the sweep.  Default 3600 = hourly.
    """

    model_config = ConfigDict(extra="ignore")

    jobs_retention_hours: int = 24
    interaction_log_retention_days: int = 90
    idempotency_key_retention_hours: int = 48
    daily_spend_retention_days: int = 365
    checkpoint_retention_days: int = 30
    sweep_interval_seconds: float = 3600.0


class ResolvedConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    meta: ConfigMeta = Field(default_factory=ConfigMeta)
    provider: ProviderSettings = Field(default_factory=ProviderSettings)
    # Named additional providers for multi-provider /model switching.
    # Configure via [providers.NAME] sections in ~/.hachi/settings.toml.
    providers: dict[str, ProviderSettings] = Field(default_factory=dict)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    permissions: PermissionsSettings = Field(default_factory=PermissionsSettings)
    limits: LimitsSettings = Field(default_factory=LimitsSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    capabilities: dict[str, CapabilityState] = Field(default_factory=dict)
    channels: ChannelSettings = Field(default_factory=ChannelSettings)
    # Optional [routing] section — absent = back-compat (one model for everything).
    routing: RoutingSettings | None = None
    # Optional [voice] section — absent = fall back to HACHI_STT_* / HACHI_TTS_* env vars.
    voice: VoiceSettings | None = None
    # Optional [events] section — absent = old direct-call funnel (back-compat).
    events: EventsSettings = Field(default_factory=EventsSettings)
    # Optional [jobs] section — absent = func= closures (back-compat).
    jobs: JobsSettings = Field(default_factory=JobsSettings)
    # Optional [observability] section — absent = tracing off (back-compat).
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    # Optional [search] section — absent = search tools not registered.
    search: SearchSettings = Field(default_factory=SearchSettings)
    # Optional [files] section — absent = default 50 MB cap, all types allowed.
    files: FileSettings = Field(default_factory=FileSettings)
    # Optional [retention] section — absent = conservative defaults (see RetentionSettings).
    retention: RetentionSettings = Field(default_factory=RetentionSettings)
    # [mcp_servers.<name>] sections — Model Context Protocol servers registered via the
    # UI/CLI. Kept as raw dicts (parsed by MCPServerConfig.from_toml_entry at boot) so the
    # section survives model_dump() — without this field it was silently dropped and
    # TOML-registered MCP servers never loaded.
    mcp_servers: dict[str, dict[str, Any]] = Field(default_factory=dict)


def default_config() -> ResolvedConfig:
    return ResolvedConfig(
        capabilities={
            "google": CapabilityState(),
            "notion": CapabilityState(),
            "slack": CapabilityState(),
        }
    )
