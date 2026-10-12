"""Optimise-for-your-reward jobs: the web app posts ranked goals, the server runs rl/custom.py as a subprocess
and the page polls its status. All numbers simulated.

    GET  /api/optimize/menu          metrics a user can pick, presets, and how ranks become weights
    POST /api/optimize               {goals: [{metric, direction: max|min, rank}], guardrails?: bool, hospital_id?} -> {job_id}
    GET  /api/optimize/{job_id}      {job_id, spec, status: {phase, gen, gens, history, ...}, result?}
    GET  /api/optimize               recent jobs, newest first

One job runs at a time (it uses every core); a second POST while one is running returns 409 with the running
job's id. Workers: HG_OPT_WORKERS (default: cores - 4). Jobs live under <state dir>/optimize/<job_id>/.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import uuid

from fastapi import APIRouter, Body, HTTPException

from .paths import ROOT, state_dir

router = APIRouter()
_lock = threading.Lock()
_proc: dict = {"job": None, "p": None}

PRESETS = [
    dict(id="margin_first", label="Profit first, then waits",
         goals=[dict(metric="profit", direction="max", rank=1), dict(metric="wait", direction="min", rank=2),
                dict(metric="patient_experience", direction="max", rank=3)]),
    dict(id="patients_first", label="Patients first",
         goals=[dict(metric="walkouts", direction="min", rank=1), dict(metric="wait", direction="min", rank=1),
                dict(metric="length_of_stay", direction="min", rank=2), dict(metric="boarding", direction="min", rank=3)]),
    dict(id="lean", label="Leanest staffing that holds service",
         goals=[dict(metric="labor_cost", direction="min", rank=1), dict(metric="wait_p95", direction="min", rank=2)]),
    dict(id="nonsense", label="Something that makes no sense (longest waits)",
         goals=[dict(metric="wait", direction="max", rank=1)], guardrails=False),
]


def _dir(job_id: str | None = None):
    d = state_dir() / "optimize"
    d.mkdir(parents=True, exist_ok=True)
    return d / job_id if job_id else d


def _read(p):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _running() -> str | None:
    p = _proc["p"]
    if p is not None and p.poll() is None:
        return _proc["job"]
    return None


def _job(job_id: str) -> dict | None:
    if not job_id.replace("-", "").isalnum():
        return None
    d = _dir(job_id)
    spec = _read(d / "spec.json")
    if spec is None:
        return None
    st = _read(d / "status.json") or dict(phase="queued")
    if st.get("phase") not in ("done", "failed") and _running() != job_id and time.time() - spec.get("created_ts", 0) > 20:
        st = dict(st, phase="failed", error=st.get("error") or "the optimizer process is no longer running (see log.txt in the job folder)")
    if st.get("phase") not in ("done", "failed"):
        st = dict(st, elapsed_s=time.time() - spec.get("created_ts", time.time()))     # computed at read time, not at the last write
    out = dict(job_id=job_id, spec=spec, status=st)
    if st.get("phase") == "done":
        out["result"] = _read(d / "result.json")
    return out


@router.get("/api/optimize/menu")
def menu():
    from rl.custom import METRIC_MENU
    return dict(synthetic=True,
                metrics=[dict(id=k, label=v["label"], unit=v["unit"], natural=v["natural"], proxy=bool(v.get("proxy"))) for k, v in METRIC_MENU.items()],
                presets=PRESETS,
                ranking="Rank 1 is most important. Each rank is worth half the rank above it; ties share a rank. Weights sum to 1.",
                guardrails="On: deaths, adverse events and high-acuity waiting no worse than current practice, no extra ambulance diversion, "
                           "bounded overtime, no extra transfers out. Ambulance diversion and the admission cap are never used as levers.",
                running=_running())


@router.get("/api/optimize")
def jobs():
    rows = []
    for d in sorted(_dir().iterdir(), key=lambda x: -x.stat().st_mtime)[:30]:
        j = _job(d.name) if d.is_dir() else None
        if j:
            rows.append(dict(job_id=j["job_id"], created=j["spec"].get("created"), goals=j["spec"].get("goals"), phase=j["status"].get("phase"),
                             headline=(j.get("result") or {}).get("headline")))
    return rows


@router.post("/api/optimize")
def start(body: dict = Body(...)):
    from rl.custom import goal_weights
    try:
        signed, rows = goal_weights(body.get("goals") or [])
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    hid = str(body.get("hospital_id") or os.environ.get("HOSPITAL_ID") or "rwjuh_nb")
    if not hid.replace("_", "").isalnum():
        raise HTTPException(status_code=422, detail="bad hospital_id")
    with _lock:
        run = _running()
        if run:
            raise HTTPException(status_code=409, detail=dict(message="an optimisation is already running", job_id=run))
        job_id = time.strftime("%H%M%S") + "-" + uuid.uuid4().hex[:6]
        d = _dir(job_id)
        d.mkdir(parents=True)
        spec = dict(goals=[dict(metric=r["metric"], direction=r["direction"], rank=r["rank"]) for r in rows], guardrails=bool(body.get("guardrails", True)),
                    hospital_id=hid, created=time.strftime("%Y-%m-%dT%H:%M:%S%z"), created_ts=time.time(), weights=signed)
        (d / "spec.json").write_text(json.dumps(spec, indent=1))
        workers = int(os.environ.get("HG_OPT_WORKERS") or max(2, (os.cpu_count() or 4) - 4))
        cmd = [sys.executable, "-m", "rl.custom", "--spec", str(d / "spec.json"), "--out", str(d), "--hospital", hid, "--cpu-workers", str(workers)]
        cmd += (os.environ.get("HG_OPT_ARGS") or "").split()
        log = open(d / "log.txt", "w")
        _proc["p"] = subprocess.Popen(cmd, cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT, env=dict(os.environ, HOSPITAL_ID=hid))
        _proc["job"] = job_id
    return dict(job_id=job_id, spec=spec, workers=workers)


@router.get("/api/optimize/{job_id}")
def get(job_id: str):
    j = _job(job_id)
    if j is None:
        raise HTTPException(status_code=404, detail=f"no optimisation job '{job_id}'")
    return j
