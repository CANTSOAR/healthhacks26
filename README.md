# HospitalGym

Rutgers Health Hack 2026 · TwinVerse track

One hospital, simulated at two fidelities.

- **Statistical.** Every interaction (a triage, a clinician seeing a patient, a scan, a handoff) is resolved by sampling from a data catalog. This is fast enough to run thousands of hospitals in parallel, which is what the managers are tuned and trained on. Run by hand, it is a strategy game.
- **Played.** Any clinician–patient encounter can be opened and played by a person, with a simulated patient on the other side who discloses only what the case allows. The result (how long it took, what was found, what was decided, how well) is written back into the same fields the sampler would have filled, so the patient you interview is the patient occupying the bed.

The played encounter is the TwinVerse Challenge 1 system (Patient Studio, split-screen encounter, explainable feedback). The connected care journey is a first cut at Challenge 2.

> **This is a model built from public information.** It is not affiliated with or endorsed by Robert Wood Johnson University Hospital. Patient flows, staffing, costs and outcomes are simulated, not the hospital's operational data. Staff and patients are fictional. Clinical cases are synthetic and need faculty review. Every number the app shows is simulated.

The overnight build log is in [overnight/STATUS.md](overnight/STATUS.md), the morning summary in [overnight/MORNING_REPORT.md](overnight/MORNING_REPORT.md), and an independent defect list in [overnight/QA_REPORT.md](overnight/QA_REPORT.md).

## Run it

Requirements: Python 3.12, Node 22, pnpm 10. On an Intel Mac, PyTorch stops at 2.2.2 and needs `numpy<2` (pinned in `requirements.txt`).

```bash
# once
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
pnpm --dir web install

# two commands, two terminals
./run_server.sh     # FastAPI on http://localhost:8000
./run_web.sh        # Next.js on http://localhost:3000
```

Open http://localhost:3000.

| Page | What it is |
|---|---|
| `/` | The 3D hospital: Play, Watch, Compare, Trade-off, and the inspector |
| `/encounter` | Student encounter: conversation left, progressively revealed chart right, feedback at the end |
| `/studio` | Patient Studio: create, validate, approve and publish a patient with no code |
| `/journey` | Connected care journey: triage → clinician → medication reconciliation → SBAR handoff on one shared record |

If the API is unreachable the web app falls back to hand-built fixture data and says so.

Tests:

```bash
.venv/bin/python -m pytest sim/tests -q                                             # simulator
.venv/bin/python -m pytest encounter/tests encounter/journey/tests server/tests -q  # encounter, journey, server
.venv/bin/python -m pytest rl/tests data/adapters -q                                # RL wrappers, data adapters
pnpm --dir web build                                                                # type-check and build (stop the dev server first)
```

## What is in the app

**Play.** You are the manager. Twenty-two decisions at four cadences (hourly, daily, weekly, monthly) drive a live simulation: staffing per shift, priority rule, overflow bays, diversion, call-ins, fast track, agency contracts, imaging hours, and structural changes (add or remove bays and ward beds, buy a scanner) that take weeks to build and cost money. You can inject a flu surge, a mass-casualty incident, a CT outage or nursing call-outs, and hand the hospital to any manager and take it back.

**Watch.** Replay a manager's recorded 30-day run with its decisions surfaced as they happen.

**Compare.** Two managers side by side on the same seed. Demand comes from a random stream that does not depend on the manager's actions, so both face exactly the same patients.

**Trade-off.** Every evaluated manager plotted on cost against wait, with confidence intervals from held-out seeds, plus a validation card comparing the default-policy simulation with public benchmarks.

**Inspector.** Click any patient, staff member, bay, room or machine: its live state, then its catalog definition — every attribute with its value or distribution, unit, and a source tag (`measured`, `literature`, `assumed`) with the citation. Rooms also carry a layout provenance tag (`surveyed`, `published`, `inferred`).

**Encounter.** Select a patient who has not yet been seen and play the clinician. The case is generated from that simulated patient's hidden truth and the condition template. The patient withholds or misreports only as the case defines and never invents a clinical fact; a disclosure ledger records what was unlocked, by which question, under which rule. Feedback is per learning objective (met, partly demonstrated, not observed, not assessable) with quoted transcript evidence.

Managers are labelled by kind everywhere: `fixed`, `rule_based`, `random`, `tuned_heuristic` (a rule-based manager whose parameters were found by evolutionary search — not a learned agent), `learned` (PPO), `human`.

## Architecture

