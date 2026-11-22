"""Dependency-usage policy guards.

`chromadb` 1.5.9 carries four unpatched advisories, all of them defects in its
**HTTP server** API (`/api/v2/...`): pre-auth code injection via a model
repository supplied to a server endpoint with `trust_remote_code`, cross-tenant
read/write, and an RBAC provider that does not scope permissions by tenant.

Hachi only ever uses the **embedded** `PersistentClient` — in-process, no
listener, single-tenant — so that surface is not reachable here. That acceptance
is only sound while these properties hold, so they are asserted structurally:
adding server mode or `trust_remote_code` must fail CI rather than quietly widen
exposure.

These guards parse the AST rather than grepping. The first version used regexes
and missed `from chromadb import HttpClient`, `import chromadb.api` and
`getattr(chromadb, "HttpClient")` — the exact shapes someone reaching for server
mode would write.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"

#: Names that mean "use chromadb as a *client of a server*", i.e. the deployment
#: mode every one of the four advisories applies to.
_SERVER_DEPLOYMENT_MODULES = ("chromadb.api", "chromadb.server", "chromadb.HttpClient")

#: `Settings(...)` keywords that switch chromadb out of embedded mode.
_SERVER_SETTINGS_KWARGS = {
    "chroma_api_impl",
    "chroma_server_host",
    "chroma_server_http_port",
    "chroma_server_grpc_url",
    "chroma_server_ssl_verify",
}


def _python_sources() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def _parse(path: Path) -> ast.Module:
    # utf-8-sig: one source file (client/models.py) carries a UTF-8 BOM, which
    # ast.parse rejects as a non-printable character.
    return ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))


def _imported_names(tree: ast.Module) -> set[str]:
    """Every fully-qualified dotted name imported anywhere in the module.

    Covers `import a.b`, `from a import b` (as `a.b`), and aliased forms, so an
    import cannot be hidden by renaming the binding.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module:
                names.add(module)
            for alias in node.names:
                names.add(f"{module}.{alias.name}" if module else alias.name)
    return names


def test_no_chromadb_server_or_http_client_imports() -> None:
    """Only the embedded PersistentClient is allowed.

    An HttpClient or the FastAPI app module makes the process a client/server of
    chromadb's HTTP surface — precisely the mode the four advisories describe.
    """
    offenders: list[str] = []
    for path in _python_sources():
        for name in _imported_names(_parse(path)):
            if any(name == m or name.startswith(m + ".") for m in _SERVER_DEPLOYMENT_MODULES):
                offenders.append(f"{path.relative_to(SRC.parent)}: imports {name}")
    assert not offenders, "chromadb server/client API must not be used:\n  " + "\n  ".join(
        offenders
    )


def test_no_trust_remote_code_argument() -> None:
    """`trust_remote_code` is the trigger for CVE-2026-45829 / -45833."""
    offenders: list[str] = []
    for path in _python_sources():
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if kw.arg == "trust_remote_code":
                        offenders.append(f"{path.relative_to(SRC.parent)}:{node.lineno}")
            elif isinstance(node, ast.Dict):
                for key in node.keys:
                    if isinstance(key, ast.Constant) and key.value == "trust_remote_code":
                        offenders.append(f"{path.relative_to(SRC.parent)}:{node.lineno}")
    assert not offenders, "trust_remote_code must never be passed:\n  " + "\n  ".join(offenders)


def test_no_chromadb_server_settings() -> None:
    """`Settings(...)` must not switch chromadb into server mode.

    The previous guard only grepped import lines, so
    `Settings(chroma_api_impl="chromadb.api.fastapi.FastAPI", is_persistent=False)`
    and `Settings(chroma_server_host=..., chroma_server_http_port=8000)` both
    passed while turning the embedded client into a server client.
    """
    offenders: list[str] = []
    for path in _python_sources():
        tree = _parse(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name != "Settings":
                continue
            for kw in node.keywords:
                if kw.arg in _SERVER_SETTINGS_KWARGS:
                    offenders.append(
                        f"{path.relative_to(SRC.parent)}:{node.lineno}: Settings({kw.arg}=...)"
                    )
    assert not offenders, "chromadb server-mode Settings must not be used:\n  " + "\n  ".join(
        offenders
    )


def test_no_chromadb_server_entrypoint() -> None:
    """Hachi must never start chromadb's HTTP server."""
    rx = re.compile(r'"chroma"\s*,\s*"run"|chromadb\.Server|/api/v2/')
    hits: list[str] = []
    for path in _python_sources():
        for lineno, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            if rx.search(line):
                hits.append(f"{path.relative_to(SRC.parent)}:{lineno}: {line.strip()}")
    assert not hits, "chromadb server entrypoint/routes must not appear:\n  " + "\n  ".join(hits)


def test_chromadb_is_imported_lazily_where_used() -> None:
    """Vault imports stay inside functions so session boot never pays for chroma.

    This is a performance contract, but it also keeps the embedded client from
    being constructed at import time where a future refactor could turn it into
    a module-level singleton listener.
    """
    vault = SRC / "hachi" / "core" / "memory_vault.py"
    tree = _parse(vault)
    top_level = [
        f"{vault.name}:{node.lineno}"
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
        and any(
            (alias.name == "chromadb" or alias.name.startswith("chromadb"))
            for alias in node.names
        )
    ]
    assert not top_level, f"chromadb must not be imported at module scope: {top_level}"
