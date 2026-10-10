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
