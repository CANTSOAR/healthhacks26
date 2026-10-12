"""FastAPI app for HospitalGym: `uvicorn server.app:app`. Routes: contracts/api.md."""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import threading

from fastapi import Body, FastAPI, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from . import __version__, attribution, cache, catalog, live, managers, runs, status as status_mod, validation
from .paths import CONTRACTS, rl_dir


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    async def sweeper():
        while True:
            await asyncio.sleep(30)
            with contextlib.suppress(Exception):
                runs.sweep()
    with contextlib.suppress(Exception):
        # batch-1 simulations are faster on one intra-op thread, and several sockets then do not fight for cores
        import torch
        torch.set_num_threads(max(1, int(os.environ.get("HG_TORCH_THREADS", "1"))))
    if not os.environ.get("HG_NO_WARM"):
        threading.Thread(target=runs.warm, name="warm", daemon=True).start()
    task = asyncio.create_task(sweeper())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(BaseException):
            await task


app = FastAPI(title="HospitalGym", version=__version__, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    # HG_CORS_ORIGINS: comma-separated extra origins for a deployed site (e.g. http://<host>:3000), or * for any
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"] + [o.strip() for o in os.environ.get("HG_CORS_ORIGINS", "").split(",") if o.strip()],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"], allow_headers=["*"], expose_headers=["Content-Encoding"],
)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content=dict(detail=f"{type(exc).__name__}: {str(exc)[:300]}"))


def J(data, status: int = 200) -> Response:
    return Response(content=cache.dumps(data), status_code=status, media_type="application/json")


def not_found(what: str):
    raise HTTPException(status_code=404, detail=what)


# ---------------------------------------------------------------- status and reference data
@app.get("/api/status")
def get_status():
    return J(status_mod.status())


@app.get("/api/enums")
def get_enums():
    return J(cache.load(CONTRACTS / "enums.yaml", default={}))


@app.get("/api/metrics")
def get_metrics():
    return J(cache.load(CONTRACTS / "metrics.yaml", default={"metrics": {}, "episode_summary": {}}))


@app.get("/api/actions")
def get_actions():
    return J(cache.load(CONTRACTS / "actions.yaml", default={"heads": []}))


@app.get("/api/catalog")
def get_catalog():
    return J(catalog.summary())


@app.get("/api/catalog/ref/{path:path}")
def get_catalog_ref(path: str):
    d = catalog.resolve_ref(path)
    if d is None:
        not_found(f"catalog ref '{path}' does not resolve")
    return J(d)


@app.get("/api/catalog/{entity_type}")
def get_catalog_entity(entity_type: str):
    d = catalog.entity(entity_type)
    if d is None:
        not_found(f"no catalog file for entity type '{entity_type}'")
    return J(d)


@app.get("/api/scenarios")
def get_scenarios():
    try:
        from sim import list_scenarios
        return J(list_scenarios())
    except Exception:  # noqa: BLE001 - simulator missing: an empty list is still the documented shape
        return J([])


@app.get("/api/hospitals")
def get_hospitals():
    return J(catalog.hospitals())


@app.get("/api/layout/{hospital_id}")
def get_layout(hospital_id: str):
    lay = catalog.layout(hospital_id)
    if lay is None:
        not_found(f"no layout for hospital '{hospital_id}'")
    return J(lay)


@app.get("/api/managers")
def get_managers():
    return J(managers.list_managers())


@app.get("/api/rollouts")
def get_rollouts():
    return J(managers.list_rollouts())


@app.get("/api/rollouts/{rollout_id}")
def get_rollout(rollout_id: str):
    raw = managers.rollout_gzip(rollout_id)
    if raw is None:
        not_found(f"no rollout '{rollout_id}'")
    return Response(content=raw, media_type="application/json", headers={"Content-Encoding": "gzip", "Vary": "Accept-Encoding"})


@app.get("/api/results")
def get_results():
    return J(managers.results())