```
 web/        Next.js + React Three Fiber
             3D hospital · knobs · charts · inspector · encounter · studio · journey
               │  HTTP + websocket (contracts/api.md)
               ▼
 server/     FastAPI: live simulation per websocket, run registry, catalog,
             rollouts, results, validation; mounts the encounter and journey routers
               │                                   │
               ▼                                   ▼
 sim/        Batched simulator on PyTorch       encounter/   cases as data, disclosure engine,
             tensors (CPU batch of 1 for the                 offline patient, grader, provider
             viewer, GPU batch of thousands                  adapters, played resolver, journey
             for training)                                     │
               │                                               │ interaction result (same four fields)
               ▼                                               ▼
 rl/         Gym wrapper, baselines, evolutionary tuner, PPO, held-out evaluation, recorded rollouts
 catalog/    Every entity type, variant and attribute with its source; hospital layouts
 data/       Fetch scripts, small processed extracts, data-service adapters
 contracts/  Schemas and API shared by all of the above
```

- **Contracts** ([contracts/](contracts/)) fix the snapshot, layout, rollout, metric, action, interaction, case and catalog formats, the simulator's Python API and the HTTP/websocket API.
- **The interaction contract.** Each interaction type declares inputs and four fixed outputs: duration, information gained, decision, quality. A sampler always exists; a played resolver is optional. The clinician encounter has both.
- **No language model produces or alters a simulation number.** The model, when configured, words the patient's reply; the disclosure engine decides which facts are available.

## What is real and what is not

| Thing | Status |
|---|---|
| Catalog | 348 attributes: 85 measured from public datasets (NHAMCS ED 2019–2022, CMS Care Compare, Provider of Services, cost reports, IPPS/OPPS, BLS OEWS, ILINet), 29 from literature, 234 assumed. The source tag is on every attribute and shown in the inspector. See [data/README.md](data/README.md) and [research/operations-data-sources.md](research/operations-data-sources.md). |
| Hospital layout | Reconstructed. Site outline and roads from OpenStreetMap (© OpenStreetMap contributors); room counts and zones the hospital has published; every room position inferred. No real interior plan was found. See [research/hospital-layout-rwjuh.md](research/hospital-layout-rwjuh.md). |
| Validation | The default-policy simulation is compared with CMS and NHAMCS figures on the Trade-off page and in [sim/BASELINE.md](sim/BASELINE.md). Median ED time and LWBS fall inside the published peer ranges; the 90th-percentile wait is too short. |
| Managers | Evaluated on held-out seeds; see [rl/results/RESULTS.md](rl/results/RESULTS.md) for what beats what. |
| Language model | **Offline tonight.** No credentials were set, so the patient answers from authored wording through a topic matcher and the grader is heuristic. Bedrock and Anthropic adapters exist and are tested against faked responses only. |
| Voice | Browser speech synthesis/recognition, implemented but not exercised. ElevenLabs adapter untested against the service. |
| Data service | Public extracts in `data/processed/`. The Vlada adapter has never been called. |
| Clinical content | Authored and synthetic, marked as needing faculty review. |
| Organizer material | Never committed. The sample patients, rubric and clinician profiles are read from `.private/` at run time when present; the app works without them. |

### Going online

Copy `.env.example` to `.env`. A service goes online purely because its credential is present; if a call fails at run time that call falls back to offline and the status indicator shows it.

| Service | Online when | Model / setting |
|---|---|---|
| Language model | AWS credentials resolve (Bedrock), otherwise `ANTHROPIC_API_KEY` | `BEDROCK_MODEL_ID` (default `us.amazon.nova-pro-v1:0`), `ANTHROPIC_MODEL` (default `claude-opus-5-5`) |
| Voice | `ELEVENLABS_API_KEY` | `ELEVENLABS_VOICE_ID` |
| Data service | `VLADA_API_KEY` | — |

## Roadmap

- Run the online language-model path against a real account and measure grounding on a held-out probe set.
- Faculty review of the seed cases and condition templates.
- Close the remaining items in [overnight/QA_REPORT.md](overnight/QA_REPORT.md).
- Longer training for the learned managers; structural decisions over 1000-day episodes; the weight-conditioned manager behind a live slider.
- Calibrate the wait-time tail; model MRI/ultrasound, staff turnover and the results-waiting area.
- Played resolvers for more interaction types with simulator write-back (triage, handoff).
- A real floor plan, traced into the layout file with `surveyed` tags, if the hospital provides one.

## Research

The teammate's research on the challenge, sponsors, clinical-education evidence and data sources is in [research/](research/README.md); start with [research/action-plan.md](research/action-plan.md). The operations-side evidence added during the build is in `research/operations-*.md`, with an independent citation audit in [research/operations-citation-audit.md](research/operations-citation-audit.md).
