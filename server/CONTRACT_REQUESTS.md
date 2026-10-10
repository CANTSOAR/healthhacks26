# Contract notes and requests from the server (`contracts/api.md`)

The server implements the contract as written. These are the places where it had to choose a reading or add
something. All additions are extra keys or extra routes; nothing documented was removed or renamed.

## Readings chosen

1. **Reply to `action`, `manager`, `inject`.** The contract says actions are acknowledged "via the `hour` message with
   `pending` and `mask`". Besides the hourly message, the server sends an `hour` message immediately in reply to
   `action`, `manager` and `inject`, with `metrics: {}` and `"ack": true`, so the UI can show the pending knobs without
   waiting up to an hour of simulated time. Clients that append `metrics` to charts must skip empty `metrics`
   (the web client's loop over `metrics` already does nothing for `{}`). Proposed text: "`hour` may also be sent as an
   acknowledgement with `ack: true` and empty `metrics`."
2. **`pending` semantics.** `pending` holds the human's requested values that have not reached their cadence boundary
   yet (a weekly head set on Wednesday stays pending until Monday 00:00). Applied values leave `pending`; the current
   settings are in `snapshot.kpis.settings`. Under a non-human manager, human `action`s are stored but not applied
   until the human takes over (an `error` message says so); handing over to a manager clears `pending`.
3. **Fast speeds.** Up to 30 ticks/s every tick is sent as a snapshot. Above that, snapshots are skipped while the
   simulation keeps its pace, and `hour` / `summary` messages are still sent for every hour / day, so several `hour`
   messages can arrive between two snapshots. When the simulator cannot reach the requested speed the server sends a
   snapshot at least every ~70 ms of wall time.
4. **`stop`.** Stops the tick loop and sends `summary` with `"final": true`; the socket stays open and a new `start`
   may follow. The run stays in the registry until the socket closes plus a grace period.
5. **`detail.catalog`.** The resolved definition of the entity's first catalog ref (same shape as
   `/api/catalog/ref/...`), plus `catalog_refs: [...]` and `refs: {ref: definition}` for all of them (a patient has
   `patient/esiN` and `conditions/<group>`).
6. **Unknown things are HTTP 404 with `{"detail": "..."}`** (catalog ref, layout, rollout, run, patient, staff).
7. **`/api/rollouts/{id}`** is sent with `Content-Encoding: gzip` regardless of `Accept-Encoding` (browsers and httpx
   decode it transparently).
8. **`/api/validation`** adds `status` (`pending` | `ready` | `error` | `no_targets`), `baseline` (how it was computed)
   and `summary`. While `pending`, `simulated` and `within` are `{}` (or the previous catalog version's values with
   `"stale": true`). Target names are the attribute name for the `rwjuh_nb` variant and `<variant>.<attribute>` for
   peer groups. Only targets with a like-for-like simulator output are compared (see `server/validation.py: MAP`).
9. **`/api/catalog`** counts every `catalog/*.yaml` (so `interaction` and `validation_target` are listed too) plus
   `hospital` and `condition` aggregated over their directories. Each entry and `totals` also carry
   `n_validation_only`.
10. **Latent truth.** `live` in entity routes and `detail` messages omits `true_acuity`, `severity`,
    `true_disposition` even though `sim.patient_detail` returns them.
11. **`POST /api/encounters`** answers 201 (the encounter router's choice), not 200.

## Additions (extra, optional for clients)

- `start` accepts `days` (stop automatically after that many simulated days, final `summary` sent).
- `inject` accepts `params` to override the catalog's event parameters.
- `action` values may be option labels (`"divert": "on"`) as well as indices.
- Header: `ticks_per_hour`, `synthetic`, `notes`. `hour`: `manager` (id in control). `summary`: `t`, `days`, `final`.
- `GET /api/runs`, `GET /api/runs/{run_id}/rooms/{room_id}`, `GET /api/runs/{run_id}/equipment/{equipment_id}`,
  `GET /api/actions` (`contracts/actions.yaml` as JSON).
- `/api/status`: `services.rl`, `services.encounter`, top-level `encounter: "available" | "unavailable"`,
  `services.sim.active_runs`.
- Patient route: `pending_interaction` (whether the clinician encounter is playable now) and `catalog`
  (resolved refs).

## Round 2 additions (rejoin, queued write-back, playability)

Proposed text for `contracts/api.md`; all implemented and tested.

- Client message `{"type": "attach", "run_id": "..."}`. Reply: `header` with `"attached": true`, `speed`, `paused`,
  `t`; then `snapshot`, `hour` (ack) and `summary`; streaming resumes at the previous speed. Unknown or expired run:
  `{"type": "error", "code": "run_gone", "run_id", "message"}`. A socket that loses its run to another attach gets
  `{"type": "error", "code": "detached"}`. `header` from `start` carries `"attached": false` and the same extra keys.
- Runs outlive their socket: 10 minutes, 30 with an open encounter or journey or a queued result; paused meanwhile.
- `stop` now also marks the run paused, so attaching to a stopped run does not restart its clock (`resume` does).
- `GET /api/runs` -> `[{run_id, scenario, seed, manager, t, clock: {day, minute_of_day, dow}, has_open_encounter,
  expires_in_s, connected, speed, paused, hospital_id, manager_info}]`. `manager` is the manager id (string);
  `manager_info` is the full object. `expires_in_s` is null while a socket is attached.
- `hour` messages carry `playable: [patient ids]`. `GET /api/runs/{run_id}/playable` -> `{run_id, t, playable}`.
- Patient route and `detail`: `playable`, `playable_code`, `playable_reason`.
- `POST /api/encounters {run_id, patient_id}`: 409 `{"detail": {"message", "code", "playable": false, "patient_id"}}`
  when not playable (the encounter router's error shape, with `code` added); `"force": true` skips the check.
- `POST /api/encounters/{id}/finish` and `GET /api/encounters/{id}`: `write_back: {status, detail, ...}` added;
  `written_back` is true only for `applied` (it used to be true whenever the simulator did not raise).
- `DELETE /api/runs/{run_id}/patients/{patient_id}/hold` -> `{run_id, patient_id, released}`.
- Not covered: journey routes (`/api/journeys...`) are not annotated; their own `writeback.written_back` is true for
  both applied and queued results.
