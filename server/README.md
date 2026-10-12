# server/ — HospitalGym API

FastAPI app `server.app:app`. Implements `contracts/api.md`: reference data, the live simulation websocket,
entity routes, the optimize jobs, and the per-hospital headline and attribution reports.

## Run

```
./run_server.sh            # uvicorn on http://127.0.0.1:8000, loads .env if present   (./run_server.sh 8001 for another port)
./run_web.sh               # pnpm --dir web install && pnpm --dir web dev  -> http://localhost:3000
.venv/bin/python -m pytest server/tests -q          # about 40 s
.venv/bin/python -m server.smoke http://localhost:8000   # every GET route + a 3-simulated-hour websocket session
```

CORS is open for `http://localhost:*` and `http://127.0.0.1:*`; `HG_CORS_ORIGINS` adds comma-separated origins for a
deployed site (or `*`). Environment switches: `HOST`, `PORT`, `HG_OPT_WORKERS` (optimize worker processes, default
cores - 4), `HOSPITAL_ID` (default hospital for optimize jobs, `rwjuh_nb`),
`HG_TORCH_THREADS` (default 1), `HG_NO_WARM` (skip the start-up warm-up), `HG_VALIDATION_DAYS` (14),
`HG_VALIDATION_BATCH` (4), `HG_STATE_DIR`, `HG_CATALOG_DIR`, `HG_RL_DIR`.

## Files

| File | What it does |
|---|---|
| `app.py` | routes, CORS, start-up warm-up, periodic sweep of dead runs |
| `live.py` | `WS /ws/sim`: one session per socket, pacing, message handling |
| `runs.py` | `Run` (one `HospitalSim`, batch 1, CPU, plus its lock) and the run registry |
| `managers.py` | bridge to `rl/` (managers, rollouts, results), built-in `human` / `fixed`, human runs |
| `catalog.py` | catalog summary, entity files, `catalog_ref` resolution, hospitals and layouts |
| `validation.py` | baseline run vs `catalog/validation_targets.yaml` |
| `status.py` | `/api/status` |
| `optimize.py` | `/api/optimize*`: runs `python -m rl.custom` as a subprocess, one job at a time, and serves its status and result |
| `attribution.py` | reads `rl/hospitals/<id>/attribution.json`; re-scores it under other weights; the inspector's value-of-this-resource block |
| `cache.py` | mtime-cached YAML/JSON reads, strict JSON output (NaN -> null) |
| `smoke.py` | integration smoke script |
| `state/` | run-time state, gitignored: `human_runs.json`, `validation_baseline.json`, `optimize/<job_id>/` |

## What each route reads

| Route | Source (re-read when the file changes; no restart needed) |
|---|---|
| `/api/status` | importability of `sim` and `rl`; `VLADA_API_KEY` for data; torch version |
| `/api/enums`, `/api/metrics`, `/api/actions` | `contracts/*.yaml` |
| `/api/catalog` | every `catalog/*.yaml`, plus `catalog/hospitals/*.yaml` and `catalog/conditions/*.yaml` aggregated; counts attributes by source tag |
| `/api/catalog/{entity_type}` | `catalog/<entity_type>.yaml`; `hospitals` and `conditions` return `{items}` |
| `/api/catalog/ref/{type}/{variant}` | the variant's attributes over the file's `shared` attributes; `hospital/<id>` and `conditions/<group>` look in their directories |
| `/api/scenarios` | `sim.list_scenarios()` (`[]` when the simulator is missing) |
| `/api/hospitals`, `/api/layout/{id}` | `catalog/hospitals/*.layout.json` |
| `/api/managers` | `rl.list_managers()` plus `human`; without `rl`: `human` and a built-in `fixed` (default settings every hour) |
| `/api/rollouts`, `/api/rollouts/{id}` | `rl/rollouts/index.json` (or the files themselves when there is no index) and `rl/rollouts/<id>.json.gz`; when there are none, the fixture rollout (`fixture`) |
| `/api/results` | `rl/results/results.json` (empty table when missing) + `server/state/human_runs.json` |
| `POST /api/results/human` | appends to `server/state/human_runs.json`, last run per (label, scenario) |
| `/api/validation` | `catalog/validation_targets.yaml` vs a baseline run: default settings, `normal_week`, 14 days, 4 hospitals, computed once per catalog version in a separate low-priority process and cached in `server/state/`; `status: "pending"` until ready |
| `/api/optimize/menu`, `POST /api/optimize`, `/api/optimize/{job_id}`, `/api/optimize` | `rl.custom` (metric menu, rank weights) and the job folders under `server/state/optimize/` |
| `/api/headline/{hospital_id}` | `rl/hospitals/<id>/headline.json` (written by `rl/headline.py`) |
| `/api/attribution/{hospital_id}` | `rl/hospitals/<id>/attribution.json` (written by `rl/attribution.py`) |
| `/api/runs/{run}/patients/{id}`, `/staff/{id}`, `/rooms/{id}`, `/equipment/{id}` | the live simulation of that run, through the registry; latent truth is never returned |

