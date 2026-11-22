"""Structural guards for the Docker self-host recipe (no daemon needed).

These assert the SPECIFIC things AUDIT P0-4 found broken — a missing frontend Dockerfile,
backend volumes mounted to ``/root`` that the non-root user cannot write, and the nginx
layer that must proxy ``/api`` → the gateway with the bearer token. They run everywhere,
fast, with no daemon. A live image build + ``docker compose up`` is verified by the
``docker-smoke`` CI job (which needs a real Docker engine).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_dockerfile_runs_the_gateway() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "hachi" in dockerfile
    assert "gateway" in dockerfile
    assert "8787" in dockerfile


def test_dockerignore_excludes_heavy_dirs() -> None:
    ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    # Without these the build context would balloon to hundreds of MB.
    assert "frontend/node_modules" in ignore
    assert ".venv" in ignore
    assert ".git" in ignore


def test_compose_exposes_gateway_port() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "8787" in compose


# --- P0-4: the bugs that made `docker compose up` fail -----------------------


def test_backend_volumes_target_non_root_home_not_root() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    # The container runs as non-root `hachi` (uid 10001); volumes must target its home
    # (platformdirs paths), not /root — which it cannot write. This was the P0-4 bug.
    assert "/home/hachi/.config/hachi" in compose
    assert "/home/hachi/.local/share/hachi" in compose
    assert "/home/hachi/.local/state/hachi" in compose
    assert "/home/hachi/.cache/hachi" in compose
    assert "/root/.config/hachi" not in compose
    assert "/root/.local" not in compose


def test_backend_uses_named_volumes() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    # Named volumes inherit the image dir's `hachi` ownership; a host bind mount would be
    # root-owned and break writes for the non-root user.
    for vol in ("hachi-config", "hachi-data", "hachi-state", "hachi-cache"):
        assert vol in compose


def test_dockerfile_precreates_xdg_dirs_for_non_root_user() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "useradd" in dockerfile and "hachi" in dockerfile
    # XDG dirs must be pre-created + chowned so the named volumes inherit hachi ownership.
    assert "/home/hachi/.local/share/hachi" in dockerfile
    assert "chown -R hachi:hachi /home/hachi" in dockerfile


def test_frontend_dockerfile_exists_and_builds_then_serves() -> None:
    fe = ROOT / "frontend" / "Dockerfile"
    assert fe.exists(), "frontend/Dockerfile is required by docker-compose's frontend service"
    text = fe.read_text(encoding="utf-8")
    assert "npm run build" in text  # builds the SPA
    assert "nginx" in text.lower()  # serves it
    assert "5173" in text  # on the compose-mapped port


def test_frontend_nginx_proxies_api_to_gateway_with_token() -> None:
    tpl = (ROOT / "frontend" / "nginx.conf.template").read_text(encoding="utf-8")
    assert "location /api/" in tpl
    assert "proxy_pass ${GATEWAY_TARGET}/" in tpl  # trailing slash strips the /api prefix
    assert "Bearer ${GATEWAY_TOKEN}" in tpl  # token injected server-side, not in the browser
    assert "proxy_buffering off" in tpl  # SSE streams must not buffer
    assert "try_files" in tpl  # SPA client-side routing fallback


def test_frontend_entrypoint_reads_token_secret_then_delegates() -> None:
    sh = (ROOT / "frontend" / "docker-entrypoint.sh").read_text(encoding="utf-8")
    assert "HACHI_GATEWAY_AUTH_HEADER_FILE" in sh or "gateway_api_token" in sh
    assert "exec /docker-entrypoint.sh" in sh  # hands off to the stock nginx entrypoint


def test_frontend_dockerignore_excludes_node_modules() -> None:
    ign = (ROOT / "frontend" / ".dockerignore").read_text(encoding="utf-8")
    assert "node_modules" in ign
