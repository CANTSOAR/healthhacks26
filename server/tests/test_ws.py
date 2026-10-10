import time

import pytest

from server import encounter_glue, managers, runs
from server.tests.conftest import recv_until

START = dict(type="start", scenario="normal_week", seed=7, manager="human", speed=0, hospital_id="rwjuh_nb")


def is_hour(m):
    return m["type"] == "hour" and not m.get("ack")


def is_ack(m):
    return m["type"] == "hour" and m.get("ack")


def open_run(ws, **kw):
    ws.send_json(dict(START, **kw))
    header = ws.receive_json()
    assert header["type"] == "header", header
    snap, _ = recv_until(ws, lambda m: m["type"] == "snapshot")
    ack, _ = recv_until(ws, is_ack)
    return header, snap, ack


def test_full_flow(client, validators):
    with client.websocket_connect("/ws/sim") as ws:
        header, snap, ack = open_run(ws)
        for k in ("run_id", "scenario", "seed", "hospital_id", "manager", "tick_minutes", "enums", "layout", "action_spec", "metric_defs"):
            assert k in header
        assert header["manager"]["id"] == "human" and header["tick_minutes"] == 5 and header["seed"] == 7
        validators["layout"].validate(header["layout"])
        assert "wait_mean_min" in header["metric_defs"] and {h["name"] for h in header["action_spec"]} >= {"divert", "rn_night"}
        validators["snapshot"].validate(snap["snapshot"])
        assert snap["snapshot"]["t"] == 0 and ack["mask"]["divert"] is True and ack["mask"]["rn_night"] is True and ack["pending"] == {}

        # human knobs: merged into pending, applied at the next boundary (tick 0 is hourly and daily)
        ws.send_json(dict(type="action", actions={"rn_night": 3}))
        ws.send_json(dict(type="action", actions={"divert": 1, "nope": 1, "priority_rule": 99}))
        a1, _ = recv_until(ws, is_ack)
        a2, seen = recv_until(ws, is_ack)
        assert a1["pending"] == {"rn_night": 3} and a2["pending"] == {"rn_night": 3, "divert": 1}
        assert len([m for m in seen if m["type"] == "error"]) == 2
        ws.send_json(dict(type="step"))
        s1, _ = recv_until(ws, lambda m: m["type"] == "snapshot")
        validators["snapshot"].validate(s1["snapshot"])
        assert s1["snapshot"]["t"] == 1
        assert s1["snapshot"]["kpis"]["settings"]["divert"] == 1 and s1["snapshot"]["kpis"]["settings"]["rn_night"] == 3
        assert {d["head"] for d in s1["snapshot"].get("decisions", [])} >= {"divert", "rn_night"}

        # paused: nothing else arrives until we ask; a weekly head stays pending until its boundary
        ws.send_json(dict(type="action", actions={"imaging_hours": 2}))
        a3, _ = recv_until(ws, is_ack)
        assert a3["pending"] == {"imaging_hours": 2} and a3["t"] == 1

        ws.send_json(dict(type="speed", ticks_per_second=3000))
        hour, seen = recv_until(ws, is_hour)
        assert hour["t"] == 12 and set(hour["metrics"]) >= set(header["metric_defs"]) and all(isinstance(v, (int, float)) for v in hour["metrics"].values())
        assert set(hour["mask"]) == {h["name"] for h in header["action_spec"]}
        assert hour["pending"] == {"imaging_hours": 2}      # weekly head: still waiting for Monday 00:00
        fast, _ = recv_until(ws, lambda m: m["type"] == "snapshot")
        assert fast["snapshot"]["t"] > 12                    # fast speeds skip snapshots but keep simulating

        # hand over to the built-in fixed manager: it puts the defaults back at the next hour
        ws.send_json(dict(type="manager", manager="fixed"))
        ack, _ = recv_until(ws, lambda m: is_ack(m) and "manager_info" in m)
        assert ack["manager"] == "fixed" and ack["manager_info"]["kind"] == "fixed"
        t_hand = ack["t"]
        snap, _ = recv_until(ws, lambda m: m["type"] == "snapshot" and m["snapshot"]["t"] >= (t_hand // 12 + 1) * 12 + 1)
        assert snap["snapshot"]["kpis"]["settings"]["divert"] == 0
        ws.send_json(dict(type="manager", manager="no_such_manager"))
        err, _ = recv_until(ws, lambda m: m["type"] == "error")
        assert "no_such_manager" in err["message"]
        ws.send_json(dict(type="manager", manager="human"))
        ack, _ = recv_until(ws, lambda m: is_ack(m) and "manager_info" in m)
        assert ack["manager"] == "human"

        # run through the end of day 0: a summary arrives; then stop: a final summary
        summ, _ = recv_until(ws, lambda m: m["type"] == "summary", limit=20000)
        assert summ["t"] % 288 == 0 and "cost_per_day" in summ["summary"] and "wait_mean_min" in summ["summary"]
        ws.send_json(dict(type="stop"))
        final, _ = recv_until(ws, lambda m: m["type"] == "summary" and m.get("final"))
        assert final["t"] >= 288 and all(v is None or isinstance(v, (int, float)) for v in final["summary"].values())
        ws.send_json(dict(type="bogus"))
        assert "unknown message type" in recv_until(ws, lambda m: m["type"] == "error")[0]["message"]


def test_errors_before_start_and_bad_scenario(client):
    with client.websocket_connect("/ws/sim") as ws:
        ws.send_text("not json")
        assert ws.receive_json()["type"] == "error"
        ws.send_json(dict(type="action", actions={"divert": 1}))
        assert "start" in ws.receive_json()["message"]
        ws.send_json(dict(START, scenario="no_such_scenario"))
        m = ws.receive_json()
        assert m["type"] == "error" and "no_such_scenario" in m["message"]
        header, _, _ = open_run(ws)   # the socket is still usable
        assert header["scenario"] == "normal_week"


def _arrivals(ws, n_steps, actions=None):
    header, snap, _ = open_run(ws)
    if actions:
        ws.send_json(dict(type="action", actions=actions))
        recv_until(ws, is_ack)
    seen = {}
    for _ in range(n_steps):
        ws.send_json(dict(type="step"))
        snap, _ = recv_until(ws, lambda m: m["type"] == "snapshot")
        p = snap["snapshot"]["patients"]
        for i, pid in enumerate(p["id"]):
            seen.setdefault(pid, (p["condition"][i], p["arrival_mode"][i], p["age_band"][i]))
    return header, seen, snap["snapshot"]


def test_same_seed_same_patients(client):
    """Two sockets on one scenario and seed see the same arrivals, whatever the managers do."""
    with client.websocket_connect("/ws/sim") as a, client.websocket_connect("/ws/sim") as b:
        ha, pa, sa = _arrivals(a, 30)
        hb, pb, sb = _arrivals(b, 30, actions={"rn_night": 4, "md_night": 0, "priority_rule": 0, "fast_track": 0})
        assert ha["run_id"] != hb["run_id"]
        assert sa["t"] == sb["t"] == 30
        assert len(pa) > 20 and pa == pb
        assert sa["kpis"]["settings"] != sb["kpis"]["settings"]
    with client.websocket_connect("/ws/sim") as c:
        _, pc, _ = _arrivals(c, 30)
        ws_other = pc
    assert ws_other == pa      # and a third run later is identical again
    with client.websocket_connect("/ws/sim") as d:
        d.send_json(dict(START, seed=8))
        assert d.receive_json()["seed"] == 8
        recv_until(d, is_ack)
        seen = {}
        for _ in range(30):
            d.send_json(dict(type="step"))
            s, _ = recv_until(d, lambda m: m["type"] == "snapshot")
            p = s["snapshot"]["patients"]
            for i, pid in enumerate(p["id"]):
                seen.setdefault(pid, (p["condition"][i], p["arrival_mode"][i], p["age_band"][i]))
    assert seen != pa          # a different seed is a different stream


def test_detail_entities_and_inject(client):
    with client.websocket_connect("/ws/sim") as ws:
        header, _, _ = open_run(ws)
        rid = header["run_id"]
        for _ in range(3):
            ws.send_json(dict(type="step"))
        snap, _ = recv_until(ws, lambda m: m["type"] == "snapshot" and m["snapshot"]["t"] == 3)
        snap = snap["snapshot"]
        pid, sid = snap["patients"]["id"][0], snap["staff"]["id"][0]
        room, eq = header["layout"]["rooms"][0]["id"], header["layout"]["equipment"][0]["id"]
        for kind, eid in (("patient", pid), ("staff", sid), ("room", room), ("equipment", eq)):
            ws.send_json(dict(type="detail", entity=dict(kind=kind, id=eid)))
            d, _ = recv_until(ws, lambda m: m["type"] == "detail")
            assert d["entity"] == dict(kind=kind, id=eid) and isinstance(d["live"], dict) and isinstance(d["interactions"], list)
            assert isinstance(d["catalog"], dict) and d["catalog"]["catalog_refs"]
            assert "severity" not in d["live"] and "true_acuity" not in d["live"]
        assert d["catalog"]["attributes"]          # equipment/<type> resolved to its catalog definition
        ws.send_json(dict(type="detail", entity=dict(kind="patient", id=987654321)))
        assert recv_until(ws, lambda m: m["type"] == "error")[0]["message"].startswith("detail")

        # entity routes read the same live simulation through the run registry
        assert rid in [r["run_id"] for r in client.get("/api/runs").json()]
        p = client.get(f"/api/runs/{rid}/patients/{pid}").json()
        assert {"live", "latent_truth_available", "known_state", "interactions", "catalog_refs"} <= set(p)
        assert p["live"]["patient_id"] == pid and isinstance(p["latent_truth_available"], bool)
        flat = str(p)
        assert "true_disposition" not in flat and "severity_index" not in flat and "'severity'" not in flat
        assert any(r.startswith("patient/esi") for r in p["catalog_refs"])
        s = client.get(f"/api/runs/{rid}/staff/{sid}").json()
        assert s["live"]["staff_id"] == sid and s["catalog_refs"][0].startswith("staff/")
        assert client.get(f"/api/runs/{rid}/patients/987654321").status_code == 404
        assert client.get(f"/api/runs/{rid}/staff/ZZ-99").status_code == 404
        assert client.get("/api/runs/run-nope/patients/1").status_code == 404

        for ev in ("flu_surge", "mass_casualty", "ct_outage", "rn_callouts"):
            ws.send_json(dict(type="inject", event=ev))
            ack, _ = recv_until(ws, lambda m: is_ack(m) and "injected" in m)
            assert ack["injected"]["event"] == ev and ack["injected"]["starts_at_tick"] == 12
        ws.send_json(dict(type="inject", event="meteor"))
        assert "meteor" in recv_until(ws, lambda m: m["type"] == "error")[0]["message"]
        ws.send_json(dict(type="speed", ticks_per_second=3000))
        started, _ = recv_until(ws, lambda m: m["type"] == "snapshot" and any(e.get("kind") == "scenario" for e in m["snapshot"].get("events", [])))
        texts = " ".join(e["text"] for e in started["snapshot"]["events"])
        assert "equipment_outage" in texts and "flu_wave" in texts
        down = header["enums"]["equipment_status"].index("down")
        recv_until(ws, lambda m: m["type"] == "snapshot" and down in m["snapshot"]["equipment"]["status"])
    # after the socket closes the run stays for the grace period, then is swept
    assert rid in [r["run_id"] for r in runs.list_runs()]
    assert runs.sweep(now=time.time() + runs.GRACE_S + 1) == [rid]
    with pytest.raises(KeyError):
        runs.get(rid)


def test_injected_events_are_exogenous():
    """An injected event belongs to one run only: a second run on the same seed is untouched."""
    a, b = runs.Run("normal_week", seed=5), runs.Run("normal_week", seed=5)
    a.inject("mass_casualty")
    assert len(a.sim.scn.events) == 1 and b.sim.scn.events == []


def test_played_write_back_through_registry():
    """The encounter glue: hold a patient, write a played result back, and the next snapshot shows flag bit 8."""
    run = runs.register(runs.Run("normal_week", seed=3))
    try:
        sim, b = runs.get(run.run_id)
        assert sim.raw is run.sim and b == 0 and runs.lock(run.run_id) is run.lock
        assert int(sim.t[0]) == run.t and sim.enums is run.sim.enums       # attributes read through
        h = encounter_glue.sim_provider(run.run_id)
        s2, b2 = h
        assert s2.raw is run.sim and b2 == 0
        sim = run.sim
        pid = None
        for _ in range(60):
            snap = run.advance(6)[-1]["snapshot"]
            for cand in snap["patients"]["id"]:
                pend = h.pending_interaction(cand)
                if pend and pend.get("status") == "waiting":
                    pid = cand
                    break
            if pid is not None:
                break
        assert pid is not None, "no patient was waiting for a provider in the first 30 simulated hours"
        assert h.latent_truth(pid)["patient_id"] == pid and "known_fact_ids" in h.known_state(pid)
        assert h.hold_for_play(pid) is True
        assert run.encounters == {f"patient-{pid}"}
        with_provider = sim.enums["patient_state"].index("with_provider")
        for _ in range(400):
            snap = run.advance(1)[-1]["snapshot"]
            i = snap["patients"]["id"].index(pid)
            if snap["patients"]["state"][i] == with_provider and (h.pending_interaction(pid) or {}).get("status") == "in_progress":
                break
        else:
            raise AssertionError("held patient never reached a provider")
        # held: the sampler does not finish the encounter on its own
        snap = run.advance(60)[-1]["snapshot"]
        i = snap["patients"]["id"].index(pid)
        assert snap["patients"]["state"][i] == with_provider and not snap["patients"]["flags"][i] & 8
        h.apply_interaction_result(dict(interaction_id="enc-test", interaction_type="clinician_encounter", patient_id=pid, resolver="played",
                                        duration_min=1.0, information_gained=[], quality=0.9, session_ref="enc-test",
                                        decision=dict(kind="disposition", orders=[], disposition="discharge")))
        assert run.encounters == set()
        snap = run.advance(1)[-1]["snapshot"]
        i = snap["patients"]["id"].index(pid)
        assert snap["patients"]["flags"][i] & 8
        moved = False
        for _ in range(36):
            snap = run.advance(1)[-1]["snapshot"]
            if pid not in snap["patients"]["id"] or snap["patients"]["state"][snap["patients"]["id"].index(pid)] != with_provider:
                moved = True
                break
        assert moved, "patient did not move on after the played result"
        d = run.patient(pid) if pid in snap["patients"]["id"] else None
        if d:
            assert "played" in d["live"]["flag_names"] and any(x.get("resolver") == "played" for x in d["interactions"])
    finally:
        runs.clear()


def test_encounter_keeps_run_alive():
    run = runs.register(runs.Run("normal_week", seed=1))
    try:
        runs.hold_open(run.run_id, "enc-1")
        runs.disconnect(run)
        assert runs.sweep(now=time.time() + runs.GRACE_S + 5) == []
        runs.release(run.run_id, "enc-1")
        assert runs.sweep(now=time.time() + runs.GRACE_S + 5) == [run.run_id]
    finally:
        runs.clear()


def test_learned_policy_gets_weights_appended(monkeypatch):
    """A policy that declares a larger input size receives obs + reward weights; a failing policy hands control back."""
    import torch
    run = runs.Run("normal_week", seed=2)
    got = {}

    class Learned:
        id, kind, label, objective = "ppo_x", "learned", "PPO x", "min_cost"
        obs_dim = run.sim.obs_dim + 3

        def reset(self, B, device):
            got["reset"] = (B, device)

        def act(self, obs, mask, sim=None):
            got["shape"] = tuple(obs.shape)
            got["tail"] = obs[0, -3:].tolist()
            return {"divert": torch.ones(1, dtype=torch.long), "not_a_head": torch.ones(1, dtype=torch.long)}

    info = dict(id="ppo_x", kind="learned", label="PPO x", objective="min_cost", reward_weights={"cost": 1.0, "wait": 0.25, "lwbs": 0.5}, available=True)
    monkeypatch.setattr(managers, "load_manager", lambda mid, device="cpu": Learned())
    monkeypatch.setattr(managers, "manager_info", lambda mid: info)
    monkeypatch.setattr(managers, "_weights_vector", lambda policy, i, k, like: torch.tensor([[1.0, 0.25, 0.5]])[:, :k])
    assert run.set_manager("ppo_x")["kind"] == "learned" and got["reset"] == (1, "cpu")
    msgs = run.advance(1)
    assert got["shape"] == (1, run.sim.obs_dim + 3) and got["tail"] == [1.0, 0.25, 0.5]
    assert msgs[-1]["snapshot"]["kpis"]["settings"]["divert"] == 1

    def boom(obs, mask, sim=None):
        raise RuntimeError("checkpoint mismatch")
    run.policy.act = boom
    msgs = run.advance(12)
    errs = [m for m in msgs if m["type"] == "error"]
    assert len(errs) == 1 and "checkpoint mismatch" in errs[0]["message"] and run.manager["id"] == "human"


def test_deferred_write_back():
    """A learner who finishes before the simulated patient is seen: the result is applied when the encounter starts."""
    run = runs.register(runs.Run("normal_week", seed=3))
    try:
        h = encounter_glue.sim_provider(run.run_id)
        pid = None
        for _ in range(60):
            snap = run.advance(6)[-1]["snapshot"]
            pid = next((c for c in snap["patients"]["id"] if (h.pending_interaction(c) or {}).get("status") == "waiting"), None)
            if pid is not None:
                break
        assert pid is not None
        res = dict(interaction_id="enc-d", interaction_type="clinician_encounter", patient_id=pid, resolver="played", duration_min=2.0,
                   information_gained=[], quality=0.7, decision=dict(kind="disposition", orders=[], disposition="discharge"))
        assert h.apply_interaction_result(res) == "deferred" and pid in run.deferred
        for _ in range(400):
            snap = run.advance(1)[-1]["snapshot"]
            if pid not in run.deferred:
                break
        assert pid not in run.deferred
        if pid in snap["patients"]["id"]:
            assert snap["patients"]["flags"][snap["patients"]["id"].index(pid)] & 8
    finally:
        runs.clear()


def test_post_encounter_from_sim_patient(client):
    """POST /api/encounters {run_id, patient_id} reaches the live simulation, whoever handles it."""
    pytest.importorskip("encounter.session")
    pytest.importorskip("encounter.templates")
    assert client.post("/api/encounters", json=dict(run_id="run-nope", patient_id=1)).status_code in (404, 409, 422)
    run = runs.register(runs.Run("normal_week", seed=3))
    h = encounter_glue.sim_provider(run.run_id)
    pid = None
    for _ in range(60):
        snap = run.advance(6)[-1]["snapshot"]
        pid = next((c for c in snap["patients"]["id"] if (h.pending_interaction(c) or {}).get("status") == "waiting"), None)
        if pid is not None:
            break
    r = client.post("/api/encounters", json=dict(run_id=run.run_id, patient_id=pid))
    assert r.status_code in (200, 201), r.text
    d = r.json()
    assert d["encounter_id"] and "case" in d and "chart" in d and "patient" in d and "llm" in d
    assert "faculty_truth" not in r.text
    assert run.patient(pid)["live"]["held_for_play"] is True
    if encounter_glue.state["mounted"]:
        f = client.post(f"/api/encounters/{d['encounter_id']}/finish", json=dict(disposition="discharge", orders=[], summary="test"))
        assert f.status_code == 200, f.text
        assert f.json()["written_back"] is True
        for _ in range(400):
            snap = run.advance(1)[-1]["snapshot"]
            if pid not in snap["patients"]["id"] or snap["patients"]["flags"][snap["patients"]["id"].index(pid)] & 8:
                break
        assert pid not in snap["patients"]["id"] or snap["patients"]["flags"][snap["patients"]["id"].index(pid)] & 8
