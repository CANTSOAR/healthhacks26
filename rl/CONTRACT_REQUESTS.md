# Contract change requests from rl/

1. **`metrics.yaml` `reward_terms`: add `labor`** — `{metric: cost_labor, scale_note: "per-hour labour cost (wages, overtime,
   agency) / baseline"}`. Fixed and per-patient costs are about 87% of `cost_total` and are not controllable by the
   manager, so "minimise cost" needs a controllable-cost term. Implemented now as an rl-side extension: the reward-weight
   vector appended to the observation has 8 entries (the 7 contract terms in order, then `labor`), and `reward_weights`
   objects may carry a `labor` key.
2. **`metrics.yaml` `episode_summary`: add `labor_cost_per_day`** (`sum(cost_labor)/days`). `rl/evaluate.py` and
   `rl/record.py` already emit it (as an extra metric in results rows and an extra key in rollout header `summary`).
3. **`/api/managers` rows: optional `note` (how the manager was produced), `heldout_verdict` (learned managers: held-out
   verdict against the tuned heuristic) and `weight_conditioned`.** `rl.list_managers()` returns them; results rows carry
   `note`, `verdict_vs_tuned_heuristic`, `stale`; rollout header `manager` carries `note` and `heldout_verdict`.
4. **`Policy.set_weights(dict)`** on the weight-conditioned learned manager (`ppo_cond`) for a live slider.
5. **Staleness fields:** every artefact carries `sim_behaviour_fingerprint` (trajectory hash) next to `sim_fingerprint` (file hash).

## Requests from the per-hospital / operator-objective work (worked around in rl/, nothing in sim/ edited)

6. **One scenario configuration per simulator.** Ensemble members differ in catalog overrides, so each member needs its own
   `HospitalSim`, and a simulator tick costs the same wall time for 64 or 1,024 hospitals. Request: per-row parameter tensors
   (at least for the calibrated attributes) so one batch can hold many ensemble members. Workaround: `rl/rollout.py` runs one
   group (member x scenario) per worker process; PPO keeps a few member slots per scenario and redraws them each episode.
7. **Episode sums the gym needs are read from `sim.ep` / `sim.exits`** (labour, fixed cost, adverse events, transfers out).
   Request: add to `episode_summary` — `labor_cost_per_day`, `fixed_cost_per_day`, `adverse_events_per_day`, `transfers_per_day`,
   `ed_los_mean_min`, `treated_per_day`.
8. **No per-acuity waiting metric.** The safety constraint "high-acuity patients do not wait longer" is computed from the
   observation entry `waiting_esi12` (end-of-hour census x 10). Request: step metrics `waiting_patient_minutes_esi12` and
   door-to-provider sums by acuity.
9. **`reward_terms` extensions:** `los` (`ed_census`, the dense proxy of ED length of stay) and `opcost` (`cost_labor + cost_fixed`).
   The weight vector appended to the observation now has 10 entries; networks trained with 8 still load.
10. **`Policy.reset(B, device, defaults=None)`** — optional per-row baseline actions (they differ between ensemble members).
    `server/` calls `reset(B, device)` and is unaffected.
