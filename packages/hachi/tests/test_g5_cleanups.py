"""
G5 cleanup tests: L5, L6, M7.

L5 (PERF-11) — engine.py: prefix_qids_per_token built in one pass;
    search results unchanged.
L6 (PERF-12) — memory.py: boundary selection is identical to brute-force
    _is_safe for sample histories.
M7 (MED-029/UX-14) — onboarding.py: lightning tier now enables memory.
"""

from __future__ import annotations

from pathlib import Path

from hachi.core.llm import Message
from hachi.core.memory import MemoryManager
from hachi.core.onboarding import OnboardingService, SetupPlan
from hachi.core.paths import HachiPaths

# ---------------------------------------------------------------------------
# L5 — BM25 prefix-set deduplication
# ---------------------------------------------------------------------------

FIXTURE = Path(__file__).parent / "fixtures" / "sample_skill.og"


def _engine():
    from hachi.og_engine.engine import SkillEngine

    engine = SkillEngine()
    engine.load_file(FIXTURE)
    return engine


class TestL5PrefixSetDedup:
    """Search results are identical before/after deduplication of prefix-set computation."""

    def test_exact_token_search_unchanged(self):
        engine = _engine()
        results = engine.search("deploy")
        names = {r["name"] for r in results}
        assert "deploy_to_prod" in names

    def test_prefix_search_unchanged(self):
        """'deployment' should still hit the 'deploy' keyword via prefix match."""
        engine = _engine()
        results = engine.search("deployment")
        names = {r["name"] for r in results}
        assert "deploy_to_prod" in names

    def test_multi_token_search_unchanged(self):
        engine = _engine()
        results = engine.search("run tests")
        names = {r["name"] for r in results}
        assert "run_tests" in names

    def test_no_match_unchanged(self):
        engine = _engine()
        assert engine.search("zzznomatch") == []

    def test_prefix_qids_per_token_built_in_candidate_loop(self):
        """
        Verify _prefix_matched_qids is called exactly once per unique query token.

        Before PERF-11 it was called twice: once during candidate collection and
        once in a separate dict comprehension.  After the fix it is called only
        during the candidate loop and the result is reused.
        """
        engine = _engine()
        call_count: list[tuple] = []
        original = engine._prefix_matched_qids

        def counting_prefix(*args, **kwargs):
            call_count.append(args)
            return original(*args, **kwargs)

        engine._prefix_matched_qids = counting_prefix  # type: ignore[method-assign]
        engine.search("deploy run")
        # Two unique tokens → exactly 2 calls (not 4)
        assert len(call_count) == 2, (
            f"Expected 2 calls to _prefix_matched_qids (one per token), "
            f"got {len(call_count)}"
        )


# ---------------------------------------------------------------------------
# L6 — O(N) boundary selection produces identical results to O(N²)
# ---------------------------------------------------------------------------


def _mm(max_msgs: int = 20) -> MemoryManager:
    return MemoryManager(max_active_messages=max_msgs)


def _tool_use_block(uid: str) -> dict:
    return {"type": "tool_use", "id": uid, "name": "dummy", "input": {}}


def _tool_result_block(uid: str) -> dict:
    return {"type": "tool_result", "tool_use_id": uid, "content": "ok"}


def _brute_force_boundary(mm: MemoryManager, candidate_cut: int) -> int:
    """Reference O(N²) implementation to compare against."""
    history = mm._history

    def _is_safe(cut: int) -> bool:
        seen_tool_use_ids: set = set()
        for msg in history[cut:]:
            content = msg.content
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    seen_tool_use_ids.add(block.get("id"))
        for msg in history[cut:]:
            content = msg.content
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_result":
                    if block.get("tool_use_id") not in seen_tool_use_ids:
                        return False
        return True

    cut = candidate_cut
    while cut > 0 and not _is_safe(cut):
        cut -= 1
    return cut


