"""GET /api/attribution/{hospital_id} and the `attribution` block of the inspector payloads (all numbers simulated)."""
import json

import pytest

from server import attribution
from server.tests.conftest import recv_until
from server.tests.test_ws import open_run

UNITS = ["provider_night", "nurse_night", "triage_station", "bay_main", "ct_scanner"]


@pytest.fixture(scope="module")
def rl_home(tmp_path_factory):
    """A real, tiny report (2 seeds x 1 day, a few units) written where the server looks for it."""
    import rl.attribution as A
    d = tmp_path_factory.mktemp("rl")
    A.run("rwjuh_nb", "fixed", ["normal_week"], 2, 1, 0, UNITS, None, d / "hospitals" / "rwjuh_nb", log=lambda *_: None)
    return d


@pytest.fixture()
def with_report(rl_home, monkeypatch):
    monkeypatch.setenv("HG_RL_DIR", str(rl_home))
    return rl_home


def test_absent_report_is_a_404_and_entities_still_answer(client, monkeypatch, tmp_path):
    monkeypatch.setenv("HG_RL_DIR", str(tmp_path))
    r = client.get("/api/attribution/rwjuh_nb")
    assert r.status_code == 404 and "rl.attribution" in r.json()["detail"]
    assert client.get("/api/attribution/..%2Fx").status_code == 404
    with client.websocket_connect("/ws/sim") as ws:
        header, _, _ = open_run(ws)
        room = next(x for x in header["layout"]["rooms"] if x["type"] == "treatment_bay")
        d = client.get(f"/api/runs/{header['run_id']}/rooms/{room['id']}").json()
        assert d["live"]["id"] == room["id"] and "attribution" not in d


def test_endpoint_returns_the_report_and_rescores(client, with_report):
    rep = client.get("/api/attribution/rwjuh_nb").json()
    assert rep["simulated"] is True and rep["hospital_id"] == "rwjuh_nb" and rep["manager"]["id"] == "fixed"
    assert {u["id"] for u in rep["units"]} == set(UNITS) and rep["protocol"]["n_seeds"] == 2
    a = next(u for u in rep["units"] if u["id"] == "provider_night")["scenarios"]["normal_week"]["minus_one"]
    assert a["verified"] and "terms_seeds" in a and "custom" not in a["reward"]
    assert [r["rank"] for r in rep["ranking"]["normal_week"]] == list(range(1, len(UNITS) + 1))
    # re-score under a preset and under free weights, without re-simulating
    b = client.get("/api/attribution/rwjuh_nb", params={"objective": "balanced"}).json()
    c = next(u for u in b["units"] if u["id"] == "provider_night")["scenarios"]["normal_week"]["minus_one"]["reward"]
    assert c["custom"]["mean"] == pytest.approx(c["balanced"]["mean"], rel=1e-3, abs=1e-6)
    w = client.get("/api/attribution/rwjuh_nb", params={"weights": json.dumps({"labor": 1.0})}).json()
    lab = next(u for u in w["units"] if u["id"] == "provider_night")["scenarios"]["normal_week"]["minus_one"]["reward"]["custom"]
    assert lab["mean"] > 0 and w["reward"]["custom_weights"] == {"labor": 1.0}
    assert client.get("/api/attribution/rwjuh_nb", params={"objective": "nope"}).status_code == 422
    assert client.get("/api/attribution/rwjuh_nb", params={"weights": "[1]"}).status_code == 422
    s = client.get("/api/attribution/rwjuh_nb", params={"view": "summary"}).json()
    sa = s["units"][0]["scenarios"]["normal_week"]
    side = sa["minus_one"] or sa["plus_one"]
    assert s["view"] == "summary" and "terms_seeds" not in side and "by_day" not in side and "by_hour" in side and s["ranking"]


