"""Rejoining a run, queued write-back for early-state patients, playability, and holds that never leak."""
import time

import pytest

from server import encounter_glue, runs
from server.tests.conftest import recv_until
from server.tests.test_ws import START, is_ack, open_run


def result(pid, eid="enc-x", disposition="discharge"):
    return dict(interaction_id=eid, session_ref=eid, interaction_type="clinician_encounter", patient_id=pid, resolver="played",
                duration_min=2.0, information_gained=[], quality=0.7, decision=dict(kind="disposition", orders=[], disposition=disposition))


def find(run, states, max_ticks=600, playable=None):
    """Advance until a patient is in one of `states`; returns (patient id, snapshot)."""
    E = run.sim.enums["patient_state"]
    want = {E.index(s) for s in states}
    for _ in range(max_ticks):
        snap = run.advance(1)[-1]["snapshot"]
        for pid, st, fl in zip(snap["patients"]["id"], snap["patients"]["state"], snap["patients"]["flags"]):
            if st in want and not fl & 8 and (playable is None or run.playable(pid)[0] == playable):
                return pid, snap
    raise AssertionError(f"no patient reached {states}")


def state_of(run, pid):
    try:
        return run.sim.patient_detail(run.b, pid)
    except KeyError:
        return None


def step_to(ws, n):
    snap = None
    for _ in range(n):
        ws.send_json(dict(type="step"))
        snap, _ = recv_until(ws, lambda m: m["type"] == "snapshot")
    return snap["snapshot"]


def key(snap):
    p = snap["patients"]
    return snap["t"], p["id"], p["state"], p["room"], p["flags"], snap["kpis"]["settings"], snap["staff"]["id"], snap["staff"]["state"]


def test_attach_resumes_same_trajectory(client):
    with client.websocket_connect("/ws/sim") as a:
        header, _, _ = open_run(a)
        rid = header["run_id"]
        assert header["attached"] is False
        a.send_json(dict(type="action", actions={"rn_night": 3, "priority_rule": 0, "imaging_hours": 2}))
        recv_until(a, is_ack)
        assert step_to(a, 20)["t"] == 20
        a.send_json(dict(type="action", actions={"imaging_hours": 0, "divert": 1}))     # still pending when the socket closes
        recv_until(a, is_ack)
    # socket closed: the run is kept, paused at its tick, and listed as resumable
    listed = {r["run_id"]: r for r in client.get("/api/runs").json()}[rid]
    for k in ("run_id", "scenario", "seed", "manager", "t", "clock", "has_open_encounter", "expires_in_s"):
        assert k in listed
    assert listed["t"] == 20 and listed["manager"] == "human" and listed["has_open_encounter"] is False and listed["seed"] == 7
    assert runs.GRACE_S >= 600 and runs.GRACE_S - 5 <= listed["expires_in_s"] <= runs.GRACE_S
    assert set(listed["clock"]) >= {"day", "minute_of_day", "dow"} and listed["clock"]["minute_of_day"] == 100
    time.sleep(0.05)
    assert runs.get_run(rid).t == 20                      # it did not advance while nobody was attached
    with client.websocket_connect("/ws/sim") as b:
        b.send_json(dict(type="attach", run_id="run-nope"))
        gone = b.receive_json()
        assert gone["type"] == "error" and gone["code"] == "run_gone"
        b.send_json(dict(type="attach", run_id=rid))
        h2 = b.receive_json()
        assert h2["type"] == "header" and h2["attached"] is True and h2["run_id"] == rid and h2["speed"] == 0 and h2["t"] == 20
        assert h2["manager"]["id"] == "human" and h2["layout"]["rooms"] and h2["action_spec"]
        snap, _ = recv_until(b, lambda m: m["type"] == "snapshot")
        ack, _ = recv_until(b, is_ack)
        assert snap["snapshot"]["t"] == 20 and ack["pending"] == {"imaging_hours": 0, "divert": 1}
        resumed = step_to(b, 20)
        # a second socket takes the run over; the first is told
        with client.websocket_connect("/ws/sim") as c:
            c.send_json(dict(type="attach", run_id=rid))
            assert c.receive_json()["attached"] is True
            kicked, _ = recv_until(b, lambda m: m["type"] == "error")
            assert kicked["code"] == "detached"
    ref = runs.Run("normal_week", seed=7, hospital_id="rwjuh_nb")
    ref.set_actions({"rn_night": 3, "priority_rule": 0, "imaging_hours": 2})
    for _ in range(20):
        ref.advance(1)
    ref.set_actions({"imaging_hours": 0, "divert": 1})
    for _ in range(20):
        uninterrupted = ref.advance(1)[-1]["snapshot"]
    assert uninterrupted["kpis"]["settings"]["divert"] == 1
    assert key(resumed) == key(uninterrupted) and resumed["t"] == 40


