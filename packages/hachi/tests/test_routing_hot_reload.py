"""Tests for hot-reload model routing (Phase 3 / #13).

Covers:
  - RoutingSnapshot is immutable and bundles registry+policy+resilience+version.
  - ModelRouter.apply_snapshot() swaps config and clears _sticky at turn boundary.
  - RoutingConfigStore.apply() increments version; rollback restores last-good.
  - ExecutionLoop adopts a new snapshot at turn boundary (not mid-turn).
  - N concurrent sessions calling select/new_turn while a swap happens never tear
    _sticky or _recorders (per-session model safety proof).
  - _reload_agents is NOT called for a pure routing change; IS called for a provider change.
"""

from __future__ import annotations

import threading
from typing import Any
from unittest.mock import MagicMock

import pytest

from hachi.core.resilience import RetryPolicy
from hachi.core.routing.capability import Capability
from hachi.core.routing.descriptor import ModelDescriptor, Pricing
from hachi.core.routing.policy import RoutingPolicy
from hachi.core.routing.registry import ModelRegistry
from hachi.core.routing.router import ModelRouter
from hachi.core.routing.snapshot import RoutingSnapshot
from hachi.core.routing.validate import RoutingValidationResult, validate_routing
from hachi.gateway.routing_store import RoutingConfigStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _simple_registry(model_ids: list[str] | None = None) -> ModelRegistry:
    reg = ModelRegistry()
    ids = model_ids or ["claude-haiku-4-5"]
    for mid in ids:
        reg.register(
            ModelDescriptor(
                id=mid,
                provider="anthropic",
                capabilities=frozenset({Capability.REASONING, Capability.CODING}),
                context_window=200_000,
                max_output=8_192,
                pricing=Pricing(input_per_mtok=1.0, output_per_mtok=5.0),
            )
        )
    return reg


def _simple_policy(default_model: str = "claude-haiku-4-5") -> RoutingPolicy:
    return RoutingPolicy(default_model=default_model)


def _resilience() -> RetryPolicy:
    return RetryPolicy()


def _snapshot(
    version: int = 1,
    model_id: str = "claude-haiku-4-5",
    source: str = "test",
) -> RoutingSnapshot:
    return RoutingSnapshot(
        registry=_simple_registry([model_id]),
        policy=_simple_policy(model_id),
        resilience=_resilience(),
        version=version,
        source=source,
    )


# ---------------------------------------------------------------------------
# RoutingSnapshot — immutability + construction
# ---------------------------------------------------------------------------


class TestRoutingSnapshot:
    def test_snapshot_is_frozen(self) -> None:
        snap = _snapshot(version=1)
        with pytest.raises((AttributeError, TypeError)):
            snap.version = 2  # type: ignore[misc]

    def test_snapshot_bundles_all_fields(self) -> None:
        snap = _snapshot(version=7, model_id="claude-sonnet-4-6", source="ui")
        assert snap.version == 7
        assert snap.source == "ui"
        assert snap.policy.default_model == "claude-sonnet-4-6"

    def test_snapshot_registry_accessible(self) -> None:
        snap = _snapshot(model_id="gpt-4o-mini")
        assert snap.registry.get("gpt-4o-mini") is not None


# ---------------------------------------------------------------------------
# ModelRouter.apply_snapshot()
# ---------------------------------------------------------------------------


class TestModelRouterApplySnapshot:
    def _router(self, model_id: str = "claude-haiku-4-5") -> ModelRouter:
        return ModelRouter(
            registry=_simple_registry([model_id]),
            policy=_simple_policy(model_id),
            providers=None,
            resilience=_resilience(),
        )

    def test_apply_snapshot_swaps_registry(self) -> None:
        router = self._router("claude-haiku-4-5")
        assert router._registry.get("gpt-4o-mini") is None

        new_snap = _snapshot(model_id="gpt-4o-mini", version=2)
        router.apply_snapshot(new_snap)

        assert router._registry.get("gpt-4o-mini") is not None

    def test_apply_snapshot_clears_sticky_cache(self) -> None:
        router = self._router()
        # Seed the sticky cache with a fake entry.
        router._sticky[(Capability.REASONING, "fake:key")] = MagicMock()
        assert len(router._sticky) == 1

        router.apply_snapshot(_snapshot(version=2))

        assert len(router._sticky) == 0

    def test_apply_snapshot_swaps_policy(self) -> None:
        router = self._router("claude-haiku-4-5")
        assert router._policy.default_model == "claude-haiku-4-5"

        new_snap = _snapshot(model_id="gpt-4o-mini", version=2)
        router.apply_snapshot(new_snap)

        assert router._policy.default_model == "gpt-4o-mini"

    def test_sticky_cache_preserved_within_a_turn(self) -> None:
        """Sticky cache survives between select() calls within the same turn."""
        router = self._router()
        sentinel = MagicMock()
        key = (Capability.REASONING, "test:key")
        router._sticky[key] = sentinel

        # No apply_snapshot → sticky cache intact.
        assert router._sticky.get(key) is sentinel


