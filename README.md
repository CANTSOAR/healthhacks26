# HospitalGym

A hospital operations twin built from public data: **build the twin → calibrate a baseline → simulate → optimize**.

1. **Twin.** `twin.build` assembles a hospital's catalog file and layout from public datasets (CMS Care Compare, CMS cost reports, CMS clinician files, NHAMCS, BLS wages and others), with a source tag and citation on every attribute.
2. **Calibrated baseline.** `twin.calibrate` fits the parameters public data does not pin down, plus a baseline staffing schedule, until the default policy reproduces the hospital's own published figures. It also keeps an ensemble of parameter sets that public data cannot tell apart.
3. **Simulate.** A batched discrete-time simulator (PyTorch tensors, 5-minute ticks) runs the emergency department and an inpatient ward pool: one hospital on a CPU for the 3D viewer, thousands in parallel for search.
4. **Optimize.** Operating policies (staffing by shift, priority rule, fast track, triage stations, imaging hours and so on) are searched against a stated objective and constraints, then compared with the calibrated baseline on held-out seeds across the ensemble. You can also pick your own ranked goals and launch a search from the web app.

The first hospital is Robert Wood Johnson University Hospital, New Brunswick (`rwjuh_nb`).

> **This is a model built from public information.** It is not affiliated with or endorsed by Robert Wood Johnson University Hospital. The baseline is fitted to published aggregates, not to the hospital's timestamps, roster or operating rules. **Every result is simulated**; none is a measurement of the real hospital or a forecast of what would happen there. Staff and patients shown in the app are fictional.

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

Open http://localhost:3000. If the API is unreachable the web app falls back to bundled fixture data and says so. Optional settings are in `.env.example` (`HG_CORS_ORIGINS` for a deployed site, `HG_OPT_WORKERS`, `HOSPITAL_ID`, `VLADA_API_KEY`).

### The web app

| Mode | What it is |
|---|---|
| **Optimize** (`/?mode=optimize`) | Pick the metrics you care about, give each a direction and a rank, and start a search. The page polls the job and shows the optimized plan against the calibrated baseline on held-out seeds. One job runs at a time and uses most of the machine's cores. |
| **Play** | You are the manager: staffing per shift, priority rule, overflow bays, fast track, imaging hours and structural changes drive a live simulation. Inject a flu surge, a mass-casualty incident, a CT outage or nursing call-outs; hand the hospital to a manager and take it back. |
| **Watch** | Replay a manager's recorded run with its decisions surfaced as they happen. |
| **Compare** | Two managers side by side on the same seed. Demand comes from a random stream that does not depend on actions, so both face the same patients. |
| **Trade-off** | Evaluated managers on cost against wait with intervals from held-out seeds, the validation card, and the value of every resource. |
| **Inspector** | Click a patient, staff member, room or machine: its live state, its catalog definition (every attribute with value, unit, source tag and citation), a patient's log of sampled interactions, and for staff, spaces and scanners the simulated value of one unit of that resource. |

### The pipeline, from the command line

```bash
# 1. Build a hospital from public data (writes catalog/hospitals/<id>.yaml, <id>.layout.json, twin/reports/<id>/DATA.md)
.venv/bin/python -m twin.build --ccn 310038 --id rwjuh_nb

# 2. Calibrate it (writes catalog/hospitals/<id>.calibration.yaml, <id>.ensemble.json, twin/reports/<id>/CALIBRATION.md)
.venv/bin/python -m twin.calibrate --hospital rwjuh_nb --device cuda     # --stage fit | check | ensemble | report | all

# 3. Tune, evaluate held-out over the ensemble and write the headline (rl/hospitals/<id>/HEADLINE.md, headline.json)
bash rl/scripts/run_hospital.sh rwjuh_nb

# 4. Optimize for a reward of your own (what the Optimize page runs)
.venv/bin/python -m rl.custom --spec spec.json --out runs/custom/job1 --hospital rwjuh_nb --cpu-workers 8

# 5. Value of every resource unit (rl/hospitals/<id>/ATTRIBUTION.md, attribution.json)
.venv/bin/python -m rl.attribution --hospital rwjuh_nb
```

