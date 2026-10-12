# RWJUH New Brunswick (model) (`rwjuh_nb`): operating-policy headline — ALL NUMBERS SIMULATED

Generated 2026-10-11T00:13:16-0400. Calibration: `catalog/hospitals/rwjuh_nb.calibration.yaml` (modified 2026-10-10T21:01:24-0400); ensemble: 24 members from `catalog/hospitals/rwjuh_nb.ensemble.json`; calibration fingerprint `13559aa34001a108`, simulator behaviour `ed6420bf3cdf4b16`.

## Headline

In a simulated twin calibrated to RWJUH New Brunswick (model)'s publicly reported figures, Tuned heuristic: Same budget, better flow (`tuned_same_budget`, tuned heuristic) cut mean door-to-provider wait by 17.0% (95% CI 9.1 to 26.2); cut median ED length of stay by 4.5% (95% CI 3.3 to 5.7); cut walk-outs (left without being seen) by 14.6% (95% CI 8.0 to 22.7); cut boarding hours by 59.6% (95% CI 36.9 to 71.4), with labour cost -4.0% vs baseline (95% CI -5.4 to -2.7; within budget), no ambulance diversion beyond baseline and deaths per 10,000 arrivals -0.27 (95% CI -0.43 to -0.14). Every constraint was met on held-out data. The improvement with budget constraints met holds in 20/24 plausible twins of the calibration ensemble (worst twin: objective at 97.6% of its baseline). All figures are simulated and not validated on the hospital's operational data.

## Objective: Same budget, better flow (`same_budget_better_flow`)

What it asks for: shortest waits and stays, fewest walk-outs and least boarding without spending more on labour or staffed space, with safety no worse than current practice, no extra diversion, bounded overtime and no extra transfers out.

**Selected policy: `tuned_same_budget`** — Tuned heuristic: Same budget, better flow (tuned heuristic). Best constrained score among the candidates that met every constraint on the validation seeds.

In a simulated twin calibrated to RWJUH New Brunswick (model)'s publicly reported figures, Tuned heuristic: Same budget, better flow (`tuned_same_budget`, tuned heuristic) cut mean door-to-provider wait by 17.0% (95% CI 9.1 to 26.2); cut median ED length of stay by 4.5% (95% CI 3.3 to 5.7); cut walk-outs (left without being seen) by 14.6% (95% CI 8.0 to 22.7); cut boarding hours by 59.6% (95% CI 36.9 to 71.4), with labour cost -4.0% vs baseline (95% CI -5.4 to -2.7; within budget), no ambulance diversion beyond baseline and deaths per 10,000 arrivals -0.27 (95% CI -0.43 to -0.14). Every constraint was met on held-out data. The improvement with budget constraints met holds in 20/24 plausible twins of the calibration ensemble (worst twin: objective at 97.6% of its baseline). All figures are simulated and not validated on the hospital's operational data.

### Held-out result, normal operations (24 twin(s) x 32 seeds x 30 days, paired against the baseline)

| Metric | Baseline | Policy | Change (95% CI) | % change (95% CI) | Reading |
|---|---|---|---|---|---|
| Median ED length of stay (min) | 203.7 | 194.6 | -9.1 (-11.8 to -6.7) | -4.5% (-5.7 to -3.3) | better |
| Mean door-to-provider wait (min) | 16.7 | 13.9 | -2.8 (-4.9 to -1.4) | -17.0% (-26.2 to -9.1) | better |
| 95th-percentile door-to-provider wait (min) | 39.0 | 27.3 | -11.7 (-21.9 to -4.5) | -30.1% (-44.4 to -14.2) | better |
| Left without being seen (% of arrivals) | 0.85 | 0.73 | -0.12 (-0.20 to -0.07) | -14.6% (-22.7 to -8.0) | better |
| Boarding (patient-hours/day) | 17.3 | 7.0 | -10.3 (-21.6 to -3.2) | -59.6% (-71.4 to -36.9) | better |
| Labour cost ($k/day) | 107.63 | 103.30 | -4.33 (-5.98 to -2.80) | -4.0% (-5.4 to -2.7) | better |
| Labour + fixed staffed-space cost ($k/day) | 500.2 | 496.0 | -4.2 (-5.8 to -2.7) | -0.8% (-1.2 to -0.5) | better |
| Margin ($k/day) | 411.9 | 414.9 | +3.0 (+0.7 to +5.4) | +0.7% (+0.2 to +1.3) | better |
| Deaths (per 10,000 arrivals) | 4.89 | 4.62 | -0.27 (-0.43 to -0.14) | -5.5% (-8.6 to -3.1) | better |
| Adverse events (per day) | 0.423 | 0.375 | -0.048 (-0.064 to -0.032) | -11.3% (-15.0 to -7.6) | better |
| ESI 1-2 patients waiting (patient-hours/day) | 4.83 | 4.02 | -0.81 (-1.17 to -0.48) | -16.8% (-22.8 to -10.6) | better |
| Ambulance diversion (h/day) | 0.00 | 0.00 | +0.00 (+0.00 to +0.00) | n/a | no significant change |
| Overtime (h/day) | 0.00 | 0.05 | +0.05 (+0.00 to +0.13) | n/a | worse |
| Transfers out (per day) | 2.26 | 2.26 | +0.01 (+0.00 to +0.01) | +0.3% (+0.1 to +0.5) | worse |

