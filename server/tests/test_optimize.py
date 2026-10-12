"""Optimise-for-your-reward endpoints (the job itself is rl/custom.py; here only the HTTP surface)."""
from fastapi.testclient import TestClient

from server.app import app

c = TestClient(app)


def test_menu_lists_metrics_and_presets():
    m = c.get("/api/optimize/menu").json()
    ids = {x["id"] for x in m["metrics"]}
    assert {"profit", "wait", "walkouts", "patient_experience"} <= ids and m["synthetic"] is True
    assert all(g["metric"] in ids for p in m["presets"] for g in p["goals"])


def test_bad_requests():
    assert c.post("/api/optimize", json={"goals": []}).status_code == 422
    assert c.post("/api/optimize", json={"goals": [{"metric": "nope", "direction": "min", "rank": 1}]}).status_code == 422
    assert c.get("/api/optimize/does-not-exist").status_code == 404
    assert c.get("/api/optimize/..%2F..%2Fetc").status_code == 404
    assert isinstance(c.get("/api/optimize").json(), list)


def test_headline_endpoint():
    assert c.get("/api/headline/no_such_hospital").status_code == 404
    assert c.get("/api/headline/..%2Fx").status_code == 404
