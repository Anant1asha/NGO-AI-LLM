"""
Hachi Ephemeral Sandbox Execution Engine

Backend options:
    - ``process`` (default): working-directory confinement via ``uv run`` subprocess.
      Dev-grade only — no namespace, seccomp, or network isolation.
    - ``container``: hardened Docker backend (operator opt-in).
      Set ``HACHI_SANDBOX_BACKEND=container`` and ensure Docker is available.
      Provides: network isolation (``--network none`` default), read-only filesystem,
      capability drop, no-new-privileges, resource limits (memory/pids/cpus/tmpfs).
      Requires ``HACHI_SANDBOX_PRODUCTION=1`` to expose the tool.

Select backend: ``HACHI_SANDBOX_BACKEND=process|container`` (default: ``process``).

WARNING — the process backend is defence-in-depth only, NOT a hardened boundary:
    * Working-directory confinement: the subprocess ``cwd`` is set to the per-execution
      directory inside ``sandbox_root``, and the minimal environment prevents accidental
      credential exposure via ``PATH``-style variables.
    * AST scan: blocks explicit ``~/.hachi/`` references before execution.
    * Env-gate: tool is only registered when ``HACHI_SANDBOX_PRODUCTION=1`` is set.

    True isolation (Linux namespaces / seccomp / gVisor / container) requires the
    container backend.  Until that is in place this layer is defence-in-depth and
    must not be used to execute untrusted third-party code in a multi-tenant context.
"""

import hashlib
import os
import shutil
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SandboxResult:
    """Represents the outcome of a sandbox execution."""

    stdout: str
    stderr: str
    exit_code: int
    duration_sec: float
    execution_dir: str
    success: bool

    @property
    def formatted_output(self) -> str:
        """Returns a consolidated view of the execution result for the LLM."""
        status = "SUCCESS" if self.success else "FAILED"
        output = (
            f"Execution Status: {status} (Exit Code: {self.exit_code})"
            f" in {self.duration_sec:.2f}s\n"
        )
        output += "-" * 40 + "\n"
        if self.stdout.strip():
            output += f"STDOUT:\n{self.stdout}\n"
        if self.stderr.strip():
            output += f"STDERR:\n{self.stderr}\n"
        if not self.stdout.strip() and not self.stderr.strip():
            output += "No output produced.\n"
        return output


# ---------------------------------------------------------------------------
# Shared dependency validation (used by both backends)
# ---------------------------------------------------------------------------

# Shell metacharacters and path indicators that must never appear in a PyPI package name.
_DEP_FORBIDDEN_CHARS: str = r";|&$(){}[]<>\n\t\\"


def validate_dependencies(dependencies: list[str]) -> None:
    """Reject dependency names containing shell metacharacters or path separators.

    This is the canonical validation shared by all sandbox backends.

    Args:
        dependencies: List of PyPI package names to validate.

    Raises:
        ValueError: If any dependency string contains a forbidden character or pattern.
    """
    import re

    # Characters that are unsafe to pass as package names.
    forbidden_pattern = re.compile(r"[;|&$(){}<>\[\]\n\t\\]")
    for dep in dependencies:
        if forbidden_pattern.search(dep):
            raise ValueError(f"Invalid dependency name: {dep}")
        # Reject path separators and relative/absolute path prefixes.
        if "/" in dep or "\\" in dep:
            raise ValueError(f"Invalid dependency name: {dep}")
        if dep.startswith(".") or dep.startswith("/"):
            raise ValueError(f"Invalid dependency name: {dep}")


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class SandboxBackend(ABC):
    """Abstract base for pluggable sandbox backends."""

    name: str
    is_hardened: bool

    @abstractmethod
    def execute(
        self,
        script_content: str,
        dependencies: list[str] | None = None,
        timeout: int = 120,
    ) -> SandboxResult:
        """Execute a Python script inside the sandbox.

        Args:
            script_content: Raw Python code to execute.
            dependencies: PyPI packages required (e.g. ``['pandas', 'requests']``).
            timeout: Maximum execution time in seconds.

        Returns:
            SandboxResult describing the execution outcome.
        """
        ...


# ---------------------------------------------------------------------------
# Process backend (existing behaviour, preserved exactly)
# ---------------------------------------------------------------------------