Minimised quantity (flow index) as a share of baseline: **78.7%** (95% CI 74.1 to 84.9). Flow index = 0.3 x wait_mean_min + 0.3 x ed_los_median_min + 0.2 x lwbs_rate + 0.2 x boarding_hours_per_day, each as policy / baseline.

### Constraints (hard check on held-out data): **FEASIBLE**

| Constraint | Baseline | Limit | Policy | Met | Status |
|---|---|---|---|---|---|
| labour cost per day | 107,630.211 | 107,630.211 | 103,299.438 | yes | better |
| labour + fixed staffed-space cost per day | 500,208.125 | 500,208.125 | 496,010.219 | yes | better |
| deaths per 10,000 arrivals | 4.891 | 4.891 | 4.623 | yes | better |
| adverse events per day | 0.423 | 0.423 | 0.375 | yes | better |
| hours ESI 1-2 patients spend waiting, per day | 4.829 | 4.829 | 4.017 | yes | better |
| ambulance diversion hours per day | 0.000 | 0.000 | 0.000 | yes | no worse |
| overtime hours per day (cap: baseline + 1% of staff-hours) | 0.000 | 15.988 | 0.055 | yes | no worse |
| transfers out per day | 2.257 | 2.302 | 2.263 | yes | no worse |

### Robustness to what public data cannot identify

Improvement with the hard constraints met holds in **20/24** ensemble members (18/24 when the rare-event safety point estimates must also be no worse). Worst member: #20, minimised quantity at 97.6% of its own baseline (mean wait 14.6 -> 14.6 min, median stay 199 -> 197 min, labour 104.9 -> 96.7 $k/day; violated: deaths_per_10k, adverse_events_per_day, hi_acuity_wait_hours_per_day). holds = the minimised quantity is below baseline AND every hard constraint (budget, diversion, overtime, transfers; for the cost objective also every flow metric) is met on that member's mean over the held-out seeds; holds_with_safety additionally requires the rare-event safety point estimates to be no worse.

### Same policy under a flu surge (held-out; feasibility: **NOT FEASIBLE: transfers_per_day**; holds in 9/24 twins)

