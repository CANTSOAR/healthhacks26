# Contracts

Shared formats between `sim/`, `rl/`, `twin/`, `server/`, `web/` and `catalog/`.
Only the orchestrator edits this directory. If you need a change, write it to
`<your-dir>/CONTRACT_REQUESTS.md`, proceed with your proposed shape, and report it.

| File | What it fixes |
|---|---|
| `enums.yaml` | Patient states, exits, staff roles and states, room types, room status, acuity, condition groups, arrival modes, age bands, payers, source tags, provenance tags |
| `snapshot.schema.json` | One simulator snapshot (struct-of-arrays) |
| `layout.schema.json` | Hospital layout: rooms, equipment, roads; provenance per room |
| `rollout.schema.json` | A recorded rollout: header, hourly metrics, decisions, snapshot segments |
| `metrics.yaml` | Every metric, defined once: unit, denominator, window |
| `actions.yaml` | Factored action heads, cadence, options, defaults |
| `interaction.schema.json` | Interaction declaration, latent truth, interaction result (sampled from the catalog; the `played` resolver value is unused by this repository) |
| `catalog.schema.json` | Shape of every `catalog/*.yaml` file |
| `sim_api.md` | Python API of the simulator that `rl/` and `server/` call |
| `api.md` | HTTP and websocket API that `web/` calls |
| `fixtures/` | `make_fixture.py` builds `layout.fixture.json` and `rollout.fixture.json`, both validated against the schemas; `optimize_status.fixture.json` and `optimize_result.fixture.json` are example answers of `GET /api/optimize/{job_id}` |

Conventions

- Time: one tick = 5 simulated minutes. `t` is the tick index from episode start (tick 0 = day 0, 00:00, a Monday). One environment step = 12 ticks = 1 hour.
- Space: metres. `x` east, `z` south, origin at the north-west corner of the site. Rooms are axis-aligned rectangles given by centre `x,z` and size `w` (along x), `d` (along z).
- Snapshots are struct-of-arrays: each column is an array of equal length. Enum columns hold integer indices into the lists in `enums.yaml` (copied into every rollout header as `enums` so a rollout is self-describing).
- Entity IDs: patients are integers unique within an episode (`P-000123` when displayed); staff are strings `ROLE-NN` (`RN-07`, `MD-02`); rooms and equipment are layout string IDs (`bay-014`, `ct-1`). Fact IDs are strings `f.<category>.<slug>`; objective IDs `obj.<slug>`.
- Money: US dollars. Synthetic and assumed numbers are labelled wherever shown.
- No language model produces or alters a simulation number.