`spec.json` for step 4 is `{"goals": [{"metric": "profit", "direction": "max", "rank": 1}, {"metric": "wait", "direction": "min", "rank": 2}], "guardrails": true}`; the metric menu is `GET /api/optimize/menu`. The RWJUH calibration search took about an hour on a GPU. `run_hospital.sh` as written syncs the repository to a remote workstation over ssh (host alias `deepstack`) and runs the heavy steps there; see [rl/README.md](rl/README.md).

Tests:

```bash
.venv/bin/python -m pytest sim/tests -q                  # simulator
.venv/bin/python -m pytest twin/tests -q                 # public-data build and calibration
.venv/bin/python -m pytest server/tests -q               # API and websocket
.venv/bin/python -m pytest rl/tests data/adapters -q     # managers, objectives, optimizer, data adapters (several minutes)
pnpm --dir web build                                     # type-check and build (stop the dev server first)
```

## Architecture

```
 web/        Next.js + React Three Fiber: 3D hospital, Optimize, Play, Watch, Compare, Trade-off, inspector
               │  HTTP + websocket (contracts/api.md)
               ▼
 server/     FastAPI: live simulation per websocket, run registry, catalog, rollouts, results,
             validation, optimize jobs, headline and attribution reports
               │
               ▼
 sim/        Batched simulator on PyTorch tensors (CPU batch of 1 for the viewer, large batches for search)
 rl/         Rule-based and tuned managers, constrained objectives, cross-entropy tuner, PPO,
             held-out evaluation, headline, custom-reward optimizer, resource attribution, recorded rollouts
 twin/       Public-data ingestion, hospital builder, calibration, uncertainty ensemble, reports
 catalog/    Every entity type, variant and attribute with its source tag; interaction declarations;
             per-hospital files, layouts, calibration and ensemble
 data/       Fetch scripts, small processed public extracts, data-service adapters
 contracts/  Schemas, the simulator's Python API and the HTTP/websocket API shared by all of the above
```

- **Interactions.** Each interaction type in `catalog/interactions.yaml` (a triage, a clinician encounter, a scan, a handoff) declares its inputs and four outputs: duration, information gained, decision, quality. The simulator samples them; the results are kept in each patient's interaction log and shown in the inspector.
- **Common random numbers.** Demand does not depend on actions or parameters, so a policy and the baseline are always compared on the same simulated patients (paired differences).
- **Managers are labeled by kind everywhere**: `fixed` (the calibrated baseline, "current practice"), `rule_based`, `random`, `tuned_heuristic` (a rule-based manager whose parameters were found by search, not a learned agent), `learned` (PPO), `human`.

## What is real and what is assumed

Read these generated reports before quoting any number:

| Report | What it holds |
|---|---|
| [twin/reports/rwjuh_nb/DATA.md](twin/reports/rwjuh_nb/DATA.md) | Every hospital attribute with value, unit, source tag and citation; what is not public; what is still national. |
| [twin/reports/rwjuh_nb/CALIBRATION.md](twin/reports/rwjuh_nb/CALIBRATION.md) | What was fitted, targets against simulated values on held-out seeds, stationarity, the ensemble, residuals that were not closed. |
| [rl/hospitals/rwjuh_nb/HEADLINE.md](rl/hospitals/rwjuh_nb/HEADLINE.md) | The constrained operating-policy results against the calibrated baseline, every candidate including the losers, protocol and caveats. |
| [rl/hospitals/rwjuh_nb/ATTRIBUTION.md](rl/hospitals/rwjuh_nb/ATTRIBUTION.md) | Simulated marginal value of every resource unit, with and without one unit on the same patients. |

**Measured for this hospital (public datasets).** Annual ED visits, median ED time for discharged patients, left-without-being-seen rate, beds, inpatient occupancy and discharges, ED cost-center salaries, and the affiliated clinician roster. Of the 129 hospital-specific attributes, 89 are measured, 6 come from literature and 34 are assumed (DATA.md, "Coverage").

**What the calibrated baseline reproduces.** On 64 held-out seeds over 60 days (CALIBRATION.md): median ED time for discharged patients 203 minutes against 206 published; left without being seen 0.91% against 1%; ED salaries $61.6k a day against $65.9k; occupancy of the modeled ward pool 84.4% against a target of 89.1%, inside its acceptance interval. The baseline is a steady state over 60 days.

