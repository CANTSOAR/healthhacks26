import gzip
import json
import time

import pytest
import yaml

from server import catalog, managers, status as status_mod, validation


def test_status_offline(client, monkeypatch):
    monkeypatch.delenv("VLADA_API_KEY", raising=False)
    d = client.get("/api/status").json()
    s = d["services"]
    assert set(s) == {"sim", "rl", "data"} and set(d) == {"services", "torch", "device", "version"}
    assert s["sim"]["live"] is True and s["sim"]["active_runs"] == 0 and s["rl"]["live"] is True
    assert s["data"] == {"live": False, "provider": "public_extracts"}
    assert d["device"] == "cpu" and d["torch"] and d["version"]


def test_status_with_credentials(client, monkeypatch):
    monkeypatch.setenv("VLADA_API_KEY", "k")
    assert client.get("/api/status").json()["services"]["data"] == {"live": True, "provider": "vlada"}


def test_status_reports_missing_rl(monkeypatch):
    monkeypatch.setattr(managers, "rl_module", lambda: None)
    monkeypatch.setattr(managers, "last_rl_error", "ImportError: no rl", raising=False)
    assert status_mod.status()["services"]["rl"] == {"live": False, "last_error": "ImportError: no rl"}


def test_played_encounter_routes_are_gone(client):
    for path in ("/api/cases", "/api/encounters/x", "/api/journeys", "/api/runs/run-x/playable"):
        assert client.get(path).status_code == 404
    assert client.delete("/api/runs/run-x/patients/1/hold").status_code in (404, 405)


def test_enums_metrics(client):
    e = client.get("/api/enums").json()
    assert e == yaml.safe_load(open("contracts/enums.yaml")) and "patient_state" in e
    m = client.get("/api/metrics").json()
    assert "wait_mean_min" in m["metrics"] and "cost_per_day" in m["episode_summary"]


def test_catalog_summary_and_files(client, validators):
    d = client.get("/api/catalog").json()
    types = {e["entity_type"]: e for e in d["entity_types"]}
    for et in ("patient", "staff", "space", "equipment", "event", "hospital"):
        e = types[et]
        assert e["n_variants"] > 0 and isinstance(e["description"], str)
        assert set(e["by_source"]) == {"measured", "literature", "assumed"}
        assert sum(e["by_source"].values()) == e["n_attributes"]
    t = d["totals"]
    assert t["n_attributes"] == sum(e["n_attributes"] for e in d["entity_types"]) == sum(t["by_source"].values())
    for et in ("patient", "staff", "space", "equipment", "event"):
        doc = client.get(f"/api/catalog/{et}").json()
        validators["catalog"].validate(doc)
        assert doc["entity_type"] == et
    assert isinstance(client.get("/api/catalog/hospitals").json()["items"], list)
    assert isinstance(client.get("/api/catalog/conditions").json()["items"], list)
    r = client.get("/api/catalog/nope")
    assert r.status_code == 404 and "detail" in r.json()


@pytest.mark.parametrize("ref", ["space/treatment_bay", "staff/rn", "equipment/ct", "patient/esi3", "event/flu_wave", "hospital/rwjuh_nb"])
def test_catalog_ref(client, ref):
    d = client.get(f"/api/catalog/ref/{ref}").json()
    et, variant = ref.split("/")
    assert d["entity_type"] == et and d["variant"] == variant and isinstance(d["label"], str) and d["attributes"]
    for a in d["attributes"].values():
        assert {"value", "unit", "source"} <= set(a)


def test_catalog_ref_merges_shared(client):
    doc = yaml.safe_load(open("catalog/space.yaml"))
    shared = set(doc.get("shared") or {})
    own = set(doc["variants"]["treatment_bay"]["attributes"])
    got = set(client.get("/api/catalog/ref/space/treatment_bay").json()["attributes"])
    assert got == shared | own
    assert client.get("/api/catalog/ref/space/no_such_room").status_code == 404
    assert client.get("/api/catalog/ref/../secrets").status_code == 404


