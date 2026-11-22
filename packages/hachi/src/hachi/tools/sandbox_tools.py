"""
Hachi Sandbox Tools

Exposes the Ephemeral Python Sandbox to the LLM orchestration engine.

WARNING (CRIT-005):
    The python_sandbox tool provides process-isolation only — it does NOT enforce
    network egress restrictions, filesystem namespace isolation, or syscall filtering.
    It must NOT be exposed in production deployments unless the operator has explicitly
    opted in by setting HACHI_SANDBOX_PRODUCTION=1.

    When HACHI_SANDBOX_PRODUCTION=1 is set, the tool is registered and a CRITICAL
    log entry is emitted so operators know the sandbox is live.
"""

import ast
import logging
import os

from hachi.core.loop import ToolRegistry
from hachi.core.permissions import PermissionGate

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# AST-based pre-execution scan (CRIT-005b)
# ---------------------------------------------------------------------------

_BLOCKED_PATH_FRAGMENTS: tuple[str, ...] = (
    # ~/.hachi/ contains the gateway token, vault DB, credentials, etc.
    ".hachi",
    "/.hachi",
    "\\.hachi",
    # Common locations for gateway tokens and secrets
    "HACHI_TOKEN",
    "HACHI_API_KEY",
    "HACHI_GATEWAY_TOKEN",
)


def _ast_scan_for_sensitive_paths(script_content: str) -> str | None:
    """Scan a Python script for references to sensitive paths/env-vars.

    Uses the AST rather than regex so it catches f-strings, concatenations,
    and indirect references at a surface level.  A simple grep over the raw
    source text is also applied as a belt-and-suspenders check.

    Returns:
        A human-readable reason string if a blocked pattern is found, else None.
    """
    # Belt-and-suspenders: raw source scan first (catches strings not yet parsed)
    lower_src = script_content.lower()
    for fragment in _BLOCKED_PATH_FRAGMENTS:
        if fragment.lower() in lower_src:
            return (
                f"Script references a sensitive path or token pattern: {fragment!r}. "
                "Accessing ~/.hachi/ or gateway credentials from inside the sandbox is blocked."
            )

    # AST scan for string literals containing blocked fragments
    try:
        tree = ast.parse(script_content, mode="exec")
    except SyntaxError:
        # Let the executor surface the real syntax error to the LLM.
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            val_lower = node.value.lower()
            for fragment in _BLOCKED_PATH_FRAGMENTS:
                if fragment.lower() in val_lower:
                    return (
                        f"Script contains a string literal referencing sensitive "
                        f"path/token pattern: {fragment!r}. "
                        "Accessing ~/.hachi/ or gateway credentials from inside the sandbox "
                        "is blocked."
                    )

    return None


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


