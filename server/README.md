# server/ — HospitalGym API

FastAPI app `server.app:app`. Implements `contracts/api.md`: reference data, the live simulation websocket,
entity routes, and (when the `encounter` package is importable) the encounter routes.

## Run

```
./run_server.sh            # uvicorn on http://127.0.0.1:8000, loads .env if present   (./run_server.sh 8001 for another port)
./run_web.sh               # pnpm --dir web install && pnpm --dir web dev  -> http://localhost:3000
.venv/bin/python -m pytest server/tests -q          # 43 tests, about 25 s
.venv/bin/python -m server.smoke http://localhost:8000   # every GET route + a 3-simulated-hour websocket session
```

CORS is open for `http://localhost:*` and `http://127.0.0.1:*`. Environment switches: `HOST`, `PORT`,
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
| `encounter_glue.py` | mounts `encounter.api.router`, hands it the live simulation |
| `cache.py` | mtime-cached YAML/JSON reads, strict JSON output (NaN -> null) |
| `smoke.py` | integration smoke script |
| `state/` | run-time state, gitignored: `human_runs.json`, `validation_baseline.json` |

## What each route reads

| Route | Source (re-read when the file changes; no restart needed) |
|---|---|
| `/api/status` | importability of `sim`, `rl`, `encounter`; `encounter.status()` for llm and voice; `VLADA_API_KEY` for data; torch version |
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
| `/api/runs/{run}/patients/{id}`, `/staff/{id}`, `/rooms/{id}`, `/equipment/{id}` | the live simulation of that run, through the registry; latent truth is never returned |

Anything optional that is missing or broken (rl, encounter, a catalog file, the validation targets) degrades to
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
sim, b = runs.get(run_id)      # KeyError if the run is not live. `sim` is a runs.LockedSim.
runs.lock(run_id)              # the RLock the tick loop holds while advancing (rarely needed, see below)
runs.get_run(run_id)           # the Run object: .sim (raw HospitalSim), .b, .lock, .patient(id), .staff(id), ...
```

`runs.get` returns a `LockedSim`: a proxy whose every method call takes the run lock, so `sim.latent_truth(b, pid)`,
`sim.hold_for_play(b, pid)` and so on are safe from any thread while the socket keeps ticking. It adds three things:

- `hold_for_play` marks the run as having an open encounter;
- `apply_interaction_result` returns `"applied"` or `"queued"` (see "Playing a simulated patient"), or raises when the
  simulation cannot use the result (the hold is released first);
- `release_hold` clears the mark and any queued result.

Lifetime and rejoining: a run is registered at `start`. When its socket closes the run is kept, paused at its
current tick with all state intact, for 10 minutes (`runs.GRACE_S`), or 30 minutes (`runs.ENCOUNTER_GRACE_S`) while an
encounter or journey holds one of its patients or a played result is queued. It does not advance while no socket is
attached. `{"type": "attach", "run_id": ...}` on any socket rejoins it: the server answers with a normal `header`
(`attached: true`, plus `speed`, `paused`, `t`, current `manager`), the current snapshot, an `hour` acknowledgement
and the summary so far, then streams on at the run's previous speed. If the run is gone the answer is
`{"type": "error", "code": "run_gone"}`. A socket whose run is attached from elsewhere gets
`{"type": "error", "code": "detached"}`. A second `start` on a socket leaves its previous run resumable.
`GET /api/runs` lists runs: `{run_id, scenario, seed, manager, t, clock, has_open_encounter, expires_in_s}`
(`expires_in_s` is null while a socket is attached; also `connected`, `speed`, `paused`, `hospital_id`, `manager_info`).
At most 12 detached runs without an open encounter are kept.

## Playing a simulated patient

- **Who is playable** (`Run.playable`): a patient before the provider (`waiting_triage`, `in_triage`, `waiting_bay`,
  `waiting_provider`, or walking to the provider) or with the provider in the clinician encounter; not already played,
  not held, no result queued. The patient route and `detail` messages carry `playable`, `playable_code`
  (`pre_provider`, `with_provider`, `past_encounter`, `already_played`, `held`, `result_queued`, `not_in_hospital`) and
  `playable_reason` (a sentence for the UI). Every `hour` message carries `playable: [patient ids]`, and
  `GET /api/runs/{run_id}/playable` returns `{run_id, t, playable}` on demand (use it while paused).
- **Starting**: `POST /api/encounters {run_id, patient_id}` is checked first by the server: 409 with
  `{"detail": {"message", "code", "playable": false}}` for a patient who is not playable, 404 for an unknown run
  (`code: "run_gone"`) or patient. Nothing is held when a start is refused.
- **Write-back**: `apply_interaction_result` goes to `sim.apply_interaction_result(b, result, defer=True)`. A patient in
  the encounter gets the result at once (`applied`). A patient who has not reached a provider gets it queued inside
  the simulator, which applies it on the tick that patient's clinician encounter starts, whenever the clock next runs
  (paused, or socket closed and attached later, makes no difference). A patient past the encounter is `rejected` and
  the hold is released.
- **What the page sees**: the answers of `POST /api/encounters/{id}/finish` and `GET /api/encounters/{id}` are
  annotated by the server (`encounter_glue.SimEncounterMiddleware`): `write_back: {status: "applied" | "queued" |
  "rejected" | "not_applicable", detail, run_id?, patient_id?}` and `written_back` is true only when `status` is
  `applied`. `GET /api/encounters/{id}` later turns from `queued` to `applied` (or `rejected` when the patient left
  without being seen, or the run expired). `not_applicable` is a case that is not a simulated patient.
- **Holds never leak**: released when a result is rejected, when the page calls
  `DELETE /api/runs/{run_id}/patients/{patient_id}/hold` (abandoned encounter), after 30 minutes without a result
  (`runs.HOLD_TTL_S`), and when the run is swept.

## Encounter glue

`encounter.api.router` is mounted under `/api` at import, and retried on `/api/status` and every 30 s, so the
package can appear after the server started. `/api/status` reports `encounter: "available" | "unavailable"`.

The live simulation reaches the encounter package through its hook: at mount the server calls
`encounter.api.register_sim_lookup(server.encounter_glue.sim_lookup)`, where `sim_lookup(run_id)` returns
`(LockedSim, b)` or `None`. `POST /api/encounters {run_id, patient_id}` then runs
`encounter.resolver.ClinicianEncounterResolver.start(sim, b, patient_id)`: hold the sampler, read the latent truth and
known state, build the case, open the session. `POST /api/encounters/{id}/finish` calls
`sim.apply_interaction_result(b, result)` on the same proxy, so the result lands in the running simulation and the
next snapshots show the patient moving on with flag bit 8 (`played`). Tested end to end in
`tests/test_ws.py::test_post_encounter_from_sim_patient` and by hand against a socket-driven run.

If a future encounter router had no such hook, `SimEncounterMiddleware` answers the `{run_id, patient_id}` form itself
with the same resolver; it steps aside whenever the router took the hook or mentions `run_id` in its source.

An abandoned encounter keeps its patient held (and not playable) until the page calls the `DELETE .../hold` route or
the 30-minute expiry passes.