| Metric | Baseline | Policy | Change (95% CI) | % change (95% CI) | Reading |
|---|---|---|---|---|---|
| Median ED length of stay (min) | 245.7 | 208.0 | -37.7 (-50.2 to -27.3) | -15.3% (-19.2 to -11.7) | better |
| Mean door-to-provider wait (min) | 42.9 | 16.0 | -26.9 (-41.1 to -15.5) | -62.7% (-70.9 to -50.4) | better |
| 95th-percentile door-to-provider wait (min) | 181.0 | 36.4 | -144.6 (-225.9 to -78.8) | -79.9% (-85.4 to -70.2) | better |
| Left without being seen (% of arrivals) | 2.47 | 0.83 | -1.64 (-2.59 to -0.90) | -66.3% (-75.4 to -52.5) | better |
| Boarding (patient-hours/day) | 193.1 | 45.4 | -147.6 (-215.1 to -84.6) | -76.5% (-81.5 to -71.6) | better |
| Labour cost ($k/day) | 106.21 | 102.95 | -3.25 (-4.96 to -1.71) | -3.1% (-4.6 to -1.6) | better |
| Labour + fixed staffed-space cost ($k/day) | 498.8 | 495.7 | -3.1 (-4.8 to -1.6) | -0.6% (-1.0 to -0.3) | better |
| Margin ($k/day) | 462.9 | 491.4 | +28.5 (+15.6 to +43.6) | +6.2% (+3.3 to +9.6) | better |
| Deaths (per 10,000 arrivals) | 7.75 | 5.18 | -2.57 (-4.03 to -1.47) | -33.1% (-44.4 to -22.0) | better |
| Adverse events (per day) | 0.869 | 0.531 | -0.339 (-0.495 to -0.211) | -39.0% (-47.8 to -29.2) | better |
| ESI 1-2 patients waiting (patient-hours/day) | 9.18 | 5.14 | -4.04 (-5.43 to -2.82) | -44.0% (-50.9 to -35.8) | better |
| Ambulance diversion (h/day) | 0.00 | 0.00 | +0.00 (+0.00 to +0.00) | n/a | no significant change |
| Overtime (h/day) | 0.00 | 0.33 | +0.33 (+0.12 to +0.60) | n/a | worse |
| Transfers out (per day) | 2.39 | 2.45 | +0.06 (+0.03 to +0.09) | +2.4% (+1.4 to +3.7) | worse |

- Stress scenario `discharge_delays` (8 seeds x 30 d x 4 twin(s)): mean wait -71.5% (-84.8 to -19.7), median stay -11.5% (-22.4 to -3.0), walk-outs -75.7% (-87.5 to -20.1), labour -2.5% (-6.1 to +1.3); NOT feasible: transfers_per_day.
- Stress scenario `nursing_absences` (8 seeds x 30 d x 4 twin(s)): mean wait -16.5% (-37.4 to +5.0), median stay -2.4% (-6.2 to +0.0), walk-outs -12.7% (-36.7 to +7.3), labour -3.7% (-7.1 to -0.0); feasible.
- Stress scenario `imaging_outage` (8 seeds x 30 d x 4 twin(s)): mean wait -17.1% (-37.5 to +3.7), median stay -2.6% (-6.1 to -0.5), walk-outs -13.7% (-37.2 to +4.7), labour -3.8% (-7.2 to -0.1); feasible.

### Annualised translation (simulated)

