"""
Turn cost measurement harness — offline token count (default) or live API run (--live).

Purpose
-------
* **Offline mode (default):** assembles the system prompt + core tool schemas + user
  message as the loop would send them, counts bytes/4 as a deterministic token
  approximation, and records the result in ``COST_BASELINE.json``.  No API call, no spend,
  safe for CI.  The Phase-4 R3 CI guard imports ``count_prompt_tokens`` from here.

* **Live mode (--live):** boots a real ExecutionLoop with the configured provider, runs the
  canonical query exactly once (max_iterations=1), records the CostTracker snapshot and
  cache metrics, then appends a row to ``COST_BASELINE.json``.  Spends real money; needs
  ``ANTHROPIC_API_KEY`` (or the configured provider key) in the environment.

Usage
-----
    uv run python scripts/measure_turn.py              # offline (CI-safe)
    uv run python scripts/measure_turn.py --live       # live turn (real spend)
    uv run python scripts/measure_turn.py --live --label "after-lazy-tools"

Notes
-----
* Set ``HACHI_DISABLE_DOTENV_AUTOLOAD=1`` before imports to avoid BB-2 (core .env load).
  Live mode loads creds from ``config_dir/.env`` lazily at call time (BB-8).
* No new runtime dependencies.  Token approximation is ≈4 UTF-8 bytes per token (adequate
  for a ±15 % tolerance CI guard; not billing-grade).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# BB-2: prevent .env autoload in the core import path.  Must come before any hachi import.
os.environ.setdefault("HACHI_DISABLE_DOTENV_AUTOLOAD", "1")

_REPO_ROOT = Path(__file__).parent.parent
_BASELINE_FILE = _REPO_ROOT / "docs" / "audit" / "2026-06-28" / "COST_BASELINE.json"
CANONICAL_QUERY = "What is my name? My name is Aditya"


# ---------------------------------------------------------------------------
# Offline token estimator
# ---------------------------------------------------------------------------


def _estimate_tokens(text: str) -> int:
    """Rough deterministic token count: 1 token ≈ 4 UTF-8 bytes (English + JSON).

    No tiktoken dependency.  For the CI guard the tolerance band is ±15%, so this
    approximation is sufficient.  It slightly under-counts for CJK-heavy text; the
    canonical query and brain.og are English, so the error is small.
    """
    return max(1, len(text.encode("utf-8")) // 4)


# ---------------------------------------------------------------------------
# Offline stub helpers (schema-only tool registration — no live backends)
# ---------------------------------------------------------------------------


class _StubSkillEngine:
    """Minimal duck-type satisfying SkillEngine's interface for schema registration."""

    def search(self, query: str, **kw: Any) -> list:
        return []

    def list_all_skills(self, **kw: Any) -> list:
        return []

    def peek(self, name: str, **kw: Any) -> dict:
        return {}

    def get(self, name: str, **kw: Any) -> None:
        return None

    def get_dependencies(self, name: str) -> list:
        return []

    def get_skill_changelog(self, name: str) -> list:
        return []

    def get_traverse_hints(self, name: str) -> dict:
        return {}

    def get_all_nodes(self, **kw: Any) -> list:
        return []

    def get_node(self, name: str) -> None:
        return None


class _StubSessionStore:
    """Minimal duck-type satisfying SessionStore's query interface."""

    def search_sessions(self, *a: Any, **kw: Any) -> list:
        return []

    def get_session(self, *a: Any, **kw: Any) -> None:
        return None


# ---------------------------------------------------------------------------
# Core-tool registry builder (used by both offline and live modes)
# ---------------------------------------------------------------------------


