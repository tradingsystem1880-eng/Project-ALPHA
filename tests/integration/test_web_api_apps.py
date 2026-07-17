"""``/api/apps`` — the declarative panel manifest the shell renders from."""

from __future__ import annotations

from fastapi.testclient import TestClient

from alpha_web.app import create_app


def test_apps_manifest_lists_panels_and_catalog_pointers() -> None:
    body = TestClient(create_app()).get("/api/apps").json()
    components = {p["component"] for p in body["panels"]}
    assert "RunBrowser" in components
    assert body["commands"] == "/api/commands"
    assert body["strategies"] == "/api/strategies"


def test_price_panel_subscribes_to_linked_context() -> None:
    body = TestClient(create_app()).get("/api/apps").json()
    price = next(p for p in body["panels"] if p["component"] == "PriceChart")
    assert price["linked"] is True
    assert price["data"][0]["endpoint"] == "/api/candles/{symbol}"
