"""Security tests for the community-pack supply chain.

SEC-001: ZIP extraction must reject path-traversal (zip-slip) and zip-bombs,
at parity with the hardened tar path (archive_safety.safe_extract).
SEC-005: a non-filesystem MCP server runs an arbitrary command at boot, so a
server whose .og definition came from an installed community pack must be
tier-gated / explicitly approved — not auto-executed.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from hachi.core import community_packs
from hachi.core.archive_safety import ArchiveSecurityError
from hachi.core.community_packs import _extract_zip
from hachi.core.permissions import MCPRules, PermissionGate
from hachi.gateway.orchestrator import _node_is_community_pack
from hachi.og_engine.parser import OGNode


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    return buf.getvalue()


# ── SEC-001: ZIP zip-slip + bomb ──────────────────────────────────────────


class TestZipExtractionSecurity:
    def test_clean_zip_extracts_only_og_and_packjson(self, tmp_path: Path) -> None:
        data = _zip_bytes(
            {
                "pack/skill.og": b"::node[x]\n",
                "pack/pack.json": b"{}",
                "pack/readme.md": b"ignored",
            }
        )
        written = _extract_zip(data, tmp_path)
        assert (tmp_path / "skill.og").exists()
        assert (tmp_path / "pack.json").exists()
        assert not (tmp_path / "readme.md").exists()
        assert [p.name for p in written] == ["skill.og"]

    def test_zip_slip_escape_is_rejected(self, tmp_path: Path) -> None:
        # After the "pack/" prefix is stripped, this still escapes the dest dir.
        data = _zip_bytes({"pack/../../evil.og": b"pwned"})
        dest = tmp_path / "dest"
        with pytest.raises(ArchiveSecurityError):
            _extract_zip(data, dest)
        assert not (dest / "evil.og").exists()
        assert not (tmp_path / "evil.og").exists()

    def test_nested_paths_within_dest_allowed(self, tmp_path: Path) -> None:
        # Containment hardening must not break legitimate nested skill paths.
        data = _zip_bytes({"pack/sub/dir/skill.og": b"::node[x]\n"})
        written = _extract_zip(data, tmp_path)
        assert (tmp_path / "sub" / "dir" / "skill.og").exists()
        assert len(written) == 1

    def test_member_count_cap(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(community_packs, "_MAX_ARCHIVE_FILES", 2)
        data = _zip_bytes({f"pack/s{i}.og": b"x" for i in range(5)})
        with pytest.raises(ArchiveSecurityError):
            _extract_zip(data, tmp_path)

    def test_total_uncompressed_size_cap(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(community_packs, "_MAX_ARCHIVE_TOTAL_BYTES", 16)
        data = _zip_bytes({"pack/big.og": b"x" * 4096})
        with pytest.raises(ArchiveSecurityError):
            _extract_zip(data, tmp_path)


# ── SEC-005: MCP server tier gate + provenance ────────────────────────────


def _sandbox_gate(tmp_path: Path) -> PermissionGate:
    # Missing file → sandbox tier, empty MCP allowlist (fail-safe default-deny).
    return PermissionGate(tmp_path / "nonexistent-device-permissions.og")


class TestNodeProvenance:
    def test_community_pack_node_detected(self, tmp_path: Path) -> None:
        packs_root = tmp_path / "skills" / "packs"
        node_src = packs_root / "evil" / "server.og"
        assert _node_is_community_pack(str(node_src), str(packs_root)) is True

    def test_builtin_node_not_flagged(self, tmp_path: Path) -> None:
        packs_root = tmp_path / "skills" / "packs"
        builtin = tmp_path / "default_skills" / "mcp.og"
        assert _node_is_community_pack(str(builtin), str(packs_root)) is False

    def test_empty_source_not_flagged(self, tmp_path: Path) -> None:
        assert _node_is_community_pack("", str(tmp_path / "packs")) is False


class TestMcpServerGate:
    def test_untrusted_denied_by_default(self, tmp_path: Path) -> None:
        gate = _sandbox_gate(tmp_path)
        result = gate.is_mcp_server_allowed("evil_pack_server", trusted=False)
        assert result.allowed is False

    def test_builtin_trusted_allowed(self, tmp_path: Path) -> None:
        gate = _sandbox_gate(tmp_path)
        assert gate.is_mcp_server_allowed("gmail_mcp", trusted=True).allowed is True

    def test_explicit_allowlist(self, tmp_path: Path) -> None:
        gate = _sandbox_gate(tmp_path)
        gate._mcp = MCPRules(
            filesystem_enabled=True,
            allow_all_servers=False,
            server_allowlist=("approved_server",),
        )
        assert gate.is_mcp_server_allowed("approved_server").allowed is True
        assert gate.is_mcp_server_allowed("other_server").allowed is False

    def test_unrestricted_allows_all(self, tmp_path: Path) -> None:
        gate = _sandbox_gate(tmp_path)
        gate._mcp = MCPRules(filesystem_enabled=True, allow_all_servers=True)
        assert gate.is_mcp_server_allowed("anything_untrusted").allowed is True

    def test_build_rules_parses_allowlist(self, tmp_path: Path) -> None:
        gate = _sandbox_gate(tmp_path)
        node_map = {
            "mcp_servers": OGNode(name="mcp_servers", config={"allowed_servers": "alpha, beta"})
        }
        rules = gate._build_mcp_rules(node_map)
        assert rules.allow_all_servers is False
        assert set(rules.server_allowlist) == {"alpha", "beta"}

    def test_build_rules_unrestricted_tier_default(self, tmp_path: Path) -> None:
        gate = _sandbox_gate(tmp_path)
        gate._tier = "unrestricted"
        rules = gate._build_mcp_rules({})
        assert rules.allow_all_servers is True