def test_attach_resumes_at_previous_speed_and_manager(client):
    with client.websocket_connect("/ws/sim") as a:
        header, _, _ = open_run(a, speed=3000, manager="fixed")
        rid = header["run_id"]
        recv_until(a, lambda m: m["type"] == "hour" and not m.get("ack"))
    t_closed = runs.get_run(rid).t
    with client.websocket_connect("/ws/sim") as b:
        b.send_json(dict(type="attach", run_id=rid))
        h = b.receive_json()
        assert h["attached"] is True and h["speed"] == 3000 and h["paused"] is False and h["manager"]["id"] == "fixed" and h["t"] == t_closed
        m, _ = recv_until(b, lambda m: m["type"] == "hour" and not m.get("ack"))      # streaming again without any other message
        assert m["t"] > t_closed and m["manager"] == "fixed"
    # a new start on the same socket keeps the old run resumable as well
    with client.websocket_connect("/ws/sim") as c:
        h1, _, _ = open_run(c)
        h2, _, _ = open_run(c, seed=9)
        ids = [r["run_id"] for r in client.get("/api/runs").json()]
        assert h1["run_id"] in ids and h2["run_id"] in ids and rid in ids


def test_retention_and_sweep_release_holds():
    run = runs.register(runs.Run("normal_week", seed=3))
    try:
        sim, b = runs.get(run.run_id)
        pid, _ = find(run, ["waiting_triage", "waiting_bay", "waiting_provider"], playable=True)
        assert sim.hold_for_play(b, pid) is True and state_of(run, pid)["held_for_play"] is True
        runs.disconnect(run)
        now = time.time()
        assert runs.sweep(now + 601) == []                      # an open encounter: kept 30 minutes, not 10
        assert run.info(now + 601)["has_open_encounter"] is True and run.info(now + 601)["expires_in_s"] > 1000
        assert runs.sweep(now + runs.ENCOUNTER_GRACE_S + 1) == [run.run_id]
        assert state_of(run, pid)["held_for_play"] is False     # swept: nothing stays held
        run2 = runs.register(runs.Run("normal_week", seed=3))
        runs.disconnect(run2)
        assert runs.sweep(time.time() + 599) == [] and runs.sweep(time.time() + 601) == [run2.run_id]
    finally:
        runs.clear()


@pytest.mark.parametrize("early", ["waiting_triage", "in_triage", "waiting_bay", "waiting_provider"])
def test_early_state_result_is_queued_then_applied(early):
    """Clock stopped, patient not yet with a provider: the result is accepted, queued, and applied when the encounter starts."""
    run = runs.register(runs.Run("normal_week", seed=3))
    try:
        sim, b = runs.get(run.run_id)
        pid, _ = find(run, [early], playable=True)
        assert state_of(run, pid)["state"] == early and run.playable(pid)[:2] == (True, "pre_provider")
        assert sim.hold_for_play(b, pid) is True
        assert run.playable(pid)[1] == "held" and pid not in run.playable_ids()
        t0 = run.t
        assert sim.apply_interaction_result(b, result(pid, "enc-early")) == "queued"     # no tick in between: the clock is stopped
        assert run.t == t0 and runs.write_back("enc-early")["status"] == "queued" and "reaches the provider" in runs.write_back("enc-early")["detail"]
        assert run.has_open_encounter() and run.playable(pid)[1] == "result_queued"
        runs.disconnect(run)                                    # ... and the socket closed: still queued, run kept
        assert runs.sweep(time.time() + 700) == [] and runs.write_back("enc-early")["status"] == "queued"
        run.connected = True                                    # attach: the clock runs again
        for _ in range(900):
            run.advance(1)
            if runs.write_back("enc-early")["status"] != "queued":
                break
        wb = runs.write_back("enc-early")
        d = state_of(run, pid)
        if d is None or d["state"] == "exited":                 # left without being seen before reaching a provider
            assert wb["status"] in ("applied", "rejected")
        else:
            assert wb["status"] == "applied" and "played" in d["flag_names"] and d["held_for_play"] is False
            assert d["disposition"] == "discharge" or d["state"] != "with_provider"
        assert not run.has_open_encounter() and pid not in run.queued
    finally:
        runs.clear()