def test_inspector_payloads_carry_the_marginal_value(client, with_report):
    with client.websocket_connect("/ws/sim") as ws:
        header, snap, _ = open_run(ws)
        rid, lay = header["run_id"], header["layout"]
        for _ in range(30):                                      # let some patients in
            ws.send_json(dict(type="step"))
            snap, _ = recv_until(ws, lambda m: m["type"] == "snapshot")
        snap = snap["snapshot"] if "snapshot" in snap else snap
        # ---- a main treatment bay
        room = next(x for x in lay["rooms"] if x["type"] == "treatment_bay" and "hallway" not in (x.get("catalog_ref") or ""))
        a = client.get(f"/api/runs/{rid}/rooms/{room['id']}").json()["attribution"]
        assert a["available"] and a["simulated"] and a["unit"] == "bay_main" and a["resource_class"] == "bay_main" and a["existing"] is True
        assert set(a["net_value_per_day"]) == {"mean", "lo", "hi"} and len(a["by_hour"]["margin"]) == 24 and len(a["top_effects"]) == 3
        assert a["now"]["hour"] == snap["clock"]["minute_of_day"] // 60 and a["scenario"] == "normal_week"
        u = a["utilisation_now"]
        assert u["of"] > 0 and 0.0 <= u["value"] <= 1.0 and u["in_use"] <= u["of"]
        assert a["location"]["modelled"] is False and "same simulated value" in a["note"]
        # the value of the unit is minus the effect of removing it
        rep = attribution.load("rwjuh_nb")
        mi = next(x for x in rep["units"] if x["id"] == "bay_main")["scenarios"]["normal_week"]["minus_one"]
        assert a["net_value_per_day"]["mean"] == pytest.approx(-mi["delta"]["margin_per_day"]["mean"], rel=1e-4, abs=1e-3)
        assert a["by_hour"]["margin"][3] == pytest.approx(-mi["by_hour"]["margin"]["mean"][3], abs=1e-9)
        # ---- a room that is not a resource has no block
        other = next(x for x in lay["rooms"] if x["type"] == "corridor")
        assert "attribution" not in client.get(f"/api/runs/{rid}/rooms/{other['id']}").json()
        # ---- a CT scanner
        ct = next(e for e in lay["equipment"] if e["type"] == "ct")
        e = client.get(f"/api/runs/{rid}/equipment/{ct['id']}").json()["attribution"]
        assert e["unit"] == "ct_scanner" and e["utilisation_now"]["of"] >= 1 and e["next_unit"] is not None
        # ---- staff: a provider and a nurse on the shift that is running, a triage nurse, and a held-constant role
        E = header["enums"]["staff_role"]
        st = snap["staff"]
        by_role = {}
        for sid, r in zip(st["id"], st["role"]):
            by_role.setdefault(E[r], sid)
        p = client.get(f"/api/runs/{rid}/staff/{by_role['attending']}").json()["attribution"]
        assert p["unit"] == "provider_night" and p["shift"] == "night" and "not of this person" in p["note"]
        assert p["utilisation_now"]["of"] == snap["kpis"]["providers_on_shift"]
        n = client.get(f"/api/runs/{rid}/staff/{by_role['rn']}").json()["attribution"]
        assert n["unit"] == "nurse_night"
        tri_room = next(i for i, x in enumerate(lay["rooms"]) if x["type"] == "triage")
        tri = next(sid for sid, r, ri in zip(st["id"], st["role"], st["room"]) if E[r] == "rn" and ri == tri_room)
        assert client.get(f"/api/runs/{rid}/staff/{tri}").json()["attribution"]["unit"] == "triage_station"
        held = client.get(f"/api/runs/{rid}/staff/{by_role['tech']}").json()["attribution"]
        assert held["available"] is False and "Held constant" in held["reason"]
        # ---- the websocket detail reply carries it too
        ws.send_json(dict(type="detail", entity=dict(kind="room", id=room["id"])))
        d, _ = recv_until(ws, lambda m: m["type"] == "detail")
        assert d["attribution"]["unit"] == "bay_main"


def test_unit_lookup_is_by_class_and_shift():
    assert attribution.unit_id("staff", dict(role="resident", staff_id="RES-01"), 16) == ("provider_evening", None)
    assert attribution.unit_id("staff", dict(role="app", staff_id="APP-01", shift="day"), 2) == ("provider_day", None)
    assert attribution.unit_id("staff", dict(role="rn", staff_id="RN-01"), 3)[0] == "nurse_night"
    assert attribution.unit_id("room", dict(type="treatment_bay", catalog_ref="space/hallway_overflow"), 0)[0] == "bay_hall"
    assert attribution.unit_id("room", dict(type="icu_bed"), 0)[0] == "ward_bed"
    assert attribution.unit_id("room", dict(type="waiting_room"), 0) == (None, None)
    assert attribution.unit_id("equipment", dict(type="mri"), 0) == (None, None)
    assert [attribution.shift_of(h) for h in (6, 7, 14, 15, 22, 23)] == ["night", "day", "day", "evening", "evening", "night"]
