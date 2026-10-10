# HospitalGym — overnight build handoff

You are the orchestrator for an unattended overnight build. The user is asleep for about 7 hours and will read the result in the morning. Nobody will answer questions, so never ask one: when something is ambiguous, pick the option that best serves the goal below, note the choice in `overnight/STATUS.md`, and keep going.

## What we are building and why

A hackathon project (Rutgers Health Hack 2026, TwinVerse track). Submission is Sunday October 11 at noon EDT, roughly 35 hours after this handoff was written, so tonight is the first long push, not the last. Build foundations properly; the team will keep working on them tomorrow. The submission needs a working prototype, the repository, a demo (video or live), and a four-minute pitch.

**Read the teammate's work first.** `research/` was written by a teammate, Akash, and is already on this branch. It covers the challenge requirements, sponsor resources, clinical-education evidence, data sources, and what is publicly known about the hospital, with a source register. Start from `research/README.md` and `research/action-plan.md`. His plan is an "ER Encounter Studio" for TwinVerse Challenge 1 and treats the operations simulation as later work; the user has decided to build the operations simulation now and treat the encounter as its drill-down, as described next. Akash may be building his encounter studio separately tonight. Use his vocabulary and contracts where he has defined them (fact IDs; faculty truth, patient-known, learner-visible, and rubric kept separate; an event ledger; objective-level results of met, partly demonstrated, not observed, not assessable) so the two efforts can be merged.

**The idea: one hospital, simulated at two fidelities.**

The hospital is a world of entities (patients, staff, spaces, equipment) and the interactions between them (a triage assessment, a doctor seeing a patient, a handoff, a scan, a manager changing the rota).

- **Statistical fidelity.** Every interaction is resolved by sampling: a duration from a distribution, an outcome from a probability table. This is fast, runs thousands of hospitals in parallel, and is what the reinforcement learning manager trains on. Run by hand, it is a strategy game.
- **Played fidelity.** Any single interaction can be opened up and played by a person, with AI on the other side. A student steps into the cardiologist seeing the patient in bay 4, interviews them (the patient may withhold or misreport), reads the chart as it reveals, and is graded. What happened is written back into the same fields the sampler would have filled: how long it took, what was found, what was decided, how well.

So the clinical encounter simulator that the challenge brief asks for, and that the user's teammate is focused on, is the drill-down of the gym, and the manager's seat in the gym is the teammate's "hospital administrator simulation". They are one product. The interaction contract (below) is what keeps them one codebase.

[README.md](README.md) holds the product plan for the gym: dynamics, the multi-timescale action table, metrics, reward design, demo script. Read it first. Where this file and the README disagree, this file wins.

The demo is the measure of success. In the morning the user should be able to run two commands, open a browser, and: watch a 3D hospital run; take it over by hand; hand it to a trained manager; compare managers tuned for different objectives on the same seed; click any entity and see every data point that defines it and where that number came from; click a patient and play the encounter.

## Ground rules

- Locally, work only inside this repository. `docs/` and the resource-pack zip in the repo root are organizer material: read them, never modify them.
- Work on the `aryan` branch, which already exists and is checked out, based on the teammate's `origin/main`. Commit there as you go, in small commits with clear messages. Never commit to or merge into `main`.
- **Do not push, open PRs, or deploy.** The GitHub repository is public. The user will push in the morning after looking.
- Organizer and sponsor material (`docs/`, any `*.zip`, anything you extract from them, including the sample patients, their photos, and the access guides) stays in gitignored paths and is never committed. `.gitignore` already covers `docs/`, `*.zip`, and `.private/`; extract into `.private/`. The app reads such files from there at run time and still works when they are absent. Leave `research/` as the teammate wrote it; add your own findings in new files.
- Do not go looking for credentials, and do not create accounts or cloud resources. If a credential is already present in the environment or in `.env`, the app uses it (see "Online and offline"); you may make a handful of small calls to confirm that path works, and no more.
- Install dependencies only into the project (`.venv`, `node_modules`). No global installs, no `brew install`, no `sudo` anywhere.
- Report honestly. Never state that something works unless you ran it. Never claim a learned manager beats a baseline unless a held-out-seed evaluation shows it. Synthetic and assumed numbers are labeled as such everywhere they appear.
- Cite only sources you actually fetched and read. No invented papers, sample sizes, or DOIs.

