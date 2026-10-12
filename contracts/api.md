# HTTP and websocket API (`server/` implements, `web/` calls)

Base URL `http://localhost:8000`. JSON everywhere. The web app reads the base from
`NEXT_PUBLIC_API_URL` (default `http://localhost:8000`). When the server is unreachable the
web app falls back to the static fixtures in `web/public/fixtures/` and shows "offline" in
the status indicator.

## Status and reference data

| Method | Path | Returns |
|---|---|---|
| GET | `/api/status` | `{services: {sim: {live: bool, active_runs, last_error?}, rl: {live: bool, last_error?}, data: {live, provider: "vlada"\|"public_extracts"}}, torch, device, version}` |
| GET | `/api/enums` | `contracts/enums.yaml` as JSON |
| GET | `/api/metrics` | `contracts/metrics.yaml` as JSON |
| GET | `/api/catalog` | `{entity_types: [{entity_type, description, n_variants, n_attributes, by_source: {measured, literature, assumed}}], totals: {...}}` |
| GET | `/api/catalog/{entity_type}` | the catalog file as JSON (`catalog.schema.json`); `conditions` and `hospitals` return `{items: [...]}` |
| GET | `/api/catalog/ref/{path}` | resolve a `catalog_ref` such as `space/treatment_bay` or `staff/rn` to `{entity_type, variant, label, attributes: {key: attribute}}` (shared attributes merged in) |
| GET | `/api/scenarios` | `[{id, label, description, hospital_id, days_default}]` |
| GET | `/api/hospitals` | `[{id, name, disclaimer}]` |
| GET | `/api/layout/{hospital_id}` | `layout.schema.json` |
| GET | `/api/managers` | `[{id, kind, label, objective, reward_weights, available}]` |
| GET | `/api/rollouts` | `[{rollout_id, manager: {id, kind, label, objective}, scenario, seed, days, summary, has_segments}]` |
| GET | `/api/rollouts/{rollout_id}` | `rollout.schema.json` (gzip) |
| GET | `/api/results` | `{generated, protocol: {seeds, days, scenarios}, rows: [{manager_id, kind, label, objective, scenario, n_seeds, metrics: {name: {mean, std, ci95}}}], human_runs: [...]}` — the trade-off chart reads this |
| POST | `/api/results/human` | body `{label, scenario, seed, days, summary}`; stores the human player's last run so it appears on the trade-off chart |
| GET | `/api/headline/{hospital_id}` | `rl/hospitals/<id>/headline.json`: `{sentence, publishable, calibration_fingerprint, ensemble, objectives: {<objective>: {selected, ...}}}` — the constrained operating-policy result against the hospital's calibrated baseline (simulated) |
| GET | `/api/attribution/{hospital_id}` | `rl/hospitals/<id>/attribution.json` (written by `rl/attribution.py`): the simulated marginal value of every resource unit. `{simulated, manager, protocol: {n_seeds, days, scenarios, ci}, reward: {terms, scales, objectives, default_objective}, baseline, units: [{id, label, resource_class, kind, shift?, unit_cost_per_day, cost_basis, utilisation: {<scenario>}, scenarios: {<scenario>: {minus_one, plus_one}}}], ranking: {<scenario>: [...]}, findings: {<scenario>: {binding, worth_adding, slack, needed, not_shown_either_way, rule}}, identifiability, location}`. `minus_one` = (without the unit) − (baseline), `plus_one` = (with one more) − (baseline); each holds `delta: {metric: {mean, lo, hi}}`, `reward: {objective: {mean, lo, hi}}`, `money`, `top_effects`, `by_hour`, `by_day`, `terms_seeds`, `verdict`, `verified`. Query: `objective=<preset>` or `weights=<JSON {term: weight}>` adds `reward.custom` to every row, re-scored from the stored per-seed term differences without re-simulating; `view=summary` omits `terms_seeds` and `by_day`. 404 until the report exists |
| GET | `/api/validation` | `{targets: [{name, value, range, source, url}], simulated: {name: value}, within: {name: bool}}` — baseline outputs against Care Compare-style targets |

## Live simulation: `WS /ws/sim`

Client → server (JSON text frames):