class SandboxExecutor(SandboxBackend):
    """
    Manages ephemeral execution of Python scripts using `uv`.

    Security note:
        This backend is intentionally classified as development-only.
    """

    name = "process"
    is_hardened = False

    def __init__(self, sandbox_root: str | None = None):
        """
        Initializes the Sandbox Executor.

        Args:
            sandbox_root: The directory where ephemeral environments will be built.
                          Defaults to ~/.hachi/sandbox.
        """
        if sandbox_root is None:
            self.sandbox_root = Path.home() / ".hachi" / "sandbox"
        else:
            self.sandbox_root = Path(sandbox_root)

        self.sandbox_root.mkdir(parents=True, exist_ok=True)
        self._uv_path = self._resolve_uv()

    def _resolve_uv(self) -> str:
        """
        Locates the `uv` executable.
        Raises EnvironmentError if `uv` is not installed on the system.
        """
        import sys

        # Check PATH first
        uv_path = shutil.which("uv")
        if uv_path:
            return uv_path

        # Check alongside the current python interpreter (e.g. inside a venv)
        uv_path_local = Path(sys.executable).parent / ("uv.exe" if os.name == "nt" else "uv")
        if uv_path_local.exists():
            return str(uv_path_local)

        raise OSError(
            "CRITICAL: The 'uv' package manager was not found on PATH or alongside Python. "
            "The Hachi Sandbox requires 'uv' to execute code securely. "
            "Please install it (e.g., pip install uv) or ensure it is accessible."
        )

    def _validate_dependencies(self, dependencies: list[str]) -> None:
        """
        Rejects dependency names that contain shell metacharacters or path separators.

        Delegates to the module-level ``validate_dependencies`` function so the
        container backend reuses the same validation logic.

        Raises:
            ValueError: If any dependency string contains a forbidden character or pattern.
        """
        validate_dependencies(dependencies)

    def _generate_env_hash(self, script_content: str, dependencies: list[str]) -> str:
        """Generates a stable hash for the specific execution payload."""
        payload = f"{script_content}-{'|'.join(sorted(dependencies))}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]

    def execute(
        self, script_content: str, dependencies: list[str] | None = None, timeout: int = 120
    ) -> SandboxResult:
        """
        Executes arbitrary Python code in an isolated, ephemeral environment.

        Args:
            script_content: The raw Python code to execute.
            dependencies: A list of PyPI packages required (e.g., ['pandas', 'requests']).
            timeout: Maximum execution time in seconds.

        Returns:
            SandboxResult: Contains the stdout, stderr, and execution metadata.
        """
        deps = dependencies or []
        self._validate_dependencies(deps)
        env_hash = self._generate_env_hash(script_content, deps)
        execution_dir = self.sandbox_root / f"exec_{env_hash}"
        start_time = time.time()
        execution_dir_str = str(execution_dir)

        try:
            execution_dir.mkdir(exist_ok=True)

            script_path = execution_dir / "main.py"
            script_path.write_text(script_content, encoding="utf-8")

            # Construct the uv run command.
            # Syntax: uv run --python 3.12 --with <dep> --with <dep> main.py
            # This implicitly manages downloading python and the dependencies without polluting
            # global state.
            cmd = [self._uv_path, "run"]
            for dep in deps:
                cmd.extend(["--with", dep])
            cmd.append(str(script_path))

            # G4-T4 (CRIT-005): cwd is explicitly set to the per-execution directory inside
            # sandbox_root, providing working-directory confinement.  Relative file access
            # by the script stays within execution_dir.  True namespace/seccomp isolation
            # requires the container backend (see module docstring).
            process = subprocess.run(
                cmd,
                cwd=str(execution_dir),
                capture_output=True,
                text=True,
                timeout=timeout,
                # Minimal environment to reduce credential/path leakage.
                env={
                    "PATH": os.environ.get("PATH", ""),
                    "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),  # Needed on Windows
                    "TMP": os.environ.get("TMP", ""),
                    "TEMP": os.environ.get("TEMP", ""),
                },
            )

            duration = time.time() - start_time
            return SandboxResult(
                stdout=process.stdout,
                stderr=process.stderr,
                exit_code=process.returncode,
                duration_sec=duration,
                execution_dir=execution_dir_str,
                success=(process.returncode == 0),
            )

        except subprocess.TimeoutExpired as e:
            duration = time.time() - start_time
            return SandboxResult(
                stdout=e.stdout.decode("utf-8", errors="replace") if e.stdout else "",
                stderr=e.stderr.decode("utf-8", errors="replace")
                if e.stderr
                else f"Execution timed out after {timeout} seconds.",
                exit_code=124,  # Standard timeout exit code
                duration_sec=duration,
                execution_dir=execution_dir_str,
                success=False,
            )
        except Exception as e:
            duration = time.time() - start_time
            return SandboxResult(
                stdout="",
                stderr=f"Sandbox execution crashed: {str(e)}",
                exit_code=-1,
                duration_sec=duration,
                execution_dir=execution_dir_str,
                success=False,
            )


# ---------------------------------------------------------------------------
# Container backend (hardened Docker)
# ---------------------------------------------------------------------------


