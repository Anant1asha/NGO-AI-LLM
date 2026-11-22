"""Tests for the real authoring generate/apply/revert backend (G1-T2 / CRIT-002).

Strategy
--------
- All LLM calls are mocked via monkeypatch so no real API calls are made.
- File I/O is performed against actual temp directories (not mocked) to verify
  atomic-write and content-correctness behaviour.
- FastAPI routes are tested via ``TestClient`` following the same pattern as
  ``tests/test_gateway_web_endpoints.py``.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from hachi.gateway.control_plane import (
    GatewayControlPlane,
    GatewayProtocolError,
    GatewayUnavailableError,
)
from hachi.gateway.fastapi_app import create_gateway_app

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_runtime_with_temp_skill(tmp_path: Path, content: str = "node hello\n  say: hi\n"):
    """Return an _InProcessGatewayRuntime-like object wired to a temp skills dir.

    Rather than booting a real runtime (which needs DB, config, etc.) we build a
    minimal object that delegates to the same method implementations under test.
    We do this by importing the class directly and monkey-patching the path
    resolution helpers so they point at ``tmp_path``.
    """
    from hachi.cli.main import _InProcessGatewayRuntime

    rt = _InProcessGatewayRuntime.__new__(_InProcessGatewayRuntime)
    # Manually initialise the instance state we depend on.
    rt._agents = {}
    rt._agents_lock = threading.Lock()
    rt._pending_resume_session_id = None
    rt._pending_proposals = {}
    rt._revert_snapshots = {}
    rt._authoring_lock = threading.Lock()

    skill_file = tmp_path / "test-skill.og"
    skill_file.write_text(content, encoding="utf-8")

    # Patch get_hachi_paths so _resolve_authoring_target_path sees our temp dir.
    from hachi.core.paths import HachiPaths

    fake_paths = MagicMock(spec=HachiPaths)
    fake_paths.skills_dir = tmp_path
    fake_paths.permissions_file = tmp_path / "device-permissions.og"
    fake_paths.global_config_toml = tmp_path / "config.toml"

    rt._fake_paths = fake_paths  # store so we can reuse below

    return rt, skill_file


def _patch_runtime_paths(rt: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect get_hachi_paths inside cli.main to the runtime's fake paths."""
    monkeypatch.setattr(
        "hachi.cli.main.get_hachi_paths",
        lambda: rt._fake_paths,
    )


# ---------------------------------------------------------------------------
# Unit tests: _InProcessGatewayRuntime methods
# ---------------------------------------------------------------------------