def build_core_registry():  # noqa: ANN201 — avoids circular import in type hint
    """Build a ToolRegistry populated with all core tool *schemas*.

    Uses stub backends so no ChromaDB, SkillEngine index, or API keys are needed.
    The schemas are identical to what the real boot sequence registers, so token
    counts are accurate.
    """
    from hachi.core.loop import ToolRegistry
    from hachi.gateway.orchestrator import _CORE_TOOL_NAMES, _GROUP_BY_TOOL_NAME
    from hachi.tools.memory_tools import register_memory_tools, register_session_tools
    from hachi.tools.og_tools import USE_TOOLS_SCHEMA, _make_use_tools, register_og_tools
    from hachi.tools.os_tools import register_os_tools

    registry = ToolRegistry()

    # OS tools — no gate needed for schema extraction (unrestricted handlers).
    register_os_tools(registry, gate=None)

    # OG / skill tools — engine only called when tools are *invoked*, not registered.
    register_og_tools(registry, _StubSkillEngine())

    # use_tools meta-tool — explicit group="core" (not in _CORE_TOOL_NAMES dict).
    registry.register(USE_TOOLS_SCHEMA, _make_use_tools(registry), group="core")

    # Memory + session tools — vault=None is documented as supported for in-memory mode.
    register_memory_tools(registry, vault=None, job_queue=None)
    register_session_tools(registry, _StubSessionStore())

    # Browser tools — browse_web is a core tool; controller is lazy (no browser launched).
    try:
        from hachi.tools.browser_tools import register_browser_tools

        register_browser_tools(registry, gate=None)
    except Exception:
        pass  # playwright not installed; schema absent but not a test-failure condition

    # Stamp lazy-loading groups (mirrors the orchestrator's classify call).
    registry.classify(
        core_names=set(_CORE_TOOL_NAMES),
        group_by_name=_GROUP_BY_TOOL_NAME,
        prefix_groups={"google_": "google"},
        default="integrations",
    )

    return registry


# ---------------------------------------------------------------------------
# Public offline measurement function (imported by CI guard test)
# ---------------------------------------------------------------------------


def count_prompt_tokens(
    brain_content: str | None = None,
    registry=None,  # noqa: ANN001
) -> dict[str, Any]:
    """Assemble the turn prompt and count tokens without an API call.

    Args:
        brain_content: System prompt text (loads from ``paths.brain_file`` when ``None``).
        registry: Pre-built ``ToolRegistry`` (built from :func:`build_core_registry` when
            ``None``).  Pass an explicit registry to speed up repeated calls in tests.

    Returns:
        Dict with ``system_tokens``, ``tool_tokens``, ``user_tokens``, ``total_tokens``,
        ``core_tool_count``, and ``method`` (always ``"offline"``) fields.
    """
    from hachi.core.paths import get_hachi_paths

    if brain_content is None:
        brain_file = get_hachi_paths().brain_file
        brain_content = brain_file.read_text(encoding="utf-8") if brain_file.exists() else ""

    if registry is None:
        registry = build_core_registry()

    core_schemas = registry.get_schemas(active_groups=set())  # only "core" group
    tool_json = json.dumps(core_schemas, separators=(",", ":"))

    system_tokens = _estimate_tokens(brain_content)
    tool_tokens = _estimate_tokens(tool_json)
    user_tokens = _estimate_tokens(CANONICAL_QUERY)

    return {
        "method": "offline",
        "system_tokens": system_tokens,
        "tool_tokens": tool_tokens,
        "user_tokens": user_tokens,
        "total_tokens": system_tokens + tool_tokens + user_tokens,
        "core_tool_count": len(core_schemas),
        "brain_content_bytes": len(brain_content.encode("utf-8")),
        "tool_json_bytes": len(tool_json.encode("utf-8")),
    }


# ---------------------------------------------------------------------------
# Live measurement
# ---------------------------------------------------------------------------