## Machines

### Local (where you run): the user's MacBook

- Intel Core i7-8559U, 4 cores / 8 threads, 16 GB RAM, no usable GPU, about 40 GB free disk. macOS.
- Python 3.12.8 at `python3.12`. `pip3` on PATH belongs to Python 3.9; create the environment with `python3.12 -m venv .venv` and use `.venv/bin/python -m pip`.
- Intel macOS wheels for PyTorch stop at 2.2.2, which needs `numpy<2`. Pin both locally.
- Node 22, npm, pnpm 10. Playwright's Python package is installed; install browsers into the project if needed.
- `pdftotext` is absent. Read PDFs with `pypdf`, `.docx` with `textutil -convert txt -stdout <file>`.
- Use it for: editing, the web app, the server, tests, running the simulator for the viewer. Keep downloads here under 2 GB.

### Remote: `ssh deepstack`

Probed at handoff time; confirm before relying on it.

- Linux x86_64, 24 cores, 62 GB RAM, NVIDIA RTX A5500 (16 GB), 429 GB free disk. Idle at the time of the probe.
- Python 3.12.10, `uv`, PyTorch 2.8 with CUDA working, Node 22, git, tmux, internet access.
- Use it for: all training and evaluation, simulator benchmarking, large data downloads and processing (up to 30 GB).
- It is the user's own machine and you may use all of it. Keep your work in one new directory under `~/projects/` (pick a name that does not exist), in your own named tmux session, with your own `uv` environment, and leave the existing directories and tmux sessions as they are.
- Get the code there with `rsync` over ssh (exclude `.venv`, `node_modules`, raw data), since nothing is pushed tonight. Start long jobs inside tmux so they survive a dropped connection, write logs and checkpoints to disk, and poll them. Pull checkpoints, evaluation results, and recorded rollouts back into the repo.
- If deepstack is unreachable, train locally at reduced scale and say so in the report. Nothing else may depend on it.

## How to run the night

Orchestrate with subagents. You own the contracts, the integration, the commits, and the status log; subagents own directories.

- **Contracts first.** Before fanning out, write the shared schemas and a fixture rollout by hand (Wave 0). Parallel work is only safe once the simulator, trainer, server, and web app agree on formats.
- **One owner per directory.** Agents share one working tree. Each brief names the directories the agent may write to. Only you edit `contracts/`; an agent that needs a contract change reports back and you make it.
- **Brief subagents fully.** They know only what you tell them. Point each at this file, the README, the relevant contracts, its directory, what done looks like, and how to verify it.
- **Verify what comes back.** Run the tests and the build yourself before committing an agent's work.
- **Keep `overnight/STATUS.md` current.** Start time, wave, what is done, what is running (host, tmux session, log path), decisions made, known problems. It is your memory across context compaction; re-read it when unsure where things stand.
- **Budget.** About 7 hours. Record the start with `date`. Begin the wrap-up no later than 6 hours in, whatever state things are in. If the core is done early, continue down the stretch list. Training on deepstack may keep running after you finish.
- **When something fails,** diagnose it and fix it or route around it. A blocked workstream never blocks the others.

### Waves

A guide to dependencies, not gates.