class ContainerSandboxExecutor(SandboxBackend):
    """Hardened Docker-backed sandbox executor.

    All configuration is read from environment variables with safe defaults.
    Operators must have Docker available and set ``HACHI_SANDBOX_BACKEND=container``
    to use this backend.

    Environment variables:
        ``HACHI_SANDBOX_IMAGE``    — Docker image (default ``python:3.12-slim``)
        ``HACHI_SANDBOX_MEMORY``   — Memory limit (default ``512m``)
        ``HACHI_SANDBOX_PIDS``     — PID limit (default ``256``)
        ``HACHI_SANDBOX_CPUS``     — CPU quota (default ``1.0``)
        ``HACHI_SANDBOX_NETWORK``  — Network mode (default ``none``)
        ``HACHI_SANDBOX_USER``     — Run as user (default ``65534:65534`` — nobody:nogroup)
    """

    name = "container"
    is_hardened = True

    def __init__(self, sandbox_root: str | None = None) -> None:
        """Initialise the container backend from environment variables.

        Args:
            sandbox_root: Host scratch directory for per-execution script files.
                          Defaults to ``~/.hachi/sandbox``.
        """
        self._image = os.environ.get("HACHI_SANDBOX_IMAGE", "python:3.12-slim")
        self._memory = os.environ.get("HACHI_SANDBOX_MEMORY", "512m")
        self._pids = os.environ.get("HACHI_SANDBOX_PIDS", "256")
        self._cpus = os.environ.get("HACHI_SANDBOX_CPUS", "1.0")
        self._network = os.environ.get("HACHI_SANDBOX_NETWORK", "none")
        self._user = os.environ.get("HACHI_SANDBOX_USER", "65534:65534")

        if sandbox_root is None:
            self.sandbox_root = Path.home() / ".hachi" / "sandbox"
        else:
            self.sandbox_root = Path(sandbox_root)
        self.sandbox_root.mkdir(parents=True, exist_ok=True)

        self._docker_path = self._resolve_docker()

    def _resolve_docker(self) -> str:
        """Locate the ``docker`` executable on PATH.

        Raises:
            OSError: If ``docker`` is not found.
        """
        docker = shutil.which("docker")
        if not docker:
            raise OSError(
                "CRITICAL: The 'docker' executable was not found on PATH. "
                "The container sandbox backend requires Docker to be installed and running. "
                "Install Docker Desktop / Engine, or set HACHI_SANDBOX_BACKEND=process "
                "to use the process-isolation fallback."
            )
        return docker

    def _generate_exec_hash(self, script_content: str, dependencies: list[str]) -> str:
        """Generate a stable short hash for a given script + dependencies combination."""
        payload = f"{script_content}-{'|'.join(sorted(dependencies))}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]

    def execute(
        self,
        script_content: str,
        dependencies: list[str] | None = None,
        timeout: int = 120,
    ) -> SandboxResult:
        """Execute a Python script inside a hardened Docker container.

        Args:
            script_content: Raw Python code to execute.
            dependencies: PyPI packages required. NOTE: with ``--network none`` (the
                default) PyPI packages cannot be installed at runtime.  Either bake
                deps into ``HACHI_SANDBOX_IMAGE`` or set
                ``HACHI_SANDBOX_NETWORK=bridge``.
            timeout: Maximum execution time in seconds.

        Returns:
            SandboxResult describing the execution outcome.
        """
        deps = dependencies or []
        validate_dependencies(deps)

        # Fail-fast: deps + no-network is incoherent — tell the operator clearly.
        if deps and self._network == "none":
            return SandboxResult(
                stdout="",
                stderr=(
                    "Container sandbox error: PyPI dependencies cannot be installed "
                    "when HACHI_SANDBOX_NETWORK=none (the default). "
                    "Either bake the required packages into HACHI_SANDBOX_IMAGE "
                    "or set HACHI_SANDBOX_NETWORK=bridge to allow pip install at runtime."
                ),
                exit_code=-1,
                duration_sec=0.0,
                execution_dir="",
                success=False,
            )

        exec_hash = self._generate_exec_hash(script_content, deps)
        execution_dir = self.sandbox_root / f"exec_{exec_hash}"
        execution_dir_str = str(execution_dir)
        start_time = time.time()

        try:
            execution_dir.mkdir(parents=True, exist_ok=True)
            script_path = execution_dir / "main.py"
            script_path.write_text(script_content, encoding="utf-8")

            container_name = f"hachi-sb-{exec_hash}"

            # Build the fully-hardened docker run command (never shell=True).
            cmd: list[str] = [
                self._docker_path, "run",
                "--rm",
                "--network", self._network,
                "--read-only",
                "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges",
                "--user", self._user,
                "--memory", self._memory,
                "--memory-swap", self._memory,   # == memory ⇒ no swap
                "--pids-limit", self._pids,
                "--cpus", self._cpus,
                "--tmpfs", "/tmp:rw,size=64m",
                "-v", f"{execution_dir}:/work:ro",
                "-w", "/work",
                "--name", container_name,
                self._image,
                "python", "/work/main.py",
            ]

            try:
                process = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                duration = time.time() - start_time
                return SandboxResult(
                    stdout=process.stdout,
                    stderr=process.stderr,
                    exit_code=process.returncode,
                    duration_sec=duration,
                    execution_dir=execution_dir_str,
                    success=(process.returncode == 0),
                )
            except subprocess.TimeoutExpired:
                duration = time.time() - start_time
                # Best-effort container kill so it does not linger.
                try:
                    subprocess.run(
                        [self._docker_path, "kill", container_name],
                        capture_output=True,
                        timeout=10,
                    )
                except Exception:  # noqa: BLE001
                    pass
                return SandboxResult(
                    stdout="",
                    stderr=f"Container execution timed out after {timeout} seconds.",
                    exit_code=124,
                    duration_sec=duration,
                    execution_dir=execution_dir_str,
                    success=False,
                )

        except Exception as e:
            duration = time.time() - start_time
            return SandboxResult(
                stdout="",
                stderr=f"Container sandbox execution crashed: {str(e)}",
                exit_code=-1,
                duration_sec=duration,
                execution_dir=execution_dir_str,
                success=False,
            )


