# sim/ — HospitalGym simulator

Batched, tensorised, 5-minute-tick simulation of an ED plus a downstream ward pool. API: `contracts/sim_api.md`.

```python
from sim import HospitalSim, load_scenario, list_scenarios
sim = HospitalSim(load_scenario("normal_week"), batch_size=4, device="cpu", seed=0)   # scenario id string also accepted
for hour in range(24):
    metrics = sim.step(sim.default_actions())      # dict[str, FloatTensor[B]], every key of contracts/metrics.yaml
obs, mask = sim.observe(), sim.action_mask()        # [B, sim.obs_dim], dict[str, BoolTensor[B]]
snap, layout = sim.snapshot(0), sim.layout(0)       # validate against contracts/*.schema.json
summary = sim.episode_summary()                     # dict[str, FloatTensor[B]]
```

- Parameters come from `catalog/*.yaml` (+ `sim/scenarios/_defaults.yaml` for engine sizing and assumed fallbacks; `scn.fallback_keys` lists what was taken from there).
- `reset(seed)`: int seed s gives hospital b the stream of seed s+b; a LongTensor[B] sets each hospital's seed directly. Same seed => same patients under any actions.
- Extras beyond the contract: `sim.conservation()`, `sim.episode_means()`, `sim.release_hold(b, pid)`, `sim.invalid_actions`, `sim.exits[B,7]`.
- Tests: `.venv/bin/python -m pytest sim/tests -q`. Benchmark: `.venv/bin/python -m sim.bench`. Numbers: `BENCHMARK.md`, `BASELINE.md`.
