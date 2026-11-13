"""The built SPA is present and served.

``static/app`` is build output and not committed. If these fail, the SPA was not built: run
``npm ci && npm run build`` in ``apps/alpha-web/frontend`` (CI builds it before the tests).
"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from alpha_web.app import _APP_INDEX, create_app


def test_spa_index_is_built_and_committed() -> None:
    # the built SPA entry must exist for the app to serve it
    assert _APP_INDEX.exists(), (
        "SPA not built: run `npm ci && npm run build` in apps/alpha-web/frontend"
    )


def test_root_and_app_routes_serve_the_spa() -> None:
    client = TestClient(create_app())
    for path in ("/", "/app"):
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert '<div id="root">' in resp.text
        assert "/static/app/assets/" in resp.text  # hashed bundle references


def test_spa_bundle_asset_is_served() -> None:
    client = TestClient(create_app())
    match = re.search(r'src="(/static/app/assets/index-[^"]+\.js)"', client.get("/app").text)
    assert match is not None
    assert client.get(match.group(1)).status_code == 200