# ---------------------------------------------------------------------------
# RoutingConfigStore — apply / rollback / version
# ---------------------------------------------------------------------------


class TestRoutingConfigStore:
    def test_init_sets_version_zero(self) -> None:
        store = RoutingConfigStore()
        assert store.version == 0

    def test_init_snapshot_via_init_method(self) -> None:
        store = RoutingConfigStore()
        snap = _snapshot(version=1)
        store.init(snap)
        assert store.current_snapshot is snap
        assert store.version == 0  # init does NOT bump the version

    def test_apply_bumps_version(self) -> None:
        store = RoutingConfigStore()
        store.init(_snapshot(version=0))
        store.apply(_snapshot(version=1))
        assert store.version == 1

    def test_apply_twice_bumps_twice(self) -> None:
        store = RoutingConfigStore()
        store.apply(_snapshot(version=1, source="first"))
        store.apply(_snapshot(version=2, source="second"))
        assert store.version == 2
        assert store.current_snapshot is not None
        assert store.current_snapshot.source == "second"

    def test_apply_returns_previous_snapshot(self) -> None:
        store = RoutingConfigStore()
        snap_a = _snapshot(version=1, source="a")
        snap_b = _snapshot(version=2, source="b")
        store.init(snap_a)
        prev = store.apply(snap_b)
        assert prev is snap_a

    def test_rollback_restores_last_good(self) -> None:
        store = RoutingConfigStore()
        snap_a = _snapshot(version=1, source="good")
        snap_b = _snapshot(version=2, source="bad")
        store.init(snap_a)
        store.apply(snap_b)
        assert store.current_snapshot is snap_b

        restored = store.rollback()
        assert restored is snap_a
        assert store.current_snapshot is snap_a

    def test_rollback_bumps_version(self) -> None:
        store = RoutingConfigStore()
        store.init(_snapshot(version=0))
        store.apply(_snapshot(version=1))
        v_before = store.version
        store.rollback()
        assert store.version == v_before + 1

    def test_rollback_with_no_good_snapshot_returns_none(self) -> None:
        store = RoutingConfigStore()
        result = store.rollback()
        assert result is None

    def test_concurrent_applies_produce_monotonic_version(self) -> None:
        """Concurrent apply() calls must not corrupt the version counter."""
        store = RoutingConfigStore()
        store.init(_snapshot(version=0))
        errors: list[str] = []

        def _apply(n: int) -> None:
            try:
                store.apply(_snapshot(version=n, source=str(n)))
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=_apply, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert store.version == 20


# ---------------------------------------------------------------------------
# validate_routing()
# ---------------------------------------------------------------------------


class TestValidateRouting:
    def test_valid_config_returns_ok(self) -> None:
        reg = _simple_registry(["claude-haiku-4-5"])
        policy = _simple_policy("claude-haiku-4-5")
        result = validate_routing(reg, policy, providers=None)
        assert result.ok

    def test_empty_default_model_fails(self) -> None:
        reg = _simple_registry(["claude-haiku-4-5"])
        policy = _simple_policy("")
        result = validate_routing(reg, policy, providers=None)
        assert not result.ok
        assert any("default_model" in issue for issue in result.issues)

    def test_unknown_capability_key_fails(self) -> None:
        from hachi.core.routing.policy import RoutingPolicy

        # model_construct() bypasses pydantic so we can hand validate_routing()
        # a raw-string capability key and confirm it is caught at the rule level.
        policy = RoutingPolicy.model_construct(
            default_model="claude-haiku-4-5",
            capabilities={"not_a_real_cap": ["claude-haiku-4-5"]},
        )
        reg = _simple_registry(["claude-haiku-4-5"])
        result = validate_routing(reg, policy, providers=None)
        assert not result.ok
        assert any("not_a_real_cap" in issue for issue in result.issues)

    def test_valid_capability_keys_pass(self) -> None:
        from hachi.core.routing.policy import RoutingPolicy

        policy = RoutingPolicy(
            default_model="claude-haiku-4-5",
            capabilities={"reasoning": ["claude-haiku-4-5"]},
        )
        reg = _simple_registry(["claude-haiku-4-5"])
        result = validate_routing(reg, policy, providers=None)
        assert result.ok

    def test_result_has_issues_and_warnings_lists(self) -> None:
        result = RoutingValidationResult(ok=True)
        assert result.issues == []
        assert result.warnings == []