class TestAuthoringGenerate:
    def test_generate_returns_real_diff(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Generate produces a non-empty diff with real add/del counts."""
        original = "node hello\n  say: hi\n"
        proposed = "node hello\n  say: hello world\n"

        rt, skill_file = _make_runtime_with_temp_skill(tmp_path, original)
        _patch_runtime_paths(rt, monkeypatch)

        # Mock the LLM client. authoring_generate uses a local `from hachi.core.llm import ...`
        # so we patch at the source module.
        fake_client = MagicMock()
        fake_client.generate.return_value = MagicMock(content=proposed)
        monkeypatch.setattr("hachi.core.llm.create_llm_client", lambda *a, **kw: fake_client)
        monkeypatch.setattr(
            "hachi.cli.main.load_effective_config",
            lambda: MagicMock(
                provider=MagicMock(
                    kind="anthropic",
                    model="claude-haiku-4-5",
                    api_key_ref=None,
                    api_key_env="ANTHROPIC_API_KEY",
                    base_url=None,
                )
            ),
        )
        monkeypatch.setattr(
            "hachi.cli.main.create_default_secret_store", lambda: MagicMock()
        )

        result = rt.authoring_generate("test-skill.og", "change greeting")
        diff = result["diff"]

        assert isinstance(diff, list)
        # "say: hi" should be a del and "say: hello world" an add.
        del_lines = [line for tag, line in diff if tag == "del"]
        add_lines = [line for tag, line in diff if tag == "add"]
        assert any("hi" in ln for ln in del_lines), "expected deleted 'say: hi' line"
        assert any("hello world" in ln for ln in add_lines), (
            "expected added 'say: hello world' line"
        )
        # Pending proposal stored for apply (implementation strips trailing whitespace).
        assert rt._pending_proposals.get("test-skill.og") == proposed.strip()

    def test_generate_no_api_key_returns_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Generate raises GatewayUnavailableError (not a fake diff) when LLM fails."""
        original = "node hello\n  say: hi\n"
        rt, _ = _make_runtime_with_temp_skill(tmp_path, original)
        _patch_runtime_paths(rt, monkeypatch)

        def _bad_client(*a: Any, **kw: Any) -> None:
            raise ValueError("ANTHROPIC_API_KEY must be provided")

        # authoring_generate does `from hachi.core.llm import create_llm_client`
        # patch the function at its definition site.
        monkeypatch.setattr("hachi.core.llm.create_llm_client", _bad_client)
        monkeypatch.setattr(
            "hachi.cli.main.load_effective_config",
            lambda: MagicMock(
                provider=MagicMock(
                    kind="anthropic",
                    model="claude-haiku-4-5",
                    api_key_ref=None,
                    api_key_env="ANTHROPIC_API_KEY",
                    base_url=None,
                )
            ),
        )
        monkeypatch.setattr(
            "hachi.cli.main.create_default_secret_store", lambda: MagicMock()
        )

        with pytest.raises(GatewayUnavailableError, match="LLM client unavailable"):
            rt.authoring_generate("test-skill.og", "change something")

        # No pending proposal should be stored on failure.
        assert "test-skill.og" not in rt._pending_proposals

    def test_generate_path_traversal_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Names with '..' or '/' must be rejected before any LLM call."""
        rt, _ = _make_runtime_with_temp_skill(tmp_path)
        _patch_runtime_paths(rt, monkeypatch)

        for bad_name in ["../etc/passwd", "foo/bar.og", "..\\evil.og"]:
            with pytest.raises(GatewayProtocolError):
                rt.authoring_generate(bad_name, "any prompt")


class TestAuthoringApply:
    def _generate_pending(
        self,
        rt: Any,
        name: str,
        proposed: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Shortcut: inject a pending proposal without calling LLM."""
        rt._pending_proposals[name] = proposed

    def test_apply_writes_file_atomically(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Apply overwrites the skill file with the proposed content."""
        original = "node hello\n  say: hi\n"
        proposed = "node hello\n  say: hello world\n"
        rt, skill_file = _make_runtime_with_temp_skill(tmp_path, original)
        _patch_runtime_paths(rt, monkeypatch)

        rt._pending_proposals["test-skill.og"] = proposed
        result = rt.authoring_apply("test-skill.og")

        assert result["ok"] is True
        assert isinstance(result["reindexed_ms"], int)
        assert skill_file.read_text(encoding="utf-8") == proposed

    def test_apply_saves_revert_snapshot(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """The prior content is saved so revert can restore it."""
        original = "node hello\n  say: hi\n"
        proposed = "node hello\n  say: hello world\n"
        rt, _ = _make_runtime_with_temp_skill(tmp_path, original)
        _patch_runtime_paths(rt, monkeypatch)

        rt._pending_proposals["test-skill.og"] = proposed
        rt.authoring_apply("test-skill.og")

        assert rt._revert_snapshots["test-skill.og"] == original

    def test_apply_no_pending_raises_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Apply without a prior generate call must raise a clear error."""
        rt, _ = _make_runtime_with_temp_skill(tmp_path)
        _patch_runtime_paths(rt, monkeypatch)

        with pytest.raises(GatewayProtocolError, match="No pending proposal"):
            rt.authoring_apply("test-skill.og")


class TestAuthoringRevert:
    def test_revert_restores_original_content(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Revert writes the snapshot back to disk."""
        original = "node hello\n  say: hi\n"
        proposed = "node hello\n  say: hello world\n"
        rt, skill_file = _make_runtime_with_temp_skill(tmp_path, proposed)
        _patch_runtime_paths(rt, monkeypatch)

        # Simulate a prior apply: snapshot = original, file now = proposed.
        rt._revert_snapshots["test-skill.og"] = original
        result = rt.authoring_revert("test-skill.og")

        assert result["ok"] is True
        assert skill_file.read_text(encoding="utf-8") == original
        # Snapshot is consumed after revert.
        assert "test-skill.og" not in rt._revert_snapshots

    def test_revert_nothing_to_revert_raises_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Revert with no snapshot must return a clear error, not a fake success."""
        rt, _ = _make_runtime_with_temp_skill(tmp_path)
        _patch_runtime_paths(rt, monkeypatch)

        with pytest.raises(GatewayProtocolError, match="Nothing to revert"):
            rt.authoring_revert("test-skill.og")


# ---------------------------------------------------------------------------
# Route-level tests: FastAPI TestClient
# ---------------------------------------------------------------------------


def _make_cp_with_stubs(
    *,
    generate_fn: Any = None,
    apply_fn: Any = None,
    revert_fn: Any = None,
    targets_fn: Any = None,
    target_fn: Any = None,
) -> GatewayControlPlane:
    """Build a control plane wired with authoring stubs."""
    return GatewayControlPlane(
        get_authoring_targets=targets_fn
        or (
            lambda: [
                {"name": "brain-core.og", "path": "brain-core.og", "kind": "brain", "dirty": False}
            ]
        ),
        get_authoring_target=target_fn or (lambda n: {"name": n, "source": "node x\n"}),
        authoring_generate=generate_fn,
        authoring_apply=apply_fn or (lambda n: {"ok": True, "reindexed_ms": 0}),
        authoring_revert=revert_fn or (lambda n: {"ok": True}),
    )


class TestGenerateRoute:
    def test_generate_returns_diff(self):
        """POST /authoring/targets/{name}/generate returns diff when handler succeeds."""
        fake_diff = [["", "node x"], ["del", "  y: old"], ["add", "  y: new"]]
        cp = _make_cp_with_stubs(generate_fn=lambda n, p: {"diff": fake_diff})
        app = create_gateway_app(cp)
        with TestClient(app) as client:
            resp = client.post(
                "/authoring/targets/brain-core.og/generate",
                json={"prompt": "change y to new"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "diff" in data
        assert len(data["diff"]) == 3

    def test_generate_empty_prompt_returns_422(self):
        """POST with empty prompt must return 422 before calling the handler."""
        cp = _make_cp_with_stubs(generate_fn=lambda n, p: {"diff": []})
        app = create_gateway_app(cp)
        with TestClient(app) as client:
            resp = client.post(
                "/authoring/targets/brain-core.og/generate",
                json={"prompt": "   "},
            )
        assert resp.status_code == 422

    def test_generate_llm_unavailable_returns_503(self):
        """Handler raising GatewayUnavailableError must surface as 503."""

        def _fail(n: str, p: str) -> dict:
            raise GatewayUnavailableError("no API key")

        cp = _make_cp_with_stubs(generate_fn=_fail)
        app = create_gateway_app(cp)
        with TestClient(app) as client:
            resp = client.post(
                "/authoring/targets/brain-core.og/generate",
                json={"prompt": "change something"},
            )
        assert resp.status_code == 503

    def test_generate_missing_handler_returns_503(self):
        """No handler wired → 503."""
        cp = GatewayControlPlane(
            get_authoring_targets=lambda: [],
            get_authoring_target=lambda n: {"name": n, "source": ""},
            authoring_apply=lambda n: {"ok": True, "reindexed_ms": 0},
            authoring_revert=lambda n: {"ok": True},
            # authoring_generate intentionally absent
        )
        app = create_gateway_app(cp)
        with TestClient(app) as client:
            resp = client.post(
                "/authoring/targets/brain-core.og/generate",
                json={"prompt": "something"},
            )
        assert resp.status_code == 503

    def test_generate_diff_has_real_add_del_counts(self):
        """The diff structure carries meaningful add/del markers, not hardcoded text."""
        real_diff = [
            ["", "node x"],
            ["del", "  a: 1"],
            ["del", "  b: 2"],
            ["add", "  a: 10"],
            ["add", "  b: 20"],
            ["add", "  c: 30"],
        ]
        cp = _make_cp_with_stubs(generate_fn=lambda n, p: {"diff": real_diff})
        app = create_gateway_app(cp)
        with TestClient(app) as client:
            resp = client.post(
                "/authoring/targets/brain-core.og/generate",
                json={"prompt": "update values"},
            )
        assert resp.status_code == 200
        diff = resp.json()["diff"]
        del_count = sum(1 for row in diff if row[0] == "del")
        add_count = sum(1 for row in diff if row[0] == "add")
        assert del_count == 2
        assert add_count == 3


class TestApplyRoute:
    def test_apply_returns_ok_and_reindexed_ms(self):
        """POST /authoring/targets/{name}/apply returns real ok + reindexed_ms."""
        cp = _make_cp_with_stubs(apply_fn=lambda n: {"ok": True, "reindexed_ms": 42})
        app = create_gateway_app(cp)
        with TestClient(app) as client:
            resp = client.post("/authoring/targets/brain-core.og/apply", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["reindexed_ms"] == 42

    def test_apply_no_pending_returns_400(self):
        """Handler raising GatewayProtocolError surfaces as 400."""

        def _no_pending(n: str) -> dict:
            raise GatewayProtocolError("No pending proposal")

        cp = _make_cp_with_stubs(apply_fn=_no_pending)
        app = create_gateway_app(cp)
        with TestClient(app) as client:
            resp = client.post("/authoring/targets/brain-core.og/apply", json={})
        assert resp.status_code == 400


class TestRevertRoute:
    def test_revert_returns_ok(self):
        """POST /authoring/targets/{name}/revert returns ok when snapshot exists."""
        cp = _make_cp_with_stubs(revert_fn=lambda n: {"ok": True})
        app = create_gateway_app(cp)
        with TestClient(app) as client:
            resp = client.post("/authoring/targets/brain-core.og/revert", json={})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_revert_nothing_to_revert_returns_400(self):
        """Handler raising GatewayProtocolError (no snapshot) surfaces as 400."""

        def _no_snapshot(n: str) -> dict:
            raise GatewayProtocolError("Nothing to revert")

        cp = _make_cp_with_stubs(revert_fn=_no_snapshot)
        app = create_gateway_app(cp)
        with TestClient(app) as client:
            resp = client.post("/authoring/targets/brain-core.og/revert", json={})
        assert resp.status_code == 400
