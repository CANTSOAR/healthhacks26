"""Smoke test against a running server: every GET route plus a 3-simulated-hour websocket session.

    .venv/bin/python -m server.smoke http://localhost:8000

Prints one PASS/FAIL line per check and exits 1 when any check failed.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time

import httpx

RESULTS: list[tuple[bool, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((bool(ok), name, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}{('  - ' + detail) if detail else ''}", flush=True)
    return bool(ok)


def get(client: httpx.Client, path: str, expect, name: str | None = None, status: int = 200):
    """expect(json) -> truthy or a description string of what is wrong (falsy = fine when it returns None)."""
    name = name or f"GET {path}"
    try:
        r = client.get(path)
        if r.status_code != status:
            check(name, False, f"HTTP {r.status_code}: {r.text[:120]}")
            return None
        data = r.json()
        problem = expect(data)
        check(name, problem in (None, True), "" if problem in (None, True) else str(problem or "unexpected shape"))
        return data
    except Exception as e:  # noqa: BLE001
        check(name, False, f"{type(e).__name__}: {str(e)[:160]}")
        return None


def keys(*names):
    def f(d):
        if isinstance(d, list):
            if not d:
                return None
            d = d[0]
        missing = [n for n in names if n not in d]
        return f"missing keys {missing}" if missing else None
    return f


def is_list(d):
    return None if isinstance(d, list) else "expected a list"


async def ws_session(base: str, scenario: str, hours: int = 3) -> dict:
    import websockets
    url = base.replace("http", "ws", 1) + "/ws/sim"
    out = dict(types={}, run_id=None, hours=0, last_t=0, errors=[], patient=None, staff=None, detail=None, summary=None, mask_ok=False)
    async with websockets.connect(url, max_size=None, open_timeout=10) as ws:
        await ws.send(json.dumps(dict(type="start", scenario=scenario, seed=7, manager="human", speed=600, hospital_id="rwjuh_nb")))
        asked = stopped = False
        deadline = time.time() + 90
        while time.time() < deadline:
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
            t = m.get("type")
            out["types"][t] = out["types"].get(t, 0) + 1
            if t == "header":
                out["run_id"] = m.get("run_id")
                out["header_keys"] = sorted(m)
                await ws.send(json.dumps(dict(type="action", actions={"priority_rule": 2})))
            elif t == "error":
                out["errors"].append(m.get("message"))
            elif t == "snapshot":
                s = m["snapshot"]
                out["last_t"] = s["t"]
                out["settings"] = (s.get("kpis") or {}).get("settings")
                if s["patients"]["id"] and out["patient"] is None:
                    out["patient"], out["staff"] = s["patients"]["id"][0], (s["staff"]["id"] or [None])[0]
                if out["patient"] is not None and not asked:
                    asked = True
                    await ws.send(json.dumps(dict(type="detail", entity=dict(kind="patient", id=out["patient"]))))
            elif t == "detail":
                out["detail"] = m
            elif t == "hour" and not m.get("ack"):
                out["hours"] += 1
                out["mask_ok"] = isinstance(m.get("mask"), dict) and isinstance(m.get("pending"), dict) and bool(m.get("metrics"))
                if out["hours"] >= hours and not stopped:
                    stopped = True
                    await ws.send(json.dumps(dict(type="pause")))
                    out["entities"] = await asyncio.to_thread(entity_checks, base, out["run_id"], out["patient"], out["staff"])
                    await ws.send(json.dumps(dict(type="stop")))
            elif t == "summary" and m.get("final"):
                out["summary"] = m.get("summary")
                break
    # rejoin: the run outlives its socket and a new socket can attach to it
    try:
        async with websockets.connect(url, max_size=None, open_timeout=10) as ws:
            await ws.send(json.dumps(dict(type="attach", run_id=out["run_id"])))
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            out["attach"] = dict(type=m.get("type"), attached=m.get("attached"), t=m.get("t"), speed=m.get("speed"))
            await ws.send(json.dumps(dict(type="attach", run_id="run-does-not-exist")))
            for _ in range(200):
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
                if m.get("type") == "error":
                    out["attach_gone"] = m.get("code")
                    break
    except Exception as e:  # noqa: BLE001
        out["attach"] = dict(error=f"{type(e).__name__}: {e}")
    return out


def entity_checks(base: str, run_id, patient, staff) -> list[tuple[str, bool, str]]:
    res = []
    with httpx.Client(base_url=base, timeout=15) as c:
        for name, path, need in ((f"GET /api/runs/<run>/patients/<id>", f"/api/runs/{run_id}/patients/{patient}",
                                  ("live", "latent_truth_available", "known_state", "interactions", "catalog_refs", "playable", "playable_reason")),
                                 ("GET /api/runs/<run>/playable", f"/api/runs/{run_id}/playable", ("run_id", "t", "playable")),
                                 (f"GET /api/runs/<run>/staff/<id>", f"/api/runs/{run_id}/staff/{staff}", ("live", "catalog_refs"))):
            try:
                r = c.get(path)
                d = r.json()
                missing = [k for k in need if k not in d]
                res.append((name, r.status_code == 200 and not missing, f"HTTP {r.status_code} {('missing ' + str(missing)) if missing else ''}".strip()))
            except Exception as e:  # noqa: BLE001
                res.append((name, False, f"{type(e).__name__}: {e}"))
    return res


def main(base: str) -> int:
    base = base.rstrip("/")
    with httpx.Client(base_url=base, timeout=30) as c:
        st = get(c, "/api/status", lambda d: keys("services", "torch", "device", "version")(d) or keys("sim", "llm", "voice", "data")(d["services"]))
        if st:
            s = st["services"]
            print(f"      sim live={s['sim']['live']}  llm={s['llm']['provider']} live={s['llm']['live']}  voice={s['voice']['provider']}  "
                  f"data={s['data']['provider']}  rl={s.get('rl', {}).get('live')}  encounter={st.get('encounter')}  torch={st['torch']}")
        get(c, "/api/enums", keys("patient_state", "room_type", "staff_role"))
        get(c, "/api/metrics", keys("metrics", "episode_summary"))
        cat = get(c, "/api/catalog", lambda d: keys("entity_types", "totals")(d) or keys("entity_type", "description", "n_variants", "n_attributes", "by_source")(d["entity_types"]))
        for et in [e["entity_type"] for e in (cat or {}).get("entity_types", []) if e["entity_type"] not in ("hospital", "condition")]:
            get(c, f"/api/catalog/{et}", keys("entity_type"))
        get(c, "/api/catalog/hospitals", keys("items"))
        get(c, "/api/catalog/conditions", keys("items"))
        for ref in ("space/treatment_bay", "staff/rn", "equipment/ct", "patient/esi3", "event/flu_wave", "hospital/rwjuh_nb"):
            get(c, f"/api/catalog/ref/{ref}", keys("entity_type", "variant", "label", "attributes"))
        enums = c.get("/api/enums").json() if cat is not None else {}
        cond = (enums.get("condition_group") or ["chest_pain"])[0]
        r = c.get(f"/api/catalog/ref/conditions/{cond}")
        check(f"GET /api/catalog/ref/conditions/{cond}", r.status_code in (200, 404),
              "resolved" if r.status_code == 200 else "404: no condition template file yet" if r.status_code == 404 else f"HTTP {r.status_code}")
        sc = get(c, "/api/scenarios", lambda d: is_list(d) or keys("id", "label", "description", "hospital_id", "days_default")(d) or (None if d else "no scenarios"))
        hs = get(c, "/api/hospitals", lambda d: is_list(d) or keys("id", "name", "disclaimer")(d) or (None if d else "no hospitals"))
        for h in hs or []:
            get(c, f"/api/layout/{h['id']}", keys("schema_version", "hospital_id", "name", "disclaimer", "site", "rooms", "equipment"))
        ms = get(c, "/api/managers", lambda d: is_list(d) or keys("id", "kind", "label", "objective", "reward_weights", "available")(d))
        if ms:
            print(f"      managers: {', '.join(m['id'] + ('' if m['available'] else ' (unavailable)') for m in ms)}")
        ro = get(c, "/api/rollouts", lambda d: is_list(d) or keys("rollout_id", "manager", "scenario", "seed", "days", "summary", "has_segments")(d))
        for item in (ro or [])[:2]:
            get(c, f"/api/rollouts/{item['rollout_id']}", keys("schema_version", "header", "hourly", "decisions", "segments"))
        res = get(c, "/api/results", keys("generated", "protocol", "rows", "human_runs"))
        if res is not None:
            print(f"      results: {len(res['rows'])} rows, {len(res['human_runs'])} human runs")
        val = get(c, "/api/validation", keys("targets", "simulated", "within"))
        if val is not None:
            print(f"      validation: status={val.get('status')} targets={len(val['targets'])} within={sum(val['within'].values())}/{len(val['within'])}")
        get(c, "/api/runs", is_list)
        get(c, "/api/cases", lambda d: None, name="GET /api/cases (encounter router)") if (st or {}).get("encounter") == "available" else \
            print("SKIP  GET /api/cases  - encounter router not mounted")
        get(c, "/api/catalog/ref/space/no_such_thing", lambda d: None if "detail" in d else "no detail", name="GET unknown catalog ref -> 404 JSON", status=404)

    scenario = (sc or [{"id": "normal_week"}])[0]["id"]
    try:
        t0 = time.time()
        w = asyncio.run(ws_session(base, scenario, hours=3))
        dt = time.time() - t0
        check("WS start -> header", w["types"].get("header") == 1 and bool(w["run_id"]), f"run_id={w['run_id']}")
        check("WS snapshots", w["types"].get("snapshot", 0) >= 3, f"{w['types'].get('snapshot', 0)} snapshots, last t={w['last_t']}")
        check("WS hour messages (3 simulated hours)", w["hours"] >= 3 and w["mask_ok"], f"{w['hours']} hours in {dt:.1f}s wall")
        check("WS action applied", (w.get("settings") or {}).get("priority_rule") == 2, f"settings.priority_rule={(w.get('settings') or {}).get('priority_rule')}")
        check("WS detail reply", isinstance(w["detail"], dict) and isinstance(w["detail"].get("live"), dict))
        for name, ok, detail in w.get("entities") or [("entity routes", False, "not reached")]:
            check(name, ok, detail)
        check("WS stop -> summary", isinstance(w["summary"], dict) and "wait_mean_min" in w["summary"],
              "" if not w["summary"] else f"wait_mean_min={w['summary'].get('wait_mean_min')}, cost_per_day={w['summary'].get('cost_per_day')}")
        a = w.get("attach") or {}
        check("WS attach after close -> header (attached)", a.get("type") == "header" and a.get("attached") is True and a.get("t") == w["last_t"],
              str(a))
        check("WS attach unknown run -> error run_gone", w.get("attach_gone") == "run_gone", str(w.get("attach_gone")))
        with httpx.Client(base_url=base, timeout=15) as c:
            listed = [r for r in c.get("/api/runs").json() if r.get("run_id") == w["run_id"]]
            need = ("run_id", "scenario", "seed", "manager", "t", "clock", "has_open_encounter", "expires_in_s")
            check("GET /api/runs lists the resumable run", bool(listed) and all(k in listed[0] for k in need),
                  f"expires_in_s={listed[0].get('expires_in_s')}" if listed else "run not listed")
        check("WS no error messages", not w["errors"], "; ".join(str(e) for e in w["errors"])[:300])
    except Exception as e:  # noqa: BLE001
        check("WS session", False, f"{type(e).__name__}: {str(e)[:200]}")

    failed = [r for r in RESULTS if not r[0]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed" + (f"; FAILED: {', '.join(r[1] for r in failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"))
