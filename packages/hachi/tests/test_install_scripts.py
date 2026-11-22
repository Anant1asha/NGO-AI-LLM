"""Structural guards for the installer scripts and the root launcher shims.

These are not behaviour tests — a real end-to-end install needs the repository to
be reachable and public. They lock the specific properties whose absence caused
real, reproduced defects (see docs/bug-bank.md BB-93) so they cannot silently
regress:

* `git` inheriting a pipe's stdin under `curl … | bash`, which consumes the rest
  of the script and hangs forever on a credential prompt.
* `git` prompting for credentials at all (hangs with no TTY).
* the PowerShell installer assuming `uv` is on PATH straight after installing it
  (upstream only edits the registry, so `uv sync` aborts).
* the guided setup being launched when no human is present.
* the POSIX launcher shim hard-coding the Windows venv layout.
"""

from __future__ import annotations

import stat
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = REPO_ROOT / "install.sh"
INSTALL_PS1 = REPO_ROOT / "install.ps1"
SHIM = REPO_ROOT / "hachi"


# ── install.sh ───────────────────────────────────────────────────────────────


def test_shell_installer_never_lets_git_prompt_for_credentials() -> None:
    """A credential prompt under `curl | bash` hangs forever with no output."""
    text = INSTALL_SH.read_text(encoding="utf-8")
    assert "GIT_TERMINAL_PROMPT=0" in text
    assert "export GIT_TERMINAL_PROMPT=0" in text


def test_shell_installer_redirects_git_stdin() -> None:
    """`git clone`/`pull` must not inherit the script's stdin.

    Under `curl -fsSL … | bash`, stdin is the pipe carrying the rest of this
    script. A git invocation that reads it consumes the remaining lines, so
    everything after the clone silently never executes.
    """
    text = INSTALL_SH.read_text(encoding="utf-8")
    # Match only real invocations, not error/comment text that mentions them.
    git_lines = [
        ln
        for ln in text.splitlines()
        if ln.strip().startswith(("git clone", "git -C", "if ! git clone", "if ! git -C"))
    ]
    assert git_lines, "expected git invocations in install.sh"
    for line in git_lines:
        assert "</dev/null" in line, f"git invocation must redirect stdin: {line.strip()}"


def test_shell_installer_checks_git_before_installing_uv() -> None:
    """Don't bootstrap a Python toolchain and only then discover git is missing."""
    text = INSTALL_SH.read_text(encoding="utf-8")
    git_check = text.index("command -v git")
    uv_install = text.index("astral.sh/uv/install.sh")
    assert git_check < uv_install


def test_shell_installer_verifies_uv_is_on_path_after_install() -> None:
    text = INSTALL_SH.read_text(encoding="utf-8")
    install_at = text.index("astral.sh/uv/install.sh")
    tail = text[install_at:]
    # An explicit re-check after the PATH export, with a real error message.
    assert "command -v uv" in tail
    assert "not on PATH" in tail


def test_shell_installer_supports_a_pinned_ref() -> None:
    text = INSTALL_SH.read_text(encoding="utf-8")
    assert "HACHI_REF" in text
    assert "--branch" in text


# ── install.ps1 ──────────────────────────────────────────────────────────────


def test_powershell_installer_refreshes_process_path_after_uv_install() -> None:
    """Upstream's uv installer only edits the registry PATH.

    Without re-reading it into $env:Path, `Get-Command uv` still fails and the
    subsequent `uv sync` aborts under $ErrorActionPreference = "Stop".
    """
    text = INSTALL_PS1.read_text(encoding="utf-8")
    assert 'GetEnvironmentVariable("Path", "Machine")' in text
    assert 'GetEnvironmentVariable("Path", "User")' in text
    assert "$env:Path =" in text


def test_powershell_installer_disables_git_credential_prompt() -> None:
    text = INSTALL_PS1.read_text(encoding="utf-8")
    assert "GIT_TERMINAL_PROMPT" in text


def test_powershell_installer_checks_git_before_installing_uv() -> None:
    text = INSTALL_PS1.read_text(encoding="utf-8")
    assert text.index("Get-Command git") < text.index("astral.sh/uv/install.ps1")


def test_powershell_installer_has_no_non_ascii() -> None:
    """PowerShell 5.1 decodes a BOM-less script as ANSI → box drawing becomes mojibake."""
    raw = INSTALL_PS1.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf") or all(b < 0x80 for b in raw), (
        "install.ps1 must be ASCII-only (or UTF-8 with BOM) for PS 5.1"
    )


# ── root launcher shim ───────────────────────────────────────────────────────


def test_posix_launcher_is_executable() -> None:
    mode = SHIM.stat().st_mode
    assert mode & stat.S_IXUSR, "the repo-root `hachi` launcher must be executable"


def test_posix_launcher_resolves_both_venv_layouts() -> None:
    """It previously hard-coded .venv/Scripts (Windows) from a bash script."""
    text = SHIM.read_text(encoding="utf-8")
    assert ".venv/bin/hachi" in text
    assert ".venv/Scripts" in text
    # It must not exec the Windows layout unconditionally.
    exec_lines = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("exec ")]
    assert exec_lines
    assert not any('exec "$(dirname "$0")/.venv/Scripts' in ln for ln in exec_lines)


def test_powershell_installer_checks_uv_sync_exit_code() -> None:
    """PS 5.1 does not treat a native non-zero exit as terminating.

    Without an explicit $LASTEXITCODE check a failed `uv sync` fell through and
    the installer printed the success banner anyway.
    """
    text = INSTALL_PS1.read_text(encoding="utf-8")
    # Find the actual command line, not a mention in a comment.
    lines = [ln.strip() for ln in text.splitlines()]
    try:
        sync_idx = lines.index("uv sync")
    except ValueError:  # pragma: no cover - would mean the command was renamed
        raise AssertionError("expected a bare `uv sync` command line in install.ps1") from None
    tail = "\n".join(lines[sync_idx : sync_idx + 6])
    assert "$LASTEXITCODE" in tail, "uv sync exit code must be checked in install.ps1"
    assert "dependency install failed" in tail.lower()


def test_powershell_installer_blanks_askpass_helper() -> None:
    """GIT_TERMINAL_PROMPT=0 does not stop Git Credential Manager's GUI prompt."""
    text = INSTALL_PS1.read_text(encoding="utf-8")
    assert "GIT_ASKPASS" in text


def test_powershell_installer_preserves_the_live_path() -> None:
    """Assigning machine;user discards session-injected directories (conda, scoop)."""
    text = INSTALL_PS1.read_text(encoding="utf-8")
    assert '$env:Path = "$env:Path;' in text, "must prepend, not replace, the live PATH"
    assert "ExpandEnvironmentVariables" in text


def test_posix_launcher_actually_runs() -> None:
    """Execute the shim, rather than merely re-asserting the mode bit.

    The previous version of this test only checked os.access(..., X_OK) — the
    same thing the preceding test asserts — and so never executed anything.
    """
    import subprocess

    result = subprocess.run(
        [str(SHIM), "--version"],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(REPO_ROOT),
        check=False,
    )
    assert result.returncode == 0, f"shim failed: {result.stdout} {result.stderr}"
    assert "hachi" in (result.stdout + result.stderr).lower()
