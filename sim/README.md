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
- `patient_detail` / `latent_truth` raise `KeyError` once the patient has left (slots are freed one tick after exit). Event and decision logs exist only for B <= 8.
- Tests: `.venv/bin/python -m pytest sim/tests -q` (about 90-110 s locally). Numbers: `BASELINE.md`, `BENCHMARK.md`.

Model notes and what is simplified: see the docstrings in `engine.py`, `action_spec()[i]["note"]`, and the "Known limits" in `BASELINE.md`.
Not modelled: staff turnover, MRI/ultrasound, results-waiting area, a dedicated fast-track nurse (the nurse budget is ED-wide), per-hospital scenarios or clocks inside one batch, triage-initiated imaging (so `relocate=triage_next_to_imaging` only changes a walking distance).
