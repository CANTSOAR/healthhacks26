# rl/ — managers for HospitalGym (all numbers simulated)

## Per hospital: one command, one headline

```bash
bash rl/scripts/run_hospital.sh <hospital_id>          # rwjuh_nb | mount_sinai | mayo_rochester | any catalog/hospitals/<id>.yaml
#  sync -> measure scales -> tune the operator heuristics -> PPO on the operator objectives (PPO_HOURS each, default 0.9; 0 = skip)
#  -> headline (select on validation seeds, evaluate held-out over the calibration ensemble) -> results table
#  -> record a baseline rollout and the selected policy's rollout -> pull.   Runs on deepstack in tmux window hospitalgym:rl_<id>.
#  Env: PPO_HOURS, LEGACY=1 (also retune the five legacy weighted heuristics), RECORD_ALL=1, SKIP_TUNE=1, GPU_WORKERS, CPU_WORKERS,
#       TUNE_ARGS, PPO_ARGS, HEADLINE_ARGS, NOWAIT=1 (start and return).
```

Output: `rl/hospitals/<id>/HEADLINE.md` + `headline.json` (+ `headline_raw.json`, per member x seed values). The report gives, per
operator objective, the selected policy's held-out change against the hospital's calibrated baseline with 95% intervals, the hard
feasibility check, the share of calibration-ensemble members in which it holds (and the worst one), the same under a flu surge and
three stress scenarios, an annualised translation on the hospital's CMS-reported volume, what the policy does differently in
operational terms, every other candidate (losses and infeasible ones included), whether PPO beat the tuned heuristic, and caveats.
**Without `catalog/hospitals/<id>.calibration.yaml` the report is stamped "UNCALIBRATED PIPELINE SMOKE RUN — NOT A HEADLINE"
(`publishable: false`).**

Hospital selection everywhere: `--hospital <id>` / `hospital=` argument > `HOSPITAL_ID` environment variable > `rwjuh_nb`
(`common.hospital_id`, same order as `sim.load_scenario`). `load_manager(id, device, hospital=)`, `list_managers(hospital=)`,
`rl.evaluate`, `rl.record`, `rl.tune`, `rl.ppo`, `rl.headline`, `rl.scripts.measure_scales`, `rl.scripts.install_policies` all take it.

Where artefacts live (`common.paths(hospital)`): the default hospital (`rwjuh_nb`) keeps `rl/policies/`, `rl/results/`,
`rl/rollouts/`, `rl/reward_scales.json` because the server and the web app read those; every other hospital uses
`rl/hospitals/<id>/{policies,results,rollouts,reward_scales.json}`. Headline files are under `rl/hospitals/<id>/` for all hospitals.
A policy file carries `hospital_id` and is never offered to another hospital.