def test_condition_ref_and_missing_catalog(client, tmp_path, monkeypatch):
    (tmp_path / "conditions").mkdir()
    attr = dict(value=0.2, unit="fraction", source="assumed")
    (tmp_path / "conditions" / "chest_pain.yaml").write_text(yaml.safe_dump(dict(
        schema_version=1, entity_type="condition", description="d", shared=dict(needs_review=dict(value=True, unit="flag", source="assumed")),
        variants=dict(chest_pain=dict(label="Chest pain", attributes=dict(acs_share=attr))), facts=[dict(fact_id="f.hpi.x")])))
    monkeypatch.setenv("HG_CATALOG_DIR", str(tmp_path))
    d = client.get("/api/catalog/ref/conditions/chest_pain").json()
    assert d["entity_type"] == "condition" and d["label"] == "Chest pain" and set(d["attributes"]) == {"needs_review", "acs_share"}
    assert len(client.get("/api/catalog/conditions").json()["items"]) == 1
    # everything else in this temp catalog is missing: routes still answer with the documented shapes
    s = client.get("/api/catalog").json()
    assert [e["entity_type"] for e in s["entity_types"]] == ["condition"] and s["totals"]["n_attributes"] == 2
    assert client.get("/api/hospitals").json() == []
    assert client.get("/api/layout/rwjuh_nb").status_code == 404
    v = client.get("/api/validation").json()
    assert v["status"] == "no_targets" and v["targets"] == [] and v["simulated"] == {} and v["within"] == {}


def test_scenarios_hospitals_layout(client, validators):
    sc = client.get("/api/scenarios").json()
    assert "normal_week" in [s["id"] for s in sc]
    for s in sc:
        assert {"id", "label", "description", "hospital_id", "days_default"} <= set(s)
    hs = client.get("/api/hospitals").json()
    assert hs[0]["id"] == "rwjuh_nb"
    for h in hs:
        assert {"id", "name", "disclaimer"} <= set(h)
        lay = client.get(f"/api/layout/{h['id']}").json()
        validators["layout"].validate(lay)
        assert lay["hospital_id"] == h["id"]
    assert client.get("/api/layout/atlantis").status_code == 404


def test_managers_without_rl(client, monkeypatch):
    monkeypatch.setattr(managers, "rl_module", lambda: None)
    ms = client.get("/api/managers").json()
    assert [m["id"] for m in ms] == ["human", "fixed"]
    for m in ms:
        assert {"id", "kind", "label", "objective", "reward_weights", "available"} <= set(m) and m["available"] is True
    assert managers.load_manager("human") is None
    assert managers.load_manager("fixed").kind == "fixed"
    with pytest.raises(KeyError):
        managers.load_manager("ppo_nope")


def test_managers_with_rl(client, monkeypatch):
    class FakeRL:
        @staticmethod
        def list_managers():
            return [dict(id="fixed_default", kind="fixed", label="Fixed", objective=None, reward_weights=None, available=True),
                    dict(id="ppo_cost", kind="learned", label="PPO", objective="min_cost", reward_weights={"cost": 1.0}, available=False)]

        @staticmethod
        def load_manager(mid, device="cpu"):
            return "policy:" + mid
    monkeypatch.setattr(managers, "rl_module", lambda: FakeRL)
    ms = client.get("/api/managers").json()
    assert [m["id"] for m in ms] == ["human", "fixed_default", "ppo_cost"]
    assert managers.load_manager("fixed_default") == "policy:fixed_default"
    with pytest.raises(RuntimeError):
        managers.load_manager("ppo_cost")

    class Broken:
        @staticmethod
        def list_managers():
            raise RuntimeError("half-written")
        load_manager = None
    monkeypatch.setattr(managers, "rl_module", lambda: Broken)
    assert [m["id"] for m in client.get("/api/managers").json()] == ["human", "fixed"]


def test_rollouts_fixture(client, validators, tmp_path, monkeypatch):
    monkeypatch.setenv("HG_RL_DIR", str(tmp_path))
    items = client.get("/api/rollouts").json()
    assert [i["rollout_id"] for i in items] == ["fixture"]
    for k in ("rollout_id", "manager", "scenario", "seed", "days", "summary", "has_segments"):
        assert k in items[0]
    assert {"id", "kind", "label", "objective"} <= set(items[0]["manager"])
    r = client.get("/api/rollouts/fixture")
    assert r.status_code == 200 and r.headers["content-encoding"] == "gzip" and r.headers["content-type"].startswith("application/json")
    validators["rollout"].validate(r.json())
    assert client.get("/api/rollouts/nope").status_code == 404
    assert client.get("/api/rollouts/..%2F..%2Fsecrets").status_code == 404
    res = client.get("/api/results").json()
    assert res["rows"] == [] and res["human_runs"] == [] and {"seeds", "days", "scenarios"} <= set(res["protocol"]) and "generated" in res