Annual volume: 81,126 ED visits (CMS-reported `ed_visits_per_year_cms`, counted per CMS certification number, which can cover more than one campus [81126 visits / 366 days = 222 per day. The hospital's own page says 'more than 95,000 emergency and trauma patients a year' (ed_visits_per_year); the two differ in year and possibly in what is counted (the CCN-level count vs. a marketing figure).]); simulated baseline 222 arrivals/day; volume factor 1.003. 30 simulated days of the `normal_week` scenario scaled to a year (x365) and to the hospital's measured annual volume (volume factor); seasonality and surge weeks are not in this figure. Simulated.

| Quantity | Per year | 95% CI |
|---|---|---|
| Patient-hours in the ED saved (patient-hours/yr) | +20,995 | +14,128 to +29,125 |
| Patient-hours waiting for a provider saved (patient-hours/yr) | +3,831 | +1,857 to +6,651 |
| Fewer walk-outs (left without being seen) (patients/yr) | +101 | +54 to +164 |
| Boarding patient-hours saved (patient-hours/yr) | +3,775 | +1,175 to +7,908 |
| Labour cost change ($/yr) | -1,580,729 | -2,183,126 to -1,021,401 |
| Margin change (assumed payer revenue) ($/yr) | +1,085,953 | +270,666 to +1,963,998 |

### What the hospital would do differently (from the settings in force on the held-out runs)

- Providers scheduled per shift (mean people, baseline -> policy): day 07-15: 15.0 -> 15.0; evening 15-23: 15.0 -> 18.0; night 23-07: 7.0 -> 7.0. Scheduled provider-hours per day 296 -> 320.
- Nurses scheduled per shift (mean people, baseline -> policy): day 07-15: 37.0 -> 18.0; evening 15-23: 37.0 -> 37.0; night 23-07: 18.0 -> 18.0. Scheduled nurse-hours per day 736 -> 584.
- Triage stations staffed: 2.7 -> 3.0 on average.
- Provider time between new patients and dispositions: baseline favor new 75%, balanced 17%, favor dispositions 8% -> policy favor new 100%.
- Ward early discharge rounds (share of days): baseline standard 100% -> policy standard 91%, early rounds 9%.
- Overtime call-in requests: 0.00 -> 0.13 per day (one rn 0.13/day); most often at 13:00, 14:00, 15:00.
- Ambulance diversion: unchanged from baseline (locked).
- Admission cap: unchanged from baseline (locked).
- Staffing reacts to yesterday's volume: +0.05 provider levels and +0.01 nurse levels per 10% of arrivals above a typical day.
- Staffing follows the published weekday arrival pattern: +0.05 provider levels and +0.04 nurse levels per 5% that the weekday runs above average.
- Call-in triggers: a nurse when patients waiting for a bay exceed 73% of the ED's bay count, a provider when patients waiting for a provider exceed 37% of it; thresholds drop by up to 10% when the next hour is forecast 50% busier than typical; also a nurse when bay occupancy exceeds 98% with a typical-or-busier hour ahead.
- Hallway overflow opens when patients waiting for a bay exceed 41% of the bay count (second tier at 86%).
- Early ward discharge rounds are triggered when ward occupancy exceeds 97% or boarders exceed 28% of the bay count at midnight.
- Provider time shifts to new patients when those waiting for a provider exceed 46% of the bay count.
- People counts above use ensemble member 0's level-to-people ladder (the point calibration); the ladders differ between ensemble members, the policy's staffing LEVELS are the same in all of them.

### Every candidate for this objective (held-out, normal operations; losses and infeasible results included)

| Manager | Kind | Selected on validation | Minimised quantity vs baseline (95% CI) | Mean wait | Median stay | LWBS | Labour cost | Feasible | Violated | Stale |
|---|---|---|---|---|---|---|---|---|---|---|
| `tuned_same_budget` | tuned_heuristic | yes | 78.7% (74.1 to 84.9) | -17.0% (-26.2 to -9.1) | -4.5% (-5.7 to -3.3) | -14.6% (-22.7 to -8.0) | -4.0% (-5.4 to -2.7) | yes | - | no |
| `ppo_same_budget` | learned | no | 80.8% (76.0 to 86.9) | -16.3% (-25.6 to -8.4) | -3.8% (-4.9 to -2.8) | -14.1% (-22.4 to -7.4) | -5.2% (-6.6 to -3.9) | yes | - | yes |

### Did the learned agent (PPO) beat the tuned heuristic?

- `ppo_same_budget` loses to `tuned_same_budget` on the constrained score, normal_week: -0.0209 (95% CI -0.0293 to -0.0128); `ppo_same_budget` feasible: yes, `tuned_same_budget` feasible: yes.
- `ppo_same_budget` loses to `tuned_same_budget` on the constrained score, flu_surge: -0.0292 (95% CI -0.0522 to -0.0157); `ppo_same_budget` feasible: no, `tuned_same_budget` feasible: no.

Selection on validation seeds (never the held-out seeds):

| Manager | Validation score | Feasible on validation | Violated |
|---|---|---|---|
| `tuned_same_budget` | +0.3486 | yes | - |
| `ppo_same_budget` | +0.3258 | yes | - |

## Objective: Same service, lower cost (`same_service_lower_cost`)

What it asks for: lowest labour cost with door-to-provider wait (mean and 95th percentile), median ED length of stay, walk-outs, boarding and safety all no worse than current practice, no extra diversion, bounded overtime, no extra transfers out.

**Selected policy: `ppo_same_service`** — Learned (PPO, cloned from tuned heuristic then fine-tuned): Same service, lower cost (learned). Best constrained score among the candidates that met every constraint on the validation seeds.

In a simulated twin calibrated to RWJUH New Brunswick (model)'s publicly reported figures, Learned (PPO, cloned from tuned heuristic then fine-tuned): Same service, lower cost (`ppo_same_service`, learned) cut labour cost by 2.9% (95% CI 1.5 to 4.3); it cut mean door-to-provider wait by 27.1% (95% CI 20.2 to 35.2); cut median ED length of stay by 9.3% (95% CI 8.1 to 10.7); cut walk-outs (left without being seen) by 25.8% (95% CI 19.8 to 33.2); cut boarding hours by 21.8% (95% CI 12.8 to 27.4), with no ambulance diversion beyond baseline and deaths per 10,000 arrivals -0.27 (95% CI -0.43 to -0.15). Every constraint was met on held-out data. The improvement with budget constraints met holds in 15/24 plausible twins of the calibration ensemble (worst twin: objective at 102.0% of its baseline). All figures are simulated and not validated on the hospital's operational data.

**STALE: this policy was tuned / trained against another calibration or simulator behaviour. Re-run `rl/scripts/run_hospital.sh`.**

### Held-out result, normal operations (24 twin(s) x 32 seeds x 30 days, paired against the baseline)

| Metric | Baseline | Policy | Change (95% CI) | % change (95% CI) | Reading |
|---|---|---|---|---|---|
| Median ED length of stay (min) | 203.7 | 184.7 | -19.0 (-22.2 to -16.2) | -9.3% (-10.7 to -8.1) | better |
| Mean door-to-provider wait (min) | 16.7 | 12.2 | -4.5 (-6.6 to -3.1) | -27.1% (-35.2 to -20.2) | better |
| 95th-percentile door-to-provider wait (min) | 39.0 | 20.4 | -18.6 (-28.4 to -11.5) | -47.6% (-58.2 to -36.1) | better |
| Left without being seen (% of arrivals) | 0.85 | 0.63 | -0.22 (-0.29 to -0.16) | -25.8% (-33.2 to -19.8) | better |
| Boarding (patient-hours/day) | 17.3 | 13.5 | -3.8 (-7.9 to -1.2) | -21.8% (-27.4 to -12.8) | better |
| Labour cost ($k/day) | 107.63 | 104.50 | -3.13 (-4.75 to -1.57) | -2.9% (-4.3 to -1.5) | better |
| Labour + fixed staffed-space cost ($k/day) | 500.2 | 491.6 | -8.6 (-10.2 to -7.0) | -1.7% (-2.0 to -1.4) | better |
| Margin ($k/day) | 411.9 | 416.4 | +4.6 (+2.7 to +6.6) | +1.1% (+0.6 to +1.6) | better |
| Deaths (per 10,000 arrivals) | 4.89 | 4.62 | -0.27 (-0.43 to -0.15) | -5.6% (-9.0 to -3.1) | better |
| Adverse events (per day) | 0.423 | 0.360 | -0.063 (-0.080 to -0.047) | -15.0% (-18.9 to -11.3) | better |
| ESI 1-2 patients waiting (patient-hours/day) | 4.83 | 3.87 | -0.96 (-1.33 to -0.64) | -19.9% (-25.6 to -14.1) | better |
| Ambulance diversion (h/day) | 0.00 | 0.00 | +0.00 (+0.00 to +0.00) | n/a | no significant change |
| Overtime (h/day) | 0.00 | 0.05 | +0.05 (+0.01 to +0.11) | n/a | worse |
| Transfers out (per day) | 2.26 | 2.27 | +0.01 (+0.01 to +0.02) | +0.5% (+0.3 to +0.7) | worse |

Minimised quantity (labour cost) as a share of baseline: **97.1%** (95% CI 95.7 to 98.5). 

### Constraints (hard check on held-out data): **FEASIBLE**

| Constraint | Baseline | Limit | Policy | Met | Status |
|---|---|---|---|---|---|
| mean door-to-provider wait | 16.707 | 16.707 | 12.174 | yes | better |
| 95th-percentile door-to-provider wait | 38.971 | 38.971 | 20.417 | yes | better |
| median ED length of stay | 203.704 | 203.704 | 184.668 | yes | better |
| left-without-being-seen rate | 0.009 | 0.009 | 0.006 | yes | better |
| boarding patient-hours per day | 17.297 | 17.297 | 13.526 | yes | better |
| labour + fixed staffed-space cost per day | 500,208.125 | 500,208.125 | 491,647.094 | yes | better |
| deaths per 10,000 arrivals | 4.891 | 4.891 | 4.619 | yes | better |
| adverse events per day | 0.423 | 0.423 | 0.360 | yes | better |
| hours ESI 1-2 patients spend waiting, per day | 4.829 | 4.829 | 3.867 | yes | better |
| ambulance diversion hours per day | 0.000 | 0.000 | 0.000 | yes | no worse |
| overtime hours per day (cap: baseline + 1% of staff-hours) | 0.000 | 15.988 | 0.047 | yes | no worse |
| transfers out per day | 2.257 | 2.302 | 2.268 | yes | no worse |

### Robustness to what public data cannot identify

Improvement with the hard constraints met holds in **15/24** ensemble members (14/24 when the rare-event safety point estimates must also be no worse). Worst member: #14, minimised quantity at 102.0% of its own baseline (mean wait 15.4 -> 11.9 min, median stay 200 -> 188 min, labour 108.8 -> 111.0 $k/day). holds = the minimised quantity is below baseline AND every hard constraint (budget, diversion, overtime, transfers; for the cost objective also every flow metric) is met on that member's mean over the held-out seeds; holds_with_safety additionally requires the rare-event safety point estimates to be no worse.

### Same policy under a flu surge (held-out; feasibility: **FEASIBLE**; holds in 9/24 twins)

| Metric | Baseline | Policy | Change (95% CI) | % change (95% CI) | Reading |
|---|---|---|---|---|---|
| Median ED length of stay (min) | 245.7 | 206.7 | -39.0 (-48.5 to -30.5) | -15.9% (-18.8 to -13.0) | better |
| Mean door-to-provider wait (min) | 42.9 | 25.4 | -17.5 (-24.0 to -11.7) | -40.7% (-48.9 to -33.0) | better |
| 95th-percentile door-to-provider wait (min) | 181.0 | 95.5 | -85.5 (-119.5 to -55.8) | -47.2% (-59.3 to -37.1) | better |
| Left without being seen (% of arrivals) | 2.47 | 1.47 | -1.00 (-1.37 to -0.68) | -40.5% (-48.0 to -33.4) | better |
| Boarding (patient-hours/day) | 193.1 | 151.6 | -41.4 (-61.4 to -24.2) | -21.5% (-26.5 to -17.2) | better |
| Labour cost ($k/day) | 106.21 | 103.45 | -2.76 (-4.40 to -1.21) | -2.6% (-4.0 to -1.2) | better |
| Labour + fixed staffed-space cost ($k/day) | 498.8 | 490.9 | -7.9 (-9.5 to -6.3) | -1.6% (-1.9 to -1.3) | better |
| Margin ($k/day) | 462.9 | 473.2 | +10.3 (+5.9 to +15.2) | +2.2% (+1.3 to +3.4) | better |
| Deaths (per 10,000 arrivals) | 7.75 | 6.27 | -1.48 (-2.18 to -0.94) | -19.1% (-24.8 to -13.2) | better |
| Adverse events (per day) | 0.869 | 0.645 | -0.224 (-0.301 to -0.159) | -25.8% (-30.5 to -20.8) | better |
| ESI 1-2 patients waiting (patient-hours/day) | 9.18 | 6.06 | -3.12 (-4.04 to -2.31) | -34.0% (-40.0 to -27.7) | better |
| Ambulance diversion (h/day) | 0.00 | 0.00 | +0.00 (+0.00 to +0.00) | n/a | no significant change |
| Overtime (h/day) | 0.00 | 0.99 | +0.99 (+0.49 to +1.64) | n/a | worse |
| Transfers out (per day) | 2.39 | 2.43 | +0.04 (+0.03 to +0.06) | +1.8% (+1.2 to +2.4) | worse |

- Stress scenario `discharge_delays` (8 seeds x 30 d x 4 twin(s)): mean wait -26.0% (-40.7 to -8.4), median stay -6.4% (-11.8 to -1.8), walk-outs -27.9% (-46.7 to -10.7), labour -2.2% (-6.1 to +1.9); NOT feasible: transfers_per_day.
- Stress scenario `nursing_absences` (8 seeds x 30 d x 4 twin(s)): mean wait -27.0% (-44.3 to -9.0), median stay -7.2% (-10.9 to -4.2), walk-outs -23.5% (-43.6 to -6.0), labour -2.8% (-6.3 to +1.0); feasible.
- Stress scenario `imaging_outage` (8 seeds x 30 d x 4 twin(s)): mean wait -27.5% (-44.4 to -10.2), median stay -7.2% (-11.0 to -4.4), walk-outs -23.9% (-43.7 to -7.2), labour -2.9% (-6.4 to +0.9); feasible.

### Annualised translation (simulated)

Annual volume: 81,126 ED visits (CMS-reported `ed_visits_per_year_cms`, counted per CMS certification number, which can cover more than one campus [81126 visits / 366 days = 222 per day. The hospital's own page says 'more than 95,000 emergency and trauma patients a year' (ed_visits_per_year); the two differ in year and possibly in what is counted (the CCN-level count vs. a marketing figure).]); simulated baseline 222 arrivals/day; volume factor 1.003. 30 simulated days of the `normal_week` scenario scaled to a year (x365) and to the hospital's measured annual volume (volume factor); seasonality and surge weeks are not in this figure. Simulated.

| Quantity | Per year | 95% CI |
|---|---|---|
| Patient-hours in the ED saved (patient-hours/yr) | +34,095 | +27,485 to +41,565 |
| Patient-hours waiting for a provider saved (patient-hours/yr) | +6,539 | +4,358 to +9,549 |
| Fewer walk-outs (left without being seen) (patients/yr) | +178 | +132 to +240 |
| Boarding patient-hours saved (patient-hours/yr) | +1,381 | +441 to +2,897 |
| Labour cost change ($/yr) | -1,143,510 | -1,733,510 to -573,764 |
| Margin change (assumed payer revenue) ($/yr) | +1,661,299 | +973,709 to +2,399,314 |

### What the hospital would do differently (from the settings in force on the held-out runs)

- Providers scheduled per shift (mean people, baseline -> policy): day 07-15: 15.0 -> 16.0; evening 15-23: 15.0 -> 17.9 (by weekday 17.5-18.0); night 23-07: 7.0 -> 7.0. Scheduled provider-hours per day 296 -> 327.
- Nurses scheduled per shift (mean people, baseline -> policy): day 07-15: 37.0 -> 18.0; evening 15-23: 37.0 -> 37.0; night 23-07: 18.0 -> 18.0. Scheduled nurse-hours per day 736 -> 584.
- Triage stations staffed: 2.7 -> 3.0 on average.
- Provider time between new patients and dispositions: baseline favor new 75%, balanced 17%, favor dispositions 8% -> policy favor new 100%.
- Fast track (share of hours): baseline open 100% -> policy closed 100%.
- Overtime call-in requests: 0.00 -> 0.09 per day (one rn 0.09/day); most often at 13:00, 14:00, 15:00.
- Ambulance diversion: unchanged from baseline (locked).
- Admission cap: unchanged from baseline (locked).
- People counts above use ensemble member 0's level-to-people ladder (the point calibration); the ladders differ between ensemble members, the policy's staffing LEVELS are the same in all of them.

### Every candidate for this objective (held-out, normal operations; losses and infeasible results included)

| Manager | Kind | Selected on validation | Minimised quantity vs baseline (95% CI) | Mean wait | Median stay | LWBS | Labour cost | Feasible | Violated | Stale |
|---|---|---|---|---|---|---|---|---|---|---|
| `tuned_same_service` | tuned_heuristic | no | 102.1% (101.8 to 102.4) | -16.6% (-25.8 to -9.0) | -3.4% (-4.3 to -2.6) | -14.4% (-22.4 to -8.2) | +2.1% (+1.8 to +2.4) | **no** | operating_cost_per_day | no |
| `ppo_same_service` | learned | yes | 97.1% (95.7 to 98.5) | -27.1% (-35.2 to -20.2) | -9.3% (-10.7 to -8.1) | -25.8% (-33.2 to -19.8) | -2.9% (-4.3 to -1.5) | yes | - | yes |

### Did the learned agent (PPO) beat the tuned heuristic?

- `ppo_same_service` beats `tuned_same_service` on the constrained score, normal_week: +0.0979 (95% CI +0.0811 to +0.1161); `ppo_same_service` feasible: yes, `tuned_same_service` feasible: no.
- `ppo_same_service` beats `tuned_same_service` on the constrained score, flu_surge: +0.0989 (95% CI +0.0625 to +0.1491); `ppo_same_service` feasible: yes, `tuned_same_service` feasible: no.

Selection on validation seeds (never the held-out seeds):

| Manager | Validation score | Feasible on validation | Violated |
|---|---|---|---|
| `tuned_same_service` | -0.0925 | no | operating_cost_per_day |
| `ppo_same_service` | +0.0216 | yes | - |

## Context: unconstrained reference managers on the same held-out runs (not candidates)

| Manager | Mean wait | Median stay | LWBS | Labour cost | Diversion h/day |
|---|---|---|---|---|---|
| `rule_based` | -2.2% (-12.7 to +6.5) | -1.2% (-2.3 to -0.3) | +1.2% (-8.5 to +8.9) | +13.9% (+12.4 to +15.5) | 0.00 |
| `tuned_min_wait` | -25.7% (-33.8 to -18.6) | -12.9% (-14.4 to -11.5) | -23.8% (-30.6 to -18.3) | +27.8% (+26.5 to +29.1) | 0.00 |
| `tuned_balanced` | -3.0% (-22.8 to +26.9) | -6.7% (-9.0 to -4.0) | -6.4% (-21.7 to +14.4) | +5.4% (+3.3 to +7.4) | 0.21 |

## Protocol

- Baseline = `fixed`: Current practice (calibrated baseline actions). Baseline actions (point calibration): priority_rule=acuity_first, overflow_bays=none, divert=off, call_in=none, fast_track=open, provider_split=favor_new, md_day=lvl2, md_evening=lvl3, md_night=lvl1, rn_day=lvl2, rn_evening=lvl2, rn_night=lvl1, triage_nurses=three, admission_cap=none, discharge_push=standard, agency_contract=none, imaging_hours=extended, bays_delta=hold, ward_beds_delta=hold, equipment_buy=none, relocate=none, headcount=hold.
- Held-out: seeds 9000000..9000031 (32) x 24 ensemble member(s) x 30 days per scenario; every manager and the baseline run on the same seeds inside the same member (common random numbers, paired).
- Selection: seeds 950000..950011 x 8 member(s) x 30 days (validation range; tuning uses 200,000+, training 400,000+).
- Intervals: 95% percentile bootstrap (2000 resamples) over ensemble members and seeds; % change = ratio of means.
- 'Median ED length of stay' is the mean over episodes of each 30-day episode's median (histogram estimate, 5-minute bins).
- Constraints use the point estimates; overtime may exceed baseline by at most 1% of baseline staff-hours per day; transfers out by at most 2%. `divert` and `admission_cap` are locked at the baseline for operator-objective managers.
- Structural / capital heads (bays, beds, scanners, relocation, headcount) are outside these objectives and stay at baseline.

## Caveats

- Everything here is SIMULATED. No number is a measurement of the real hospital and none is a forecast of what would happen there.
- The twin is calibrated to public aggregates only (CMS-reported and other published figures listed in the hospital's catalog file). Parameters those figures do not pin down (service-time shapes, patience, staffing rosters, ward capacity share, cost allocation) are assumed; the calibration ensemble spans the sets found consistent with the public figures, and the 'holds in k/N twins' line is the only robustness statement made about them.
- The baseline ('current practice') is the calibration's reconstruction of the hospital's staffing and operating rules from public data. The real roster, call-in practice, fast-track hours and bed management are not known to us; if the real baseline is better than the reconstructed one, the real improvement is smaller.
- Not validated on the hospital's operational data. To validate: (1) one year of de-identified ED timestamps (arrival, triage, first provider, disposition, departure), acuity and disposition; (2) the actual staffing roster by hour and role, call-in and overtime logs; (3) inpatient bed occupancy and boarding logs; (4) the ED cost centre's labour ledger. With those, refit the twin, check it reproduces held-out weeks, and re-run this report before any operational change.
- Safety figures (deaths, adverse events) come from literature hazard rates applied to simulated waiting; they are rare events with wide intervals and are a guard-rail in the optimisation, not a clinical prediction.
- Money: labour cost uses published wage levels with assumed benefit, overtime and agency multipliers; margin additionally depends on assumed payer revenue and is reported for completeness only.
- The policy acts hourly on the simulator's observation (queue lengths, occupancy, arrivals in the last day, a next-hour arrival forecast). Running it in a real ED needs those signals live, and staff rules (minimum ratios, contract terms, call-in willingness) that the twin does not model.
