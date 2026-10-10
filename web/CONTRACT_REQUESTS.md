# Contract requests from `web/`

Nothing here blocks the web app; each item says what the app assumes today.

1. **Where patients sit or lie inside a room.** `layout.schema.json` says positions are `slots` when given, "otherwise a grid
   inside the rectangle", without defining the grid. The scene draws beds and chairs where it expects patients to be, so it
   needs the same rule as the simulator. Assumed (copied from `contracts/fixtures/make_fixture.py`): columns =
   `max(1, floor(w / 1.5))`, slot `k` at `(x - w/2 + 0.75 + (k % cols) * 1.5, z - d/2 + 0.75 + (k // cols) * 1.5)`.
   Request: either state that rule in the contract or have layouts always carry explicit `slots`. If the simulator uses a
   different grid, patients will be drawn beside their beds rather than on them. Code: `slotsOf` in
   `web/components/scene/build.ts`.

2. **Catalog references for people.** Rooms and equipment carry `catalog_ref`; snapshots carry none for patients or staff.
   Assumed: staff resolve to `staff/<role key>` (e.g. `staff/rn`) and patients to `patient/esi<acuity>` (the variants in
   `catalog/patient.yaml`). Request: confirm, or add the refs to the header / the `/api/runs/...` responses
   (`catalog_refs` is already listed there; the inspector does not read it yet).

3. **Which rollout belongs to which manager.** The trade-off chart needs to open Watch / Compare for a clicked manager. It
   matches `results.rows[].manager_id` to `rollouts[].manager.id` (preferring the same scenario). No contract change
   needed if those ids agree.

4. **Hourly messages on a live run.** The app treats the `hour` message at tick `t` as describing the hour that ended at
   `t`, and appends its metrics to the run's hourly series in arrival order.

5. **Human run posted on stop.** After sending `{"type":"stop"}` the app waits about 0.6 s for the final `summary` message
   and then POSTs `{label: "You", scenario, seed, days, summary}` to `/api/results/human`. If no summary has arrived it
   computes one from the hourly series using the `episode_summary` formulas it can (`wait_mean_min`, `lwbs_rate`,
   `cost_per_day`, `margin_per_day`, `cost_per_treated`).
