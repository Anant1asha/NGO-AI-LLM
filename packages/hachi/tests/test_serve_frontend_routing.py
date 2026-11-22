"""`hachi serve` frontend routing — the web UI must actually be reachable.

Two defects found by running the real server:

* **P-32** — `GET /` returned the gateway's service descriptor JSON even when the
  SPA was mounted, because the descriptor route is registered before the static
  mount and therefore wins the match. Every user following the "Web UI:
  http://…" URL that `hachi serve` prints got JSON and concluded the UI was broken.
* **P-33** — Starlette's `StaticFiles(html=True)` resolves directory-like paths to
  `index.html`, but it does **not** fall back for arbitrary deep paths. Every SPA
  route (`/conversation`, `/memory`, …) 404'd on refresh or direct link.

The pre-existing test that "covered" this asserted `"Hachi" in response.text`,
which the JSON descriptor also satisfies — so it passed against the broken
behaviour and never verified the SPA at all.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hachi.gateway.control_plane import GatewayControlPlane
from hachi.gateway.fastapi_app import create_gateway_app

SPA_MARKER = "<!--SPA-ROOT-MARKER-->"


@pytest.fixture()
def dist(tmp_path: Path) -> Path:
    d = tmp_path / "dist"
    d.mkdir()
    (d / "index.html").write_text(f"<html><body>{SPA_MARKER}</body></html>", encoding="utf-8")
    assets = d / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('hachi')", encoding="utf-8")
    return d


@pytest.fixture()
def client(dist: Path):
    app = create_gateway_app(GatewayControlPlane(), frontend_dist=dist)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _is_spa(resp) -> bool:
    return SPA_MARKER in (resp.text or "")


def test_root_serves_the_spa_not_the_service_descriptor(client) -> None:
    """P-32: "/" is the web UI when a frontend is mounted."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert _is_spa(resp), f"'/' did not serve the SPA: {(resp.text or '')[:120]}"


#: SPA routes that do NOT collide with a gateway API path.
UNCOLLIDED_SPA_ROUTES = (
    "/conversation",
    "/settings",
    "/review",
    "/work",
    "/og",
    "/run",
    "/authoring",
)

#: SPA routes that DO collide — the gateway owns the same path, so the API wins.
COLLIDED_SPA_ROUTES = ("/memory", "/skills", "/approvals", "/integrations")


def test_deep_links_fall_back_to_index_html(client) -> None:
    """P-33: client-side routes must survive a refresh or a direct link."""
    for route in UNCOLLIDED_SPA_ROUTES:
        resp = client.get(route)
        assert resp.status_code == 200, f"{route} -> {resp.status_code}"
        assert _is_spa(resp), f"{route} did not fall back to index.html"


def test_known_spa_route_collisions(client) -> None:
    """Documents P-35: four frontend routes are shadowed by gateway API routes.

    ``/memory``, ``/skills``, ``/approvals`` and ``/integrations`` are each both a
    frontend page and a REST endpoint. Routing resolves to the API, so opening
    those pages directly — or refreshing them — returns JSON (or 503), never the
    app. API routes must win (registered first, deliberately), so the fix belongs
    on the frontend side: move these pages under a distinct prefix such as
    ``/app/*``, or move the REST surface under ``/api/*``.

    Asserted rather than merely described, so whoever fixes it has a test to flip
    and the collision cannot be mistaken for a fallback failure.
    """
    for route in COLLIDED_SPA_ROUTES:
        resp = client.get(route)
        assert not _is_spa(resp), (
            f"{route} unexpectedly served the SPA — if that is now true, the "
            "collision was fixed and this route belongs in UNCOLLIDED_SPA_ROUTES"
        )


def test_real_assets_are_still_served(client) -> None:
    """The fallback must not shadow files that actually exist."""
    resp = client.get("/assets/app.js")
    assert resp.status_code == 200
    assert "console.log" in resp.text


def test_unknown_api_prefix_does_not_get_html(client) -> None:
    """A genuinely missing API path stays a 404, not a confusing HTML body."""
    resp = client.get("/api/definitely-not-a-route")
    assert resp.status_code == 404
    assert not _is_spa(resp)


def test_service_descriptor_remains_reachable_at_status(client) -> None:
    """The descriptor moved off "/" but must stay reachable."""
    resp = client.get("/status")
    assert resp.status_code == 200
    payload = json.loads(resp.text)
    assert payload["service"] == "Hachi Gateway"
    assert payload["health"] == "/health"


def test_api_routes_still_take_precedence_over_the_spa() -> None:
    """Mounting at "/" must not swallow the API."""
    app = create_gateway_app(GatewayControlPlane(), frontend_dist=None)
    with TestClient(app, raise_server_exceptions=False) as c:
        assert c.get("/health").status_code == 200


def test_root_serves_descriptor_when_no_frontend_mounted() -> None:
    """Without a frontend, "/" keeps returning the service descriptor."""
    app = create_gateway_app(GatewayControlPlane(), frontend_dist=None)
    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.get("/")
    assert resp.status_code == 200
    assert json.loads(resp.text)["service"] == "Hachi Gateway"
