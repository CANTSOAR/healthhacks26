"""Rejoining a run: attach resumes the same trajectory, speed and manager; detached runs are kept, then swept."""
import time

from server import runs
from server.tests.conftest import recv_until
from server.tests.test_ws import START, is_ack, open_run


def step_to(ws, n):
    snap = None
    for _ in range(n):
        ws.send_json(dict(type="step"))
        snap, _ = recv_until(ws, lambda m: m["type"] == "snapshot")
    return snap["snapshot"]


def settled_t(rid):
    """The tick a run stopped at once its socket is gone. The server cancels the tick loop on close, but a burst
    already running in the worker thread finishes first, so wait for the detach and then read under the run lock."""
    run = runs.get_run(rid)
    for _ in range(200):
        if not run.connected:
            break
        time.sleep(0.01)
    time.sleep(0.1)
    with run.lock:
        return run.t


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
    for k in ("run_id", "scenario", "seed", "manager", "t", "clock", "expires_in_s"):
        assert k in listed
    assert listed["t"] == 20 and listed["manager"] == "human" and listed["seed"] == 7
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
    t_closed = settled_t(rid)
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


def test_retention_and_sweep():
    try:
        run = runs.register(runs.Run("normal_week", seed=3))
        assert runs.sweep(time.time() + 10 * runs.GRACE_S) == []          # attached runs are never swept
        runs.disconnect(run)
        now = time.time()
        info = run.info(now + 100)
        assert info["connected"] is False and runs.GRACE_S - 101 <= info["expires_in_s"] <= runs.GRACE_S - 100
        assert "has_open_encounter" not in info and "open_encounters" not in info
        assert runs.sweep(now + runs.GRACE_S - 1) == [] and runs.sweep(now + runs.GRACE_S + 1) == [run.run_id]
        # more detached runs than MAX_IDLE_RUNS: the oldest go first
        extra = [runs.register(runs.Run("normal_week", seed=i)) for i in range(2)]
        for i, r in enumerate(extra):
            runs.disconnect(r)
            r.last_seen = now - 10 + i
        keep = runs.MAX_IDLE_RUNS
        try:
            runs.MAX_IDLE_RUNS = 1
            assert runs.sweep(now) == [extra[0].run_id]
        finally:
            runs.MAX_IDLE_RUNS = keep
        assert [r["run_id"] for r in runs.list_runs()] == [extra[1].run_id]
    finally:
        runs.clear()


def test_patient_detail_has_no_played_fields(client):
    with client.websocket_connect("/ws/sim") as ws:
        header, _, ack = open_run(ws)
        assert "playable" not in ack
        snap = step_to(ws, 60)
        pid = snap["patients"]["id"][0]
        p = client.get(f"/api/runs/{header['run_id']}/patients/{pid}").json()
        assert {"live", "latent_truth_available", "known_state", "interactions", "catalog_refs", "catalog"} <= set(p)
        assert not {"playable", "playable_code", "playable_reason"} & set(p)
        ws.send_json(dict(type="detail", entity=dict(kind="patient", id=pid)))
        d, _ = recv_until(ws, lambda m: m["type"] == "detail")
        assert d["entity"] == {"kind": "patient", "id": pid} and isinstance(d["interactions"], list) and "playable" not in d