# ---------------------------------------------------------------------------
# Availability probe + factory
# ---------------------------------------------------------------------------


def container_backend_available() -> bool:
    """Return ``True`` if Docker is present on PATH, ``False`` otherwise."""
    return shutil.which("docker") is not None


def create_sandbox_backend(
    backend: str | None = None,
    *,
    sandbox_root: str | None = None,
) -> SandboxBackend:
    """Factory: return the configured sandbox backend.

    Args:
        backend: ``"process"`` or ``"container"``.  Defaults to the
            ``HACHI_SANDBOX_BACKEND`` env var, falling back to ``"process"``.
        sandbox_root: Optional scratch directory override.

    Returns:
        A ``SandboxBackend`` instance ready for use.

    Raises:
        OSError: When ``backend="container"`` but Docker is not available.
            **Never** silently downgrades to the weaker process backend — that
            would be a security surprise.
        ValueError: For unknown backend names.
    """
    resolved = (
        backend or os.environ.get("HACHI_SANDBOX_BACKEND", "process")
    ).strip().lower()

    if resolved == "process":
        return SandboxExecutor(sandbox_root=sandbox_root)

    if resolved == "container":
        if not container_backend_available():
            raise OSError(
                "HACHI_SANDBOX_BACKEND=container is set but Docker is not available on PATH. "
                "Install Docker Desktop / Engine, or set HACHI_SANDBOX_BACKEND=process."
            )
        return ContainerSandboxExecutor(sandbox_root=sandbox_root)

    raise ValueError(
        f"Unknown sandbox backend {resolved!r}. "
        "Valid values: 'process' (default), 'container'."
    )


# ---------------------------------------------------------------------------
# Audit-finding helper (pure, testable)
# ---------------------------------------------------------------------------


def sandbox_audit_finding(
    backend: str,
    docker_available: bool,
) -> tuple[str, str, str, str] | None:
    """Return an audit finding tuple or ``None`` when the backend is hardened and available.

    Args:
        backend: The configured backend name (value of ``HACHI_SANDBOX_BACKEND``).
        docker_available: Whether ``docker`` is present on PATH
            (pass ``container_backend_available()``).

    Returns:
        ``None`` if the active backend is hardened and operational — no finding to emit.
        Otherwise a ``(severity, id, message, recommendation)`` tuple.
    """
    resolved = backend.strip().lower()

    if resolved == "container":
        if docker_available:
            # Hardened backend active and operational — no finding.
            return None
        # Container selected but Docker is missing — HIGH finding.
        return (
            "high",
            "sandbox.container_unavailable",
            (
                "HACHI_SANDBOX_BACKEND=container is set but Docker is not available on PATH. "
                "The sandbox tool will fail closed when invoked."
            ),
            "Install Docker or set HACHI_SANDBOX_BACKEND=process.",
        )

    # Process backend (or any unrecognised value) — emit the existing medium finding.
    return (
        "medium",
        "sandbox.process_backend",
        "Current sandbox backend is process-isolation only and development-grade.",
        "Use a container-backed sandbox for production deployments.",
    )