**What is not this hospital's data.**

- **Staffing schedules are fitted, not observed.** No public source lists an ED's schedule. The head-counts by shift are the ones that, in this model, reproduce the published ED time and walk-out rate; fewer providers who each work faster fit the same figures. Clinician time per patient is assumed and identified only jointly with staffing. The real roster, call-in practice and bed management are unknown.
- **National survey figures stand in for the hospital's own.** The arrival pattern by hour and weekday, the acuity and condition mix, admission, imaging and lab probabilities by acuity, treatment times, the ED payer mix and inpatient stay length of ED admissions are national NHAMCS estimates. ED admissions per day are derived from them.
- **Scope is the ED plus one inpatient ward pool.** Elective and transfer admissions, ICU-versus-ward mismatch and time-of-day discharge patterns are not modeled. Boarding is the least certain output of the baseline.
- **Residuals not closed.** The front-door wait tail (90th-percentile waits) and mean boarding time are shorter in the twin than in the national survey; median ED time for ESI 4 is longer.
- **Safety and money.** Deaths and adverse events come from literature hazard rates applied to simulated waiting; they are a guardrail, not a clinical prediction. Labor cost uses published wage levels with assumed benefit, overtime and agency multipliers; margin also depends on assumed payer revenue.
- **Layout.** Room counts and zones follow what the hospital has published; every room position is inferred.

**Results so far (simulated, held-out seeds, 24 ensemble members × 32 seeds × 30 days, against the calibrated baseline; HEADLINE.md).**

- *Same budget, better flow*: the tuned rule-based plan cut mean door-to-provider wait by 17.0% (95% CI 9.1 to 26.2), median ED length of stay by 4.5%, walk-outs by 14.6% and boarding hours by 59.6%, with labor cost 4.0% lower and every constraint met. The improvement holds in 20 of 24 ensemble members. Under a flu surge the same plan misses the transfers-out constraint.
- *Same service, lower cost*: the tuned rule-based plan fails the operating-cost constraint on held-out data. The only candidate that passes is a PPO policy that the report marks as stale (trained against an earlier calibration), so there is no current result for this objective.
- **Learned PPO agents have not beaten the tuned rule-based plans.** On the same-budget objective PPO loses to the tuned plan in both scenarios; the same-service PPO result is the stale one above.
- The attribution report uses the point calibration only (ensemble member 0); providers of a role and bays of a class are interchangeable in the model, so it values "one evening provider", not a named person.

None of this is validated on the hospital's operational data. HEADLINE.md lists what would be needed: de-identified ED timestamps, the actual roster by hour and role, bed occupancy and boarding logs, and the ED cost center's labor ledger.

## Add a hospital

1. Find the hospital's CMS certification number (CCN).
2. `.venv/bin/python -m twin.build --ccn <ccn> --id <id> --expect "<name words>" "<city>"`. `--expect` guards against a wrong number; `--fetch` re-downloads the sources. This writes `catalog/hospitals/<id>.yaml`, `catalog/hospitals/<id>.layout.json` and `twin/reports/<id>/DATA.md`. Read DATA.md for what could not be sourced.
3. `.venv/bin/python -m twin.calibrate --hospital <id> --device cuda`. This writes the calibration file, the ensemble and `twin/reports/<id>/CALIBRATION.md`. Check the held-out table and the stationarity section before going further.
4. `bash rl/scripts/run_hospital.sh <id>` for the tuned plans and the headline, then `.venv/bin/python -m rl.attribution --hospital <id>`.
5. Start the server with `HOSPITAL_ID=<id>` to make it the default for optimize jobs; the web app lists every hospital that has a layout.

`mount_sinai` and `mayo_rochester` have been built (step 2) but not calibrated or optimized.

## Static snapshot

A recorded snapshot of Watch, Compare, Trade-off and the inspector can be exported without a server (Play and Optimize need the API). With the API running and `next dev` stopped:

```bash
.venv/bin/python web/scripts/make_snapshot.py
cd web && STATIC_EXPORT=1 NEXT_PUBLIC_BASE_PATH=/healthhacks26 NEXT_PUBLIC_STATIC_SNAPSHOT=1 pnpm build
# then publish web/out (plus an empty .nojekyll)
```