def test_past_encounter_is_rejected_and_never_left_held(client):
    run = runs.register(runs.Run("normal_week", seed=3))
    sim, b = runs.get(run.run_id)
    pid, _ = find(run, ["waiting_results", "in_ward", "boarding", "waiting_test"])
    ok, code, reason = run.playable(pid)
    assert (ok, code) == (False, "past_encounter") and "past the clinician encounter" in reason
    r = client.post("/api/encounters", json=dict(run_id=run.run_id, patient_id=pid))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "past_encounter" and "past the clinician encounter" in r.json()["detail"]["message"]
    assert sim.hold_for_play(b, pid) is False and state_of(run, pid)["held_for_play"] is False and not run.has_open_encounter()
    assert client.post("/api/encounters", json=dict(run_id=run.run_id, patient_id=987654)).status_code == 404
    assert client.post("/api/encounters", json=dict(run_id="run-nope", patient_id=1)).json()["detail"]["code"] == "run_gone"
    # a result that arrives after the simulation resolved the encounter itself: rejected, hold released, readable detail
    with pytest.raises(ValueError):
        sim.apply_interaction_result(b, result(pid, "enc-late"))
    wb = runs.write_back("enc-late")
    assert wb["status"] == "rejected" and "already resolved" in wb["detail"] and state_of(run, pid)["held_for_play"] is False
    p = client.get(f"/api/runs/{run.run_id}/patients/{pid}").json()
    assert p["playable"] is False and p["playable_code"] == "past_encounter" and p["playable_reason"]


def test_holds_released_on_abandon_and_expiry(client):
    run = runs.register(runs.Run("normal_week", seed=3))
    sim, b = runs.get(run.run_id)
    pid, _ = find(run, ["waiting_triage", "waiting_bay", "waiting_provider"], playable=True)
    r = client.post("/api/encounters", json=dict(run_id=run.run_id, patient_id=pid))
    assert r.status_code in (200, 201), r.text
    assert state_of(run, pid)["held_for_play"] is True and run.has_open_encounter()
    again = client.post("/api/encounters", json=dict(run_id=run.run_id, patient_id=pid))
    assert again.status_code == 409 and again.json()["detail"]["code"] == "held"
    # abandoned: the page releases the hold
    d = client.delete(f"/api/runs/{run.run_id}/patients/{pid}/hold")
    assert d.status_code == 200 and d.json()["released"] is True
    assert state_of(run, pid)["held_for_play"] is False and not run.has_open_encounter() and run.playable(pid)[0] is True
    # abandoned without telling anyone: the hold expires
    assert sim.hold_for_play(b, pid) is True
    assert run.expire_holds(time.time() + 60) == [] and run.expire_holds(time.time() + runs.HOLD_TTL_S + 1) == [pid]
    assert state_of(run, pid)["held_for_play"] is False and not run.has_open_encounter()


def test_playable_lists_and_fields(client):
    with client.websocket_connect("/ws/sim") as ws:
        header, _, ack = open_run(ws)
        rid = header["run_id"]
        assert isinstance(ack["playable"], list)
        ws.send_json(dict(type="speed", ticks_per_second=3000))
        hour, _ = recv_until(ws, lambda m: m["type"] == "hour" and not m.get("ack") and m["t"] >= 120 and m["playable"])
        ws.send_json(dict(type="pause"))
        ws.send_json(dict(type="detail", entity=dict(kind="patient", id=0)))      # sync point: everything before it is drained
        recv_until(ws, lambda m: m["type"] in ("detail", "error") and (m["type"] == "detail" or m["message"].startswith("detail")))
        run = runs.get_run(rid)
        ids = client.get(f"/api/runs/{rid}/playable").json()
        assert ids["run_id"] == rid and ids["t"] == run.t and ids["playable"]
        snap = run._quiet_snapshot()
        E = header["enums"]["patient_state"]
        by_id = dict(zip(snap["patients"]["id"], snap["patients"]["state"]))
        assert all(E[by_id[p]] in ("waiting_triage", "in_triage", "waiting_bay", "waiting_provider", "with_provider", "walking") for p in ids["playable"])
        late = [p for p, st in by_id.items() if E[st] in ("in_ward", "waiting_results", "boarding")]
        assert late and not set(late) & set(ids["playable"])
        pid = ids["playable"][0]
        p = client.get(f"/api/runs/{rid}/patients/{pid}").json()
        assert p["playable"] is True and p["playable_code"] in ("pre_provider", "with_provider") and p["playable_reason"]
        ws.send_json(dict(type="detail", entity=dict(kind="patient", id=pid)))
        d, _ = recv_until(ws, lambda m: m["type"] == "detail" and m["entity"]["id"] == pid)
        assert d["playable"] is True and d["playable_reason"]
        ws.send_json(dict(type="detail", entity=dict(kind="patient", id=late[0])))
        d, _ = recv_until(ws, lambda m: m["type"] == "detail" and m["entity"]["id"] == late[0])
        assert d["playable"] is False and d["playable_code"] == "past_encounter"