@app.post("/api/results/human")
def post_human_result(body: dict = Body(...)):
    summary = body.get("summary")
    if not isinstance(summary, dict) or not isinstance(body.get("scenario"), str):
        raise HTTPException(status_code=422, detail="body needs {label, scenario, seed, days, summary: {metric: number}}")
    run = dict(label=str(body.get("label") or "You"), scenario=body["scenario"], seed=int(body.get("seed") or 0),
               days=float(body.get("days") or 0), summary={k: v for k, v in summary.items() if isinstance(v, (int, float))})
    days = run["days"]
    run["days"] = int(days) if float(days).is_integer() else days
    for k in ("run_id", "hospital_id", "manager_id"):
        if isinstance(body.get(k), str):
            run[k] = body[k]
    runs_ = managers.add_human_run(run)
    return J(dict(ok=True, stored=runs_[-1], n_human_runs=len(runs_)))


from . import optimize as _optimize  # noqa: E402
app.include_router(_optimize.router)


@app.get("/api/headline/{hospital_id}")
def get_headline(hospital_id: str):
    """The per-hospital operating-policy headline written by rl/headline.py (all numbers simulated)."""
    if not hospital_id.replace("_", "").isalnum():
        not_found(f"no headline for hospital '{hospital_id}'")
    f = rl_dir() / "hospitals" / hospital_id / "headline.json"
    if not f.exists():
        not_found(f"no headline for hospital '{hospital_id}': run rl/scripts/run_hospital.sh {hospital_id}")
    return J(json.loads(f.read_text()))


@app.get("/api/attribution/{hospital_id}")
def get_attribution(hospital_id: str, objective: str | None = None, weights: str | None = None, view: str | None = None):
    """Marginal value of every resource unit, written by rl/attribution.py (all numbers simulated). `objective=<preset>`
    or `weights=<json {term: weight}>` adds `reward.custom` to every row, re-scored from the stored term differences
    without re-simulating; `view=summary` leaves out the per-seed and per-day arrays."""
    rep = attribution.load(hospital_id)
    if rep is None:
        not_found(f"no attribution for hospital '{hospital_id}': run `python -m rl.attribution --hospital {hospital_id}`")
    w = None
    if weights:
        try:
            w = json.loads(weights)
            assert isinstance(w, dict)
        except Exception:  # noqa: BLE001
            raise HTTPException(status_code=422, detail="weights must be a JSON object {term: number}") from None
    if objective and not w and objective not in (rep["reward"].get("objectives") or {}):
        raise HTTPException(status_code=422, detail=f"unknown objective '{objective}'; have {sorted(rep['reward'].get('objectives') or {})}")
    ww = attribution.weights_for(rep, objective, w)
    if ww:
        rep = attribution.rescored(rep, ww)
    return J(attribution.summary(rep) if view == "summary" else rep)


@app.get("/api/validation")
def get_validation():
    return J(validation.report())


# ---------------------------------------------------------------- live simulation
@app.websocket("/ws/sim")
async def ws_sim(ws: WebSocket):
    await live.ws_sim(ws)


@app.get("/api/runs")
def get_runs():
    return J(runs.list_runs())


def _run(run_id: str) -> runs.Run:
    try:
        return runs.get_run(run_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e.args[0])) from None


@app.get("/api/runs/{run_id}/patients/{patient_id}")
def get_run_patient(run_id: str, patient_id: int):
    run = _run(run_id)
    try:
        return J(run.patient(patient_id))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e.args[0])) from None


@app.get("/api/runs/{run_id}/staff/{staff_id}")
def get_run_staff(run_id: str, staff_id: str):
    run = _run(run_id)
    try:
        return J(run.staff(staff_id))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e.args[0])) from None


@app.get("/api/runs/{run_id}/rooms/{room_id}")
def get_run_room(run_id: str, room_id: str):
    run = _run(run_id)
    try:
        return J(run.room(room_id))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e.args[0])) from None


@app.get("/api/runs/{run_id}/equipment/{equipment_id}")
def get_run_equipment(run_id: str, equipment_id: str):
    run = _run(run_id)
    try:
        return J(run.equipment(equipment_id))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e.args[0])) from None


@app.get("/")
def root():
    return J(dict(name="HospitalGym server", version=__version__, docs="/docs", status="/api/status"))