class TestL6BoundarySelection:
    """O(N) implementation selects the same boundary as the O(N²) reference."""

    def _check(self, messages: list[Message], candidate_cut: int):
        mm = _mm()
        mm._history = messages[:]
        expected = _brute_force_boundary(mm, candidate_cut)
        actual = mm._find_safe_sliding_boundary(candidate_cut)
        assert actual == expected, (
            f"Boundary mismatch at candidate_cut={candidate_cut}: "
            f"brute-force={expected}, new O(N)={actual}"
        )

    def test_simple_plain_messages(self):
        """No tool pairs — any cut is safe."""
        msgs = [
            Message(role="user" if i % 2 == 0 else "assistant", content=f"msg {i}")
            for i in range(10)
        ]
        self._check(msgs, candidate_cut=5)

    def test_paired_inside_retained(self):
        """tool_use and tool_result both in [cut:] — safe at candidate_cut."""
        msgs = [
            Message(role="user", content="ask"),
            Message(role="assistant", content=[_tool_use_block("id1")]),
            Message(role="user", content=[_tool_result_block("id1")]),
            Message(role="assistant", content="done"),
            Message(role="user", content="next"),
        ]
        self._check(msgs, candidate_cut=2)

    def test_tool_use_before_cut_result_after(self):
        """tool_use before cut, result after → boundary must walk back."""
        msgs = [
            Message(role="user", content="ask"),
            Message(role="assistant", content=[_tool_use_block("id2")]),  # idx 1
            Message(role="user", content=[_tool_result_block("id2")]),    # idx 2
            Message(role="assistant", content="ok"),
            Message(role="user", content="next"),
        ]
        # candidate_cut=2: tool_use at 1 (< 2), result at 2 (>= 2) → unsafe
        self._check(msgs, candidate_cut=2)

    def test_multiple_pairs_all_cuts(self):
        """Multiple pairs, some crossing boundary — check all cuts."""
        msgs = [
            Message(role="user", content="q"),
            Message(
                role="assistant",
                content=[_tool_use_block("a"), _tool_use_block("b")],
            ),
            Message(role="user", content=[_tool_result_block("a")]),
            Message(role="assistant", content=[_tool_result_block("b")]),
            Message(role="user", content="more"),
            Message(role="assistant", content="ans"),
        ]
        for cut in range(1, 6):
            self._check(msgs, candidate_cut=cut)

    def test_candidate_zero_always_safe(self):
        msgs = [
            Message(role="user", content=[_tool_result_block("orphan")]),
        ]
        mm = _mm()
        mm._history = msgs[:]
        assert mm._find_safe_sliding_boundary(0) == 0


# ---------------------------------------------------------------------------
# M7 — Lightning tier enables memory
# ---------------------------------------------------------------------------


def _paths(tmp_path: Path) -> HachiPaths:
    return HachiPaths(
        config_dir=tmp_path / "config",
        data_dir=tmp_path / "data",
        cache_dir=tmp_path / "cache",
        state_dir=tmp_path / "state",
    )


class TestM7LightningMemory:
    def test_lightning_plan_enable_memory_true(self, tmp_path: Path):
        """build_tier_plan('lightning') must produce enable_memory=True."""
        svc = OnboardingService(paths=_paths(tmp_path))
        plan_dict = svc.build_tier_plan("lightning", answers={})
        plan = SetupPlan.model_validate(plan_dict)
        assert plan.enable_memory is True, (
            "Lightning tier must enable memory — it is core to the product"
        )

    def test_all_tiers_enable_memory(self, tmp_path: Path):
        """All tiers now enable memory by default."""
        svc = OnboardingService(paths=_paths(tmp_path))
        for tier in ("lightning", "recommended", "enhanced", "power"):
            plan_dict = svc.build_tier_plan(tier, answers={})
            plan = SetupPlan.model_validate(plan_dict)
            assert plan.enable_memory is True, f"Tier '{tier}' has enable_memory=False"

    def test_lightning_apply_setup_writes_memory_config(
        self, tmp_path: Path, monkeypatch
    ):
        """apply_setup() for lightning tier must write memory enabled to config."""
        from hachi.core.config_loader import load_effective_config

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        svc = OnboardingService(paths=_paths(tmp_path))
        answers = {
            "provider": {
                "kind": "anthropic",
                "model": "claude-haiku-4-5",
                "api_key_env": "ANTHROPIC_API_KEY",
            },
            "permission_tier": "guided",
        }
        plan_dict = svc.build_tier_plan("lightning", answers)
        svc.apply_setup(plan_dict, project_dir=None)

        config = load_effective_config(paths=_paths(tmp_path))
        assert config.memory.enable_session_history is True
        assert config.memory.enable_semantic_memory is True
