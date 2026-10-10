# rl/ — managers for HospitalGym (all numbers simulated)

| File | What |
|---|---|
| `env.py` | `HospitalEnv` (batched, GPU end to end, 1 step = 1 h, obs = `sim.observe()` ++ 7 reward weights, factored masked heads, curriculum stages) and `ConcatEnv` (several scenarios in one batch) |
| `managers.py` | `Policy` interface; `fixed`, `rule_based`, `random`; the 21-parameter rule manager; `LearnedPolicy`; `list_managers()` / `load_manager()` (re-exported by `rl/__init__.py`) |
| `tune.py` | cross-entropy-method tuner for the rule manager -> **tuned heuristics** (kind `tuned_heuristic`, not learned) |
| `ppo.py`, `net.py` | PPO written here (factored categorical heads, masks, GAE, value + observation normalisation, behaviour-cloning warm start, Lagrangian weight for the constrained objective) -> kind `learned` |
| `evaluate.py` | held-out evaluation -> `results/results.json` (`/api/results` shape), `results/RESULTS.md`, `results/eval_raw.json` |
| `record.py` | rollouts for the viewer -> `rollouts/<id>.json.gz` + `rollouts/index.json` (`/api/rollouts` shape), schema-validated |
| `reward_scales.json` | baseline scales of the reward terms + the p95-wait threshold (measured by `scripts/measure_scales.py`) |
| `policies/` | one JSON per saved manager (+ `.pt` plain state_dict for learned ones) |
| `SIM_ISSUES.md` | simulator problems met and the workarounds |

Seeds: scales 100,000+; tuning 200,000+; PPO training 400,000+; in-training validation 900,000+;
**held-out evaluation and recording 9,000,000+** (recorded seed 9,000,001).

Objectives (`common.OBJECTIVES`; weights on baseline-normalised terms, reward = -sum of weight x term). They are blunt on
purpose, so each manager visibly does what it was asked:

| objective | weights | meaning |
|---|---|---|
| `min_cost` | labor 1 | lowest controllable cost (wages + overtime + agency); no wait, LWBS or safety term |
| `min_wait` | wait 1, lwbs 0.25 | least waiting and fewest walk-outs; no cost term |
| `max_margin` | cost 1, revenue 1 | revenue minus total cost |
| `balanced` | cost 1, revenue 1, wait 0.5, lwbs 0.25, safety 0.25, boarding 0.1, staff 0.1 | everything together |
| `cost_s.t._p95_wait` | labor 1 + penalty | lowest labour cost subject to episode p95 door-to-provider wait <= 60 min |

`labor` is an rl-side eighth reward term (see `CONTRACT_REQUESTS.md`); the weight vector in the observation has 8 entries.

Managers: `fixed`, `rule_based`, `random`; `tuned_<objective>` (tuned heuristics); `ppo_<objective>` (PPO, behaviour-cloned
from the tuned heuristic of the same objective, then fine-tuned); `ppo_scratch_min_cost`, `ppo_scratch_min_wait` (PPO with
no cloning); `ppo_cond` (+ `ppo_cond_<objective>` presets). Every learned manager carries a `note` saying how it was made
and a `heldout_verdict` against its tuned heuristic; a cloned agent that only matches its teacher is labelled as matching.

Staleness: every artefact carries `sim_behaviour_fingerprint` — a hash of the simulator's hourly patient counts and
labour cost on a fixed seed under a fixed action script (`common.behaviour_fingerprint()`, identical on the Mac and on
deepstack). It changes only when the dynamics change; retune/retrain only then. `sim_fingerprint` (hash of `sim/*.py`,
`sim/scenarios/*.yaml`, `catalog/**/*.yaml`) is recorded as information only. `results.json` rows carry `stale: true`
for a manager built against a different behaviour.
`python -c "from rl.common import fingerprints; print(fingerprints())"` prints the current pair.

The 60-minute threshold is a service target that binds: the fixed baseline's p95 is 61-63 min, `tuned_min_wait` sits near
24 min and the labour-cost floor far above it.

Weight-conditioned agent: `ppo_cond` (one network, reward weights in the observation; trained on the min_cost /
min_wait / max_margin / balanced presets and random mixtures of them). `load_manager("ppo_cond").set_weights({...})` moves the dial;
`ppo_cond_<objective>` are the same network at the presets.

## Regenerate (deepstack does the work; run from the Mac)

```bash
bash rl/scripts/refresh_all.sh          # sync, install newest exports, re-evaluate + re-record every available manager, pull (~12 min)
bash rl/scripts/status.sh               # what is running on deepstack; each PPO run vs its tuned heuristic (paired validation)
# full rebuild after a simulator change:
bash rl/scripts/sync.sh
ssh deepstack 'tmux new-window -d -t hospitalgym -n rl_regen "HOURS=2.5 bash ~/projects/hospitalgym_aryan/rl/scripts/remote_regen.sh > ~/projects/hospitalgym_aryan/runs/regen_stdout.txt 2>&1"'
#   = stop PPO, archive runs/, re-measure scales, re-tune 5 heuristics (~25 min), start 8 PPO windows, evaluate + record; marker runs/regen_done
bash rl/scripts/refresh_all.sh
```

Tests: `.venv/bin/python -m pytest rl/tests -q` (about a minute on the Mac).