def test_http_round_trip_queued_then_applied_after_attach(client):
    """The default demo path: pause, pick a waiting patient, play in the same tab (socket closed), finish, come back."""
    pytest.importorskip("encounter.api")
    if not encounter_glue.state["mounted"]:
        pytest.skip("encounter router not mounted")
    with client.websocket_connect("/ws/sim") as ws:
        header, _, _ = open_run(ws, seed=3)
        rid = header["run_id"]
        E = header["enums"]["patient_state"]
        pid = None
        for _ in range(400):
            ws.send_json(dict(type="step"))
            snap, _ = recv_until(ws, lambda m: m["type"] == "snapshot")
            p = snap["snapshot"]["patients"]
            pid = next((i for i, st in zip(p["id"], p["state"]) if E[st] == "waiting_triage"), None)
            if pid is not None and snap["snapshot"]["t"] > 100:
                break
        assert pid is not None
        r = client.post("/api/encounters", json=dict(run_id=rid, patient_id=pid))
        assert r.status_code in (200, 201), r.text
        eid = r.json()["encounter_id"]
    # the page navigated away: socket closed, run kept with its open encounter
    info = {x["run_id"]: x for x in client.get("/api/runs").json()}[rid]
    assert info["has_open_encounter"] is True and info["expires_in_s"] > runs.GRACE_S
    f = client.post(f"/api/encounters/{eid}/finish", json=dict(disposition="admit", orders=["order:cbc"], summary="t")).json()
    assert f["written_back"] is False and f["write_back"]["status"] == "queued" and "reaches the provider" in f["write_back"]["detail"]
    assert "writeback_error" not in f["feedback"]
    assert client.get(f"/api/encounters/{eid}").json()["write_back"]["status"] == "queued"
    with client.websocket_connect("/ws/sim") as ws:
        ws.send_json(dict(type="attach", run_id=rid))
        assert ws.receive_json()["attached"] is True
        ws.send_json(dict(type="speed", ticks_per_second=3000))
        flagged = None
        for _ in range(3000):
            m = ws.receive_json()
            if m["type"] != "snapshot":
                continue
            p = m["snapshot"]["patients"]
            if pid not in p["id"]:
                break
            if p["flags"][p["id"].index(pid)] & 8:
                flagged = m["snapshot"]["t"]
                break
        g = client.get(f"/api/encounters/{eid}").json()
        if flagged is not None:
            assert g["write_back"]["status"] == "applied" and g["written_back"] is True
            d = client.get(f"/api/runs/{rid}/patients/{pid}").json()
            assert "played" in d["live"]["flag_names"] and d["live"]["held_for_play"] is False and d["playable_code"] == "already_played"
        else:
            assert g["write_back"]["status"] in ("applied", "rejected")
    # a case that is not a simulated patient: nothing to write back, said plainly
    cases = [c for c in client.get("/api/cases?status=published").json() if not str(c["case_id"]).startswith("sim-")]
    if cases:
        e = client.post("/api/encounters", json=dict(case_id=cases[0]["case_id"])).json()
        f = client.post(f"/api/encounters/{e['encounter_id']}/finish", json=dict(disposition="discharge")).json()
        assert f["written_back"] is False and f["write_back"]["status"] == "not_applicable"