Anything optional that is missing or broken (rl, a catalog file, the validation targets) degrades to
an empty-but-valid answer; nothing takes the server down.

## The live simulation (`WS /ws/sim`)

Messages are exactly those of `contracts/api.md`; choices and additions are listed in `CONTRACT_REQUESTS.md`.

- `start` builds a `Run`: `HospitalSim(scenario, batch_size=1, device="cpu", seed=seed)`. The server sends `header`,
  the tick-0 `snapshot`, and an `hour` acknowledgement with the first `mask`, then starts the tick loop.
- The simulator is only ever called in a worker thread (`asyncio.to_thread`) under `run.lock`; the event loop never blocks.
- Pacing: one tick and one snapshot per `1 / ticks_per_second` up to 30 per second; above that, several ticks per
  snapshot. `speed 0` or `pause` stops the loop; `step` advances one tick while paused.
- `action` merges into `run.pending`; at each hour boundary the heads whose cadence mask is true are applied and
  leave `pending`. Under a manager, `policy.act(obs, mask, sim)` is called every simulated hour instead.
  The observation passed is `sim.observe()`; `rl`'s learned policies append their own reward weights when they see the
  raw simulator observation (`rl/managers.py: LearnedPolicy.act`). For policies that instead declare a larger
  `obs_dim`, the server appends `rl.common.weights_vec(reward_weights)` the way `rl.env.HospitalEnv.observe` does
  (`managers.policy_act`). A policy that raises hands control back to `human` and an `error` message is sent.
- `inject` appends an event (parameters from `catalog/event.yaml`) to the run's own scenario, starting at the next
  simulated hour; see `SIM_REQUESTS.md` item 1.
- Same scenario + seed on two sockets gives the same arrivals whatever the managers do (tested).
- Every failure is sent as `{"type": "error", "message": ...}`; the socket stays open.

## Run registry

```python
from server import runs
run = runs.get_run(run_id)     # KeyError if the run is not live. .sim (HospitalSim), .b, .lock, .patient(id), .staff(id), ...
with run.lock: ...             # the RLock the tick loop holds while advancing
```

Lifetime and rejoining: a run is registered at `start`. When its socket closes the run is kept, paused at its
current tick with all state intact, for 10 minutes (`runs.GRACE_S`). It does not advance while no socket is
attached. `{"type": "attach", "run_id": ...}` on any socket rejoins it: the server answers with a normal `header`
(`attached: true`, plus `speed`, `paused`, `t`, current `manager`), the current snapshot, an `hour` acknowledgement
and the summary so far, then streams on at the run's previous speed. If the run is gone the answer is
`{"type": "error", "code": "run_gone"}`. A socket whose run is attached from elsewhere gets
`{"type": "error", "code": "detached"}`. A second `start` on a socket leaves its previous run resumable.
`GET /api/runs` lists runs: `{run_id, scenario, seed, manager, t, clock, expires_in_s}`
(`expires_in_s` is null while a socket is attached; also `connected`, `speed`, `paused`, `finished`, `hospital_id`,
`manager_info`). At most 12 detached runs are kept (`runs.MAX_IDLE_RUNS`); the oldest go first.

## Inspector payloads

`Run.patient(id)` returns the public live state, `latent_truth_available`, `known_state`, `pending_interaction`, the
patient's `interactions` (the log of interaction results the simulator sampled from `catalog/interactions.yaml`:
duration, information gained, decision, quality) and the resolved catalog entries. Staff, rooms and equipment also
carry `attribution` when `rl/hospitals/<id>/attribution.json` exists. The latent truth is never returned.
