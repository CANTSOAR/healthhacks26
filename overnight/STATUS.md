# Overnight status

Start: Sat 2026-10-10 00:59 EDT. Wrap-up starts by 06:59. Target end ~08:00.

## Where things run
- Local: repo, `.venv` (py3.12, torch 2.2.2, numpy 1.26.4).
- deepstack: `~/projects/hospitalgym_aryan`, uv env `.venv`, tmux session `hospitalgym`.

## Wave 0 (orchestrator) — done 01:10
- Read HANDOFF, README, research/ (README, action-plan, technical-and-data-research), Challenge 1 brief, resource pack.
- Extracted `docs/TwinVerse.zip` and the SHP resource pack into `.private/` (gitignored).
- Contracts written: enums, snapshot, layout, rollout, metrics, actions, interaction, case, catalog, sim_api, api; fixture layout + rollout validated.
- Catalog skeleton written with ASSUMED placeholder values (patient, staff, space, equipment, event, interactions, hospitals/rwjuh_nb).

## Decisions made on the user's behalf
- No credentials present in env or `.env`: everything verified tonight is the offline path.
- Snapshots are struct-of-arrays with integer enum columns (compact enough for browser replay).
- Action set fixed in `contracts/actions.yaml` (6 hourly, 9 daily, 2 weekly, 5 monthly heads).
- Downstream inpatient capacity is modelled as one ward pool available to ED admissions, not all 700 beds.
- Three 8-hour shifts (07/15/23) for staffing actions.
- Resource-pack content is read from `.private/` at run time; tracked cases are our own authored synthetic cases (the repo is public).

