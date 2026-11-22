"""G4 security-depth regression tests.

G4-T2 (SEC-03): memory/recall responses must have secrets redacted before
    they reach the API client.

G4-T4 (CRIT-005): sandbox subprocess must run with cwd == the per-execution
    directory inside sandbox_root (working-directory confinement).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# G4-T2 — recall redaction
# ---------------------------------------------------------------------------

class TestMemoryRecallRedaction:
    """Secrets stored in memory must be redacted in GET /memory/recall responses."""

    _FAKE_SK_ANT = "sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    _FAKE_AWS = "AKIAIOSFODNN7EXAMPLE"

    def _make_runtime(self, vault_rows: list[dict]) -> object:
        """Return a minimal _InProcessGatewayRuntime-like object with a mocked vault."""
        # Import here so the module is available; we patch the vault only.
        from hachi.cli.main import _InProcessGatewayRuntime  # type: ignore[attr-defined]

        runtime = _InProcessGatewayRuntime.__new__(_InProcessGatewayRuntime)
        # Provide the lock and agents dict expected by get_memory_recall
        import threading
        runtime._agents_lock = threading.Lock()

        vault = MagicMock()
        vault.semantic_search.return_value = vault_rows

        agent = MagicMock()
        agent.vault = vault

        runtime._agents = {"session-1": agent}
        return runtime

    def test_anthropic_key_is_redacted_in_recall_fact(self) -> None:
        """A stored Anthropic API key must not appear verbatim in recall output."""
        rows = [
            {
                "content": f"My API key is {self._FAKE_SK_ANT}",
                "raw_content": f"My API key is {self._FAKE_SK_ANT}",
                "category": "workspace_state",
                "score": 0.9,
            }
        ]
        runtime = self._make_runtime(rows)
        results = runtime.get_memory_recall("api key", top_k=1)

        assert len(results) == 1
        assert self._FAKE_SK_ANT not in results[0]["fact"], (
            "Anthropic API key must be redacted in recall fact"
        )
        assert "[REDACTED" in results[0]["fact"]

    def test_aws_key_is_redacted_in_recall_fact(self) -> None:
        """A stored AWS access key must not appear verbatim in recall output."""
        rows = [
            {
                "content": f"AWS key: {self._FAKE_AWS}",
                "raw_content": f"AWS key: {self._FAKE_AWS}",
                "category": "workspace_state",
                "score": 0.85,
            }
        ]
        runtime = self._make_runtime(rows)
        results = runtime.get_memory_recall("aws credentials", top_k=1)

        assert len(results) == 1
        assert self._FAKE_AWS not in results[0]["fact"], (
            "AWS access key must be redacted in recall fact"
        )
        assert "[REDACTED" in results[0]["fact"]

    def test_safe_content_is_not_altered(self) -> None:
        """Non-secret content must pass through unmodified."""
        safe_text = "User prefers dark mode and Python 3.12"
        rows = [
            {
                "content": safe_text,
                "raw_content": safe_text,
                "category": "user_profile",
                "score": 0.7,
            }
        ]
        runtime = self._make_runtime(rows)
        results = runtime.get_memory_recall("preference", top_k=1)

        assert results[0]["fact"] == safe_text

    def test_empty_vault_returns_empty_list(self) -> None:
        """When there is no active agent, recall returns an empty list."""
        import threading

        from hachi.cli.main import _InProcessGatewayRuntime  # type: ignore[attr-defined]

        runtime = _InProcessGatewayRuntime.__new__(_InProcessGatewayRuntime)
        runtime._agents_lock = threading.Lock()
        runtime._agents = {}

        results = runtime.get_memory_recall("anything", top_k=5)
        assert results == []


# ---------------------------------------------------------------------------
# G4-T4 — sandbox working-directory confinement
# ---------------------------------------------------------------------------

class TestSandboxCwdConfinement:
    """Sandbox subprocess must always run with cwd == the execution_dir inside sandbox_root."""

    def test_subprocess_cwd_equals_execution_dir(self, tmp_path: Path) -> None:
        """subprocess.run must be called with cwd set to the per-execution directory."""
        from hachi.core.sandbox import SandboxExecutor

        executor = SandboxExecutor(sandbox_root=str(tmp_path))

        captured_kwargs: dict = {}

        def fake_run(cmd: list, **kwargs: object) -> MagicMock:
            captured_kwargs.update(kwargs)
            result = MagicMock()
            result.stdout = "hello"
            result.stderr = ""
            result.returncode = 0
            return result

        with patch("hachi.core.sandbox.subprocess.run", side_effect=fake_run):
            res = executor.execute("print('hello')")

        assert res.success is True

        # The cwd passed to subprocess must be the execution_dir inside sandbox_root
        cwd_used = Path(captured_kwargs["cwd"])
        assert cwd_used.parent == tmp_path, (
            f"subprocess cwd {cwd_used} must be a direct child of sandbox_root {tmp_path}"
        )
        assert cwd_used.name.startswith("exec_"), (
            "execution directory name must start with 'exec_'"
        )

    def test_execution_dir_is_inside_sandbox_root(self, tmp_path: Path) -> None:
        """SandboxResult.execution_dir must be under sandbox_root."""
        from hachi.core.sandbox import SandboxExecutor

        executor = SandboxExecutor(sandbox_root=str(tmp_path))

        def fake_run(cmd: list, **kwargs: object) -> MagicMock:
            result = MagicMock()
            result.stdout = ""
            result.stderr = ""
            result.returncode = 0
            return result

        with patch("hachi.core.sandbox.subprocess.run", side_effect=fake_run):
            res = executor.execute("x = 1")

        exec_dir = Path(res.execution_dir)
        assert str(exec_dir).startswith(str(tmp_path)), (
            f"execution_dir {exec_dir} must be inside sandbox_root {tmp_path}"
        )

    def test_env_gate_prevents_registration_without_flag(self, monkeypatch: object) -> None:
        """python_sandbox tool must NOT be registered without HACHI_SANDBOX_PRODUCTION=1."""
        monkeypatch.delenv("HACHI_SANDBOX_PRODUCTION", raising=False)

        from hachi.tools.sandbox_tools import register_sandbox_tools  # type: ignore[attr-defined]

        registry = MagicMock()
        register_sandbox_tools(registry)

        registry.register.assert_not_called()

    def test_env_gate_allows_registration_with_flag(self, monkeypatch: object) -> None:
        """python_sandbox tool must be registered when HACHI_SANDBOX_PRODUCTION=1."""
        monkeypatch.setenv("HACHI_SANDBOX_PRODUCTION", "1")

        from hachi.tools.sandbox_tools import register_sandbox_tools  # type: ignore[attr-defined]

        registry = MagicMock()
        # register_sandbox_tools may call registry.register; we just verify no exception.
        register_sandbox_tools(registry)
        # At minimum the registry was touched (register called once for python_sandbox).
        registry.register.assert_called_once()