**Wave 0 — you, alone.** Read `research/`. Extract `docs/TwinVerse.zip` (the two briefs) and `RU Health Hack 2026 SHP (public).zip` (the organizers' resource pack, described under "Encounter") into `.private/` and read them. Scaffold, `.venv`, first commit on `aryan` (this file and the README are not committed yet). Set up the deepstack directory and environment and confirm a round trip. Write `contracts/` and a small hand-built fixture rollout that conforms, so the web app can start before the simulator exists. Draft the entity catalog skeleton (types, variants, attribute names; values come later).

**Wave 1 — parallel.** Simulator core. Web viewer against the fixture. Research. Data and catalog values. Encounter engine.

**Wave 2 — parallel, needs the simulator.** Gym wrapper, baselines, tuned heuristics, PPO; training starts on deepstack the moment the environment passes its tests and something is always training from then on. Server and play mode. Encounter pages.

**Wave 3.** Watch and compare on recorded rollouts. Trade-off chart. Entity inspector fed by the catalog. Encounter opened from the 3D hospital and written back. Slow structural actions. Stretch items.

## Repository layout

```
contracts/    schemas and fixtures (orchestrator only)
catalog/      entity catalog: every type, variant, attribute, and its source
sim/          simulator core, Python package
rl/           gym environment, baselines, PPO, evaluation, saved policies, rollouts
server/       FastAPI: live simulation over websocket, rollouts, catalog, encounter API
web/          Next.js app
encounter/    case templates, disclosure engine, grader, provider adapters
data/         raw/ (gitignored), processed/, fetch scripts
research/     evidence records
overnight/    STATUS.md, MORNING_REPORT.md, screenshots/
docs/         hackathon material, read-only
```

## The entity catalog (`catalog/`)

The project's claim is that every thing in the hospital is defined by data you can inspect. The catalog is where that is true. It is the single source the simulator, the encounter engine, and the viewer's inspector all read.

One file per entity type. Each lists its variants, and for each variant every attribute with: value or distribution, unit, a source tag (**measured** from a dataset, **literature** with citation, or **assumed** with reasoning), and the link or file it came from. No simulator parameter lives in code.

| Entity | Variants | Attributes to define | Where to look |
|---|---|---|---|
| Patient | Acuity level (5-level triage scale) × condition group × arrival mode × age band × payer | Arrival rate by hour, weekday, season; acuity and condition mix; pathway probabilities between stations; service time per step; tests ordered; admission probability; inpatient length of stay; deterioration hazard while waiting; patience before leaving; revenue per case | CDC's national emergency department survey public-use microdata (arrival hour, triage level, wait, visit length, tests, disposition, payer, age, reason for visit). Medicare inpatient rate tables for payment weight and mean length of stay per diagnosis group. Medicare outpatient rates. CDC influenza surveillance for seasonality. Literature for deterioration and walk-outs. |
| Staff | Attending, resident, nurse practitioner or PA, registered nurse, charge nurse, technician, registration clerk, pharmacist, imaging technologist, transport, cleaning | Wage and overtime rate; shift patterns; patients per hour by acuity; legal or recommended staffing ratios; absence rate; turnover; fatigue effect on speed and error | Bureau of Labor Statistics occupational wage data. Published nurse staffing ratio regulations. Labor-force absence statistics. Literature for productivity, fatigue, turnover. |
| Space | Waiting room, triage room, treatment bay, resuscitation bay, fast track, X-ray, CT, MRI, ultrasound, operating room, recovery, ICU bed, step-down bed, ward bed, lab, pharmacy | Count; staffed vs physical; floor position and area; adjacency and walking time; fixed cost; cleaning and turnaround time; build and relocation cost and duration | CMS Provider of Services file and hospital cost reports for bed counts by unit type and cost by department. Design-guideline figures and literature for areas and turnaround. Layout is authored. |
| Equipment | CT, MRI, X-ray, ultrasound, monitor, ventilator, lab analyzer | Procedure duration; capacity; failure and repair time; purchase and maintenance cost; revenue per use | Medicare outpatient rates for revenue. Literature and manufacturer figures for the rest; expect many to be assumed. |
| Event | Flu wave, mass-casualty incident, staff call-outs, equipment outage, discharge delay | Frequency, size, duration, what it changes | CDC influenza surveillance. Literature. |
| Hospital | Robert Wood Johnson University Hospital, New Brunswick, as the primary; a small community and a mid-size hospital as contrasts if time allows | A complete composition of the above, plus the layout | See "The hospital" below. |
| Clinical condition | One per condition group | Symptoms, history items, exam findings, lab and imaging findings with plausible ranges, typical concealments, learning objectives, rubric | The organizers' sample patients and the datasets their notes link to. Open-access clinical references and guidelines. Authored and synthetic; marked as needing faculty review. |

Staff also come as named individuals: the resource pack includes five fictional clinician profiles for a Rutgers emergency department (role, experience, scope, communication style). Use them as the named staff in the hospital and as the AI colleagues in played interactions.

Also collect, as **validation targets rather than inputs**: Care Compare emergency department measures (median time in department, share who leave without being seen), by hospital size. The simulator's outputs under baseline management should land inside those ranges, and the report should show whether they do.

What public data will not give: one specific hospital's hourly arrivals, rosters, floor plan, or downtime logs. Those are literature-derived or assumed, and the catalog says so line by line. Take extracts, not full national files, into the repo; do heavy processing on deepstack. The hackathon's commercial data service (Vlada, catalog in `docs/`) is mostly repackaged versions of the same public sources; write an adapter with the same interface for it so access can be dropped in.

The table names where to look, not guaranteed URLs or schemas. Find each source, confirm what it actually contains, and record what you found. The teammate's `research/data-acquisition-manifest.json` and `research/data-sources-and-hospital-context.md` list a planned data backlog that has not been run; carry out the parts that feed this catalog.

## The hospital: RWJUH New Brunswick

The user wants the simulated hospital to be Robert Wood Johnson University Hospital in New Brunswick, as close to its real floor plan as public information allows.

**What was found before handoff.** No architectural floor plan of the hospital or its emergency department is published; two searches and the teammate's research agree. What does exist:

- An official campus map PDF and a partial interior map (admitting, lobby, Tower elevators, surgery waiting), both linked in `research/data-sources-and-hospital-context.md`. An older lettered-building campus map is hosted on cinj.org.
- The hospital's emergency department expansion pages: expanded from 40,000 to 60,000 square feet; more than 100 private treatment areas; a separate pediatric emergency department; a fast-track area; radiology inside the department; a new walk-in entrance; an ambulance bay for eight ambulances; phase one added three resuscitation bays, a decontamination area, a care-initiation area, and a results-waiting area; more than 95,000 emergency and trauma patients a year; Level I trauma center.
- Its public description as a 700+ bed adult hospital with a 100+ bed children's hospital.
- Leads not yet opened: a Healthcare Design magazine photo tour of the new emergency department (blocked the fetch tool; try a browser), the project pages of the architects (Francis Cauffman, Array Architects), New Brunswick planning board filings for the expansion, and OpenStreetMap building footprints for the campus.

**What to build.**

- Keep looking for a real plan through those leads, within reason. If you find one, use it and cite it.
- Otherwise reconstruct: exterior footprints and building arrangement from map data and the campus maps; the emergency department interior from the published areas, room counts, named zones, and photos; the rest of the hospital at the level of units and bed counts.
- The layout is a data file, with each room carrying a provenance tag: **surveyed** (from a real plan), **published** (a count or zone the hospital has stated), or **inferred** (placed by you to be consistent with the above). A real plan can then be traced in later without code changes, and the inspector shows the tag.
- Use the published figures as calibration and validation anchors: 95,000 visits a year is about 260 arrivals a day; bed counts and departmental costs come from the federal facility and cost-report data for this hospital.
- In the app, state plainly that this is a model built from public information, not affiliated with or endorsed by the hospital, and that patient flows, staffing, and outcomes are simulated, not the hospital's operational data. Staff are fictional; never use a real clinician's name.

## The interaction contract

Every interaction type in the simulator (triage, clinician encounter, handoff, test, discharge planning, and so on) is declared once with:

- **Inputs:** participants, and the patient's state split into what is true and what is known so far.
- **Outputs:** duration, information gained, decision made, quality of the outcome. Fixed fields, defined in `contracts/`.
- **A sampler:** draws the outputs from catalog distributions. Always present. This is what training uses.
- **Optionally a played resolver:** produces the same outputs from a human-and-AI session.

For this to work, a simulated patient carries a latent truth (condition, severity, the facts a clinician could discover) generated from its condition template at arrival. The sampler uses it to draw outcomes; the played resolver turns it into an encounter case on demand. A patient the student interviews is therefore the same patient occupying the bed.

## Workstreams

### Simulator (`sim/`)

The model described in the README, starting with an emergency department plus a downstream ward (so boarding and discharge delays exist), then imaging, then more.

- Written on PyTorch tensors with a device argument, batched over independent hospitals. The same code runs a batch of one on the local CPU for the viewer and thousands on the deepstack GPU for training. Keep to tensor operations that work on both PyTorch 2.2 and 2.8, and run the test suite on both machines. Do not write a second simplified simulator.
- Time-stepped at a fine tick (about 5 simulated minutes). Deterministic for a given seed and device.
- **Common random numbers.** Demand and other outside randomness (arrivals, patient attributes, call-outs, failures) come from a stream that does not depend on the manager's actions, so two managers given the same seed face exactly the same patients. The compare mode depends on this.
- The simulator alone computes consequences. No language model produces or alters a number.
- Staffed and physical capacity are distinct. Conservation holds: every arrival is waiting, in service, or has left through a defined exit. Invalid actions are rejected by rule.
- All parameters come from the catalog through a scenario config. Ship scenarios: normal week, flu surge, nursing absences, imaging outage, discharge delays.
- Emits snapshots (entity positions included) and per-step metrics conforming to `contracts/`. Each metric is defined once with unit, denominator, and time window.

Verification: stripped to a plain multi-server queue, simulated mean wait matches the analytic M/M/c result within sampling error. Same seed gives the same trajectory. Conservation holds under random actions over long runs. Baseline outputs are compared against the validation targets. Measure throughput in hospital-days per second on both machines, record it, and size training from the measured number.

### RL (`rl/`)

- Gymnasium-style batched environment over the simulator, staying on the GPU end to end. One step is one simulated hour. Factored action heads with masks so slow actions are only available at their boundary.
- Baselines behind the same policy interface: fixed staffing with first-come-first-served; a rule-based manager; random.
- **Tuned heuristics, early.** Parameterize the rule-based manager (staffing by shift, thresholds for opening bays and diverting) and tune it per objective with evolutionary search. It is cheap and reliable, gives compare mode real content within the first hours, and is the bar the learned agents must clear. Label these as tuned heuristics, separate from learned agents.
- PPO written in the repo (the environment is GPU-native, which library trainers handle poorly). Reward is a weighted combination of metrics; the weights are part of the observation.
- Curriculum: 30-day episodes with hourly and daily actions. Then weekly. Then structural actions (add or remove beds, move a bay) with switching costs and build delays, lengthening toward 1000-day episodes.
- Train: minimize cost; minimize wait; balanced; cost subject to 95th-percentile wait under a threshold (a penalty weight that rises while the constraint is violated). Then one weight-conditioned agent with weights resampled per episode, for a live slider.
- Evaluate on held-out seeds against every baseline, under normal and surge scenarios; write means and spread to a results file.
- Record rollouts for the viewer: full snapshots for chosen days, hourly metrics for the whole episode, every structural change. A year of full snapshots is too large for a browser.
- Policies must load and run on the local CPU for watch mode.

### Web app (`web/`)

Next.js, TypeScript, React Three Fiber with drei, Zustand, Tailwind, Inter. The canvas is client-only.

The reference is a logistics demo that makes operations software feel like a strategy game. Reproduce that feel for a hospital:

- **Scene.** Matte, clay-like low-poly world on a pale lavender-white ground (around `#E9ECFB`). One strong royal-blue accent (around `#2F55F5`), white and light grey walls, soft shadows, light fog at the edges, no hard outlines. Procedural boxes, cylinders, and rounded boxes; instanced meshes. A hospital with the roof cut away: waiting area, triage, treatment bays, imaging, ward beds, pharmacy, an ambulance bay and road outside. The layout is drawn from the scenario, so when a manager moves a bay, the building changes.
- **People.** Patients colored by acuity, staff by role, walking between rooms with positions interpolated between snapshots. Queues are people visibly waiting.
- **Selection.** Click any person, bed, room, machine, or ambulance: a blue corner-bracket box with a pill label ("Bay 4 · In treatment", "RN-07 · Triage"), and the camera eases toward it.
- **Camera.** Perspective at 40 to 55 degrees of pitch; orbit, pan, dolly; slow idle drift; eased fly-to.
- **Interface.** Frosted-glass cards over a full-screen canvas. Top bar: name, search, scenario and hospital switcher, simulated clock, speed control. Three KPI cards top-left with a big number and delta chip. Zoom and rotate controls in a vertical pill at right. A patient-journey stepper bottom-left that follows the selected patient. A tabbed list bottom-right (Beds, Staff, Patients) with status chips and mini progress bars; rows cross-highlight the 3D object.
- **Inspector.** The right-hand panel shows the selected entity's live state and, beneath it, its catalog definition: every attribute, its value or distribution, and its source tag and link. This is the "every data point about every thing" promise made visible.
- **Modes.** Play: knobs for staffing, policy, and structure wired to a live simulation. Watch: replay a manager's recorded rollout with its decisions surfaced as they happen. Compare: two managers side by side on the same seed with synchronized clocks and live charts. Trade-off: every evaluated manager plotted on cost against wait, including the human player's last run. Encounter: opened from a selected patient.
- **Honesty.** Managers are labeled by kind (learned, tuned heuristic, rule-based). A small status indicator shows which services are live and which are offline.

Verification: a 3D interface cannot be judged from code. Drive the app with headless Playwright, save screenshots to `overnight/screenshots/`, and look at them: each mode, a selection, the inspector, a narrow viewport. Fix what looks broken. `pnpm build` passes with no type errors.

### Server (`server/`)

FastAPI. A websocket streaming snapshots from a live simulation and accepting actions. Endpoints for the catalog, scenarios, managers, recorded rollouts, evaluation results, service status, and encounters. One command starts it.

### Encounter (`encounter/`, pages in `web/`)

The played resolver for the clinician-patient interaction, built to the shape of TwinVerse Challenge 1 (read the brief for the full list).

- **Case as data.** A versioned schema: profile, clinical facts, chart sections and artifacts, disclosure rule per fact (volunteered; only if asked; only after rapport; denied until confronted with evidence), learning objectives, rubric. A case is either instantiated from a simulated patient's latent truth and its condition template, or authored by faculty. No case-specific code. Validation catches missing fields and contradictions. Draft → approved → published; published versions are immutable.
- **Patient Studio.** A faculty page to create, edit, validate, preview, and publish a case or a condition template.
- **Encounter.** Split screen: conversation left, chart right, sections revealing as their conditions are met. A disclosure ledger records what was unlocked and by which question. The patient withholds or misreports only as the case defines; it never invents a clinical fact.
- **Feedback.** A grader separate from the role-play. Per-criterion results with quoted transcript evidence, an uncertainty flag where evidence is thin, a suggestion for next time. Sessions are logged.
- **Write-back.** On completion the encounter returns the interaction contract's outputs to the simulation.
- **Use the organizers' resource pack** (`RU Health Hack 2026 SHP (public).zip`): seven or so sample patients with background, personality, hidden habits, and photos; an encounter evaluation rubric as JSON (a four-point scale across named domains) plus two further rubrics; a sample course syllabus; five clinician profiles; challenge overviews for both challenges; and notes linking to public patient-profile, patient-doctor dialogue, and pathology-result datasets. Build the polished cases from the sample patients, make the supplied rubric the grader's default, and fetch the linked datasets for condition templates and lab artifacts where they can be downloaded without an account.
- Ship condition templates for the main condition groups and at least three polished cases, one with a patient who conceals something important (several of the sample patients are written that way).

### Research (`research/`)

The teammate has already covered the challenge requirements, sponsor resources, competing products, and the clinical-education evidence; do not redo that. Fill what his research leaves open, which is the operations side. Write to new files and add to the source register rather than rewriting his.

Evidence that informs design, from the web: emergency department arrival and service-time patterns; patient flow and boarding; simulation and RL for hospital operations (state, action, and reward designs that have been tried); AI-simulated patients and automated assessment of clinical interviews. Per source: title, authors, year, link, study design, sample size, comparator, outcomes, limitations, implication for this project; "not reported" where a field is absent. Feed parameter ranges to the catalog and design implications to the simulator and RL workstreams as you find them, not only at the end.

## Online and offline

Each outside service sits behind an interface with a real implementation and an offline one. Which is used is decided at startup purely by whether the credential is present, with no flag or setting to change. A `.env.example` lists the variables; `.env` is gitignored.

| Service | Online when | Offline behavior |
|---|---|---|
| Language model | AWS credentials resolve (Bedrock), otherwise an Anthropic API key is set | The patient matches the student's question to case facts by topic and answers in the fact's authored wording, under the disclosure rules. The grader checks rubric items against the ledger and transcript. |
| Voice | An ElevenLabs key is set | The browser's built-in speech synthesis and recognition. |
| Data service | A Vlada key is set | Public sources and local extracts. |

- Offline must work end to end with no network. No credentials are set tonight and the user will add them tomorrow, so everything you verify will be on the offline path; the online path has to be right without you having run it against the real service.
- The teammate's notes in `research/resource-feasibility-2026-10-10.md` record which models the workshop AWS account lists. Make the model identifier configurable for each provider.
- If an online call fails at run time, fall back to offline for that call and show it in the status indicator. Never fail the user's action because a service is down.
- Online and offline obey the same grounding rules: the language model words the patient's answer but the disclosure engine decides which facts are available.
- Use current Claude model identifiers, checked against documentation rather than memory.
- Tests exercise the online implementations against faked responses.

## Order of work

Everything here is in scope for tonight; this is the order to protect if things go slowly.

1. Simulator, catalog skeleton, viewer, play mode.
2. Gym, baselines, tuned heuristics, compare mode, trade-off chart.
3. Catalog filled from real sources, inspector, validation against benchmarks.
4. Learned agents trained on deepstack and honestly evaluated.
5. Encounter end to end, opened from the 3D hospital, written back.
6. Stretch: structural actions over 1000-day episodes; weight-conditioned agent with a slider; more departments and interaction types with played resolvers; voice; a multi-encounter care journey with shared patient state and provenance (TwinVerse Challenge 2).

Research runs alongside from Wave 1.

## Wrap-up

Start no later than 6 hours in.

1. Checkpoint training. Evaluate the latest managers, regenerate rollouts and the results file, and pull them into the repo. Leave training running on deepstack if it is still improving.
2. From a clean shell, follow your own setup instructions on the Mac: environment, install, all tests, web build, start server and app, screenshot every mode.
3. Rewrite `README.md` to describe what exists: what it is, how to run it, architecture, what is real and what is offline. Keep what is still ahead as a roadmap, and keep a pointer to the teammate's `research/`.
4. Write `overnight/MORNING_REPORT.md` for someone who just woke up and has ten minutes: the commands to run it; what works and how it was verified; what is partial or broken; results for learned agents and tuned heuristics against baselines on held-out seeds, stated plainly whichever way they came out; how much of the catalog is measured, literature-derived, and assumed; what is running on deepstack and how to check or stop it; decisions made on the user's behalf; and a proposed plan for the remaining hours before submission. Embed the best screenshots.
5. Final commit on `aryan`. Check that nothing from `docs/`, the zips, or `.private/` is tracked. Do not push. Leave no stray local processes.
