# sim/ - HospitalGym simulator

Batched, tensorised, 5-minute-tick simulation of an ED plus a downstream ward pool. API: `contracts/sim_api.md`.

```python
from sim import HospitalSim, load_scenario, list_scenarios
sim = HospitalSim(load_scenario("normal_week"), batch_size=4, device="cpu", seed=0)   # a scenario id string also works
for hour in range(24):
    metrics = sim.step(sim.default_actions())      # every key of contracts/metrics.yaml, then `waiting_patient_minutes`
obs, mask = sim.observe(), sim.action_mask()        # [B, sim.obs_dim = 80], dict[str, BoolTensor[B]]
snap, layout = sim.snapshot(0), sim.layout(0)       # validate against contracts/*.schema.json
summary = sim.episode_summary()
```

- Parameters come from `catalog/*.yaml`; `sim/scenarios/_defaults.yaml` holds engine sizing and a fallback copy of the sim-owned assumed attributes (`scn.fallback_keys` lists any actually taken from there; normally empty).
- Seeds: `reset(s)` with an int gives hospital b the stream of seed s+b; a LongTensor[B] sets each hospital's seed. Same seed means the same arrivals, patients, call-outs and failures under any actions. The exogenous hourly series is `arrivals + diverted`.
- Files: `engine.py` (tick path), `config.py` (catalog -> numbers), `layoutmodel.py`, `viewer.py` (snapshot, layout, detail), `interact.py` (latent truth, hold, played write-back), `rng.py` (stateless hash RNG), `bench.py`.
- Additive API beyond the contract: `step()` also returns `waiting_patient_minutes`; `snapshot(b, consume=False)`; `patient_detail(b, pid, public=True)`; `apply_interaction_result(b, result, defer=True)` (result arrives before the encounter starts); `inject_event(b, type, **params)`; `release_hold(b, pid)`; `conservation()`; `episode_means()`; `sim.invalid_actions`, `sim.exits[B,7]`, `sim.pool_overflow`.
- Event and decision logs (and last-known records of departed patients) exist only for B <= 8.
- Tests: `.venv/bin/python -m pytest sim/tests -q` (about 90-110 s locally). Numbers: `BASELINE.md`, `BENCHMARK.md`.

Model notes and what is simplified: see the docstrings in `engine.py`, `action_spec()[i]["note"]`, and the "Known limits" in `BASELINE.md`.
Not modelled: staff turnover, MRI/ultrasound, results-waiting area, a dedicated fast-track nurse (the nurse budget is ED-wide), per-hospital scenarios or clocks inside one batch, triage-initiated imaging (so `relocate=triage_next_to_imaging` only changes a walking distance).

## Round 2 additions (dynamics frozen at M2)

- `sim/tests/test_golden.py` + `sim/tests/golden_trajectories.json`: hashes of every step metric for normal_week / flu_surge, seeds 0 and 123, 5 days, default and fixed pseudo-random hourly+daily actions. One CPU golden (identical on Mac torch 2.2.2 and deepstack torch 2.8.0) and one CUDA golden (same discrete trajectory, float sums differ in the last bits). Regenerate only for an announced change: `python -m sim.tests.golden --write [--cuda]`.
- `python -m sim.scripts.baseline --days 60 [--batch 16] [--write]` regenerates `BASELINE.md` (`--from-json sim/scripts/baseline_60d.json --write` re-renders the saved deepstack run). `python -m sim.scripts.long_run` is the long-horizon structural run.
- `patient_detail` returns the last-known record of a patient who has left (`state: exited`, `in_hospital: false`, `exit_t`, interaction log) for B <= 8, last 5,000 per hospital; `latent_truth` / `known_state` still raise `KeyError` after exit.
- Snapshot: `staff.name` (fictional, from `sim/scenarios/_staff_names.yaml`, cosmetic), `patients.bay` (room index of the held treatment space), ward and scanner rooms never show more patients than their capacity (sticky bed / room assignment).
- `reset(seed, start_day=k)` or engine setting `start_day`: calendar day of tick 0 (weekday and seasonal profiles only; cadence boundaries stay on the episode clock).
- `apply_interaction_result(b, result, defer=True)` accepts any patient who has not started the encounter; `release_hold` also discards a stored early result; `cancel_deferred_result(b, pid)` is the public cancel for a queued result.
- Slow test (120 simulated days of structural actions): `SIM_SLOW=1 .venv/bin/python -m pytest sim/tests -q -k structural_actions_120`.