def _load_config_env() -> None:
    """Load creds from config_dir/.env at call time (BB-8)."""
    from hachi.core.paths import get_hachi_paths

    env_path = get_hachi_paths().config_dir / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def measure_live() -> dict[str, Any]:
    """Run the canonical query live against the configured provider.

    Boots a minimal ExecutionLoop (real client, real CostTracker, real brain.og, core
    tool schemas with stub backends), runs one turn, and returns cost metrics.

    Spends real money.  Reads provider creds lazily from config_dir/.env (BB-8).
    """
    _load_config_env()

    from hachi.core.config_loader import load_effective_config
    from hachi.core.cost import CostTracker
    from hachi.core.llm import create_llm_client
    from hachi.core.loop import ExecutionLoop
    from hachi.core.paths import get_hachi_paths
    from hachi.core.sub_agent import SubAgentMemory

    config = load_effective_config()
    raw = config.model_dump(mode="python")
    provider_config: dict[str, Any] = raw.get("provider", {})
    agent_config: dict[str, Any] = raw.get("agent", {})
    max_tokens: int = int(agent_config.get("max_tokens", 4096))

    client = create_llm_client(provider_config, max_tokens=max_tokens)

    registry = build_core_registry()

    brain_file = get_hachi_paths().brain_file
    brain_content = brain_file.read_text(encoding="utf-8") if brain_file.exists() else ""

    cost_tracker = CostTracker()
    memory = SubAgentMemory()

    loop = ExecutionLoop(
        llm_client=client,
        registry=registry,
        memory=memory,
        base_system_prompt=brain_content,
        cost_tracker=cost_tracker,
    )

    loop.add_user_message(CANONICAL_QUERY)
    result = loop.run(max_iterations=1)
    loop.shutdown(wait=False)

    snap = cost_tracker.snapshot()
    model_id = getattr(client, "model", provider_config.get("model", "unknown"))

    # Cache metrics from the tracker (uses the same pricing look-up path).
    from hachi.core.llm import TokenUsage

    cache_usage = TokenUsage(
        input_tokens=snap.input_tokens,
        output_tokens=snap.output_tokens,
        cache_read_tokens=snap.cache_read_tokens,
        cache_creation_tokens=snap.cache_creation_tokens,
    )
    cache_metrics: dict[str, Any] = cost_tracker.cache_metrics(model_id, cache_usage)

    return {
        "method": "live",
        "model": model_id,
        "provider_kind": provider_config.get("kind", "unknown"),
        "input_tokens": snap.input_tokens,
        "output_tokens": snap.output_tokens,
        "cache_read_tokens": snap.cache_read_tokens,
        "cache_creation_tokens": snap.cache_creation_tokens,
        "total_tokens": snap.total_tokens,
        "estimated_cost_usd": snap.estimated_cost_usd,
        "call_count": snap.call_count,
        "cache_hit_rate": cache_metrics.get("cache_hit_rate", 0.0),
        "llm_response_preview": str(result)[:120],
    }


# ---------------------------------------------------------------------------
# Baseline record helpers
# ---------------------------------------------------------------------------


def _load_baseline() -> dict[str, Any]:
    if _BASELINE_FILE.exists():
        return json.loads(_BASELINE_FILE.read_text(encoding="utf-8"))
    return {}


def _append_run(baseline: dict[str, Any], label: str, metrics: dict[str, Any]) -> None:
    runs: list[dict[str, Any]] = baseline.setdefault("runs", [])
    runs.append({"label": label, **metrics})


def _save_baseline(baseline: dict[str, Any]) -> None:
    _BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _BASELINE_FILE.write_text(json.dumps(baseline, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--live", action="store_true", help="Run a real API turn (spends money).")
    parser.add_argument(
        "--label",
        default="",
        help="Optional label for the baseline record (e.g. 'before-optimizer-X').",
    )
    args = parser.parse_args(argv)

    if args.live:
        print("Running LIVE measurement (will spend real API tokens)…", flush=True)
        metrics = measure_live()
    else:
        print("Running OFFLINE measurement (no API call)…", flush=True)
        metrics = count_prompt_tokens()

    label = args.label or metrics["method"]
    print(json.dumps(metrics, indent=2))

    baseline = _load_baseline()
    _append_run(baseline, label, metrics)
    _save_baseline(baseline)
    print(f"\nAppended to {_BASELINE_FILE.relative_to(_REPO_ROOT)}")

    total = metrics.get("total_tokens", metrics.get("total_tokens", 0))
    print(f"Total tokens: {total:,}")
    if metrics["method"] == "live":
        print(f"Estimated cost: ${metrics.get('estimated_cost_usd', 0):.6f} USD")

    return 0


if __name__ == "__main__":
    sys.exit(main())