def register_sandbox_tools(registry: ToolRegistry, gate: PermissionGate = None) -> None:
    """Registers the python_sandbox tool.

    The tool is only registered when HACHI_SANDBOX_PRODUCTION=1 is set in the
    environment (CRIT-005a).  When enabled, a CRITICAL warning is logged.

    When the tool is invoked:
      - Tier gating blocks sandbox/guided tiers (existing behaviour).
      - An AST pre-execution scan blocks scripts that reference ~/.hachi/ or
        gateway token environment variables (CRIT-005b).
    """
    # CRIT-005a: explicit operator opt-in required to expose the sandbox tool.
    sandbox_enabled = os.environ.get("HACHI_SANDBOX_PRODUCTION", "").strip() == "1"
    if not sandbox_enabled:
        logger.debug(
            "python_sandbox tool NOT registered: "
            "set HACHI_SANDBOX_PRODUCTION=1 to enable (process-isolation only, "
            "not a hardened security boundary)."
        )
        return

    _active_backend = os.environ.get("HACHI_SANDBOX_BACKEND", "process").strip().lower()
    if _active_backend == "container":
        logger.warning(
            "HACHI_SANDBOX_PRODUCTION=1 is set — python_sandbox tool is ACTIVE "
            "with the container (Docker) backend. "
            "Container-isolated execution is enabled; ensure Docker is available."
        )
    else:
        logger.critical(
            "HACHI_SANDBOX_PRODUCTION=1 is set — python_sandbox tool is ACTIVE. "
            "This tool provides process-isolation only and grants unrestricted host "
            "filesystem and network access within the subprocess.  Do NOT use in "
            "multi-tenant or publicly reachable deployments without additional "
            "container/syscall isolation."
        )

    # Backend is constructed lazily on first call so a missing binary (uv / docker)
    # does not raise during tool registration and block the rest of the registry.
    from hachi.core.sandbox import SandboxBackend, create_sandbox_backend

    _executor: list[SandboxBackend] = []

    def run_python_sandbox(script_content: str, dependencies: list = None) -> str:
        """
        Execute Python code in an ephemeral environment.

        The sandbox backend is selected by HACHI_SANDBOX_BACKEND (default: process).
        With the process backend this tool provides process-isolation only — it is
        NOT a hardened security sandbox.  Network egress, filesystem access outside
        the execution directory, and environment variable visibility are NOT
        restricted.  With the container backend a hardened Docker sandbox is used.
        The operator has explicitly enabled this tool by setting
        HACHI_SANDBOX_PRODUCTION=1.
        """
        if gate is not None:
            # Use the public `tier` property: both PermissionGate and
            # InteractivePermissionGate expose it, but only the former has the
            # private `_tier`. Reading `_tier` returned None under the interactive
            # gate (the TUI path), silently disabling this restriction.
            tier = getattr(gate, "tier", None)
            if tier in ("sandbox", "guided"):
                raise PermissionError(
                    f"python_sandbox is not available in {tier} tier"
                    " -- it grants unrestricted host access."
                )

        # CRIT-005b: AST pre-execution scan for sensitive path references.
        block_reason = _ast_scan_for_sensitive_paths(script_content)
        if block_reason:
            return f"[python_sandbox blocked] {block_reason}"

        try:
            if not _executor:
                backend = create_sandbox_backend()
                if backend.is_hardened:
                    logger.warning(
                        "python_sandbox: container-isolated backend is active "
                        "(backend=%s). Hardened mode enabled.",
                        backend.name,
                    )
                else:
                    logger.critical(
                        "python_sandbox: process-isolation backend is active — "
                        "this grants unrestricted host filesystem and network access "
                        "within the subprocess.  Do NOT use in multi-tenant or publicly "
                        "reachable deployments without additional container/syscall isolation."
                    )
                _executor.append(backend)
            result = _executor[0].execute(script_content, dependencies)
            return result.formatted_output
        except OSError as e:
            return str(e)
        except Exception as e:
            return f"Sandbox tool failed: {str(e)}"

    registry.register(
        {
            "name": "python_sandbox",
            "description": (
                "Execute Python code in an ephemeral environment managed by uv. "
                "IMPORTANT: This tool provides process-isolation only — it is NOT a "
                "hardened security sandbox.  Network egress, host filesystem access, "
                "and environment variables are NOT restricted. "
                "Use this tool for data processing, web scraping, chart generation "
                "(matplotlib), or math calculations. "
                "DO NOT use this for OS file management or email sending (use the "
                "native tools for that). "
                "The environment automatically installs requested PyPI dependencies "
                "using 'uv'. "
                "Outputs must be communicated via print() statements. If you generate "
                "a file (e.g. a PNG chart), save it to an absolute path (like the "
                "user's Desktop) and print that path so you can use it in later steps."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "script_content": {
                        "type": "string",
                        "description": "The raw Python code to execute.",
                    },
                    "dependencies": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "A list of PyPI package names required to run the script "
                        "(e.g., ['pandas', 'matplotlib']).",
                    },
                },
                "required": ["script_content"],
            },
        },
        run_python_sandbox,
    )
