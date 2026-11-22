"""Tests for the pluggable sandbox backend (S1).

All tests are unit-level — no live Docker required.
``subprocess.run`` and ``shutil.which`` are mocked throughout.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from hachi.core.sandbox import (
    ContainerSandboxExecutor,
    SandboxBackend,
    SandboxExecutor,
    container_backend_available,
    create_sandbox_backend,
    sandbox_audit_finding,
    validate_dependencies,
)

# ---------------------------------------------------------------------------
# Factory tests
# ---------------------------------------------------------------------------


class TestCreateSandboxBackend:
    """create_sandbox_backend() must return the right backend and fail-fast correctly."""

    def test_default_is_process_backend(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With no HACHI_SANDBOX_BACKEND, factory returns a SandboxExecutor."""
        monkeypatch.delenv("HACHI_SANDBOX_BACKEND", raising=False)
        with patch("hachi.core.sandbox.shutil.which", return_value="/usr/bin/uv"):
            backend = create_sandbox_backend()
        assert isinstance(backend, SandboxExecutor)
        assert backend.name == "process"
        assert backend.is_hardened is False

    def test_explicit_process_returns_sandbox_executor(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HACHI_SANDBOX_BACKEND", "process")
        with patch("hachi.core.sandbox.shutil.which", return_value="/usr/bin/uv"):
            backend = create_sandbox_backend(backend="process")
        assert isinstance(backend, SandboxExecutor)
        assert backend.name == "process"

    def test_container_with_docker_present_returns_container_executor(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When docker is on PATH, factory returns a ContainerSandboxExecutor."""

        def fake_which(name: str) -> str | None:
            return "/usr/bin/docker" if name == "docker" else None

        with patch("hachi.core.sandbox.shutil.which", side_effect=fake_which):
            backend = create_sandbox_backend(backend="container", sandbox_root=str(tmp_path))
        assert isinstance(backend, ContainerSandboxExecutor)
        assert backend.name == "container"
        assert backend.is_hardened is True

    def test_container_without_docker_raises_os_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """factory MUST fail-fast; never silently fall back to process."""
        with patch("hachi.core.sandbox.shutil.which", return_value=None):
            with pytest.raises(OSError, match="[Dd]ocker"):
                create_sandbox_backend(backend="container")

    def test_unknown_backend_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown sandbox backend"):
            create_sandbox_backend(backend="gvisor")

    def test_env_var_selects_container(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("HACHI_SANDBOX_BACKEND", "container")

        def fake_which(name: str) -> str | None:
            return "/usr/bin/docker" if name == "docker" else None

        with patch("hachi.core.sandbox.shutil.which", side_effect=fake_which):
            backend = create_sandbox_backend(sandbox_root=str(tmp_path))
        assert backend.name == "container"


# ---------------------------------------------------------------------------
# ContainerSandboxExecutor — attributes and command construction
# ---------------------------------------------------------------------------


class TestContainerSandboxExecutor:
    """Tests for the container backend without live Docker."""

    def _make_executor(self, tmp_path: Path, **env_overrides: str) -> ContainerSandboxExecutor:
        """Return a ContainerSandboxExecutor with docker stubbed out."""

        def fake_which(name: str) -> str | None:
            return "/usr/bin/docker" if name == "docker" else None

        with patch("hachi.core.sandbox.shutil.which", side_effect=fake_which):
            with patch.dict("os.environ", env_overrides, clear=False):
                return ContainerSandboxExecutor(sandbox_root=str(tmp_path))

    def test_name_and_is_hardened(self, tmp_path: Path) -> None:
        executor = self._make_executor(tmp_path)
        assert executor.name == "container"
        assert executor.is_hardened is True

    def test_is_subclass_of_sandbox_backend(self, tmp_path: Path) -> None:
        executor = self._make_executor(tmp_path)
        assert isinstance(executor, SandboxBackend)

    def test_command_contains_all_hardening_flags(self, tmp_path: Path) -> None:
        """The docker run command MUST include every required hardening flag."""
        executor = self._make_executor(tmp_path)

        captured: list[list[str]] = []

        def fake_run(
            cmd: list[str], *args: Any, **kwargs: Any
        ) -> MagicMock:
            captured.append(cmd)
            result = MagicMock()
            result.stdout = "hello"
            result.stderr = ""
            result.returncode = 0
            return result

        with patch("hachi.core.sandbox.subprocess.run", side_effect=fake_run):
            result = executor.execute("print('hi')")

        assert result.success is True
        assert len(captured) == 1
        cmd = captured[0]

        # Must be a list (no shell=True)
        assert isinstance(cmd, list)

        # All required hardening flags
        assert "--rm" in cmd
        assert "--network" in cmd
        assert "none" in cmd
        assert "--read-only" in cmd
        assert "--cap-drop" in cmd
        assert "ALL" in cmd
        assert "--security-opt" in cmd
        assert "no-new-privileges" in cmd
        assert "--user" in cmd
        assert "--memory" in cmd
        assert "--pids-limit" in cmd
        assert "--cpus" in cmd
        assert "--tmpfs" in cmd
        assert "python:3.12-slim" in cmd
        assert "python" in cmd
        # Volume mount with read-only flag
        assert any(":ro" in arg for arg in cmd), "Volume must be mounted read-only"
        # Working directory
        assert "-w" in cmd
        assert "/work" in cmd

    def test_stdout_and_exit_code_flow_into_result(self, tmp_path: Path) -> None:
        executor = self._make_executor(tmp_path)

        def fake_run(cmd: list[str], *args: Any, **kwargs: Any) -> MagicMock:
            result = MagicMock()
            result.stdout = "output here"
            result.stderr = ""
            result.returncode = 0
            return result

        with patch("hachi.core.sandbox.subprocess.run", side_effect=fake_run):
            result = executor.execute("print('output here')")

        assert result.stdout == "output here"
        assert result.exit_code == 0
        assert result.success is True

    def test_failed_exit_code_maps_correctly(self, tmp_path: Path) -> None:
        executor = self._make_executor(tmp_path)

        def fake_run(cmd: list[str], *args: Any, **kwargs: Any) -> MagicMock:
            result = MagicMock()
            result.stdout = ""
            result.stderr = "error!"
            result.returncode = 1
            return result

        with patch("hachi.core.sandbox.subprocess.run", side_effect=fake_run):
            result = executor.execute("raise ValueError('x')")

        assert result.exit_code == 1
        assert result.success is False

    def test_timeout_returns_exit_code_124(self, tmp_path: Path) -> None:
        executor = self._make_executor(tmp_path)
        docker_killed: list[list[str]] = []

        def fake_run(cmd: list[str], *args: Any, **kwargs: Any) -> MagicMock:
            if "kill" in cmd:
                docker_killed.append(cmd)
                return MagicMock()
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=1)

        with patch("hachi.core.sandbox.subprocess.run", side_effect=fake_run):
            result = executor.execute("while True: pass", timeout=1)

        assert result.exit_code == 124
        assert result.success is False
        assert "timed out" in result.stderr.lower()
        # Best-effort kill should have been attempted
        assert any("kill" in c for c in docker_killed)

    def test_deps_with_network_none_fails_without_docker_run(self, tmp_path: Path) -> None:
        """With deps + network=none the executor must fail before calling docker run."""
        executor = self._make_executor(tmp_path, HACHI_SANDBOX_NETWORK="none")

        docker_run_called: list[bool] = []

        def fake_run(cmd: list[str], *args: Any, **kwargs: Any) -> MagicMock:
            if "run" in cmd and "docker" in cmd[0]:
                docker_run_called.append(True)
            return MagicMock()

        with patch("hachi.core.sandbox.subprocess.run", side_effect=fake_run):
            result = executor.execute("import pandas", dependencies=["pandas"])

        assert result.success is False
        assert result.exit_code == -1
        assert "HACHI_SANDBOX_NETWORK" in result.stderr or "network" in result.stderr.lower()
        # docker run must NOT have been called
        assert not docker_run_called

    def test_no_deps_runs_successfully(self, tmp_path: Path) -> None:
        """No deps + network=none is valid — docker run should be called."""
        executor = self._make_executor(tmp_path)

        docker_run_called: list[bool] = []

        def fake_run(cmd: list[str], *args: Any, **kwargs: Any) -> MagicMock:
            if "run" in cmd:
                docker_run_called.append(True)
            result = MagicMock()
            result.stdout = "42"
            result.stderr = ""
            result.returncode = 0
            return result

        with patch("hachi.core.sandbox.subprocess.run", side_effect=fake_run):
            result = executor.execute("print(42)")

        assert result.success is True
        assert docker_run_called

    def test_custom_image_via_env(self, tmp_path: Path) -> None:
        executor = self._make_executor(tmp_path, HACHI_SANDBOX_IMAGE="my-org/python:custom")

        captured: list[list[str]] = []

        def fake_run(cmd: list[str], *args: Any, **kwargs: Any) -> MagicMock:
            captured.append(cmd)
            result = MagicMock()
            result.stdout = ""
            result.stderr = ""
            result.returncode = 0
            return result

        with patch("hachi.core.sandbox.subprocess.run", side_effect=fake_run):
            executor.execute("pass")

        assert "my-org/python:custom" in captured[0]

    def test_resolve_docker_raises_when_absent(self) -> None:
        with patch("hachi.core.sandbox.shutil.which", return_value=None):
            executor = ContainerSandboxExecutor.__new__(ContainerSandboxExecutor)
            with pytest.raises(OSError, match="docker"):
                ContainerSandboxExecutor._resolve_docker(executor)


# ---------------------------------------------------------------------------
# validate_dependencies (module-level function, shared by both backends)
# ---------------------------------------------------------------------------


class TestValidateDependencies:
    """Module-level validate_dependencies must reject unsafe names."""

    def test_valid_package_names_pass(self) -> None:
        validate_dependencies(["pandas", "requests", "numpy==1.26.0", "my-pkg"])

    def test_semicolon_rejected(self) -> None:
        with pytest.raises(ValueError, match="Invalid dependency name"):
            validate_dependencies(["ok", "bad;pkg"])

    def test_pipe_rejected(self) -> None:
        with pytest.raises(ValueError, match="Invalid dependency name"):
            validate_dependencies(["bad|pkg"])

    def test_forward_slash_rejected(self) -> None:
        with pytest.raises(ValueError, match="Invalid dependency name"):
            validate_dependencies(["/usr/local/lib/evil.py"])

    def test_backslash_rejected(self) -> None:
        with pytest.raises(ValueError, match="Invalid dependency name"):
            validate_dependencies(["C:\\evil\\pkg"])

    def test_dot_prefix_rejected(self) -> None:
        with pytest.raises(ValueError, match="Invalid dependency name"):
            validate_dependencies(["../evil"])

    def test_dollar_sign_rejected(self) -> None:
        with pytest.raises(ValueError, match="Invalid dependency name"):
            validate_dependencies(["$HOME"])

    def test_empty_list_passes(self) -> None:
        validate_dependencies([])  # should not raise


# ---------------------------------------------------------------------------
# sandbox_audit_finding (pure helper)
# ---------------------------------------------------------------------------


class TestSandboxAuditFinding:
    """sandbox_audit_finding must return correct tuples for all combinations."""

    def test_container_with_docker_returns_none(self) -> None:
        assert sandbox_audit_finding("container", docker_available=True) is None

    def test_container_without_docker_returns_high(self) -> None:
        finding = sandbox_audit_finding("container", docker_available=False)
        assert finding is not None
        severity, finding_id, message, recommendation = finding
        assert severity == "high"
        assert finding_id == "sandbox.container_unavailable"
        assert "docker" in message.lower() or "Docker" in message
        assert "HACHI_SANDBOX_BACKEND" in message

    def test_process_backend_returns_medium(self) -> None:
        finding = sandbox_audit_finding("process", docker_available=False)
        assert finding is not None
        severity, finding_id, _, _ = finding
        assert severity == "medium"
        assert finding_id == "sandbox.process_backend"

    def test_process_backend_docker_present_still_medium(self) -> None:
        """Docker being present doesn't matter for the process backend."""
        finding = sandbox_audit_finding("process", docker_available=True)
        assert finding is not None
        severity, finding_id, _, _ = finding
        assert severity == "medium"
        assert finding_id == "sandbox.process_backend"

    def test_default_empty_string_returns_medium(self) -> None:
        """A blank / unrecognised backend value falls through to the medium finding."""
        finding = sandbox_audit_finding("", docker_available=False)
        assert finding is not None
        assert finding[0] == "medium"
        assert finding[1] == "sandbox.process_backend"

    def test_unknown_backend_string_returns_medium(self) -> None:
        finding = sandbox_audit_finding("gvisor", docker_available=True)
        assert finding is not None
        assert finding[0] == "medium"

    def test_container_finding_has_four_elements(self) -> None:
        finding = sandbox_audit_finding("container", docker_available=False)
        assert finding is not None
        assert len(finding) == 4

    def test_process_finding_has_four_elements(self) -> None:
        finding = sandbox_audit_finding("process", docker_available=False)
        assert finding is not None
        assert len(finding) == 4

    def test_whitespace_in_backend_name_is_stripped(self) -> None:
        """Env vars may have leading/trailing whitespace."""
        assert sandbox_audit_finding("  container  ", docker_available=True) is None
        finding = sandbox_audit_finding("  process  ", docker_available=False)
        assert finding is not None
        assert finding[1] == "sandbox.process_backend"


# ---------------------------------------------------------------------------
# container_backend_available
# ---------------------------------------------------------------------------


class TestContainerBackendAvailable:
    def test_returns_true_when_docker_on_path(self) -> None:
        with patch("hachi.core.sandbox.shutil.which", return_value="/usr/bin/docker"):
            assert container_backend_available() is True

    def test_returns_false_when_docker_absent(self) -> None:
        with patch("hachi.core.sandbox.shutil.which", return_value=None):
            assert container_backend_available() is False


# ---------------------------------------------------------------------------
# SandboxExecutor backward-compat: _validate_dependencies still works as method
# ---------------------------------------------------------------------------


class TestSandboxExecutorValidateDepsMethod:
    """_validate_dependencies on SandboxExecutor must still work (test_phase7 calls it)."""

    def test_method_accepts_valid_deps(self, tmp_path: Path) -> None:
        with patch("hachi.core.sandbox.shutil.which", return_value="/usr/bin/uv"):
            executor = SandboxExecutor(sandbox_root=str(tmp_path))
        executor._validate_dependencies(["requests", "pandas"])  # should not raise

    def test_method_rejects_invalid_deps(self, tmp_path: Path) -> None:
        with patch("hachi.core.sandbox.shutil.which", return_value="/usr/bin/uv"):
            executor = SandboxExecutor(sandbox_root=str(tmp_path))
        with pytest.raises(ValueError, match="Invalid dependency name"):
            executor._validate_dependencies(["bad;dep"])
