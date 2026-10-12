# CURRENT — live status (newest first)

Updated by Claude as things happen. All result numbers are SIMULATED.

## LINK (Sun ~01:20): http://54.185.19.108:3000/

- New version is live: landing page (what it is, how it works, results so far, what each page does), Optimize, Play, Watch, Compare, Trade-off + Resources. US spellings, no-jitter goal picker, tour only opens from its button.
- The clinical-education side (Encounter / Studio / Journey) is removed from the site and the API. Python package deleted locally (uncommitted). The web folders for those pages still exist LOCALLY (deletion was blocked by the permission system) but are not deployed.
- Optimize: ~4.4 min per run, one at a time. API browser access fixed (CORS).
- Link dies when the workshop AWS account closes or the instance restarts.

## RWJ HEADLINE (Sun 00:15) - simulated, held-out seeds, 24 twins, vs calibrated current practice

- **Same budget, better flow** (tuned rule-based plan): mean wait **-17.0%** (CI 9.1 to 26.2), median stay **-4.5%** (3.3 to 5.7), walk-outs **-14.6%** (8.0 to 22.7), boarding hours **-59.6%** (36.9 to 71.4), labour cost **-4.0%** (within budget), deaths per 10k -0.27. Every constraint met. Holds in **20 of 24** twins (worst twin: 2.4% better).
- **Same service, lower cost: no result to present.** The tuned plan misses the operating-cost constraint on held-out data (0 of 24 twins). The only candidate that passes is a PPO network trained against the earlier, unstable calibration (labour -2.9%, holds in 15 of 24 twins, worst twin 2% worse) - provisional at best.
- **Reproducible:** deepstack and AWS tuned independently and arrived at the identical plan and identical held-out numbers.
- PPO vs tuned rules on same-budget: PPO loses in both scenarios.
- Full report: `rl/hospitals/rwjuh_nb/HEADLINE.md`. Live on the site's recommended-plan card.

## Entity-level learned dispatch (Sun ~01:40) - mixed, mostly negative; simulated, 8 twins x 24 held-out seeds x 30 days

- Learned "who is seen next" beats the best fixed queue rule, but: in a normal week mean wait barely moves (-0.33 min) and median stay -14.7 min is mostly a reshuffle (mean stay only -5.6 min); in a flu surge the flow gains are large (wait -12.8 min) but **deaths rise** (+0.94 per 10k, CI 0.20 to 1.88) and it fails the safety constraints. Not something to present as a win.
- Dispatch alone loses clearly to the tuned staffing plan. Added ON TOP of that plan it gives a small safety-neutral gain (median stay -8 min normal, -15 min surge; 8 of 8 twins).
- Why: almost no choice exists at the front door in this twin (about one new patient queued for a provider on average), patients within a triage level are interchangeable, providers are identical. The model needs provider skill differences, patient features that predict service time, and scarce-bay matching before dispatch can matter. Full report: `rl/hospitals/rwjuh_nb/DISPATCH.md`.
- Engine change is off by default; golden trajectories unchanged.

## Status (Mon Oct 12)

- All work committed and pushed on branch `aryan`. Full suites passed on the final tree: 110 (twin, RL, data, server), 39 simulator (16 GPU variants skipped), web type-check clean.
- Open ideas, not started: make treatment time / admission / imaging depend on age and condition (national survey data), then retry dispatch; retrain PPO on the final calibration; fix the revenue-per-admission quirk.

## Done

- Public-data twin builder: `python -m twin.build --ccn <ccn> --id <name>` (RWJ, Mount Sinai, Mayo build; only RWJ in use).
- RWJ calibration: baseline steady over 60 days; held-out median ED time 203 vs 206 min published, walk-outs 0.91% vs 1%, occupancy 84%, ED salaries $61.6k vs $65.9k/day. Report: `twin/reports/rwjuh_nb/CALIBRATION.md`.
- 24-twin ensemble (parameter sets public data can't tell apart): `catalog/hospitals/rwjuh_nb.ensemble.json`.
- Constrained objectives (same budget/better flow, same service/lower cost) with diversion and admission caps locked.
- `GET /api/headline/{hospital_id}`.
- AWS tuning is ~3x deepstack per generation (86 s vs ~265 s).

## Known issues / caveats

- First calibrated baseline drifted into gridlock over 60 days; fixed by running the ward pool at 85% (matches RWJ's federal weekly occupancy figure). RWJ's cost-report occupancy (92.5%) is not reproduced.
- National survey tail waits (90th percentile) are still shorter in the twin than in the survey.
- PPO over the 22 management levers has only matched the tuned rule-based manager so far.
- AWS keys are a temporary workshop role: boxes keep running, but the link dies when the workshop account closes.

## Where things are

- Headline (when done): `rl/hospitals/rwjuh_nb/HEADLINE.md`
- Data provenance: `twin/reports/rwjuh_nb/DATA.md`
- Run the pipeline: `bash rl/scripts/run_hospital.sh rwjuh_nb`
- SSH: `ssh hgaws`, `ssh hgaws2`, `ssh hgapp`
