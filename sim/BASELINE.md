# Baseline sanity: `normal_week`, default actions (fixed roster)

All numbers are SIMULATED. Runs on deepstack CPU (torch 2.8.0), simulator code as at `M2_READY`.
Scripts used were scratch scripts (hourly `step()` with `default_actions()`; the discharged-only and
median-wait figures were collected by reading patient tensors every tick).

## Result vs validation targets (`catalog/validation_targets.yaml`; targets are never simulator inputs)

Run: 16 hospitals (seeds 100-115), 3 warm-up days discarded, then 28 days.

| Measure | Simulated | Target | Verdict |
|---|---|---|---|
| Median ED time, discharged patients | 185 min | RWJUH CMS OP-18b 206 min; very-high-volume peers 10th-90th pct 133-269 | inside the peer range, 21 min below the hospital's own value |
| LWBS share of arrivals | 1.4 % | RWJUH 1 % (published as a whole percent); peers 1-5 % | inside |
| Median arrival-to-provider wait | 15 min (ESI 1..5: 10, 10, 15, 15, 15) | NHAMCS metro teaching 17 min (by ESI 9, 11, 16, 18, 17) | close; waits are multiples of the 5-min tick |
| 90th pct wait | 35 min | NHAMCS by ESI 63-118 min | OUTSIDE (too short: the simulated tail is thinner than the survey's) |
| Median ED time, discharged, by ESI 1..5 | 230, 210, 210, 140, 140 min | NHAMCS metro teaching 252, 252, 219, 124, 100 | ESI 3 close; ESI 1-2 short by ~20-40 min; ESI 4-5 long by 16-40 min |
| 90th pct ED time, discharged | 445 min | NHAMCS by ESI 292-721 | plausible |
| Admission decisions / arrivals | 14.1 % | NHAMCS metro teaching 14.1 % | inside (follows from measured p_admit) |
| Arrivals per day | 219.5 | 222 (81,126 / 365) | inside |

Other baseline outputs (same run): mean wait 21.5 min, p95 wait 55 min, median ED time over all ED
departures 190 min, boarding 4.6 patient-hours/day, bay occupancy 0.41 (of staffed bays), ward-pool
occupancy 0.82, provider utilisation 0.69, nurse utilisation 0.38, mean fatigue 0.06, ED census 36,
staff on shift 50, deaths 0.12/day, deteriorations 0.12/day, adverse events 0.43/day.
Money per day: cost 578 k USD (labour 77 k, fixed 392 k, variable 109 k), revenue 1,012 k, margin 434 k.
Fixed cost is dominated by the measured, fully allocated ward and ED-space overhead, so total cost
moves little with staffing (see "Known limits").

## Stationarity: 60 days, default actions, 16 hospitals (seeds 100000-100015), no warm-up discarded

Six-day means across the batch. Conservation residual 0, pool overflow 0.

| Days | Arrivals/day | Mean wait (min) | p95 wait, trailing 24 h | Median ED time, all departures | LWBS % | Admissions/day | Boarding pt-h/day | Ward occupancy | Bay occupancy | Cost k$/day | Margin k$/day |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0-5 | 224 | 21.4 | 56 | 196 | 1.42 | 29.9 | 4.5 | 0.834 | 0.412 | 579 | 440 |
| 6-11 | 224 | 23.6 | 63 | 201 | 1.47 | 31.4 | 12.0 | 0.824 | 0.429 | 578 | 416 |
| 12-17 | 221 | 23.3 | 66 | 197 | 1.47 | 30.4 | 5.0 | 0.805 | 0.419 | 576 | 470 |
| 18-23 | 221 | 21.7 | 54 | 200 | 1.39 | 31.2 | 4.9 | 0.838 | 0.416 | 579 | 420 |
| 24-29 | 222 | 22.3 | 61 | 198 | 1.49 | 31.0 | 4.5 | 0.835 | 0.421 | 579 | 430 |
| 30-35 | 218 | 20.9 | 52 | 187 | 1.24 | 31.0 | 4.4 | 0.848 | 0.396 | 580 | 466 |
| 36-41 | 215 | 20.1 | 50 | 198 | 1.25 | 31.7 | 4.4 | 0.860 | 0.399 | 581 | 478 |
| 42-47 | 226 | 23.0 | 63 | 200 | 1.42 | 31.4 | 4.5 | 0.834 | 0.431 | 579 | 459 |
| 48-53 | 225 | 22.8 | 61 | 200 | 1.42 | 31.0 | 5.3 | 0.822 | 0.430 | 578 | 416 |
| 54-59 | 223 | 22.9 | 66 | 197 | 1.47 | 31.4 | 4.7 | 0.828 | 0.423 | 579 | 449 |

Worst single day (batch mean): ward occupancy 0.879, mean wait 35 min, LWBS 2.7 %, boarding 21.7 pt-h.
60-day episode summary: mean wait 22.6 min, p95 wait 62 min, median ED time (all) 193 min, LWBS 1.4 %,
cost 579 k/day, margin 444 k/day, 5.1 deaths per 10,000 arrivals, boarding 5.4 pt-h/day; mean ward occupancy 0.833.
No drift: the earlier non-stationary behaviour (ward pool filling, boarding blocking bays) is gone.

## What was changed to get here, and why (ASSUMED attributes only; measured/literature values untouched)

| Attribute | Was | Now | Reason |
|---|---|---|---|
| `staff.shared.provider_levels` | 3/5/7/9/11 | 4/6/8/10/12 | With 7 providers at the default level the run gave median discharged ED time 250 min, LWBS 2.3 %, p90 wait 80 min; 8 gives 185 min / 1.4 % (hospital's own values 206 min / 1 %). 9 gave 165 min / 1.0 %. |
| `hospitals/rwjuh_nb.ward_pool_los_factor` (new, sim-owned) | - | 0.85 | Ward inflow is about 31 admissions/day (measured p_admit) and measured LOS is 5.29 days, i.e. 164 occupied beds against a 168-bed pool (layout: ward 120 + ICU 24 + step-down 24): about 98 %, not stationary. The factor is the assumed share of the stay spent in the modelled pool; 0.85 gives a long-run occupancy near 83-84 %. The layout's bed counts were left alone (not this agent's file). |
| `patient.shared.wrong_disposition_max_prob` (sim-owned) | 0.25 | 0.08 | 0.25 flipped about 5 % of discharges to admissions and inflated admissions by a quarter over the measured rate. |
| `patient.shared.inpatient_variable_cost_per_day` (sim-owned) | 2300 | 600 | The measured ward fixed cost is fully allocated (includes nursing), so 2300 double-counted. |
| Ward warm start (code, derived from the LOS distribution, not a parameter) | remaining stay = LOS x U | LOS x U x (1 + cv^2) | Matches the mean residual life of a stay in progress, so occupancy does not sag in week 1. |
| Treatment clock (model choice) | started when the clinician encounter ended | starts at first provider contact | `treatment_min` is measured from first contact; the old reading double-counted provider time. |

These are assumed calibrations of a model, not statements about the real hospital.

Earlier points on the calibration path (same script, 8 hospitals, 3 + 10 days):
provider levels 3/5/7/9/11: mean wait 37 min, p95 150, discharged median 250, LWBS 2.3 %;
4/6/8/10/12: 22 min, 55, 185, 1.4 %; 4/6/9/11/13: 17 min, 40, 165, 1.0 %.

## Known limits

- The 90th-percentile wait is well below the survey's; the model has no ED-wide bad days beyond call-outs, failures and Poisson noise.
- Low-acuity visits run long and high-acuity discharged visits run short relative to NHAMCS by-acuity medians.
- Cost is insensitive to staffing because measured overhead dominates (labour is 13 % of cost). That is what the cost report says, not a bug, but it leaves a cost-minimising manager little room.
- `community_small` and `midsize` layouts run (arrivals and rosters scaled by bay count) but are NOT calibrated: a 2-day check gave mean wait 111 min / LWBS 6 % (small) and 39 min / 3 % (midsize).
