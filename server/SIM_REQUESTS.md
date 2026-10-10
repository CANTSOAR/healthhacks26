# Requests to the simulator (`sim/`) from the server

Nothing here blocks the server; each item has a working stand-in on the server side.

1. **Event injection hook.** `WS inject` (`flu_surge`, `mass_casualty`, `ct_outage`, `rn_callouts`) has no simulator
   method. The server appends a resolved event to the run's own `sim.scn.events` list (read once per simulated hour by
   `HospitalSim._scenario_state`), starting at the next hour, with parameters from `catalog/event.yaml`
   (`server/runs.py: Run.inject`). This relies on two internals: `scn.events` being re-read every hour, and the keys
   `_scenario_state` expects (`start_day`, `start_hour`, `duration_days` / `duration_hours` / `window_min`, ...).
   Wanted: `sim.inject_event(b, type, **params) -> dict` so the server stops depending on those. Note the list is
   shared by all hospitals of a batch; the server only ever runs batch 1.
2. **Played result before the encounter starts: done in the simulator** (`apply_interaction_result(..., defer=True)`);
   the server uses it and keeps its own queue only for a simulator without `defer`. Two small things remain: there is
   no public way to ask "is a result queued for this patient" or to cancel one, so on an abandoned encounter the
   server pops `sim._deferred[b][pid]` directly (`Run._release`); and `release_hold` does not drop a queued result.
   Wanted: `sim.deferred_result(b, pid)` and `release_hold` cancelling the queued result.
3. **Snapshot without side effects.** `snapshot(b)` drains the event and decision buffers. For room and equipment
   detail the server needs the current row without consuming them and saves/restores `sim._events[b]` /
   `sim._decisions[b]` around the call (`Run._quiet_snapshot`, same trick `staff_detail` uses). Wanted:
   `sim.snapshot(b, consume=False)` or `sim.room_detail(b, room_id)` / `sim.equipment_detail(b, equipment_id)`.
4. **Latent values in `patient_detail`.** It returns `true_acuity` and `severity`. The API must never return the latent
   truth, so the server strips `true_acuity`, `severity`, `true_disposition`, `latent_truth` from `live`
   (`runs.LATENT_KEYS`). Wanted: a `public=True` flag, or those keys moved to `latent_truth` only.
5. **Scenario load time.** `load_scenario` takes about 1 s (YAML parsing of the catalog). The server caches the
   resolved `ScenarioConfig` per (scenario, hospital, file times) and hands each run a deep copy. A faster loader
   (`yaml.CSafeLoader` when available) would help the first socket of each scenario.