```
{"type": "start", "scenario": "normal_week", "seed": 7, "manager": "human" | <manager id>, "speed": 12, "hospital_id": "rwjuh_nb"}
{"type": "action", "actions": {"rn_night": 3, "divert": 1}}       // human knobs; applied at the next valid boundary
{"type": "manager", "manager": <manager id> | "human"}             // hand over / take back mid-run
{"type": "speed", "ticks_per_second": 12}                           // 0 = pause
{"type": "pause"} | {"type": "resume"} | {"type": "step"}           // step = one tick while paused
{"type": "inject", "event": "flu_surge" | "mass_casualty" | "ct_outage" | "rn_callouts"}
{"type": "attach", "run_id": "run-..."}                          // rejoin a run whose socket closed (kept 10 minutes, paused)
{"type": "detail", "entity": {"kind": "patient"|"staff"|"room"|"equipment", "id": ...}}
{"type": "stop"}
```

Server → client:

```
{"type": "header", "run_id", "scenario", "seed", "hospital_id", "manager": {...}, "tick_minutes": 5,
 "enums": {...}, "layout": {...}, "action_spec": [...], "metric_defs": {...}}
{"type": "snapshot", "snapshot": {...snapshot.schema.json...}}       // one per tick
{"type": "hour", "t": <tick>, "metrics": {name: value}, "pending": {head: value}, "mask": {head: bool}}   // one per simulated hour
{"type": "layout", "layout": {...}}                                  // after a structural change
{"type": "detail", "entity": {...}, "live": {...}, "catalog": {...}, "interactions": [...]}   // interactions = the patient's sampled
                                                                     // interaction log (interaction.schema.json results)
{"type": "summary", "summary": {...episode_summary so far...}}      // every simulated day and on stop
{"type": "error", "message": "..."}
```

Two sockets with the same scenario and seed see the same patients (common random numbers),
which is how live compare works; recorded compare uses two rollouts with the same seed.

## Entities

| Method | Path | Returns |
|---|---|---|
| GET | `/api/runs/{run_id}/patients/{patient_id}` | `{live, latent_truth_available: bool, known_state, interactions, pending_interaction, catalog_refs, catalog}` (never the latent truth itself); `interactions` is the patient's log of sampled interaction results |
| GET | `/api/runs/{run_id}/staff/{staff_id}` | `{live, profile?, catalog_refs, catalog, attribution?}` |
| GET | `/api/runs/{run_id}/rooms/{room_id}` , `/api/runs/{run_id}/equipment/{equipment_id}` | `{live, catalog_refs, catalog, attribution?}` |
| GET | `/api/runs` | `[{run_id, scenario, seed, hospital_id, manager, manager_info, t, clock: {day, minute_of_day, dow}, expires_in_s, connected, speed, paused, finished}]` — live and resumable runs; `expires_in_s` is null while a socket is attached |

## Optimize for a chosen reward (`server/optimize.py` runs `python -m rl.custom`; all numbers simulated)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/optimize/menu` | `{synthetic: true, metrics: [{id, label, unit, natural: "max"\|"min", proxy: bool}], presets: [{id, label, goals, guardrails?}], ranking, guardrails, running: <job_id>\|null}` |
| POST | `/api/optimize` | body `{goals: [{metric, direction: "max"\|"min", rank}], guardrails?: bool (default true), hospital_id?}` → `{job_id, spec, workers}`. 422 for a bad goal list or hospital id. One job runs at a time: 409 `{"detail": {"message", "job_id"}}` while another is running |
| GET | `/api/optimize/{job_id}` | `{job_id, spec: {goals, guardrails, hospital_id, created, created_ts, weights}, status: {phase, ..., elapsed_s?, error?}, result?}` — poll it; `result` (the `result.json` written by `rl/custom.py`) is present when `status.phase` is `done`; `failed` carries `error`. 404 for an unknown job. Examples: `fixtures/optimize_status.fixture.json`, `fixtures/optimize_result.fixture.json` |
| GET | `/api/optimize` | the 30 most recent jobs, newest first: `[{job_id, created, goals, phase, headline}]` |

