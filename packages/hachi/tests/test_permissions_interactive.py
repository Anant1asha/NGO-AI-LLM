from __future__ import annotations

from pathlib import Path

from hachi.core.permissions import (
    InteractivePermissionGate,
    PermissionDecision,
    PermissionGate,
    generate_permissions_og,
)


def _make_gate(tmp_path: Path) -> PermissionGate:
    allowed_dir = tmp_path / "allowed"
    allowed_dir.mkdir(parents=True, exist_ok=True)

    permissions_file = tmp_path / "device-permissions.og"
    permissions_file.write_text(
        generate_permissions_og("guided", custom_paths=[str(allowed_dir)]),
        encoding="utf-8",
    )
    return PermissionGate(permissions_file)


def test_interactive_gate_approve_persists_for_session(tmp_path: Path) -> None:
    base = _make_gate(tmp_path)
    calls = {"count": 0}

    events: list[tuple[str, dict]] = []

    def handler(_request):
        calls["count"] += 1
        return PermissionDecision(action="approve", rationale="operator approved")

    gate = InteractivePermissionGate(
        base, approval_handler=handler, event_emitter=lambda n, p: events.append((n, p))
    )

    result1 = gate.check_command("rm -rf /tmp")
    result2 = gate.check_command("rm -rf /tmp")

    assert result1.allowed is True
    assert result2.allowed is True
    assert calls["count"] == 1
    assert [name for name, _ in events] == ["permission.requested", "permission.decided"]


def test_interactive_gate_deny_uses_rationale(tmp_path: Path) -> None:
    base = _make_gate(tmp_path)

    gate = InteractivePermissionGate(
        base,
        approval_handler=lambda _request: PermissionDecision(
            action="deny", rationale="needs manual review"
        ),
    )

    denied = gate.check_command("shutdown now")

    assert denied.allowed is False
    assert "manual review" in denied.reason


def test_interactive_gate_allow_once_applies_single_call(tmp_path: Path) -> None:
    base = _make_gate(tmp_path)

    attempts = {"count": 0}

    def handler(_request):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return PermissionDecision(action="allow_once", rationale="one-time run")
        return PermissionDecision(action="deny", rationale="second attempt denied")

    gate = InteractivePermissionGate(base, approval_handler=handler)

    first = gate.check_command("reg add HKCU\\foo")
    second = gate.check_command("reg add HKCU\\foo")

    assert first.allowed is True
    assert second.allowed is False
    assert "second attempt denied" in second.reason
