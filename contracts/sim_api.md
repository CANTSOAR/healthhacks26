# Simulator Python API (`sim/`)

What `rl/` and `server/` call. Everything is batched over `B` independent hospitals
on one torch device. Works on PyTorch 2.2 (local CPU) and 2.8 (deepstack GPU).

```python
from sim import HospitalSim, load_scenario, list_scenarios

list_scenarios() -> list[dict]          # [{id, label, description, hospital_id, days_default}]
scn = load_scenario("normal_week")      # ScenarioConfig built from catalog/ + sim/scenarios/<id>.yaml
                                        # overrides: load_scenario(id, overrides={"arrival_scale": 1.2})

sim = HospitalSim(scn, batch_size=B, device="cpu", seed=0)
sim.reset(seed: int | LongTensor[B] | None = None) -> None

# ---- constants / specs
sim.B, sim.device, sim.tick_minutes (=5), sim.ticks_per_step (=12)
sim.t                                   # LongTensor[B] current tick (all equal unless envs auto-reset)
sim.action_spec() -> list[dict]         # contracts/actions.yaml heads, each with:
                                        #   name, cadence, options[list[str]], default[int], desc,
                                        #   values[list]  concrete quantity per option (e.g. nurses on shift)
sim.metric_names() -> list[str]         # keys of contracts/metrics.yaml in a fixed order
sim.obs_dim -> int
sim.enums -> dict                       # contracts/enums.yaml

# ---- stepping
sim.default_actions() -> dict[str, LongTensor[B]]
sim.action_mask() -> dict[str, BoolTensor[B]]     # True where the head is at its cadence boundary now
sim.step(actions: dict[str, LongTensor[B]]) -> dict[str, FloatTensor[B]]
        # advance 1 hour (12 ticks); returns this hour's metrics (all keys of metrics.yaml).
        # Missing heads keep their current setting. Out-of-range or masked values are
        # rejected by rule: ignored, counted in sim.invalid_actions[B].
sim.tick(actions: dict | None = None) -> None     # advance one 5-minute tick (viewer granularity).
        # actions are applied only on ticks that start an hour; step() == 12 x tick().
sim.metrics_last_hour() -> dict[str, FloatTensor[B]]
sim.observe() -> FloatTensor[B, obs_dim]          # normalised; does NOT include reward weights (rl/ appends them)
sim.obs_names() -> list[str]

# ---- viewer / recording (one hospital from the batch; plain python types, JSON-serialisable)
sim.layout(b=0) -> dict                 # contracts/layout.schema.json (reflects structural changes)
sim.snapshot(b=0) -> dict               # contracts/snapshot.schema.json
sim.episode_summary() -> dict[str, FloatTensor[B]]   # metrics.yaml episode_summary since reset

# ---- entities and the interaction contract
sim.patient_detail(b, patient_id) -> dict          # live state + history of interactions + catalog refs
sim.staff_detail(b, staff_id) -> dict
sim.latent_truth(b, patient_id) -> dict            # interaction.schema.json#/$defs/latent_truth
sim.known_state(b, patient_id) -> dict             # interaction.schema.json#/$defs/known_state
sim.pending_interaction(b, patient_id) -> dict | None
        # the interaction this patient is in or waiting for, with participants; None if not playable now
sim.hold_for_play(b, patient_id) -> bool           # freeze the sampler for this patient's clinician_encounter
sim.apply_interaction_result(b, result: dict) -> None
        # interaction.schema.json#/$defs/result with resolver="played": writes duration, information
        # gained, decision and quality into the same fields the sampler would have filled
sim.interaction_log(b, patient_id=None) -> list[dict]   # results (sampled and played) for the viewer

# ---- determinism
# Same scenario + seed + device + action sequence => identical trajectory.
# Common random numbers: arrivals, patient attributes and latent truth, staff call-outs
# and equipment failures come from an exogenous stream keyed by (seed, hospital, tick or
# patient index) that never depends on actions. Two managers on one seed face the same patients.
```

Scenario ids shipped: `normal_week`, `flu_surge`, `nursing_absences`, `imaging_outage`,
`discharge_delays`, plus `mmc_validation` (plain M/M/c queue used by the tests).
Hospital ids: `rwjuh_nb` (primary), `community_small`, `midsize` (if time allows).

Policy interface (`rl/`), shared by baselines, tuned heuristics and learned agents:

```python
class Policy:
    id: str; kind: str; label: str; objective: str | None   # kind is one of enums.manager_kind
    def reset(self, B: int, device) -> None
    def act(self, obs: FloatTensor[B, D], mask: dict[str, BoolTensor[B]], sim=None) -> dict[str, LongTensor[B]]

from rl import load_manager, list_managers
list_managers() -> list[dict]   # [{id, kind, label, objective, reward_weights, available: bool}]
load_manager(id, device="cpu") -> Policy
```