Rank 1 is the most important goal; each rank is worth half the rank above it, ties share a rank, weights sum to 1.
With guardrails on, deaths, adverse events and high-acuity waiting may be no worse than the calibrated baseline, with no
extra ambulance diversion, bounded overtime and no extra transfers out. Ambulance diversion and the admission cap are
never used as levers. Jobs are stored under `<state dir>/optimize/<job_id>/`. Environment: `HG_OPT_WORKERS` (worker
processes, default cores − 4), `HOSPITAL_ID` (default hospital, `rwjuh_nb`).


## Addenda accepted during the build (2026-10-10)

All additive. Details and examples live with the implementers:
`server/CONTRACT_REQUESTS.md`, `web/CONTRACT_REQUESTS.md`.

- `hour` may also be sent immediately as an acknowledgement of `action` / `manager` / `inject` with `ack: true` and empty `metrics`. `hour` carries `manager` and `manager_info` (who is in control).
- `pending` holds only requested values that have not reached their cadence boundary; current settings are `snapshot.kpis.settings`.
- Above ~30 ticks/s snapshots are skipped while `hour` / `summary` are still sent for every hour / day.
- `stop` sends `summary` with `final: true`; the socket stays open. `start` accepts `days`. `inject` accepts `params`. `action` values may be option labels.
- `action_spec[]` entries carry `implemented: bool`. Event kinds also include `scenario`, `structural_started`, `structural_done`.
- Extra route: `GET /api/actions` (`contracts/actions.yaml` as JSON).
- `/api/validation` adds `status` (`pending` | `ready` | `error` | `no_targets`), `baseline`, `summary`, `stale`.
- Unknown items: HTTP 404 `{"detail": ...}`.
- `POST /api/results/human` accepts fractional `days`; result rows may carry extra metrics (e.g. labour cost per day).
- Entity `live` views omit `true_acuity`, `severity`, `true_disposition`.
- People resolve to catalog refs `staff/<role>` and `patient/esi<acuity>` (+ `conditions/<group>`).
- Slot grid inside a room (when `slots` is absent): `cols = ceil(sqrt(capacity * w / d))`, `rows = ceil(capacity / cols)`, one slot at the centre of each cell (the simulator's rule; the hand-built fixture predates it).
- Snapshot `patients` may carry an optional `bay` column: room index of the treatment space the patient holds, -1 if none.
- Marginal value (simulated): the entity payloads of staff, rooms and equipment (`GET /api/runs/{run_id}/staff|rooms|equipment/{id}` and the websocket `detail` reply) may carry `attribution`: `{available, simulated: true, unit, label, unit_label, resource_class, kind, shift, scenario, existing, net_value_per_day: {mean, lo, hi}, unit_cost_per_day, net_value_per_dollar, reward, verdict, top_effects: [3], effects_of, now: {hour, margin_per_hour: {mean, hw}, reward_per_hour}, by_hour: {margin[24], margin_hw[24], reward[24], reward_hw[24]}, utilisation_now: {value, in_use?, of, basis}, utilisation_typical, next_unit, note, location?}`. It is the precomputed value of ONE UNIT of the entity's resource class at the run's hour of day (people of a role and bays of a class are interchangeable in the model), looked up in `attribution.json`; `utilisation_now` is read from the live run. Roles the model holds constant answer `{available: false, reason}`. The field is absent when no report exists or the entity is not a resource.

## Removed 2026-10-11: played patient encounters

The clinical-education stack (cases, played encounters, care journeys, Patient Studio) moved to a separate repository.
Gone from this API: every route under `/api/cases`, `/api/encounters`, `/api/encounter/status`, `/api/journeys`,
`/api/templates`, `/api/rubrics`, `/api/clinicians`, `/api/tts`; `GET /api/runs/{run_id}/playable`;
`DELETE /api/runs/{run_id}/patients/{patient_id}/hold`; `services.llm`, `services.voice`, `services.encounter` and the
top-level `encounter` field of `/api/status`; the `playable` list on `hour` messages; `playable`, `playable_code`,
`playable_reason` on the patient route and the `detail` reply; `has_open_encounter` and `open_encounters` on
`GET /api/runs`. A detached run is now always kept for 10 minutes. No websocket message type was removed. The
simulator's own interactions are unchanged: a clinician encounter is still an interaction type sampled from
`catalog/interactions.yaml`, and its results still appear in a patient's `interactions`.