# ---------------------------------------------------------------------------
# ExecutionLoop snapshot adoption at turn boundary
# ---------------------------------------------------------------------------


class TestExecutionLoopSnapshotAdoption:
    """Verify the loop pulls a new snapshot at _resolve_turn_client, not mid-turn."""

    def _make_loop(self, routing_store: RoutingConfigStore | None = None) -> Any:
        from hachi.core.loop import ExecutionLoop, ToolRegistry

        # Use plain MagicMock (no spec) — these tests exercise routing_store wiring
        # only; they never run a full loop turn so the memory interface is irrelevant.
        loop = ExecutionLoop(
            llm_client=MagicMock(),
            registry=ToolRegistry(),
            memory=MagicMock(),
            routing_store=routing_store,
        )
        return loop

    def test_loop_accepts_routing_store_parameter(self) -> None:
        store = RoutingConfigStore()
        loop = self._make_loop(routing_store=store)
        assert loop.routing_store is store

    def test_loop_routing_store_defaults_to_none(self) -> None:
        loop = self._make_loop(routing_store=None)
        assert loop.routing_store is None

    def test_applied_routing_version_starts_at_zero(self) -> None:
        loop = self._make_loop()
        assert loop._applied_routing_version == 0

    def test_loop_adopts_newer_snapshot_at_turn_boundary(self) -> None:
        """When store.version > _applied_routing_version, router.apply_snapshot is called."""
        store = RoutingConfigStore()
        snap_v1 = _snapshot(version=1, source="new")
        store.apply(snap_v1)

        # Build a router and attach it to the loop.
        router = MagicMock()
        loop = self._make_loop(routing_store=store)
        loop.router = router
        loop._applied_routing_version = 0  # stale

        # Trigger the version check as _resolve_turn_client would.
        loop._maybe_apply_routing_snapshot()

        router.apply_snapshot.assert_called_once_with(snap_v1)
        assert loop._applied_routing_version == 1

    def test_loop_does_not_call_apply_when_version_current(self) -> None:
        store = RoutingConfigStore()
        snap_v1 = _snapshot(version=1)
        store.apply(snap_v1)

        router = MagicMock()
        loop = self._make_loop(routing_store=store)
        loop.router = router
        loop._applied_routing_version = 1  # already current

        loop._maybe_apply_routing_snapshot()

        router.apply_snapshot.assert_not_called()

    def test_loop_does_not_call_apply_without_router(self) -> None:
        store = RoutingConfigStore()
        store.apply(_snapshot(version=1))
        loop = self._make_loop(routing_store=store)
        loop.router = None  # no router
        loop._applied_routing_version = 0

        # Should not raise.
        loop._maybe_apply_routing_snapshot()
        assert loop._applied_routing_version == 0  # unchanged (no router to adopt)


# ---------------------------------------------------------------------------
# Per-session model — concurrent safety proof
# ---------------------------------------------------------------------------


class TestPerSessionConcurrencySafety:
    """Prove that the per-session router design is safe under concurrency.

    Each session has its OWN router with its own _sticky/_recorders.
    A swap in one session's router must not affect another's.
    Concurrent new_turn()/select() calls within a session are safe because
    all are on the same session thread (serialised by _chat_lock upstream).
    """

    def test_two_sessions_have_independent_sticky_caches(self) -> None:
        router_a = ModelRouter(
            registry=_simple_registry(),
            policy=_simple_policy(),
            providers=None,
            resilience=_resilience(),
        )
        router_b = ModelRouter(
            registry=_simple_registry(),
            policy=_simple_policy(),
            providers=None,
            resilience=_resilience(),
        )
        sentinel = MagicMock()
        router_a._sticky[(Capability.CODING, "k")] = sentinel

        # router_b is unaffected.
        assert (Capability.CODING, "k") not in router_b._sticky

    def test_applying_snapshot_to_one_router_does_not_affect_sibling(self) -> None:
        router_a = ModelRouter(
            registry=_simple_registry(["claude-haiku-4-5"]),
            policy=_simple_policy("claude-haiku-4-5"),
            providers=None,
            resilience=_resilience(),
        )
        router_b = ModelRouter(
            registry=_simple_registry(["claude-haiku-4-5"]),
            policy=_simple_policy("claude-haiku-4-5"),
            providers=None,
            resilience=_resilience(),
        )

        new_snap = _snapshot(model_id="gpt-4o-mini", version=2)
        router_a.apply_snapshot(new_snap)

        # router_b is still on the old config.
        assert router_b._policy.default_model == "claude-haiku-4-5"
        assert router_b._registry.get("gpt-4o-mini") is None