Baseline: `fixed` plays the action heads' defaults. With a calibration file those are the calibration's `baseline_actions` (the
hospital's reconstructed current practice); every comparison in the headline is against it, on the same seeds, in the same ensemble
member. `Policy.reset(B, device, defaults)` binds per-row baseline actions, because they differ between ensemble members.

Ensemble: `common.load_ensemble(hospital)` reads `catalog/hospitals/<id>.ensemble.json` when it exists (else one member, the point
calibration); `HospitalEnv(..., hospital=, member=i)` builds member i; a `ConcatEnv` over members is the domain-randomised
environment (`ConcatEnv.replace` redraws a member). One simulator holds one parameter set, so `rl/rollout.py` runs one GROUP
(member x scenario; every policy x every seed in one batch, common random numbers) per worker process, GPU and CPU.

### Operator objectives (`rl/objectives.py`)

| objective | minimises | subject to (against the baseline, same seeds, same member) |
|---|---|---|
| `same_budget_better_flow` | flow index = 0.3 mean door-to-provider wait + 0.3 median ED length of stay + 0.2 LWBS rate + 0.2 boarding hours, each as policy / baseline | labour cost <= baseline; labour + fixed staffed-space cost <= baseline; deaths per 10k, adverse events and ESI 1-2 waiting hours <= baseline; diversion hours <= baseline; overtime <= baseline + 1% of staff-hours; transfers out <= baseline + 2% |
| `same_service_lower_cost` | labour cost | mean and p95 wait, median stay, LWBS rate, boarding all <= baseline; labour + fixed cost <= baseline; the same safety, diversion, overtime and transfer constraints |

What stops gaming: `divert` and `admission_cap` are locked at baseline by the environment (`HospitalEnv(locked_heads=)`) and in the
saved policy, and diversion / transfers are constrained anyway; LWBS is in the flow index and is a constraint of the cost objective;
the budget counts fixed staffed-space cost, so hallway spaces are not free; overtime is inside labour cost and capped; monthly
(structural / capital) heads are outside these objectives (stage 2). Scores use group means (deaths are too rare per episode):
`score = 1 - objective ratio - 10 x sum of weighted relative violations`, with a small head-room margin while tuning. On held-out
data `objectives.feasibility` is a hard check on point estimates with no margin. A selected policy that is infeasible on held-out
data is reported as infeasible, never swapped.

### Optimisers

- `tune.py`: CEM over the 31-parameter rule manager (the 21 original parameters plus weekday-following staffing, demand-following
  triage, anticipatory and late-shift-aware call-in, occupancy call-in, boarding-triggered discharge rounds, queue-driven provider
  split, night fast-track closure; every new parameter defaults to a no-op so 21-parameter files load unchanged). Groups = sampled
  ensemble members x scenarios, baseline rows on the same seeds, robust score = blend of mean and worst quartile over members.
  Operator searches start from the rule that reproduces the hospital's baseline (`tune.baseline_theta`).
- `ppo.py`: for operator objectives a baseline block of rows per sub-environment, one Lagrange multiplier per constraint term
  (updated every rollout from training rows vs baseline rows; they act on the reward only, the observation carries the objective's constant weights), locked heads, sub-environments =
  scenarios x `--members` ensemble slots redrawn each episode, behaviour-cloned from the tuned heuristic.
- `headline.py` decides between them on validation seeds and reports the held-out verdict of PPO against its tuned heuristic.

Seeds: scales 100,000+; tuning 200,000+; PPO training 400,000+; in-training validation 900,000+; headline selection 950,000+;
**held-out evaluation and recording 9,000,000+**.

Staleness: every artefact carries `hospital_id`, `sim_behaviour_fingerprint` (trajectory hash on that hospital's point calibration)
and `calibration_fingerprint` (hash of `<id>.yaml`, `<id>.calibration.yaml`, `<id>.ensemble.json`). `common.is_stale(artefact)` is
true when either differs from the current one; `list_managers()` rows, results rows, rollout headers and the headline flag it.
Re-run `run_hospital.sh <id>` whenever the calibration or ensemble file changes.

Tests: `.venv/bin/python -m pytest rl/tests -q` (about two minutes on the Mac).

## Files

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
| `objectives.py` | operator objectives, constraints, flow index, feasibility check, the per-episode metric list |
| `rollout.py` | group runner (policies x seeds on one member x scenario) and the GPU/CPU process pool |
| `headline.py` | selection, held-out evaluation over the ensemble, bootstrap intervals, `HEADLINE.md` |
| `scripts/run_hospital.sh`, `scripts/remote_hospital.sh` | the per-hospital pipeline (Mac side / deepstack side) |

Recorded seed: 9,000,001.

## Legacy weighted objectives (the web app's Trade-off page)

Objectives (`common.OBJECTIVES`; weights on baseline-normalised terms, reward = -sum of weight x term). They are blunt on
purpose, so each manager visibly does what it was asked:

| objective | weights | meaning |
|---|---|---|
| `min_cost` | labor 1 | lowest controllable cost (wages + overtime + agency); no wait, LWBS or safety term |
| `min_wait` | wait 1, lwbs 0.25 | least waiting and fewest walk-outs; no cost term |
| `max_margin` | cost 1, revenue 1 | revenue minus total cost |
| `balanced` | cost 1, revenue 1, wait 0.5, lwbs 0.25, safety 0.25, boarding 0.1, staff 0.1 | everything together |
| `cost_s.t._p95_wait` | labor 1 + penalty | lowest labour cost subject to episode p95 door-to-provider wait <= 60 min |

`labor`, `los` and `opcost` are rl-side reward terms (see `CONTRACT_REQUESTS.md`); the weight vector in the observation has 10
entries (networks trained with 8 still load).

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

## Marginal value of every resource (`rl/attribution.py`, simulated)

"Point at a doctor, a room or a machine and quantify its effect." For each resource unit the twin is run without one unit and
with one more, on the same held-out seeds as the hospital's calibrated baseline (demand is a random stream independent of
actions and parameters, so the comparison is paired on the same patients):

```bash
python -m rl.attribution --hospital rwjuh_nb --seeds 32 --days 30 --workers 24     # single-thread processes
# -> rl/hospitals/rwjuh_nb/attribution.json + ATTRIBUTION.md   (served at GET /api/attribution/rwjuh_nb)
python -m rl.attribution --hospital rwjuh_nb --manager tuned_same_budget           # under a policy: capacity units only
```

Units: one provider / nurse on each shift (the 5-entry staffing ladder is rebuilt to contain the wanted head-count and the
baseline action indices re-pointed), a triage station, fast track open/closed, hallway spaces and second-CT hours (baseline
actions), a bay of each class, ward beds, a CT scanner and an X-ray room (the `layout_edit` override of `sim.load_scenario`).
Every manipulation is asserted against the counts the simulator uses. Per unit and direction the report holds the paired
difference of every episode metric with a 95% interval, the reward difference for every preset plus the per-seed term
differences (so any weight vector can be re-scored without re-simulating), the money translation (margin per day and year
against what the unit costs), the profile by day and by hour of day, utilisation, and a verdict that follows the intervals.
Providers of a role and bays of a class are interchangeable in the model, and the report says so instead of inventing
per-individual differences. Finished runs are checkpointed under `runs/attribution/` and reused.
