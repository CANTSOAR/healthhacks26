# Contract requests from `web/`

Nothing here blocks the web app; each item says what the app assumes today.

1. **Where patients sit or lie inside a room.** `layout.schema.json` says positions are `slots` when given, "otherwise a grid
   inside the rectangle", without defining the grid. The scene draws beds and chairs where patients will be, so it needs
   the simulator's rule. Two rules exist today: the simulator (`sim/layoutmodel.py`) uses `cols = ceil(sqrt(capacity * w / d))`,
   `rows = ceil(capacity / cols)` with one slot at the centre of each cell; the contract fixture
   (`contracts/fixtures/make_fixture.py`) uses a 1.5 m grid from the north-west corner. The web app follows the simulator's
   rule and falls back to the fixture's only for `hospital_id == "fixture"` (`slotsOf` in `web/components/scene/build.ts`).
   Request: write the simulator's rule into the contract (or always emit `slots`) and regenerate the fixture with it.

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

6. **Server additions the app now relies on** (from `server/CONTRACT_REQUESTS.md`; worth adding to `api.md`): `hour` messages
   with `ack: true` and empty `metrics` (ignored for charts), `summary.final` after `stop` (awaited before the human run is
   posted), `action_spec[].implemented` (shown as "not modelled yet" when false), `/api/validation.status`, `.baseline`
   and `.stale`, and per-target `unit`, `variant_label`, `attribute`, `citation`.

7. **More server extras the app reads** (round 2): `hour.manager` and `hour.manager_info` (who is in charge, shown in Play
   and used to confirm a hand-over), and the `scenario`, `structural_started` and `structural_done` event kinds (shown as
   toasts). Worth documenting in `api.md`.

8. **Which patient holds a bay.** `rooms.status` reports a bay as occupied while its patient is away at imaging, and
   `rooms.occupancy` counts only people physically present, so the two disagree for held bays. The app shows "Held" and
   infers the patient from the journey it has observed. A `patients.bay` column (room index of the held bay, -1 if none)
   would make that exact.

9. **Human run length.** The app posts `days` as a fraction (for example 0.375 for a nine-hour run) so the trade-off chart
   can flag runs shorter than the evaluation protocol.

10. **Round 3, now relied on** (all implemented by the server; listed so `api.md` can catch up): websocket `attach`
    (`header.attached`, `speed`, `paused`; errors with `code: run_gone | detached`), `hour.playable`,
    `GET /api/runs/{run_id}/playable`, `playable` / `playable_reason` on the patient route,
    `DELETE /api/runs/{run_id}/patients/{id}/hold`, `write_back: {status, detail}` on finish and on the encounter state,
    and `results.comparisons[].verdict`.

11. **Still inferred by the app:** which patient holds a bay (item 8), and how a learned manager was trained: no
    `note` / `training` / `description` field is on `/api/managers` or the result rows yet, so only the held-out verdict
    is shown.
