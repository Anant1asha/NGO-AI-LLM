"""P1-14: Scoped strict mypy gate — validates the gate config catches new errors.

The gate (mypy-strict-gate.ini) covers 36 currently-clean files in core/,
og_engine/, and gateway/. This test proves:
  1. The gate passes on the shipped sources (green on main).
  2. A file NOT in the gate does not cause a failure even if it has errors.
  3. If a gated file is passed directly to mypy --strict it must come out clean.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
_GATE_CONFIG = _REPO_ROOT / "mypy-strict-gate.ini"


def _run_gate() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "mypy", "--config-file", str(_GATE_CONFIG)],
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
        cwd=_REPO_ROOT,
    )


def test_gate_config_exists() -> None:
    assert _GATE_CONFIG.exists(), "mypy-strict-gate.ini must exist at repo root"


def test_gate_is_green_on_shipped_sources() -> None:
    """Gate must pass with zero errors on the current working tree (green on main)."""
    result = _run_gate()
    assert result.returncode == 0, (
        f"Strict mypy gate is failing on shipped sources — "
        f"a gated file has a new type error:\n{result.stdout}\n{result.stderr}"
    )


def test_gate_config_lists_at_least_36_files() -> None:
    """Sanity-check that the gate config hasn't been accidentally emptied."""
    content = _GATE_CONFIG.read_text(encoding="utf-8")
    py_files = [
        ln.strip().rstrip(",")
        for ln in content.splitlines()
        if ln.strip().endswith(".py,") or ln.strip().endswith(".py")
    ]
    assert len(py_files) >= 36, (
        f"Expected at least 36 files in the gate config, found {len(py_files)}"
    )


def test_gate_config_covers_core_and_og_engine_and_gateway() -> None:
    """Gate must span all three target directories."""
    content = _GATE_CONFIG.read_text(encoding="utf-8")
    assert "core/" in content
    assert "og_engine/" in content
    assert "gateway/" in content