def test_rollouts_and_results_from_rl_dir(client, validators, tmp_path, monkeypatch):
    monkeypatch.setenv("HG_RL_DIR", str(tmp_path))
    fx = json.load(open("contracts/fixtures/rollout.fixture.json"))
    fx["header"]["rollout_id"] = "ppo_cost__normal_week__s1"
    fx["segments"][0]["snapshots"] = fx["segments"][0]["snapshots"][:3]
    (tmp_path / "rollouts").mkdir()
    (tmp_path / "results").mkdir()
    with gzip.open(tmp_path / "rollouts" / "ppo_cost__normal_week__s1.json.gz", "wt") as f:
        json.dump(fx, f)
    # no index yet: built from the files
    items = client.get("/api/rollouts").json()
    assert [i["rollout_id"] for i in items] == ["ppo_cost__normal_week__s1"] and items[0]["has_segments"] is True
    # an index appears (and names one rollout whose file is missing): picked up without a restart
    m = dict(id="ppo_cost", kind="learned", label="PPO cost", objective="min_cost")
    (tmp_path / "rollouts" / "index.json").write_text(json.dumps([
        dict(rollout_id="ppo_cost__normal_week__s1", manager=m, scenario="normal_week", seed=1, days=2, summary={"wait_mean_min": 30.0}, has_segments=True),
        dict(rollout_id="missing_file", manager=m, scenario="normal_week", seed=1, days=2, summary={}, has_segments=True)]))
    items = client.get("/api/rollouts").json()
    assert len(items) == 1 and items[0]["manager"]["kind"] == "learned" and items[0]["summary"] == {"wait_mean_min": 30.0}
    r = client.get("/api/rollouts/ppo_cost__normal_week__s1")
    assert r.headers["content-encoding"] == "gzip"
    validators["rollout"].validate(r.json())
    row = dict(manager_id="ppo_cost", kind="learned", label="PPO cost", objective="min_cost", scenario="normal_week", n_seeds=3,
               metrics={"cost_per_day": {"mean": 1.0, "std": 0.1, "ci95": 0.2}})
    (tmp_path / "results" / "results.json").write_text(json.dumps(dict(generated="2026-10-10T03:00:00Z", protocol=dict(seeds=[1, 2, 3], days=14,
                                                                                                                scenarios=["normal_week"]), rows=[row])))
    res = client.get("/api/results").json()
    assert res["rows"] == [row] and res["generated"].startswith("2026") and isinstance(res["human_runs"], list)


def test_human_result_roundtrip(client):
    body = dict(label="Test player", scenario="normal_week", seed=7, days=2, summary={"cost_per_day": 123.0, "wait_mean_min": 20.5, "junk": "x"})
    r = client.post("/api/results/human", json=body)
    assert r.status_code == 200 and r.json()["ok"] is True
    body2 = dict(body, summary={"cost_per_day": 99.0, "wait_mean_min": 18.0})
    client.post("/api/results/human", json=body2)
    mine = [h for h in client.get("/api/results").json()["human_runs"] if h["label"] == "Test player"]
    assert len(mine) == 1 and mine[0]["summary"] == body2["summary"] and mine[0]["seed"] == 7 and mine[0]["created"]
    assert client.post("/api/results/human", json=dict(label="x")).status_code == 422


def test_validation_pending_then_ready(client, monkeypatch):
    calls = []

    def fake(s):
        calls.append(s)
        time.sleep(0.2)
        return dict(ed_los_median_min=200.0, lwbs_rate=0.5, ed_visits_per_year=80000.0, admission_rate=0.13, wait_mean_min=20.0)
    monkeypatch.setattr(validation, "run_baseline", fake)
    d = client.get("/api/validation").json()
    assert d["status"] == "pending" and d["simulated"] == {} and d["within"] == {} and len(d["targets"]) > 3
    for t in d["targets"]:
        assert {"name", "value", "range", "source", "url"} <= set(t)
    for _ in range(100):
        d = client.get("/api/validation").json()
        if d["status"] == "ready":
            break
        time.sleep(0.05)
    assert d["status"] == "ready" and len(calls) == 1 and calls[0]["scenario"] == "normal_week"
    assert d["simulated"]["median_ed_time_discharged_min"] == 200.0 and d["within"]["median_ed_time_discharged_min"] is True
    assert d["within"]["lwbs_rate"] is False and d["baseline"]["synthetic"] is True
    assert set(d["within"]) <= set(d["simulated"]) <= {t["name"] for t in d["targets"]}
    # cached: a second request does not recompute; a restart reads the file in server/state
    validation.reset()
    assert client.get("/api/validation").json()["status"] == "ready" and len(calls) == 1


def test_validation_real_baseline_tiny():
    out = validation.compute_baseline("normal_week", days=1, batch=1, seed=3)
    assert out["arrivals_per_day"] > 0 and 0 <= out["admission_rate"] <= 1 and out["ed_los_median_min"] > 0


def test_content_hash_stable():
    assert catalog.content_hash() == catalog.content_hash() and len(catalog.content_hash()) == 16


def test_cors(client):
    r = client.get("/api/enums", headers={"Origin": "http://localhost:3000"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
