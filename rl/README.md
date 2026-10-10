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

Objectives (weights on baseline-normalised terms, `common.OBJECTIVES`): `min_cost`, `min_wait`, `balanced`
(margin + wait + LWBS + safety + boarding + staff), `cost_s.t._p95_wait` (cost with a penalty when the episode
p95 wait exceeds the threshold in `reward_scales.json`).

Every artefact carries `sim_fingerprint` (hash of `sim/*.py`, `sim/scenarios/*.yaml`, `catalog/**/*.yaml`);
compare it with `python -c "from rl.common import sim_fingerprint; print(sim_fingerprint())"` to spot stale files.

## Regenerate (deepstack does the work; run from the Mac)

```bash
bash rl/scripts/refresh_all.sh          # sync, re-evaluate + re-record every available manager, pull (~10 min)
# full rebuild after a simulator change:
bash rl/scripts/sync.sh
ssh deepstack 'tmux new-window -d -t hospitalgym -n rl_tune "REMEASURE=1 bash ~/projects/hospitalgym_aryan/rl/scripts/remote_tune.sh"'   # scales + 4 tuned heuristics, ~25 min
ssh deepstack 'tmux new-window -d -t hospitalgym -n rl_ppo "HOURS=2.5 bash ~/projects/hospitalgym_aryan/rl/scripts/remote_train.sh"'      # 4 PPO runs
bash rl/scripts/refresh_all.sh
```

Tests: `.venv/bin/python -m pytest rl/tests -q` (about a minute on the Mac).