## Log
- 01:15 Wave 1 launched (6 background agents): sim (owns sim/), web (web/), layout (catalog/hospitals/*.layout.json), data+catalog (data/, catalog values), ops research (research/operations-*), encounter engine (encounter/, catalog/conditions/). Markers: sim/M1_READY (API runnable) -> launch RL + server agents; sim/M2_READY (tests pass).
- deepstack env: uv default torch build had no CUDA with the installed driver; pinned torch 2.8.0+cu128 (same as system python).
- 01:27 Layout agent done: rwjuh_nb.layout.json v2 (148 rooms, 114 published / 34 inferred / 0 surveyed; OSM footprints surveyed), community_small + midsize. No real interior plan found. Axes rotated 34 deg to building grid.
- 01:37 sim M1 reached (API runs: 4 hospitals x 48 h in 6 s local CPU; baseline wait ~54 min, LWBS 4%, assumed calibration). Wave 2 launched: RL agent (rl/, deepstack tmux hospitalgym, runs/ dir; marker rl/R1_READY) and server agent (server/, dev port 8001; 8000 reserved for integration).
- 01:39 Data agent done: catalog 302 attrs = 85 measured / 26 literature / 191 assumed (data/processed/catalog_coverage.json). Validation targets: RWJUH OP-18b 206 min, LWBS 1%, ED visits 81,126 (2024). Sim agent told to recalibrate assumed values only.
- 01:45 Ops research agent done: 78 evidence records, 23 literature catalog edits. Spot-check agent launched to re-fetch a sample of citations.
- 01:52 Citation audit: 22/23 catalog literature attrs verified, 15/15 sampled evidence records verified; 1 mismatch (Guttmann totals) + wording fixes applied; mixed-provenance arrays flagged with mixed_provenance field. 63 of 78 evidence records not audited.
- 02:00 Server agent done: 33 tests pass (re-run by orchestrator), smoke 42/42. Baseline validation: median ED time 305 min vs target range 133-269 (outside), LWBS 3.9% (inside). Integration server running locally on :8000 (background) for the web agent.
- 02:01 Encounter pages agent launched (owns web/app/encounter, web/app/studio, web/components/encounter, web/lib/encounter). Running now: sim, web, encounter engine, RL, encounter pages.
- 02:12 Encounter engine agent done: 138 tests pass (re-run by orchestrator); offline probes 46/48 (development set). It flagged organizer sample names hard-coded in a test in two local commits: working tree fixed, local history from f67418b squashed and re-committed; verified no commit reachable from aryan contains those names. Old objects remain only in the local reflog (never pushed).
- 02:15 RL R1: env, baselines, 4 tuned heuristics, held-out eval (32 seeds x 30 d, normal + flu), rollouts; committed. PPO x4 training on deepstack tmux windows rl_ppo_* (runs/ppo_*). Known: baseline non-stationary over 30 d (ward fills), cost dominated by fixed/variable terms, GPU ~267 hospital-days/s. Sim agent asked to fix; RL retrains at sim/M2_READY.
- 02:29 Web agent round 1 done (build passes per agent; screenshots reviewed by orchestrator: play, inspector, trade-off look right). Round 2 sent: inspector fixes, inject/hand-over/structural tests, chart zoom, demo tour.
- 02:29 Encounter pages agent done: /encounter and /studio verified in browser (55/56 e2e, studio 24/24 after test fix), sim-patient write-back shown. Server on :8000 restarted to pick up newer engine code.
- 02:30 Core list items 1-3 and 5 are built; item 4 (learned agents) training. Stretch started: care-journey agent (Challenge 2: encounter/journey, web/app/journey; test ports 8011/3002). Running: sim (to M2), RL, web round 2, care journey. bdvg7fuds-style watcher on sim/M2_READY.
- 02:33 sim/M2_READY appeared but orchestrator's local run: 10 passed, 1 FAILED (test_same_seed_same_trajectory[cpu], reproducible), 11 skipped; BASELINE.md/BENCHMARK.md missing. Sim agent told to fix determinism and re-verify before M2 stands.
- 02:51 sim M2: orchestrator ran sim/tests locally: 11 passed, 11 skipped (CUDA params). Determinism fixed. RL agent retrains on this.
- 02:55 Sim agent round 1 done. Verified by it: Mac 11 passed/11 skipped; deepstack 22 passed (CPU+CUDA). Baseline (default actions, simulated): median discharged ED time 185 min (target 206, peers 133-269), LWBS 1.4% (1-5%), median wait 15 (17); p90 wait 35 vs survey 63-118 = OUTSIDE (too short). Stationary 60 d. GPU ~210 hospital-days/s shared (364 idle, older code). BEHAVIOUR FREEZE declared at this commit for RL; sim round 2 must be trajectory-neutral (golden test).
- 02:57 RL R2: tuned heuristics re-tuned on M2 sim; held-out (32 seeds x 30 d): normal week mean wait fixed 23.1, rule_based 18.0, tuned_min_wait 12.6, tuned_min_cost 20.8 (labor $65.9k/d vs fixed $77.0k/d), constrained threshold p95<=60 min. No learned agent evaluated yet; PPO training.
- 02:58 Web round 2 done (build passes per agent). Verified live: inject x4, hand-over, 48x, structural layout change (bays 125->129) re-render. Black-people bug: root cause not found, remount workaround holds. Cleared agent-made test rows from server/state/human_runs.json (gitignored) so the trade-off chart shows no fake human run.
- 02:59 Independent QA agent launched (writes overnight/QA_REPORT.md; web dev on :3000). Contracts updated with accepted addenda. Running: sim round 2, RL (PPO), care journey, QA.
- 03:07 Care journey agent done: encounter+journey+server tests re-run by orchestrator (see log line below); server on :8000 restarted, /api/journeys live. Needs: Journey link in nav.
- 03:10 Orchestrator: fixed test-order dependency (encounter+journey+server = 190 passed together), added Encounter/Studio/Journey links to main top bar and Care Journey tab to encounter nav (tsc clean; not yet screenshot-checked).
- 03:46 QA report in (overnight/QA_REPORT.md): 4 P0, 17 P1, 16 P2. P0: return-to-hospital loses the run (D1); play-encounter button fails for most patients (D2); write-back rejected for pre-provider patients when paused (D3); Studio from-description builds the wrong patient (D4). Fix round dispatched: server r2 (attach to run, deferred write-back, playable list), web r3 (D1/D2 UI, D9, D10, D14, D15, D17, D6 UI, honesty labels), encounter engine r2 (D4, D12, D13, D16, D18, D19), RL (bigger rollout windows, distinct objectives, honest PPO notes; marker rl/R3_READY), sim r2 addendum (D11, D21, D3). Rule added: nobody runs pnpm build while dev servers are up; orchestrator builds at wrap-up.
- QA left test cases in data/encounters/cases (gitignored): delete at wrap-up. PPO policies landed at 03:19: currently BC clones statistically identical to tuned heuristics (must be labelled as such).
- 03:57 Server r2 done: server tests re-run by orchestrator (count in commit log), :8000 restarted with attach/queued write-back/playable. Encounter tests currently red while its agent edits (5 failing per server agent) - recheck when engine r2 reports.
- 04:08 Encounter engine r2 done; orchestrator re-ran encounter+journey+server suites (result in next line of log). :8000 restarted.
- 04:10 INTERRUPTION: account usage limit hit; sim r2, web r3 and RL agents terminated mid-task; orchestrator stopped too. Nothing ran locally 04:10-09:08. deepstack training continued and finished 05:44 (tuned x5, PPO x6 BC-warm-started incl. max_margin and weight-conditioned, PPO x2 from scratch).
- 09:10 Resumed (user awake, said continue). Server r2 and encounter engine r2 were already committed (222 tests pass together). Resumed RL (install/evaluate/record/pull -> rl/R3_READY), web (finish r3), sim (close out r2). Orchestrator starting wrap-up docs.
