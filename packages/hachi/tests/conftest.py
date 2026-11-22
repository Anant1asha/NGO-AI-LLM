"""Shared pytest fixtures for the Hachi test suite.

Autouse fixtures here reset process-level singletons between tests so that
tests that boot an in-process gateway (test_cockpit_gaps.py,
test_cockpit_live_refresh.py, test_cockpit_chat_live.py, etc.) do not leave
a stale ProcessSharedServices instance (and an open ChromaDB PersistentClient)
that corrupts later vault/ChromaDB tests.

Root cause of the shared-state leak
-------------------------------------
``ProcessSharedServices._INSTANCES`` is a module-level dict.  Every call to
``ProcessSharedServices.get_or_create()`` stores the new singleton there.
Tests that call ``_start_gateway_server()`` boot a real vault-backed shared
service. After the test's ``runtime.shutdown()`` + ``server.stop()`` the
``ProcessSharedServices`` instance (and its embedded ChromaDB PersistentClient)
remain in ``_INSTANCES``. When enough such tests run before the vault tests, the
accumulation of open PersistentClient handles on Windows (ChromaDB 1.5.x /
SQLite WAL mode) causes later vault tests to see "vault unavailable" errors or
incorrect state.

Fix
---
An autouse session-scoped fixture drains the ``_INSTANCES`` dict via
``shutdown_all()`` once after the entire test session to flush Chroma WAL files.
A second autouse function-scoped fixture calls ``ProcessSharedServices.clear()``
(no vault close — avoids double-close on vaults that tests manage themselves)
**before each test** so every test that calls ``get_or_create()`` or
``instance()`` starts with a clean slate. The vault tests are unaffected because
they construct ``MemoryVault`` directly with ``tmp_path`` and never go through
``ProcessSharedServices``.
"""

from __future__ import annotations

import os

# Test hermeticity: hachi.cli.main merges <cwd>/.env and the config-dir .env into
# os.environ at IMPORT time. During a full pytest run that pulls the developer's
# real provider keys (ANTHROPIC_API_KEY, etc.) into the process, which flips
# import-time skipif guards on live-gateway tests (flaky, order-dependent
# failures) and leaks real secrets into the test process. Disable the autoload
# before any test module imports hachi.cli.main. Export
# HACHI_DISABLE_DOTENV_AUTOLOAD=0 to opt back in for a local debugging run.
os.environ.setdefault("HACHI_DISABLE_DOTENV_AUTOLOAD", "1")

# Cockpit/live-gateway tests boot a real in-process uvicorn + orchestrator and POST
# /sessions, which does heavy synchronous skill-engine + ChromaDB vault init. On a
# cold Windows process (uncached imports) or under full-suite load (the Nth
# PersistentClient in one process), that can exceed GatewayClient's 15s default and
# raise a transport timeout — the deterministic-looking "cockpit flakiness". Grant a
# generous client timeout for the test process so session creation reliably
# completes. Production keeps the 15s default (this only sets the env override).
os.environ.setdefault("HACHI_GATEWAY_CLIENT_TIMEOUT", "90")

# Warm the chromadb native (Rust/PyO3) extension once at session start. chromadb's
# native module CANNOT be re-initialized once unloaded — CPython raises
# "cannot load module more than once per process". Several tests use
# patch.dict(sys.modules, {...}) to simulate a missing dependency; patch.dict
# snapshots sys.modules on enter and restores it on exit, DROPPING any module that
# was first-imported INSIDE the block. When chromadb is first-imported lazily inside
# such a block (e.g. via the file-extractor chain in test_file_platform), the exit
# wipes its native submodules and every later `import chromadb` in the process fails
# — silently degrading vault/embedding tests to "chromadb not installed". Importing
# it here guarantees chromadb is in every patch.dict enter-snapshot, so it survives
# the restore. No-op if chromadb is not installed in this environment.
try:
    import chromadb  # noqa: F401
    import chromadb.config  # noqa: F401
except Exception:  # pragma: no cover - chromadb is optional in some CI envs
    pass

import pytest


@pytest.fixture(autouse=True)
def _reset_process_shared_services() -> None:  # type: ignore[return]
    """Clear the ProcessSharedServices singleton cache before each test.

    Runs before the test body (setup phase). Does NOT close open vaults — that
    is left to the individual test's teardown (runtime.shutdown() + server.stop())
    or to the session-level atexit handler registered by shared_services.py.
    """
    try:
        from hachi.gateway.shared_services import ProcessSharedServices

        ProcessSharedServices.clear()
    except ImportError:
        # Package not yet importable (e.g. missing dependency in partial CI env).
        pass
    yield  # run the test
    # No post-test cleanup here — _flush_shared_services_at_session_end handles WAL flush.


@pytest.fixture(autouse=True)
def _restore_os_environ():  # type: ignore[no-untyped-def]
    """Snapshot os.environ before each test and restore it after.

    Tests occasionally mutate os.environ directly (or trigger production code
    that does — e.g. the tokoboros→hachi rename shim writes HACHI_* vars), and
    pytest's monkeypatch only undoes vars IT set. Without this, a leaked var
    (e.g. HACHI_SMTP_PORT='value-for-...') pollutes later tests and makes the
    full-suite gate order-dependent. Diff-based restore (no clear()) avoids a
    window where concurrent in-process-gateway threads observe an empty env.
    """
    snapshot = dict(os.environ)
    yield
    # Remove keys the test added that weren't present before.
    for key in list(os.environ.keys()):
        if key not in snapshot:
            del os.environ[key]
    # Restore keys that were changed or deleted during the test.
    for key, value in snapshot.items():
        if os.environ.get(key) != value:
            os.environ[key] = value


@pytest.fixture(autouse=True, scope="session")
def _flush_shared_services_at_session_end() -> None:  # type: ignore[return]
    """Flush ChromaDB WAL files once after all tests complete.

    shutdown_all() closes every MemoryVault in _INSTANCES and then clears the
    dict — the same action the atexit handler would take at process exit. Running
    it explicitly at session end ensures the WAL is flushed before pytest exits,
    which prevents SQLite "database disk image is malformed" errors on the next
    run.
    """
    yield  # run all tests first
    try:
        from hachi.gateway.shared_services import ProcessSharedServices

        ProcessSharedServices.shutdown_all()
    except Exception:
        pass
