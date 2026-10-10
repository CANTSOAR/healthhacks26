# HTTP and websocket API (`server/` implements, `web/` calls)

Base URL `http://localhost:8000`. JSON everywhere. The web app reads the base from
`NEXT_PUBLIC_API_URL` (default `http://localhost:8000`). When the server is unreachable the
web app falls back to the static fixtures in `web/public/fixtures/` and shows "offline" in
the status indicator.

## Status and reference data

| Method | Path | Returns |
|---|---|---|
| GET | `/api/status` | `{services: {sim: {live: bool}, llm: {live: bool, provider: "bedrock"\|"anthropic"\|"offline", model, last_error?}, voice: {live, provider: "elevenlabs"\|"browser"}, data: {live, provider: "vlada"\|"public_extracts"}}, torch, device, version}` |
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
{"type": "detail", "entity": {...}, "live": {...}, "catalog": {...}, "interactions": [...]}
{"type": "summary", "summary": {...episode_summary so far...}}      // every simulated day and on stop
{"type": "error", "message": "..."}
```

Two sockets with the same scenario and seed see the same patients (common random numbers),
which is how live compare works; recorded compare uses two rollouts with the same seed.

## Entities

| Method | Path | Returns |
|---|---|---|
| GET | `/api/runs/{run_id}/patients/{patient_id}` | `{live, latent_truth_available: bool, known_state, interactions, catalog_refs}` (never the latent truth itself) |
| GET | `/api/runs/{run_id}/staff/{staff_id}` | `{live, profile?, catalog_refs}` |

## Encounter (router lives in `encounter/api.py`, mounted by the server under `/api`)

Faculty (Patient Studio):

| Method | Path | Notes |
|---|---|---|
| GET | `/api/cases?status=` | list `{case_id, version, status, title, origin, profile: {name, age, gender}, updated}` |
| GET | `/api/cases/{case_id}?version=&view=faculty` | full case (`case.schema.json`) |
| POST | `/api/cases` | create a draft (body: full or partial case; or `{from_template, overrides}`; or `{from_description: "free text"}`) |
| PUT | `/api/cases/{case_id}` | edit; editing a published case creates a new draft version |
| POST | `/api/cases/{case_id}/validate` | `{ok, errors: [{path, message}], warnings: [...], consistency: [...]}` |
| POST | `/api/cases/{case_id}/approve` , `/publish` | draft → approved → published; published is immutable |
| GET | `/api/templates` , `/api/templates/{id}` | condition templates (`catalog/conditions/`) |
| GET | `/api/rubrics` , `/api/rubrics/{id}` | rubrics; default is the organizers' encounter rubric |
| GET | `/api/clinicians` | named fictional staff profiles (from `.private/` when present, else built-in fictional stand-ins) |

Student (never returns `faculty_truth`, undisclosed facts, or the rubric answer key):

| Method | Path | Notes |
|---|---|---|
| POST | `/api/encounters` | body `{case_id, version?}` or `{run_id, patient_id}` (instantiates a case from the simulated patient's latent truth; holds the sampler for that patient). Returns `{encounter_id, case: <learner view>, chart, patient: {name, age, gender, image?}, llm: {provider, live}}` |
| POST | `/api/encounters/{id}/turn` | body `{text, request_id}` → `{reply, disclosed: [{fact_id, chart_section, text}], chart, ledger_tail, rapport, provider: "bedrock"\|"anthropic"\|"offline", fallback?: bool}` |
| POST | `/api/encounters/{id}/request` | body `{request: "order:troponin" \| "exam:abdomen" \| "artifact:<id>", request_id}` → same shape as turn |
| GET | `/api/encounters/{id}` | state: transcript, learner-visible chart, ledger |
| POST | `/api/encounters/{id}/finish` | body `{disposition, orders?, summary?}` → `{feedback: {objectives: [{objective_id, criterion, result, evidence: [{turn, quote}], uncertain: bool, suggestion}], rubric: {domains: [{key, name, score, rationale, evidence, uncertain}]}, elicited: [...], missed: [...], strengths: [...], next_time: [...], grader: "llm"\|"offline"}, interaction_result: <interaction.schema.json result>, written_back: bool}` |
| GET | `/api/encounters?case_id=` | session log |
| POST | `/api/tts` | body `{text, voice?}` → audio (ElevenLabs when keyed; 204 otherwise so the browser uses speech synthesis) |

## Addenda accepted during the build (2026-10-10)

All additive; nothing above was removed or renamed. Details and examples live with the implementers:
`server/CONTRACT_REQUESTS.md`, `web/CONTRACT_REQUESTS.md`, `encounter/CONTRACT_REQUESTS.md`, `encounter/API_NOTES.md`.

- `hour` may also be sent immediately as an acknowledgement of `action` / `manager` / `inject` with `ack: true` and empty `metrics`. `hour` carries `manager` and `manager_info` (who is in control).
- `pending` holds only requested values that have not reached their cadence boundary; current settings are `snapshot.kpis.settings`.
- Above ~30 ticks/s snapshots are skipped while `hour` / `summary` are still sent for every hour / day.
- `stop` sends `summary` with `final: true`; the socket stays open. `start` accepts `days`. `inject` accepts `params`. `action` values may be option labels.
- `action_spec[]` entries carry `implemented: bool`. Event kinds also include `scenario`, `structural_started`, `structural_done`.
- Extra routes: `GET /api/actions`, `GET /api/runs`, `GET /api/runs/{run_id}/rooms/{room_id}`, `GET /api/runs/{run_id}/equipment/{equipment_id}`, `GET /api/cases/{case_id}/image`, `GET /api/encounter/status`, and the care-journey routes under `/api/journeys` (see `encounter/journey/`).
- `/api/validation` adds `status` (`pending` | `ready` | `error` | `no_targets`), `baseline`, `summary`, `stale`.
- `/api/status` adds `services.rl`, `services.encounter`, `services.sim.active_runs`.
- Unknown items: HTTP 404 `{"detail": ...}`. `POST /api/encounters` answers 201 and accepts `preview`, `learner`, `force`.
- `POST /api/results/human` accepts fractional `days`; result rows may carry extra metrics (e.g. labour cost per day).
- Entity `live` views omit `true_acuity`, `severity`, `true_disposition`.
- People resolve to catalog refs `staff/<role>` and `patient/esi<acuity>` (+ `conditions/<group>`).
- Slot grid inside a room (when `slots` is absent): `cols = ceil(sqrt(capacity * w / d))`, `rows = ceil(capacity / cols)`, one slot at the centre of each cell (the simulator's rule; the hand-built fixture predates it).
- Snapshot `patients` may carry an optional `bay` column: room index of the treatment space the patient holds, -1 if none.
