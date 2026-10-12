# Learned per-patient dispatch: rwjuh_nb (SIMULATED)

Every number below is simulated. Nothing here is a measurement of the real hospital.

Generated 2026-10-11T05:28:38+0000. Held-out seeds 9,000,000..9,000,023 (24 seeds) x 30 days x 8 calibration-ensemble members x ['normal_week', 'flu_surge']. every arm runs the same seeds in the same ensemble member; differences are paired per episode. Intervals: 95% two-way bootstrap over ensemble members and seeds; `(ns)` = the interval contains zero.

## Arms

- `fixed`: the calibrated baseline (current practice), every lever at its default.
- `rule:<priority>+<split>`: baseline levers with a hard-coded queue rule and provider split forced (4 x 3 = 12 arms). Best by patient index at the baseline split (`favor_new`): `rule:acuity_first+favor_new`; best over all 12: `rule:acuity_first+favor_new`; best by flow index: `rule:acuity_first+favor_new`. picked on the held-out episodes themselves, which favours the hard-coded rules.
- `tuned_same_budget`: the tuned rule manager for same_budget_better_flow (current for this calibration).
- `dispatch_dispatch_only_*`: learned per-patient index, every lever at the baseline (isolates dispatch), searched on the patient index.
- `dispatch_dispatch_flow_*`: the same, searched on the operator objective same_budget_better_flow (flow index + constraints).
- `dispatch_joint_*`: learned index plus re-tuned rule-manager parameters on same_budget_better_flow.
- `ablate:<joint>:levers_only`: the joint policy's lever parameters with the hard-coded queue rule they select (no learned index); `ablate:<joint>:index_on_tuned`: the tuned rule manager's levers with the joint policy's learned index.

  - `dispatch_dispatch_flow_context`: context index, unified provider queue = True, stale = False
  - `dispatch_dispatch_flow_linear`: linear index, unified provider queue = True, stale = False
  - `dispatch_dispatch_flow_mlp`: mlp index, unified provider queue = True, stale = False
  - `dispatch_dispatch_only_linear`: linear index, unified provider queue = False, stale = False
  - `dispatch_joint_linear`: linear index, unified provider queue = False, stale = False

## normal_week

### Means

| Metric | `fixed` | `rule:acuity_first+favor_new` | `tuned_same_budget` | `dispatch_dispatch_flow_context` | `dispatch_dispatch_flow_linear` | `dispatch_dispatch_flow_mlp` | `dispatch_dispatch_only_linear` | `dispatch_joint_linear` | `ablate:dispatch_joint_linear:levers_only` | `ablate:dispatch_joint_linear:index_on_tuned` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 18.7 | 15.3 | 14.0 | 15.2 | 15.0 | 15.0 | 18.7 | 14.0 | 14.0 | 13.9 |
| 95th-percentile wait (min) | 50 | 32 | 28 | 31 | 30 | 30 | 50 | 27 | 28 | 27 |
| Median ED length of stay (min) | 204 | 205 | 194 | 191 | 190 | 191 | 204 | 186 | 194 | 186 |
| Mean ED length of stay (min) | 252 | 253 | 234 | 248 | 247 | 248 | 252 | 232 | 234 | 232 |
| ED census (patient-hours per day) (patient-h/day) | 922 | 928 | 860 | 910 | 909 | 911 | 922 | 854 | 860 | 854 |
| Left without being seen (% of arrivals) | 0.87 | 0.74 | 0.69 | 0.75 | 0.72 | 0.73 | 0.87 | 0.69 | 0.69 | 0.69 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 5.08 | 4.62 | 4.13 | 4.49 | 4.52 | 4.50 | 5.08 | 4.10 | 4.13 | 4.10 |
| Deaths (per 10,000 arrivals) | 5.29 | 5.20 | 4.90 | 5.18 | 5.27 | 5.19 | 5.29 | 4.96 | 4.88 | 4.97 |
| Adverse events (per day) | 0.43 | 0.42 | 0.37 | 0.41 | 0.42 | 0.42 | 0.43 | 0.37 | 0.37 | 0.37 |
| Boarding (patient-h/day) | 15.7 | 15.9 | 7.0 | 15.5 | 15.6 | 15.5 | 15.7 | 5.8 | 5.8 | 7.0 |
| Labour cost ($k/day) | 105.85 | 105.85 | 102.37 | 105.85 | 105.85 | 105.85 | 105.85 | 102.22 | 102.22 | 102.36 |
| Mean wait, triage ESI 1 (min) | 9.6 | 9.1 | 8.6 | 9.0 | 9.0 | 9.1 | 9.6 | 8.5 | 8.6 | 8.5 |
| Mean wait, triage ESI 2 (min) | 11.9 | 11.3 | 10.6 | 11.1 | 11.1 | 11.1 | 11.9 | 10.6 | 10.6 | 10.6 |
| Mean wait, triage ESI 3 (min) | 16.0 | 14.4 | 13.1 | 14.4 | 14.2 | 14.3 | 16.0 | 13.0 | 13.1 | 13.0 |
| Mean wait, triage ESI 4 (min) | 25.7 | 19.0 | 17.4 | 18.1 | 18.3 | 18.1 | 25.7 | 17.3 | 17.4 | 17.3 |
| Mean wait, triage ESI 5 (min) | 38.1 | 22.3 | 19.8 | 25.8 | 22.0 | 21.7 | 38.1 | 19.8 | 19.8 | 19.8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 5.07 | 4.60 | 4.08 | 4.48 | 4.49 | 4.47 | 5.07 | 4.06 | 4.09 | 4.05 |
| ESI 3 waiting (patient-h/day) | 19.2 | 16.4 | 14.1 | 16.5 | 16.1 | 16.4 | 19.2 | 14.1 | 14.1 | 14.1 |
| ESI 4-5 waiting (patient-h/day) | 27.8 | 18.5 | 16.3 | 18.2 | 18.1 | 17.8 | 27.8 | 16.6 | 16.3 | 16.6 |
| Walk-outs, triage ESI 3 (per day) | 0.89 | 0.83 | 0.77 | 0.85 | 0.82 | 0.83 | 0.89 | 0.77 | 0.77 | 0.77 |
| Walk-outs, triage ESI 4 (per day) | 0.69 | 0.55 | 0.51 | 0.53 | 0.53 | 0.53 | 0.69 | 0.52 | 0.51 | 0.52 |
| Walk-outs, triage ESI 5 (per day) | 0.27 | 0.18 | 0.16 | 0.21 | 0.17 | 0.17 | 0.27 | 0.16 | 0.16 | 0.16 |
| Patient index (1 = baseline) | 1.000 | 0.914 | 0.831 | 0.904 | 0.899 | 0.897 | 1.000 | 0.830 | 0.833 | 0.829 |
| Flow index (1 = baseline) | 1.000 | 0.945 | 0.802 | 0.922 | 0.911 | 0.914 | 1.000 | 0.776 | 0.788 | 0.790 |

### Paired differences (a minus b; negative = a is lower)

**`dispatch_dispatch_flow_context` minus `fixed`** (patient index 0.904 vs 1.000; flow index 0.922 vs 1.000)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 15.2 | 18.7 | -3.52 [-8.34, 0.01] (ns) | 5 / 3 of 8 |
| 95th-percentile wait (min) | 31 | 50 | -19.2 [-44.1, -0.7] | 7 / 1 of 8 |
| Median ED length of stay (min) | 191 | 204 | -12.9 [-17.2, -9.1] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 248 | 252 | -3.9 [-7.1, -0.8] | 7 / 1 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 910 | 922 | -12.2 [-26.3, 1.6] (ns) | 6 / 2 of 8 |
| Left without being seen (% of arrivals) | 0.75 | 0.87 | -0.125 [-0.315, 0.019] (ns) | 4 / 4 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 4.49 | 5.08 | -0.592 [-1.206, -0.128] | 8 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 5.18 | 5.29 | -0.111 [-0.332, 0.093] (ns) | 5 / 3 of 8 |
| Adverse events (per day) | 0.41 | 0.43 | -0.015 [-0.032, -0.001] | 6 / 2 of 8 |
| Boarding (patient-h/day) | 15.5 | 15.7 | -0.23 [-1.35, 0.56] (ns) | 4 / 4 of 8 |
| Labour cost ($k/day) | 105.85 | 105.85 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 1 (min) | 9.0 | 9.6 | -0.57 [-1.30, -0.03] | 7 / 1 of 8 |
| Mean wait, triage ESI 2 (min) | 11.1 | 11.9 | -0.81 [-1.64, -0.18] | 8 / 0 of 8 |
| Mean wait, triage ESI 3 (min) | 14.4 | 16.0 | -1.59 [-3.87, 0.09] (ns) | 4 / 4 of 8 |
| Mean wait, triage ESI 4 (min) | 18.1 | 25.7 | -7.51 [-16.68, -0.67] | 8 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 25.8 | 38.1 | -12.26 [-35.00, 4.35] (ns) | 3 / 5 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 4.48 | 5.07 | -0.593 [-1.217, -0.122] | 8 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 16.5 | 19.2 | -2.75 [-6.77, 0.23] (ns) | 4 / 4 of 8 |
| ESI 4-5 waiting (patient-h/day) | 18.2 | 27.8 | -9.61 [-22.63, 0.32] (ns) | 5 / 3 of 8 |

**`dispatch_dispatch_flow_context` minus `rule:acuity_first+favor_new`** (patient index 0.904 vs 0.914; flow index 0.922 vs 0.945)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 15.2 | 15.3 | -0.10 [-0.61, 0.16] (ns) | 4 / 4 of 8 |
| 95th-percentile wait (min) | 31 | 32 | -1.1 [-3.6, 0.0] (ns) | 5 / 1 of 8 |
| Median ED length of stay (min) | 191 | 205 | -13.7 [-17.5, -10.1] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 248 | 253 | -5.0 [-7.9, -2.9] | 8 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 910 | 928 | -17.8 [-30.4, -9.2] | 8 / 0 of 8 |
| Left without being seen (% of arrivals) | 0.75 | 0.74 | 0.009 [-0.018, 0.029] (ns) | 2 / 6 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 4.49 | 4.62 | -0.134 [-0.214, -0.075] | 8 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 5.18 | 5.20 | -0.017 [-0.166, 0.138] (ns) | 5 / 3 of 8 |
| Adverse events (per day) | 0.41 | 0.42 | -0.005 [-0.016, 0.004] (ns) | 5 / 3 of 8 |
| Boarding (patient-h/day) | 15.5 | 15.9 | -0.43 [-1.57, 0.28] (ns) | 5 / 3 of 8 |
| Labour cost ($k/day) | 105.85 | 105.85 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 1 (min) | 9.0 | 9.1 | -0.03 [-0.08, 0.00] (ns) | 6 / 2 of 8 |
| Mean wait, triage ESI 2 (min) | 11.1 | 11.3 | -0.18 [-0.29, -0.10] | 8 / 0 of 8 |
| Mean wait, triage ESI 3 (min) | 14.4 | 14.4 | 0.02 [-0.11, 0.18] (ns) | 3 / 5 of 8 |
| Mean wait, triage ESI 4 (min) | 18.1 | 19.0 | -0.87 [-2.17, -0.20] | 7 / 1 of 8 |
| Mean wait, triage ESI 5 (min) | 25.8 | 22.3 | 3.50 [1.31, 4.95] | 1 / 7 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 4.48 | 4.60 | -0.121 [-0.206, -0.062] | 8 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 16.5 | 16.4 | 0.09 [-0.16, 0.40] (ns) | 3 / 5 of 8 |
| ESI 4-5 waiting (patient-h/day) | 18.2 | 18.5 | -0.30 [-3.78, 1.73] (ns) | 3 / 5 of 8 |

**`dispatch_dispatch_flow_context` minus `tuned_same_budget`** (patient index 0.904 vs 0.831; flow index 0.922 vs 0.802)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 15.2 | 14.0 | 1.22 [0.34, 2.07] | 1 / 7 of 8 |
| 95th-percentile wait (min) | 31 | 28 | 2.9 [-0.3, 6.2] (ns) | 1 / 5 of 8 |
| Median ED length of stay (min) | 191 | 194 | -2.7 [-5.7, 0.3] (ns) | 5 / 3 of 8 |
| Mean ED length of stay (min) | 248 | 234 | 13.6 [5.6, 21.7] | 1 / 7 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 910 | 860 | 50.3 [21.0, 80.2] | 1 / 7 of 8 |
| Left without being seen (% of arrivals) | 0.75 | 0.69 | 0.063 [0.018, 0.105] | 1 / 7 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 4.49 | 4.13 | 0.360 [-0.087, 0.850] (ns) | 3 / 5 of 8 |
| Deaths (per 10,000 arrivals) | 5.18 | 4.90 | 0.282 [0.046, 0.566] | 3 / 5 of 8 |
| Adverse events (per day) | 0.41 | 0.37 | 0.046 [0.020, 0.071] | 1 / 7 of 8 |
| Boarding (patient-h/day) | 15.5 | 7.0 | 8.49 [2.85, 17.30] | 0 / 8 of 8 |
| Labour cost ($k/day) | 105.85 | 102.37 | 3.487 [1.368, 5.769] | 1 / 7 of 8 |
| Mean wait, triage ESI 1 (min) | 9.0 | 8.6 | 0.48 [0.05, 1.02] | 2 / 6 of 8 |
| Mean wait, triage ESI 2 (min) | 11.1 | 10.6 | 0.52 [-0.04, 1.15] (ns) | 2 / 6 of 8 |
| Mean wait, triage ESI 3 (min) | 14.4 | 13.1 | 1.30 [0.29, 2.32] | 1 / 7 of 8 |
| Mean wait, triage ESI 4 (min) | 18.1 | 17.4 | 0.79 [-0.07, 1.66] (ns) | 1 / 7 of 8 |
| Mean wait, triage ESI 5 (min) | 25.8 | 19.8 | 5.98 [4.14, 7.70] | 0 / 8 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 4.48 | 4.08 | 0.392 [-0.017, 0.856] (ns) | 2 / 6 of 8 |
| ESI 3 waiting (patient-h/day) | 16.5 | 14.1 | 2.35 [0.55, 4.17] | 1 / 7 of 8 |
| ESI 4-5 waiting (patient-h/day) | 18.2 | 16.3 | 1.90 [-0.08, 3.69] (ns) | 2 / 6 of 8 |

**`dispatch_dispatch_flow_linear` minus `fixed`** (patient index 0.899 vs 1.000; flow index 0.911 vs 1.000)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 15.0 | 18.7 | -3.76 [-8.52, -0.29] | 8 / 0 of 8 |
| 95th-percentile wait (min) | 30 | 50 | -19.7 [-44.2, -1.5] | 8 / 0 of 8 |
| Median ED length of stay (min) | 190 | 204 | -13.9 [-18.3, -9.8] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 247 | 252 | -4.4 [-7.4, -1.5] | 7 / 1 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 909 | 922 | -13.5 [-25.1, -0.1] | 6 / 2 of 8 |
| Left without being seen (% of arrivals) | 0.72 | 0.87 | -0.151 [-0.332, -0.013] | 7 / 1 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 4.52 | 5.08 | -0.564 [-1.181, -0.081] | 7 / 1 of 8 |
| Deaths (per 10,000 arrivals) | 5.27 | 5.29 | -0.024 [-0.252, 0.189] (ns) | 3 / 5 of 8 |
| Adverse events (per day) | 0.42 | 0.43 | -0.007 [-0.024, 0.009] (ns) | 5 / 3 of 8 |
| Boarding (patient-h/day) | 15.6 | 15.7 | -0.10 [-1.23, 0.56] (ns) | 4 / 4 of 8 |
| Labour cost ($k/day) | 105.85 | 105.85 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 1 (min) | 9.0 | 9.6 | -0.61 [-1.35, -0.06] | 7 / 1 of 8 |
| Mean wait, triage ESI 2 (min) | 11.1 | 11.9 | -0.79 [-1.63, -0.16] | 8 / 0 of 8 |
| Mean wait, triage ESI 3 (min) | 14.2 | 16.0 | -1.79 [-4.04, -0.16] | 8 / 0 of 8 |
| Mean wait, triage ESI 4 (min) | 18.3 | 25.7 | -7.38 [-16.55, -0.66] | 8 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 22.0 | 38.1 | -16.07 [-38.11, -0.03] | 5 / 3 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 4.49 | 5.07 | -0.577 [-1.209, -0.093] | 8 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 16.1 | 19.2 | -3.11 [-7.10, -0.21] | 8 / 0 of 8 |
| ESI 4-5 waiting (patient-h/day) | 18.1 | 27.8 | -9.76 [-22.85, -0.17] | 7 / 1 of 8 |

**`dispatch_dispatch_flow_linear` minus `rule:acuity_first+favor_new`** (patient index 0.899 vs 0.914; flow index 0.911 vs 0.945)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 15.0 | 15.3 | -0.33 [-0.67, -0.11] | 7 / 1 of 8 |
| 95th-percentile wait (min) | 30 | 32 | -1.6 [-3.7, -0.5] | 7 / 0 of 8 |
| Median ED length of stay (min) | 190 | 205 | -14.7 [-18.6, -10.9] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 247 | 253 | -5.6 [-7.8, -3.6] | 8 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 909 | 928 | -19.1 [-27.1, -11.6] | 8 / 0 of 8 |
| Left without being seen (% of arrivals) | 0.72 | 0.74 | -0.016 [-0.040, 0.008] (ns) | 7 / 1 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 4.52 | 4.62 | -0.106 [-0.188, -0.022] | 7 / 1 of 8 |
| Deaths (per 10,000 arrivals) | 5.27 | 5.20 | 0.070 [-0.072, 0.234] (ns) | 1 / 6 of 8 |
| Adverse events (per day) | 0.42 | 0.42 | 0.003 [-0.004, 0.012] (ns) | 4 / 4 of 8 |
| Boarding (patient-h/day) | 15.6 | 15.9 | -0.29 [-1.45, 0.38] (ns) | 6 / 2 of 8 |
| Labour cost ($k/day) | 105.85 | 105.85 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 1 (min) | 9.0 | 9.1 | -0.07 [-0.12, -0.00] | 7 / 1 of 8 |
| Mean wait, triage ESI 2 (min) | 11.1 | 11.3 | -0.16 [-0.25, -0.10] | 8 / 0 of 8 |
| Mean wait, triage ESI 3 (min) | 14.2 | 14.4 | -0.17 [-0.28, -0.08] | 8 / 0 of 8 |
| Mean wait, triage ESI 4 (min) | 18.3 | 19.0 | -0.74 [-1.65, -0.20] | 7 / 1 of 8 |
| Mean wait, triage ESI 5 (min) | 22.0 | 22.3 | -0.32 [-1.76, 0.51] (ns) | 4 / 4 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 4.49 | 4.60 | -0.105 [-0.173, -0.036] | 8 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 16.1 | 16.4 | -0.26 [-0.45, -0.09] | 8 / 0 of 8 |
| ESI 4-5 waiting (patient-h/day) | 18.1 | 18.5 | -0.45 [-2.20, 1.61] (ns) | 6 / 2 of 8 |

**`dispatch_dispatch_flow_linear` minus `tuned_same_budget`** (patient index 0.899 vs 0.831; flow index 0.911 vs 0.802)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 15.0 | 14.0 | 0.98 [0.07, 1.90] | 1 / 7 of 8 |
| 95th-percentile wait (min) | 30 | 28 | 2.4 [-0.9, 5.7] (ns) | 2 / 5 of 8 |
| Median ED length of stay (min) | 190 | 194 | -3.7 [-6.8, -0.7] | 6 / 1 of 8 |
| Mean ED length of stay (min) | 247 | 234 | 13.0 [5.1, 21.2] | 1 / 7 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 909 | 860 | 49.0 [19.5, 79.0] | 1 / 7 of 8 |
| Left without being seen (% of arrivals) | 0.72 | 0.69 | 0.037 [-0.010, 0.083] (ns) | 2 / 6 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 4.52 | 4.13 | 0.388 [-0.056, 0.867] (ns) | 2 / 6 of 8 |
| Deaths (per 10,000 arrivals) | 5.27 | 4.90 | 0.369 [0.125, 0.671] | 1 / 7 of 8 |
| Adverse events (per day) | 0.42 | 0.37 | 0.054 [0.027, 0.083] | 1 / 7 of 8 |
| Boarding (patient-h/day) | 15.6 | 7.0 | 8.63 [2.86, 17.83] | 0 / 8 of 8 |
| Labour cost ($k/day) | 105.85 | 102.37 | 3.487 [1.368, 5.769] | 1 / 7 of 8 |
| Mean wait, triage ESI 1 (min) | 9.0 | 8.6 | 0.44 [0.02, 0.97] | 3 / 5 of 8 |
| Mean wait, triage ESI 2 (min) | 11.1 | 10.6 | 0.53 [-0.02, 1.15] (ns) | 2 / 6 of 8 |
| Mean wait, triage ESI 3 (min) | 14.2 | 13.1 | 1.11 [0.11, 2.11] | 1 / 7 of 8 |
| Mean wait, triage ESI 4 (min) | 18.3 | 17.4 | 0.92 [-0.04, 1.93] (ns) | 1 / 7 of 8 |
| Mean wait, triage ESI 5 (min) | 22.0 | 19.8 | 2.17 [0.66, 3.89] | 1 / 7 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 4.49 | 4.08 | 0.408 [-0.010, 0.865] (ns) | 3 / 5 of 8 |
| ESI 3 waiting (patient-h/day) | 16.1 | 14.1 | 1.99 [0.22, 3.79] | 1 / 7 of 8 |
| ESI 4-5 waiting (patient-h/day) | 18.1 | 16.3 | 1.76 [0.19, 4.25] | 1 / 7 of 8 |

**`dispatch_dispatch_flow_mlp` minus `fixed`** (patient index 0.897 vs 1.000; flow index 0.914 vs 1.000)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 15.0 | 18.7 | -3.74 [-8.51, -0.24] | 8 / 0 of 8 |
| 95th-percentile wait (min) | 30 | 50 | -19.6 [-44.1, -1.3] | 8 / 0 of 8 |
| Median ED length of stay (min) | 191 | 204 | -13.0 [-17.2, -9.1] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 248 | 252 | -3.7 [-6.4, -0.9] | 7 / 1 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 911 | 922 | -10.9 [-21.8, 1.9] (ns) | 6 / 2 of 8 |
| Left without being seen (% of arrivals) | 0.73 | 0.87 | -0.146 [-0.331, -0.006] | 7 / 1 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 4.50 | 5.08 | -0.584 [-1.184, -0.128] | 8 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 5.19 | 5.29 | -0.104 [-0.316, 0.101] (ns) | 5 / 3 of 8 |
| Adverse events (per day) | 0.42 | 0.43 | -0.011 [-0.026, 0.001] (ns) | 6 / 2 of 8 |
| Boarding (patient-h/day) | 15.5 | 15.7 | -0.16 [-1.27, 0.59] (ns) | 4 / 4 of 8 |
| Labour cost ($k/day) | 105.85 | 105.85 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 1 (min) | 9.1 | 9.6 | -0.49 [-1.25, 0.07] (ns) | 4 / 4 of 8 |
| Mean wait, triage ESI 2 (min) | 11.1 | 11.9 | -0.82 [-1.65, -0.19] | 8 / 0 of 8 |
| Mean wait, triage ESI 3 (min) | 14.3 | 16.0 | -1.63 [-3.91, 0.06] (ns) | 6 / 2 of 8 |
| Mean wait, triage ESI 4 (min) | 18.1 | 25.7 | -7.54 [-16.79, -0.71] | 8 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 21.7 | 38.1 | -16.31 [-38.39, -0.25] | 5 / 3 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 4.47 | 5.07 | -0.598 [-1.220, -0.128] | 8 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 16.4 | 19.2 | -2.81 [-6.85, 0.21] (ns) | 5 / 3 of 8 |
| ESI 4-5 waiting (patient-h/day) | 17.8 | 27.8 | -9.97 [-23.15, -0.26] | 7 / 1 of 8 |

**`dispatch_dispatch_flow_mlp` minus `rule:acuity_first+favor_new`** (patient index 0.897 vs 0.914; flow index 0.914 vs 0.945)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 15.0 | 15.3 | -0.31 [-0.69, -0.09] | 7 / 1 of 8 |
| 95th-percentile wait (min) | 30 | 32 | -1.5 [-3.4, -0.4] | 7 / 0 of 8 |
| Median ED length of stay (min) | 191 | 205 | -13.8 [-17.6, -10.2] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 248 | 253 | -4.8 [-6.8, -3.0] | 8 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 911 | 928 | -16.4 [-23.7, -9.7] | 8 / 0 of 8 |
| Left without being seen (% of arrivals) | 0.73 | 0.74 | -0.011 [-0.033, 0.015] (ns) | 6 / 2 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 4.50 | 4.62 | -0.125 [-0.197, -0.069] | 8 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 5.19 | 5.20 | -0.009 [-0.159, 0.147] (ns) | 5 / 3 of 8 |
| Adverse events (per day) | 0.42 | 0.42 | -0.001 [-0.007, 0.005] (ns) | 5 / 3 of 8 |
| Boarding (patient-h/day) | 15.5 | 15.9 | -0.36 [-1.43, 0.28] (ns) | 4 / 4 of 8 |
| Labour cost ($k/day) | 105.85 | 105.85 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 1 (min) | 9.1 | 9.1 | 0.05 [0.00, 0.10] | 2 / 6 of 8 |
| Mean wait, triage ESI 2 (min) | 11.1 | 11.3 | -0.19 [-0.29, -0.12] | 8 / 0 of 8 |
| Mean wait, triage ESI 3 (min) | 14.3 | 14.4 | -0.01 [-0.13, 0.17] (ns) | 5 / 3 of 8 |
| Mean wait, triage ESI 4 (min) | 18.1 | 19.0 | -0.90 [-2.19, -0.20] | 7 / 1 of 8 |
| Mean wait, triage ESI 5 (min) | 21.7 | 22.3 | -0.56 [-1.93, 0.31] (ns) | 4 / 4 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 4.47 | 4.60 | -0.126 [-0.196, -0.074] | 8 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 16.4 | 16.4 | 0.03 [-0.21, 0.44] (ns) | 4 / 4 of 8 |
| ESI 4-5 waiting (patient-h/day) | 17.8 | 18.5 | -0.66 [-2.72, 1.52] (ns) | 6 / 2 of 8 |

**`dispatch_dispatch_flow_mlp` minus `tuned_same_budget`** (patient index 0.897 vs 0.831; flow index 0.914 vs 0.802)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 15.0 | 14.0 | 1.00 [0.11, 1.89] | 1 / 7 of 8 |
| 95th-percentile wait (min) | 30 | 28 | 2.6 [-0.7, 5.7] (ns) | 2 / 5 of 8 |
| Median ED length of stay (min) | 191 | 194 | -2.8 [-6.0, 0.3] (ns) | 5 / 3 of 8 |
| Mean ED length of stay (min) | 248 | 234 | 13.8 [5.5, 22.1] | 1 / 7 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 911 | 860 | 51.7 [21.2, 82.6] | 1 / 7 of 8 |
| Left without being seen (% of arrivals) | 0.73 | 0.69 | 0.042 [-0.007, 0.086] (ns) | 1 / 7 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 4.50 | 4.13 | 0.368 [-0.080, 0.858] (ns) | 2 / 6 of 8 |
| Deaths (per 10,000 arrivals) | 5.19 | 4.90 | 0.289 [0.047, 0.604] | 3 / 5 of 8 |
| Adverse events (per day) | 0.42 | 0.37 | 0.050 [0.025, 0.076] | 1 / 7 of 8 |
| Boarding (patient-h/day) | 15.5 | 7.0 | 8.56 [2.93, 17.43] | 0 / 8 of 8 |
| Labour cost ($k/day) | 105.85 | 102.37 | 3.487 [1.368, 5.769] | 1 / 7 of 8 |
| Mean wait, triage ESI 1 (min) | 9.1 | 8.6 | 0.56 [0.13, 1.09] | 1 / 7 of 8 |
| Mean wait, triage ESI 2 (min) | 11.1 | 10.6 | 0.51 [-0.05, 1.13] (ns) | 2 / 6 of 8 |
| Mean wait, triage ESI 3 (min) | 14.3 | 13.1 | 1.27 [0.19, 2.39] | 1 / 7 of 8 |
| Mean wait, triage ESI 4 (min) | 18.1 | 17.4 | 0.75 [-0.05, 1.58] (ns) | 1 / 7 of 8 |
| Mean wait, triage ESI 5 (min) | 21.7 | 19.8 | 1.92 [0.47, 3.69] | 1 / 7 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 4.47 | 4.08 | 0.388 [-0.022, 0.852] (ns) | 2 / 6 of 8 |
| ESI 3 waiting (patient-h/day) | 16.4 | 14.1 | 2.29 [0.37, 4.33] | 1 / 7 of 8 |
| ESI 4-5 waiting (patient-h/day) | 17.8 | 16.3 | 1.55 [0.15, 3.84] | 1 / 7 of 8 |

**`dispatch_dispatch_only_linear` minus `fixed`** (patient index 1.000 vs 1.000; flow index 1.000 vs 1.000)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 18.7 | 18.7 | 0.00 [0.00, 0.00] (ns) | 0 / 0 of 8 |
| 95th-percentile wait (min) | 50 | 50 | 0.0 [0.0, 0.0] (ns) | 0 / 0 of 8 |
| Median ED length of stay (min) | 204 | 204 | 0.0 [0.0, 0.0] (ns) | 0 / 0 of 8 |
| Mean ED length of stay (min) | 252 | 252 | 0.0 [0.0, 0.0] (ns) | 0 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 922 | 922 | 0.0 [0.0, 0.0] (ns) | 0 / 0 of 8 |
| Left without being seen (% of arrivals) | 0.87 | 0.87 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 5.08 | 5.08 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 5.29 | 5.29 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Adverse events (per day) | 0.43 | 0.43 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Boarding (patient-h/day) | 15.7 | 15.7 | 0.00 [0.00, 0.00] (ns) | 0 / 0 of 8 |
| Labour cost ($k/day) | 105.85 | 105.85 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 1 (min) | 9.6 | 9.6 | 0.00 [0.00, 0.00] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 2 (min) | 11.9 | 11.9 | 0.00 [0.00, 0.00] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 3 (min) | 16.0 | 16.0 | 0.00 [0.00, 0.00] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 4 (min) | 25.7 | 25.7 | 0.00 [0.00, 0.00] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 38.1 | 38.1 | 0.00 [0.00, 0.00] (ns) | 0 / 0 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 5.07 | 5.07 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 19.2 | 19.2 | 0.00 [0.00, 0.00] (ns) | 0 / 0 of 8 |
| ESI 4-5 waiting (patient-h/day) | 27.8 | 27.8 | 0.00 [0.00, 0.00] (ns) | 0 / 0 of 8 |

**`dispatch_dispatch_only_linear` minus `rule:acuity_first+favor_new`** (patient index 1.000 vs 0.914; flow index 1.000 vs 0.945)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 18.7 | 15.3 | 3.43 [0.00, 8.23] (ns) | 0 / 2 of 8 |
| 95th-percentile wait (min) | 50 | 32 | 18.1 [0.0, 43.3] (ns) | 0 / 2 of 8 |
| Median ED length of stay (min) | 204 | 205 | -0.8 [-2.3, 0.0] (ns) | 2 / 0 of 8 |
| Mean ED length of stay (min) | 252 | 253 | -1.1 [-3.5, 0.0] (ns) | 2 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 922 | 928 | -5.5 [-17.3, 0.0] (ns) | 2 / 0 of 8 |
| Left without being seen (% of arrivals) | 0.87 | 0.74 | 0.135 [0.000, 0.325] (ns) | 0 / 2 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 5.08 | 4.62 | 0.459 [0.000, 1.103] (ns) | 0 / 2 of 8 |
| Deaths (per 10,000 arrivals) | 5.29 | 5.20 | 0.094 [0.000, 0.258] (ns) | 0 / 2 of 8 |
| Adverse events (per day) | 0.43 | 0.42 | 0.010 [0.000, 0.026] (ns) | 0 / 2 of 8 |
| Boarding (patient-h/day) | 15.7 | 15.9 | -0.19 [-0.62, 0.00] (ns) | 2 / 0 of 8 |
| Labour cost ($k/day) | 105.85 | 105.85 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 1 (min) | 9.6 | 9.1 | 0.54 [0.00, 1.28] (ns) | 0 / 2 of 8 |
| Mean wait, triage ESI 2 (min) | 11.9 | 11.3 | 0.63 [0.00, 1.52] (ns) | 0 / 2 of 8 |
| Mean wait, triage ESI 3 (min) | 16.0 | 14.4 | 1.62 [0.00, 3.89] (ns) | 0 / 2 of 8 |
| Mean wait, triage ESI 4 (min) | 25.7 | 19.0 | 6.64 [0.00, 16.02] (ns) | 0 / 2 of 8 |
| Mean wait, triage ESI 5 (min) | 38.1 | 22.3 | 15.75 [0.00, 37.88] (ns) | 0 / 2 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 5.07 | 4.60 | 0.472 [0.000, 1.139] (ns) | 0 / 2 of 8 |
| ESI 3 waiting (patient-h/day) | 19.2 | 16.4 | 2.85 [0.00, 6.85] (ns) | 0 / 2 of 8 |
| ESI 4-5 waiting (patient-h/day) | 27.8 | 18.5 | 9.31 [0.00, 22.09] (ns) | 0 / 2 of 8 |

**`dispatch_joint_linear` minus `fixed`** (patient index 0.830 vs 1.000; flow index 0.776 vs 1.000)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 14.0 | 18.7 | -4.78 [-9.94, -0.91] | 7 / 1 of 8 |
| 95th-percentile wait (min) | 27 | 50 | -22.8 [-47.7, -3.3] | 7 / 1 of 8 |
| Median ED length of stay (min) | 186 | 204 | -18.3 [-24.5, -12.3] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 232 | 252 | -19.2 [-30.1, -9.2] | 8 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 854 | 922 | -67.9 [-108.7, -29.5] | 7 / 1 of 8 |
| Left without being seen (% of arrivals) | 0.69 | 0.87 | -0.183 [-0.372, -0.032] | 7 / 1 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 4.10 | 5.08 | -0.986 [-1.822, -0.261] | 7 / 1 of 8 |
| Deaths (per 10,000 arrivals) | 4.96 | 5.29 | -0.332 [-0.656, -0.049] | 7 / 1 of 8 |
| Adverse events (per day) | 0.37 | 0.43 | -0.059 [-0.086, -0.035] | 8 / 0 of 8 |
| Boarding (patient-h/day) | 5.8 | 15.7 | -9.87 [-20.57, -3.11] | 8 / 0 of 8 |
| Labour cost ($k/day) | 102.22 | 105.85 | -3.636 [-5.966, -1.507] | 8 / 0 of 8 |
| Mean wait, triage ESI 1 (min) | 8.5 | 9.6 | -1.10 [-2.05, -0.31] | 8 / 0 of 8 |
| Mean wait, triage ESI 2 (min) | 10.6 | 11.9 | -1.36 [-2.49, -0.40] | 7 / 1 of 8 |
| Mean wait, triage ESI 3 (min) | 13.0 | 16.0 | -2.92 [-5.53, -0.83] | 7 / 1 of 8 |
| Mean wait, triage ESI 4 (min) | 17.3 | 25.7 | -8.35 [-18.08, -1.12] | 7 / 1 of 8 |
| Mean wait, triage ESI 5 (min) | 19.8 | 38.1 | -18.28 [-40.90, -1.62] | 7 / 1 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 4.06 | 5.07 | -1.014 [-1.855, -0.298] | 7 / 1 of 8 |
| ESI 3 waiting (patient-h/day) | 14.1 | 19.2 | -5.14 [-9.71, -1.49] | 7 / 1 of 8 |
| ESI 4-5 waiting (patient-h/day) | 16.6 | 27.8 | -11.21 [-23.73, -1.48] | 7 / 1 of 8 |

**`dispatch_joint_linear` minus `rule:acuity_first+favor_new`** (patient index 0.830 vs 0.914; flow index 0.776 vs 0.945)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 14.0 | 15.3 | -1.35 [-2.51, -0.30] | 7 / 1 of 8 |
| 95th-percentile wait (min) | 27 | 32 | -4.7 [-8.8, -1.0] | 6 / 1 of 8 |
| Median ED length of stay (min) | 186 | 205 | -19.1 [-25.0, -13.0] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 232 | 253 | -20.3 [-30.8, -10.3] | 8 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 854 | 928 | -73.4 [-112.8, -36.5] | 7 / 1 of 8 |
| Left without being seen (% of arrivals) | 0.69 | 0.74 | -0.048 [-0.097, 0.001] (ns) | 6 / 2 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 4.10 | 4.62 | -0.528 [-0.995, -0.073] | 7 / 1 of 8 |
| Deaths (per 10,000 arrivals) | 4.96 | 5.20 | -0.238 [-0.525, 0.008] (ns) | 6 / 2 of 8 |
| Adverse events (per day) | 0.37 | 0.42 | -0.049 [-0.077, -0.023] | 7 / 1 of 8 |
| Boarding (patient-h/day) | 5.8 | 15.9 | -10.07 [-20.69, -3.34] | 8 / 0 of 8 |
| Labour cost ($k/day) | 102.22 | 105.85 | -3.636 [-5.966, -1.507] | 8 / 0 of 8 |
| Mean wait, triage ESI 1 (min) | 8.5 | 9.1 | -0.56 [-1.06, -0.15] | 8 / 0 of 8 |
| Mean wait, triage ESI 2 (min) | 10.6 | 11.3 | -0.73 [-1.35, -0.16] | 6 / 2 of 8 |
| Mean wait, triage ESI 3 (min) | 13.0 | 14.4 | -1.30 [-2.31, -0.29] | 7 / 1 of 8 |
| Mean wait, triage ESI 4 (min) | 17.3 | 19.0 | -1.71 [-3.40, -0.41] | 7 / 1 of 8 |
| Mean wait, triage ESI 5 (min) | 19.8 | 22.3 | -2.53 [-5.62, -0.36] | 7 / 1 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 4.06 | 4.60 | -0.542 [-0.994, -0.115] | 7 / 1 of 8 |
| ESI 3 waiting (patient-h/day) | 14.1 | 16.4 | -2.29 [-4.07, -0.51] | 7 / 1 of 8 |
| ESI 4-5 waiting (patient-h/day) | 16.6 | 18.5 | -1.89 [-4.39, 0.34] (ns) | 6 / 2 of 8 |

**`dispatch_joint_linear` minus `tuned_same_budget`** (patient index 0.830 vs 0.831; flow index 0.776 vs 0.802)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 14.0 | 14.0 | -0.04 [-0.07, -0.01] | 8 / 0 of 8 |
| 95th-percentile wait (min) | 27 | 28 | -0.7 [-1.2, -0.2] | 5 / 0 of 8 |
| Median ED length of stay (min) | 186 | 194 | -8.0 [-9.9, -6.2] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 232 | 234 | -1.7 [-2.3, -1.1] | 8 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 854 | 860 | -5.4 [-8.2, -1.0] | 7 / 1 of 8 |
| Left without being seen (% of arrivals) | 0.69 | 0.69 | 0.005 [-0.006, 0.019] (ns) | 2 / 6 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 4.10 | 4.13 | -0.035 [-0.061, -0.011] | 7 / 1 of 8 |
| Deaths (per 10,000 arrivals) | 4.96 | 4.90 | 0.061 [-0.047, 0.192] (ns) | 2 / 6 of 8 |
| Adverse events (per day) | 0.37 | 0.37 | 0.002 [-0.005, 0.007] (ns) | 2 / 6 of 8 |
| Boarding (patient-h/day) | 5.8 | 7.0 | -1.15 [-2.25, -0.35] | 8 / 0 of 8 |
| Labour cost ($k/day) | 102.22 | 102.37 | -0.150 [-0.273, -0.018] | 7 / 1 of 8 |
| Mean wait, triage ESI 1 (min) | 8.5 | 8.6 | -0.04 [-0.08, -0.01] | 7 / 1 of 8 |
| Mean wait, triage ESI 2 (min) | 10.6 | 10.6 | -0.04 [-0.06, -0.02] | 8 / 0 of 8 |
| Mean wait, triage ESI 3 (min) | 13.0 | 13.1 | -0.03 [-0.05, 0.00] (ns) | 6 / 2 of 8 |
| Mean wait, triage ESI 4 (min) | 17.3 | 17.4 | -0.05 [-0.18, 0.05] (ns) | 4 / 4 of 8 |
| Mean wait, triage ESI 5 (min) | 19.8 | 19.8 | -0.05 [-0.21, 0.12] (ns) | 5 / 3 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 4.06 | 4.08 | -0.029 [-0.046, -0.014] | 8 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 14.1 | 14.1 | -0.04 [-0.09, 0.01] (ns) | 6 / 2 of 8 |
| ESI 4-5 waiting (patient-h/day) | 16.6 | 16.3 | 0.31 [-0.29, 1.93] (ns) | 3 / 5 of 8 |

**`dispatch_joint_linear` minus `ablate:dispatch_joint_linear:levers_only`** (patient index 0.830 vs 0.833; flow index 0.776 vs 0.788)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 14.0 | 14.0 | -0.05 [-0.07, -0.02] | 8 / 0 of 8 |
| 95th-percentile wait (min) | 27 | 28 | -0.7 [-1.2, -0.2] | 5 / 0 of 8 |
| Median ED length of stay (min) | 186 | 194 | -8.2 [-10.2, -6.3] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 232 | 234 | -1.7 [-2.3, -1.1] | 8 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 854 | 860 | -5.3 [-8.1, -1.0] | 7 / 1 of 8 |
| Left without being seen (% of arrivals) | 0.69 | 0.69 | 0.004 [-0.006, 0.018] (ns) | 2 / 6 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 4.10 | 4.13 | -0.035 [-0.062, -0.011] | 8 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 4.96 | 4.88 | 0.077 [-0.024, 0.207] (ns) | 1 / 7 of 8 |
| Adverse events (per day) | 0.37 | 0.37 | -0.000 [-0.006, 0.004] (ns) | 3 / 5 of 8 |
| Boarding (patient-h/day) | 5.8 | 5.8 | 0.04 [-0.04, 0.15] (ns) | 4 / 4 of 8 |
| Labour cost ($k/day) | 102.22 | 102.22 | 0.000 [-0.014, 0.015] (ns) | 3 / 5 of 8 |
| Mean wait, triage ESI 1 (min) | 8.5 | 8.6 | -0.04 [-0.08, -0.01] | 8 / 0 of 8 |
| Mean wait, triage ESI 2 (min) | 10.6 | 10.6 | -0.04 [-0.06, -0.02] | 8 / 0 of 8 |
| Mean wait, triage ESI 3 (min) | 13.0 | 13.1 | -0.04 [-0.07, 0.00] (ns) | 7 / 1 of 8 |
| Mean wait, triage ESI 4 (min) | 17.3 | 17.4 | -0.07 [-0.19, 0.03] (ns) | 5 / 3 of 8 |
| Mean wait, triage ESI 5 (min) | 19.8 | 19.8 | -0.07 [-0.23, 0.08] (ns) | 5 / 3 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 4.06 | 4.09 | -0.030 [-0.045, -0.017] | 8 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 14.1 | 14.1 | -0.06 [-0.12, 0.02] (ns) | 7 / 1 of 8 |
| ESI 4-5 waiting (patient-h/day) | 16.6 | 16.3 | 0.29 [-0.31, 1.91] (ns) | 4 / 4 of 8 |

**`ablate:dispatch_joint_linear:index_on_tuned` minus `tuned_same_budget`** (patient index 0.829 vs 0.831; flow index 0.790 vs 0.802)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 13.9 | 14.0 | -0.05 [-0.08, -0.02] | 8 / 0 of 8 |
| 95th-percentile wait (min) | 27 | 28 | -0.8 [-1.4, -0.3] | 5 / 0 of 8 |
| Median ED length of stay (min) | 186 | 194 | -8.1 [-10.0, -6.2] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 232 | 234 | -1.7 [-2.3, -1.1] | 8 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 854 | 860 | -5.3 [-8.1, -1.0] | 7 / 1 of 8 |
| Left without being seen (% of arrivals) | 0.69 | 0.69 | 0.005 [-0.006, 0.018] (ns) | 3 / 5 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 4.10 | 4.13 | -0.035 [-0.060, -0.013] | 8 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 4.97 | 4.90 | 0.069 [-0.031, 0.198] (ns) | 1 / 7 of 8 |
| Adverse events (per day) | 0.37 | 0.37 | -0.001 [-0.007, 0.003] (ns) | 4 / 4 of 8 |
| Boarding (patient-h/day) | 7.0 | 7.0 | -0.03 [-0.18, 0.08] (ns) | 4 / 4 of 8 |
| Labour cost ($k/day) | 102.36 | 102.37 | -0.003 [-0.017, 0.010] (ns) | 4 / 3 of 8 |
| Mean wait, triage ESI 1 (min) | 8.5 | 8.6 | -0.04 [-0.08, -0.01] | 8 / 0 of 8 |
| Mean wait, triage ESI 2 (min) | 10.6 | 10.6 | -0.04 [-0.06, -0.02] | 8 / 0 of 8 |
| Mean wait, triage ESI 3 (min) | 13.0 | 13.1 | -0.04 [-0.07, 0.00] (ns) | 7 / 1 of 8 |
| Mean wait, triage ESI 4 (min) | 17.3 | 17.4 | -0.07 [-0.20, 0.02] (ns) | 6 / 2 of 8 |
| Mean wait, triage ESI 5 (min) | 19.8 | 19.8 | -0.06 [-0.22, 0.09] (ns) | 5 / 3 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 4.05 | 4.08 | -0.033 [-0.050, -0.018] | 8 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 14.1 | 14.1 | -0.06 [-0.12, 0.02] (ns) | 7 / 1 of 8 |
| ESI 4-5 waiting (patient-h/day) | 16.6 | 16.3 | 0.29 [-0.32, 1.90] (ns) | 5 / 3 of 8 |

**`tuned_same_budget` minus `fixed`** (patient index 0.831 vs 1.000; flow index 0.802 vs 1.000)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 14.0 | 18.7 | -4.74 [-9.92, -0.86] | 7 / 1 of 8 |
| 95th-percentile wait (min) | 28 | 50 | -22.1 [-47.5, -2.3] | 7 / 1 of 8 |
| Median ED length of stay (min) | 194 | 204 | -10.3 [-15.8, -4.9] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 234 | 252 | -17.5 [-28.1, -7.7] | 7 / 1 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 860 | 922 | -62.5 [-101.8, -26.3] | 7 / 1 of 8 |
| Left without being seen (% of arrivals) | 0.69 | 0.87 | -0.188 [-0.384, -0.033] | 7 / 1 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 4.13 | 5.08 | -0.952 [-1.801, -0.215] | 7 / 1 of 8 |
| Deaths (per 10,000 arrivals) | 4.90 | 5.29 | -0.393 [-0.713, -0.142] | 8 / 0 of 8 |
| Adverse events (per day) | 0.37 | 0.43 | -0.061 [-0.086, -0.037] | 8 / 0 of 8 |
| Boarding (patient-h/day) | 7.0 | 15.7 | -8.73 [-18.26, -2.72] | 8 / 0 of 8 |
| Labour cost ($k/day) | 102.37 | 105.85 | -3.487 [-5.769, -1.368] | 7 / 1 of 8 |
| Mean wait, triage ESI 1 (min) | 8.6 | 9.6 | -1.06 [-2.02, -0.25] | 7 / 1 of 8 |
| Mean wait, triage ESI 2 (min) | 10.6 | 11.9 | -1.33 [-2.48, -0.36] | 7 / 1 of 8 |
| Mean wait, triage ESI 3 (min) | 13.1 | 16.0 | -2.89 [-5.51, -0.80] | 7 / 1 of 8 |
| Mean wait, triage ESI 4 (min) | 17.4 | 25.7 | -8.30 [-18.03, -1.06] | 7 / 1 of 8 |
| Mean wait, triage ESI 5 (min) | 19.8 | 38.1 | -18.24 [-40.86, -1.58] | 7 / 1 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 4.08 | 5.07 | -0.985 [-1.842, -0.257] | 7 / 1 of 8 |
| ESI 3 waiting (patient-h/day) | 14.1 | 19.2 | -5.10 [-9.68, -1.44] | 7 / 1 of 8 |
| ESI 4-5 waiting (patient-h/day) | 16.3 | 27.8 | -11.52 [-24.61, -1.42] | 7 / 1 of 8 |

**`rule:acuity_first+favor_new` minus `fixed`** (patient index 0.914 vs 1.000; flow index 0.945 vs 1.000)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 15.3 | 18.7 | -3.43 [-8.23, 0.00] (ns) | 2 / 0 of 8 |
| 95th-percentile wait (min) | 32 | 50 | -18.1 [-43.3, 0.0] (ns) | 2 / 0 of 8 |
| Median ED length of stay (min) | 205 | 204 | 0.8 [0.0, 2.3] (ns) | 0 / 2 of 8 |
| Mean ED length of stay (min) | 253 | 252 | 1.1 [0.0, 3.5] (ns) | 0 / 2 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 928 | 922 | 5.5 [0.0, 17.3] (ns) | 0 / 2 of 8 |
| Left without being seen (% of arrivals) | 0.74 | 0.87 | -0.135 [-0.325, 0.000] (ns) | 2 / 0 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 4.62 | 5.08 | -0.459 [-1.103, 0.000] (ns) | 2 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 5.20 | 5.29 | -0.094 [-0.258, 0.000] (ns) | 2 / 0 of 8 |
| Adverse events (per day) | 0.42 | 0.43 | -0.010 [-0.026, 0.000] (ns) | 2 / 0 of 8 |
| Boarding (patient-h/day) | 15.9 | 15.7 | 0.19 [0.00, 0.62] (ns) | 0 / 2 of 8 |
| Labour cost ($k/day) | 105.85 | 105.85 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 1 (min) | 9.1 | 9.6 | -0.54 [-1.28, 0.00] (ns) | 2 / 0 of 8 |
| Mean wait, triage ESI 2 (min) | 11.3 | 11.9 | -0.63 [-1.52, 0.00] (ns) | 2 / 0 of 8 |
| Mean wait, triage ESI 3 (min) | 14.4 | 16.0 | -1.62 [-3.89, 0.00] (ns) | 2 / 0 of 8 |
| Mean wait, triage ESI 4 (min) | 19.0 | 25.7 | -6.64 [-16.02, 0.00] (ns) | 2 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 22.3 | 38.1 | -15.75 [-37.88, 0.00] (ns) | 2 / 0 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 4.60 | 5.07 | -0.472 [-1.139, 0.000] (ns) | 2 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 16.4 | 19.2 | -2.85 [-6.85, 0.00] (ns) | 2 / 0 of 8 |
| ESI 4-5 waiting (patient-h/day) | 18.5 | 27.8 | -9.31 [-22.09, 0.00] (ns) | 2 / 0 of 8 |

### same_budget_better_flow on held-out episodes (no tuning margin)

| Arm | score on pooled means (higher is better) | feasible | members feasible | mean per-member score | violated |
|---|---:|---|---:|---:|---|
| `dispatch_dispatch_flow_context` | +0.1070 | True | 4 / 8 | +0.0589 | - |
| `dispatch_dispatch_flow_linear` | +0.1164 | True | 3 / 8 | +0.0482 | - |
| `dispatch_dispatch_flow_mlp` | +0.1145 | True | 4 / 8 | +0.0775 | - |
| `dispatch_dispatch_only_linear` | +0.0000 | True | 8 / 8 | +0.0000 | - |
| `dispatch_joint_linear` | +0.2709 | True | 7 / 8 | +0.1033 | - |
| `ablate:dispatch_joint_linear:levers_only` | +0.2595 | True | 7 / 8 | +0.0844 | - |
| `ablate:dispatch_joint_linear:index_on_tuned` | +0.2570 | True | 6 / 8 | +0.0810 | - |
| `rule:fcfs+favor_new` | -0.0284 | False | 2 / 8 | -0.9643 | deaths_per_10k, hi_acuity_wait_hours_per_day |
| `rule:fcfs+balanced` | -2.4727 | False | 1 / 8 | -3.2268 | deaths_per_10k, adverse_events_per_day, hi_acuity_wait_hours_per_day |
| `rule:fcfs+favor_dispositions` | -17.4129 | False | 0 / 8 | -18.6333 | deaths_per_10k, adverse_events_per_day, hi_acuity_wait_hours_per_day |
| `rule:acuity_first+favor_new` | +0.0821 | True | 8 / 8 | +0.0552 | - |
| `rule:acuity_first+balanced` | +0.0508 | True | 4 / 8 | -0.0166 | - |
| `rule:acuity_first+favor_dispositions` | -4.9095 | False | 2 / 8 | -5.5563 | deaths_per_10k, adverse_events_per_day, hi_acuity_wait_hours_per_day |
| `rule:acuity_with_aging+favor_new` | +0.0820 | True | 5 / 8 | -0.0124 | - |
| `rule:acuity_with_aging+balanced` | +0.0483 | True | 2 / 8 | -0.0982 | - |
| `rule:acuity_with_aging+favor_dispositions` | -8.2949 | False | 0 / 8 | -9.1296 | deaths_per_10k, adverse_events_per_day, hi_acuity_wait_hours_per_day |
| `rule:shortest_first+favor_new` | -0.6640 | False | 2 / 8 | -1.5996 | deaths_per_10k, adverse_events_per_day, hi_acuity_wait_hours_per_day |
| `rule:shortest_first+balanced` | -5.5452 | False | 1 / 8 | -6.2478 | deaths_per_10k, adverse_events_per_day, hi_acuity_wait_hours_per_day |
| `rule:shortest_first+favor_dispositions` | -33.7619 | False | 0 / 8 | -35.7017 | deaths_per_10k, adverse_events_per_day, hi_acuity_wait_hours_per_day |
| `tuned_same_budget` | +0.2451 | True | 6 / 8 | +0.0599 | - |

### Patient index per ensemble member (1 = that member's baseline)

| Arm | m0 | m1 | m2 | m3 | m4 | m5 | m6 | m7 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `dispatch_dispatch_flow_context` | 1.004 | 0.958 | 0.659 | 0.993 | 0.969 | 0.646 | 1.011 | 0.992 |
| `dispatch_dispatch_flow_linear` | 0.999 | 0.986 | 0.655 | 0.986 | 0.954 | 0.646 | 0.989 | 0.974 |
| `dispatch_dispatch_flow_mlp` | 1.002 | 0.966 | 0.660 | 0.982 | 0.958 | 0.643 | 0.986 | 0.980 |
| `dispatch_dispatch_only_linear` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| `dispatch_joint_linear` | 0.966 | 0.861 | 0.668 | 1.046 | 0.865 | 0.523 | 0.940 | 0.773 |
| `rule:acuity_first+favor_new` | 1.000 | 1.000 | 0.658 | 1.000 | 1.000 | 0.652 | 1.000 | 1.000 |
| `tuned_same_budget` | 0.969 | 0.867 | 0.661 | 1.058 | 0.868 | 0.521 | 0.938 | 0.770 |

### Flow index per ensemble member (1 = that member's baseline)

| Arm | m0 | m1 | m2 | m3 | m4 | m5 | m6 | m7 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `dispatch_dispatch_flow_context` | 1.001 | 0.944 | 0.776 | 0.995 | 0.958 | 0.756 | 0.981 | 0.968 |
| `dispatch_dispatch_flow_linear` | 0.982 | 0.936 | 0.771 | 0.982 | 0.942 | 0.751 | 0.966 | 0.957 |
| `dispatch_dispatch_flow_mlp` | 0.992 | 0.950 | 0.775 | 0.982 | 0.941 | 0.757 | 0.958 | 0.960 |
| `dispatch_dispatch_only_linear` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| `dispatch_joint_linear` | 0.916 | 0.747 | 0.713 | 0.931 | 0.748 | 0.586 | 0.806 | 0.762 |
| `rule:acuity_first+favor_new` | 1.000 | 1.000 | 0.781 | 1.000 | 1.000 | 0.778 | 1.000 | 1.000 |
| `tuned_same_budget` | 0.942 | 0.774 | 0.722 | 0.961 | 0.775 | 0.621 | 0.834 | 0.784 |

### All hard-coded rule arms

| Arm | wait | p95 | LOS median | LWBS % | ESI 1-2 waiting h/day | adverse/day | patient index | flow index |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `fixed` | 18.7 | 50 | 204 | 0.87 | 5.08 | 0.43 | 1.000 | 1.000 |
| `rule:fcfs+favor_new` | 14.9 | 30 | 209 | 0.71 | 5.13 | 0.42 | 0.932 | 0.934 |
| `rule:fcfs+balanced` | 16.0 | 34 | 208 | 0.75 | 6.33 | 0.43 | 1.039 | 0.960 |
| `rule:fcfs+favor_dispositions` | 30.9 | 115 | 198 | 1.46 | 13.38 | 0.51 | 1.948 | 1.355 |
| `rule:acuity_first+favor_new` | 15.3 | 32 | 205 | 0.74 | 4.62 | 0.42 | 0.914 | 0.945 |
| `rule:acuity_first+balanced` | 16.7 | 38 | 204 | 0.81 | 4.61 | 0.42 | 0.953 | 0.980 |
| `rule:acuity_first+favor_dispositions` | 32.2 | 118 | 197 | 1.64 | 7.23 | 0.46 | 1.611 | 1.421 |
| `rule:acuity_with_aging+favor_new` | 15.0 | 31 | 210 | 0.73 | 4.60 | 0.42 | 0.905 | 0.944 |
| `rule:acuity_with_aging+balanced` | 16.3 | 37 | 209 | 0.79 | 4.64 | 0.42 | 0.948 | 0.981 |
| `rule:acuity_with_aging+favor_dispositions` | 31.7 | 124 | 199 | 1.56 | 8.91 | 0.48 | 1.695 | 1.398 |
| `rule:shortest_first+favor_new` | 14.6 | 29 | 199 | 0.70 | 5.44 | 0.43 | 0.947 | 0.912 |
| `rule:shortest_first+balanced` | 15.5 | 33 | 198 | 0.72 | 7.83 | 0.44 | 1.121 | 0.929 |
| `rule:shortest_first+favor_dispositions` | 29.6 | 115 | 194 | 1.30 | 21.50 | 0.55 | 2.407 | 1.289 |

## flu_surge

### Means

| Metric | `fixed` | `rule:acuity_first+favor_new` | `tuned_same_budget` | `dispatch_dispatch_flow_context` | `dispatch_dispatch_flow_linear` | `dispatch_dispatch_flow_mlp` | `dispatch_dispatch_only_linear` | `dispatch_joint_linear` | `ablate:dispatch_joint_linear:levers_only` | `ablate:dispatch_joint_linear:index_on_tuned` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 46.8 | 42.4 | 15.8 | 29.6 | 31.0 | 33.2 | 46.8 | 15.2 | 15.6 | 15.4 |
| 95th-percentile wait (min) | 200 | 185 | 35 | 77 | 80 | 78 | 200 | 31 | 34 | 32 |
| Median ED length of stay (min) | 251 | 254 | 209 | 214 | 213 | 214 | 251 | 194 | 208 | 195 |
| Mean ED length of stay (min) | 364 | 371 | 261 | 348 | 351 | 351 | 364 | 254 | 259 | 257 |
| ED census (patient-hours per day) (patient-h/day) | 1,480 | 1,512 | 1,048 | 1,454 | 1,489 | 1,469 | 1,480 | 1,020 | 1,037 | 1,031 |
| Left without being seen (% of arrivals) | 2.63 | 2.47 | 0.78 | 2.03 | 2.01 | 1.95 | 2.63 | 0.76 | 0.77 | 0.77 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 9.66 | 8.88 | 5.21 | 8.23 | 13.28 | 8.42 | 9.66 | 5.03 | 5.15 | 5.09 |
| Deaths (per 10,000 arrivals) | 8.28 | 8.28 | 5.58 | 9.23 | 9.80 | 9.80 | 8.28 | 5.60 | 5.55 | 5.63 |
| Adverse events (per day) | 0.91 | 0.90 | 0.53 | 0.94 | 1.07 | 0.97 | 0.91 | 0.53 | 0.53 | 0.53 |
| Boarding (patient-h/day) | 202.4 | 208.4 | 48.7 | 208.0 | 213.6 | 209.2 | 202.4 | 36.5 | 36.7 | 48.5 |
| Labour cost ($k/day) | 104.44 | 104.44 | 102.06 | 104.44 | 104.44 | 104.44 | 104.44 | 102.28 | 102.29 | 102.06 |
| Mean wait, triage ESI 1 (min) | 12.4 | 11.5 | 9.0 | 13.8 | 51.4 | 13.1 | 12.4 | 8.9 | 9.0 | 8.9 |
| Mean wait, triage ESI 2 (min) | 17.6 | 16.7 | 11.4 | 19.8 | 15.8 | 21.5 | 17.6 | 11.2 | 11.4 | 11.3 |
| Mean wait, triage ESI 3 (min) | 47.0 | 44.9 | 14.9 | 34.6 | 32.0 | 45.4 | 47.0 | 14.6 | 14.8 | 14.9 |
| Mean wait, triage ESI 4 (min) | 64.8 | 56.1 | 19.6 | 26.0 | 34.4 | 23.1 | 64.8 | 18.5 | 19.3 | 18.6 |
| Mean wait, triage ESI 5 (min) | 88.0 | 68.9 | 23.4 | 50.5 | 47.6 | 40.4 | 88.0 | 21.7 | 22.8 | 22.0 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 9.60 | 8.82 | 5.09 | 8.16 | 13.18 | 8.34 | 9.60 | 4.92 | 5.04 | 4.98 |
| ESI 3 waiting (patient-h/day) | 88.7 | 85.2 | 19.0 | 130.0 | 130.8 | 146.5 | 88.7 | 18.6 | 18.7 | 19.2 |
| ESI 4-5 waiting (patient-h/day) | 114.6 | 103.5 | 20.7 | 37.5 | 62.7 | 30.9 | 114.6 | 18.8 | 20.2 | 19.0 |
| Walk-outs, triage ESI 3 (per day) | 2.91 | 2.84 | 0.95 | 3.39 | 2.82 | 3.43 | 2.91 | 0.94 | 0.94 | 0.96 |
| Walk-outs, triage ESI 4 (per day) | 2.30 | 2.11 | 0.64 | 0.85 | 1.37 | 0.74 | 2.30 | 0.61 | 0.63 | 0.61 |
| Walk-outs, triage ESI 5 (per day) | 0.99 | 0.89 | 0.21 | 0.53 | 0.51 | 0.41 | 0.99 | 0.20 | 0.21 | 0.20 |
| Patient index (1 = baseline) | 1.000 | 0.945 | 0.487 | 0.827 | 1.005 | 0.850 | 1.000 | 0.475 | 0.484 | 0.478 |
| Flow index (1 = baseline) | 1.000 | 0.979 | 0.495 | 0.831 | 0.841 | 0.843 | 1.000 | 0.460 | 0.481 | 0.474 |

### Paired differences (a minus b; negative = a is lower)

**`dispatch_dispatch_flow_context` minus `fixed`** (patient index 0.827 vs 1.000; flow index 0.831 vs 1.000)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 29.6 | 46.8 | -17.17 [-30.19, -7.21] | 8 / 0 of 8 |
| 95th-percentile wait (min) | 77 | 200 | -123.2 [-220.4, -54.9] | 8 / 0 of 8 |
| Median ED length of stay (min) | 214 | 251 | -36.5 [-53.0, -21.6] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 348 | 364 | -16.4 [-32.1, -1.5] | 7 / 1 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,454 | 1,480 | -25.2 [-64.6, 24.6] (ns) | 6 / 2 of 8 |
| Left without being seen (% of arrivals) | 2.03 | 2.63 | -0.599 [-1.020, -0.252] | 8 / 0 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 8.23 | 9.66 | -1.423 [-2.355, -0.687] | 8 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 9.23 | 8.28 | 0.943 [0.200, 1.920] | 1 / 7 of 8 |
| Adverse events (per day) | 0.94 | 0.91 | 0.028 [-0.023, 0.096] (ns) | 4 / 4 of 8 |
| Boarding (patient-h/day) | 208.0 | 202.4 | 5.59 [-3.57, 17.55] (ns) | 2 / 6 of 8 |
| Labour cost ($k/day) | 104.44 | 104.44 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 1 (min) | 13.8 | 12.4 | 1.44 [-1.08, 5.05] (ns) | 1 / 7 of 8 |
| Mean wait, triage ESI 2 (min) | 19.8 | 17.6 | 2.17 [-1.30, 7.99] (ns) | 4 / 4 of 8 |
| Mean wait, triage ESI 3 (min) | 34.6 | 47.0 | -12.39 [-32.25, -1.54] | 6 / 2 of 8 |
| Mean wait, triage ESI 4 (min) | 26.0 | 64.8 | -38.82 [-62.30, -19.13] | 8 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 50.5 | 88.0 | -37.51 [-65.97, -13.28] | 7 / 1 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 8.16 | 9.60 | -1.439 [-2.362, -0.710] | 8 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 130.0 | 88.7 | 41.24 [6.86, 92.57] | 0 / 8 of 8 |
| ESI 4-5 waiting (patient-h/day) | 37.5 | 114.6 | -77.12 [-131.92, -34.59] | 8 / 0 of 8 |

**`dispatch_dispatch_flow_context` minus `rule:acuity_first+favor_new`** (patient index 0.827 vs 0.945; flow index 0.831 vs 0.979)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 29.6 | 42.4 | -12.83 [-25.28, -4.98] | 8 / 0 of 8 |
| 95th-percentile wait (min) | 77 | 185 | -107.9 [-206.3, -43.4] | 8 / 0 of 8 |
| Median ED length of stay (min) | 214 | 254 | -39.7 [-54.4, -26.2] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 348 | 371 | -23.4 [-36.9, -13.8] | 8 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,454 | 1,512 | -57.4 [-85.4, -36.2] | 8 / 0 of 8 |
| Left without being seen (% of arrivals) | 2.03 | 2.47 | -0.446 [-0.851, -0.175] | 8 / 0 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 8.23 | 8.88 | -0.647 [-0.958, -0.328] | 8 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 9.23 | 8.28 | 0.944 [0.205, 1.885] | 1 / 7 of 8 |
| Adverse events (per day) | 0.94 | 0.90 | 0.038 [-0.011, 0.100] (ns) | 4 / 4 of 8 |
| Boarding (patient-h/day) | 208.0 | 208.4 | -0.39 [-6.33, 6.28] (ns) | 4 / 4 of 8 |
| Labour cost ($k/day) | 104.44 | 104.44 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 1 (min) | 13.8 | 11.5 | 2.34 [0.18, 5.92] | 0 / 8 of 8 |
| Mean wait, triage ESI 2 (min) | 19.8 | 16.7 | 3.09 [-0.29, 8.80] (ns) | 3 / 5 of 8 |
| Mean wait, triage ESI 3 (min) | 34.6 | 44.9 | -10.34 [-30.24, -0.07] | 6 / 2 of 8 |
| Mean wait, triage ESI 4 (min) | 26.0 | 56.1 | -30.17 [-52.16, -13.60] | 8 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 50.5 | 68.9 | -18.47 [-39.94, -3.43] | 7 / 1 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 8.16 | 8.82 | -0.664 [-0.972, -0.363] | 7 / 1 of 8 |
| ESI 3 waiting (patient-h/day) | 130.0 | 85.2 | 44.76 [12.80, 93.42] | 0 / 8 of 8 |
| ESI 4-5 waiting (patient-h/day) | 37.5 | 103.5 | -66.03 [-121.28, -27.65] | 8 / 0 of 8 |

**`dispatch_dispatch_flow_context` minus `tuned_same_budget`** (patient index 0.827 vs 0.487; flow index 0.831 vs 0.495)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 29.6 | 15.8 | 13.78 [6.83, 23.35] | 0 / 8 of 8 |
| 95th-percentile wait (min) | 77 | 35 | 42.0 [17.7, 79.3] | 0 / 8 of 8 |
| Median ED length of stay (min) | 214 | 209 | 5.4 [-2.6, 15.3] (ns) | 3 / 5 of 8 |
| Mean ED length of stay (min) | 348 | 261 | 86.4 [52.4, 124.9] | 0 / 8 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,454 | 1,048 | 406.3 [236.5, 614.0] | 0 / 8 of 8 |
| Left without being seen (% of arrivals) | 2.03 | 0.78 | 1.248 [0.533, 2.278] | 0 / 8 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 8.23 | 5.21 | 3.023 [1.688, 4.794] | 0 / 8 of 8 |
| Deaths (per 10,000 arrivals) | 9.23 | 5.58 | 3.651 [1.633, 6.506] | 0 / 8 of 8 |
| Adverse events (per day) | 0.94 | 0.53 | 0.409 [0.189, 0.729] | 0 / 8 of 8 |
| Boarding (patient-h/day) | 208.0 | 48.7 | 159.31 [86.56, 243.46] | 0 / 8 of 8 |
| Labour cost ($k/day) | 104.44 | 102.06 | 2.372 [0.206, 4.721] | 3 / 5 of 8 |
| Mean wait, triage ESI 1 (min) | 13.8 | 9.0 | 4.85 [2.00, 9.23] | 0 / 8 of 8 |
| Mean wait, triage ESI 2 (min) | 19.8 | 11.4 | 8.34 [3.29, 16.75] | 0 / 8 of 8 |
| Mean wait, triage ESI 3 (min) | 34.6 | 14.9 | 19.67 [9.50, 33.52] | 0 / 8 of 8 |
| Mean wait, triage ESI 4 (min) | 26.0 | 19.6 | 6.41 [2.75, 11.92] | 0 / 8 of 8 |
| Mean wait, triage ESI 5 (min) | 50.5 | 23.4 | 27.03 [14.98, 42.60] | 0 / 8 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 8.16 | 5.09 | 3.072 [1.797, 4.787] | 0 / 8 of 8 |
| ESI 3 waiting (patient-h/day) | 130.0 | 19.0 | 110.99 [38.78, 224.09] | 0 / 8 of 8 |
| ESI 4-5 waiting (patient-h/day) | 37.5 | 20.7 | 16.86 [7.28, 31.94] | 0 / 8 of 8 |

**`dispatch_dispatch_flow_linear` minus `fixed`** (patient index 1.005 vs 1.000; flow index 0.841 vs 1.000)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 31.0 | 46.8 | -15.76 [-28.81, -5.83] | 8 / 0 of 8 |
| 95th-percentile wait (min) | 80 | 200 | -120.4 [-221.3, -53.1] | 8 / 0 of 8 |
| Median ED length of stay (min) | 213 | 251 | -37.3 [-53.4, -23.1] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 351 | 364 | -13.5 [-27.6, -0.1] | 7 / 1 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,489 | 1,480 | 9.3 [-30.3, 60.9] (ns) | 5 / 3 of 8 |
| Left without being seen (% of arrivals) | 2.01 | 2.63 | -0.618 [-1.051, -0.287] | 8 / 0 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 13.28 | 9.66 | 3.628 [-0.605, 10.642] (ns) | 3 / 5 of 8 |
| Deaths (per 10,000 arrivals) | 9.80 | 8.28 | 1.521 [0.438, 3.079] | 1 / 7 of 8 |
| Adverse events (per day) | 1.07 | 0.91 | 0.154 [0.024, 0.334] | 2 / 6 of 8 |
| Boarding (patient-h/day) | 213.6 | 202.4 | 11.15 [2.61, 23.11] | 0 / 8 of 8 |
| Labour cost ($k/day) | 104.44 | 104.44 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 1 (min) | 51.4 | 12.4 | 39.03 [6.25, 96.56] | 1 / 7 of 8 |
| Mean wait, triage ESI 2 (min) | 15.8 | 17.6 | -1.78 [-3.63, 0.01] (ns) | 7 / 1 of 8 |
| Mean wait, triage ESI 3 (min) | 32.0 | 47.0 | -14.97 [-36.56, -2.45] | 8 / 0 of 8 |
| Mean wait, triage ESI 4 (min) | 34.4 | 64.8 | -30.38 [-49.83, -13.97] | 8 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 47.6 | 88.0 | -40.36 [-68.94, -17.02] | 8 / 0 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 13.18 | 9.60 | 3.580 [-0.636, 10.554] (ns) | 3 / 5 of 8 |
| ESI 3 waiting (patient-h/day) | 130.8 | 88.7 | 42.05 [5.01, 95.26] | 0 / 8 of 8 |
| ESI 4-5 waiting (patient-h/day) | 62.7 | 114.6 | -51.93 [-86.44, -23.22] | 8 / 0 of 8 |

**`dispatch_dispatch_flow_linear` minus `rule:acuity_first+favor_new`** (patient index 1.005 vs 0.945; flow index 0.841 vs 0.979)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 31.0 | 42.4 | -11.42 [-24.09, -4.08] | 8 / 0 of 8 |
| 95th-percentile wait (min) | 80 | 185 | -105.2 [-207.6, -41.1] | 8 / 0 of 8 |
| Median ED length of stay (min) | 213 | 254 | -40.6 [-54.6, -27.5] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 351 | 371 | -20.5 [-32.5, -12.9] | 8 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,489 | 1,512 | -22.8 [-51.4, 10.7] (ns) | 6 / 2 of 8 |
| Left without being seen (% of arrivals) | 2.01 | 2.47 | -0.464 [-0.873, -0.202] | 8 / 0 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 13.28 | 8.88 | 4.404 [0.383, 11.317] | 2 / 6 of 8 |
| Deaths (per 10,000 arrivals) | 9.80 | 8.28 | 1.522 [0.466, 3.031] | 1 / 7 of 8 |
| Adverse events (per day) | 1.07 | 0.90 | 0.163 [0.041, 0.341] | 2 / 6 of 8 |
| Boarding (patient-h/day) | 213.6 | 208.4 | 5.18 [-0.01, 11.92] (ns) | 1 / 7 of 8 |
| Labour cost ($k/day) | 104.44 | 104.44 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 1 (min) | 51.4 | 11.5 | 39.93 [7.35, 97.22] | 1 / 7 of 8 |
| Mean wait, triage ESI 2 (min) | 15.8 | 16.7 | -0.87 [-2.28, 0.42] (ns) | 7 / 1 of 8 |
| Mean wait, triage ESI 3 (min) | 32.0 | 44.9 | -12.91 [-34.64, -1.14] | 8 / 0 of 8 |
| Mean wait, triage ESI 4 (min) | 34.4 | 56.1 | -21.73 [-38.87, -9.78] | 8 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 47.6 | 68.9 | -21.32 [-42.36, -6.82] | 8 / 0 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 13.18 | 8.82 | 4.355 [0.345, 11.244] | 2 / 6 of 8 |
| ESI 3 waiting (patient-h/day) | 130.8 | 85.2 | 45.57 [11.82, 96.71] | 0 / 8 of 8 |
| ESI 4-5 waiting (patient-h/day) | 62.7 | 103.5 | -40.83 [-74.40, -17.49] | 8 / 0 of 8 |

**`dispatch_dispatch_flow_linear` minus `tuned_same_budget`** (patient index 1.005 vs 0.487; flow index 0.841 vs 0.495)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 31.0 | 15.8 | 15.20 [7.17, 25.83] | 0 / 8 of 8 |
| 95th-percentile wait (min) | 80 | 35 | 44.8 [17.0, 85.2] | 0 / 8 of 8 |
| Median ED length of stay (min) | 213 | 209 | 4.5 [-4.0, 15.5] (ns) | 3 / 5 of 8 |
| Mean ED length of stay (min) | 351 | 261 | 89.3 [53.1, 130.4] | 0 / 8 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,489 | 1,048 | 440.9 [245.8, 677.1] | 0 / 8 of 8 |
| Left without being seen (% of arrivals) | 2.01 | 0.78 | 1.229 [0.507, 2.227] | 0 / 8 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 13.28 | 5.21 | 8.074 [2.978, 16.627] | 0 / 8 of 8 |
| Deaths (per 10,000 arrivals) | 9.80 | 5.58 | 4.229 [1.842, 7.688] | 0 / 8 of 8 |
| Adverse events (per day) | 1.07 | 0.53 | 0.535 [0.234, 0.971] | 0 / 8 of 8 |
| Boarding (patient-h/day) | 213.6 | 48.7 | 164.87 [89.96, 251.20] | 0 / 8 of 8 |
| Labour cost ($k/day) | 104.44 | 102.06 | 2.372 [0.206, 4.721] | 3 / 5 of 8 |
| Mean wait, triage ESI 1 (min) | 51.4 | 9.0 | 42.44 [9.12, 100.76] | 0 / 8 of 8 |
| Mean wait, triage ESI 2 (min) | 15.8 | 11.4 | 4.39 [2.56, 6.72] | 0 / 8 of 8 |
| Mean wait, triage ESI 3 (min) | 32.0 | 14.9 | 17.10 [8.05, 29.42] | 0 / 8 of 8 |
| Mean wait, triage ESI 4 (min) | 34.4 | 19.6 | 14.86 [6.99, 24.63] | 0 / 8 of 8 |
| Mean wait, triage ESI 5 (min) | 47.6 | 23.4 | 24.19 [11.49, 40.15] | 0 / 8 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 13.18 | 5.09 | 8.091 [3.070, 16.577] | 0 / 8 of 8 |
| ESI 3 waiting (patient-h/day) | 130.8 | 19.0 | 111.81 [38.29, 224.70] | 0 / 8 of 8 |
| ESI 4-5 waiting (patient-h/day) | 62.7 | 20.7 | 42.06 [16.39, 78.99] | 0 / 8 of 8 |

**`dispatch_dispatch_flow_mlp` minus `fixed`** (patient index 0.850 vs 1.000; flow index 0.843 vs 1.000)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 33.2 | 46.8 | -13.55 [-22.23, -6.11] | 8 / 0 of 8 |
| 95th-percentile wait (min) | 78 | 200 | -121.9 [-216.1, -55.5] | 8 / 0 of 8 |
| Median ED length of stay (min) | 214 | 251 | -36.8 [-53.4, -21.9] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 351 | 364 | -12.7 [-25.3, 0.7] (ns) | 7 / 1 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,469 | 1,480 | -10.7 [-45.3, 38.2] (ns) | 6 / 2 of 8 |
| Left without being seen (% of arrivals) | 1.95 | 2.63 | -0.675 [-1.111, -0.322] | 8 / 0 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 8.42 | 9.66 | -1.239 [-2.221, -0.469] | 8 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 9.80 | 8.28 | 1.517 [0.552, 2.893] | 0 / 8 of 8 |
| Adverse events (per day) | 0.97 | 0.91 | 0.058 [-0.007, 0.147] (ns) | 2 / 6 of 8 |
| Boarding (patient-h/day) | 209.2 | 202.4 | 6.76 [-2.18, 18.79] (ns) | 3 / 5 of 8 |
| Labour cost ($k/day) | 104.44 | 104.44 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 1 (min) | 13.1 | 12.4 | 0.72 [-1.07, 3.39] (ns) | 2 / 6 of 8 |
| Mean wait, triage ESI 2 (min) | 21.5 | 17.6 | 3.88 [-0.86, 11.31] (ns) | 4 / 4 of 8 |
| Mean wait, triage ESI 3 (min) | 45.4 | 47.0 | -1.60 [-9.14, 5.35] (ns) | 5 / 3 of 8 |
| Mean wait, triage ESI 4 (min) | 23.1 | 64.8 | -41.72 [-67.29, -20.39] | 8 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 40.4 | 88.0 | -47.59 [-77.55, -22.02] | 8 / 0 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 8.34 | 9.60 | -1.254 [-2.204, -0.498] | 8 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 146.5 | 88.7 | 57.77 [13.06, 123.76] | 0 / 8 of 8 |
| ESI 4-5 waiting (patient-h/day) | 30.9 | 114.6 | -83.75 [-143.99, -37.99] | 8 / 0 of 8 |

**`dispatch_dispatch_flow_mlp` minus `rule:acuity_first+favor_new`** (patient index 0.850 vs 0.945; flow index 0.843 vs 0.979)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 33.2 | 42.4 | -9.21 [-16.50, -4.41] | 8 / 0 of 8 |
| 95th-percentile wait (min) | 78 | 185 | -106.6 [-203.1, -43.3] | 8 / 0 of 8 |
| Median ED length of stay (min) | 214 | 254 | -40.0 [-54.9, -26.4] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 351 | 371 | -19.7 [-28.9, -12.8] | 8 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,469 | 1,512 | -42.9 [-66.0, -21.6] | 8 / 0 of 8 |
| Left without being seen (% of arrivals) | 1.95 | 2.47 | -0.521 [-0.946, -0.233] | 8 / 0 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 8.42 | 8.88 | -0.463 [-0.852, 0.084] (ns) | 7 / 1 of 8 |
| Deaths (per 10,000 arrivals) | 9.80 | 8.28 | 1.518 [0.565, 2.863] | 0 / 8 of 8 |
| Adverse events (per day) | 0.97 | 0.90 | 0.067 [0.008, 0.153] | 1 / 7 of 8 |
| Boarding (patient-h/day) | 209.2 | 208.4 | 0.78 [-4.86, 6.82] (ns) | 5 / 3 of 8 |
| Labour cost ($k/day) | 104.44 | 104.44 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 1 (min) | 13.1 | 11.5 | 1.62 [0.13, 4.15] | 1 / 7 of 8 |
| Mean wait, triage ESI 2 (min) | 21.5 | 16.7 | 4.79 [0.17, 12.19] | 3 / 5 of 8 |
| Mean wait, triage ESI 3 (min) | 45.4 | 44.9 | 0.46 [-6.17, 6.56] (ns) | 4 / 4 of 8 |
| Mean wait, triage ESI 4 (min) | 23.1 | 56.1 | -33.07 [-57.57, -14.84] | 8 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 40.4 | 68.9 | -28.56 [-54.15, -10.71] | 8 / 0 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 8.34 | 8.82 | -0.479 [-0.848, 0.058] (ns) | 7 / 1 of 8 |
| ESI 3 waiting (patient-h/day) | 146.5 | 85.2 | 61.30 [18.34, 125.90] | 0 / 8 of 8 |
| ESI 4-5 waiting (patient-h/day) | 30.9 | 103.5 | -72.66 [-133.84, -30.86] | 8 / 0 of 8 |

**`dispatch_dispatch_flow_mlp` minus `tuned_same_budget`** (patient index 0.850 vs 0.487; flow index 0.843 vs 0.495)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 33.2 | 15.8 | 17.40 [7.54, 31.71] | 0 / 8 of 8 |
| 95th-percentile wait (min) | 78 | 35 | 43.3 [17.0, 82.8] | 0 / 8 of 8 |
| Median ED length of stay (min) | 214 | 209 | 5.1 [-2.9, 14.8] (ns) | 3 / 5 of 8 |
| Mean ED length of stay (min) | 351 | 261 | 90.1 [53.7, 131.5] | 0 / 8 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,469 | 1,048 | 420.8 [242.9, 640.1] | 0 / 8 of 8 |
| Left without being seen (% of arrivals) | 1.95 | 0.78 | 1.172 [0.473, 2.181] | 0 / 8 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 8.42 | 5.21 | 3.207 [1.748, 5.311] | 0 / 8 of 8 |
| Deaths (per 10,000 arrivals) | 9.80 | 5.58 | 4.225 [1.966, 7.496] | 0 / 8 of 8 |
| Adverse events (per day) | 0.97 | 0.53 | 0.439 [0.205, 0.781] | 0 / 8 of 8 |
| Boarding (patient-h/day) | 209.2 | 48.7 | 160.48 [87.19, 243.44] | 0 / 8 of 8 |
| Labour cost ($k/day) | 104.44 | 102.06 | 2.372 [0.206, 4.721] | 3 / 5 of 8 |
| Mean wait, triage ESI 1 (min) | 13.1 | 9.0 | 4.13 [1.91, 7.78] | 0 / 8 of 8 |
| Mean wait, triage ESI 2 (min) | 21.5 | 11.4 | 10.04 [3.70, 20.28] | 0 / 8 of 8 |
| Mean wait, triage ESI 3 (min) | 45.4 | 14.9 | 30.47 [12.51, 56.50] | 0 / 8 of 8 |
| Mean wait, triage ESI 4 (min) | 23.1 | 19.6 | 3.51 [1.26, 6.74] | 0 / 8 of 8 |
| Mean wait, triage ESI 5 (min) | 40.4 | 23.4 | 16.95 [7.77, 29.21] | 1 / 7 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 8.34 | 5.09 | 3.257 [1.838, 5.324] | 0 / 8 of 8 |
| ESI 3 waiting (patient-h/day) | 146.5 | 19.0 | 127.53 [44.67, 253.84] | 0 / 8 of 8 |
| ESI 4-5 waiting (patient-h/day) | 30.9 | 20.7 | 10.24 [4.07, 19.59] | 0 / 8 of 8 |

**`dispatch_dispatch_only_linear` minus `fixed`** (patient index 1.000 vs 1.000; flow index 1.000 vs 1.000)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 46.8 | 46.8 | 0.00 [0.00, 0.00] (ns) | 0 / 0 of 8 |
| 95th-percentile wait (min) | 200 | 200 | 0.0 [0.0, 0.0] (ns) | 0 / 0 of 8 |
| Median ED length of stay (min) | 251 | 251 | 0.0 [0.0, 0.0] (ns) | 0 / 0 of 8 |
| Mean ED length of stay (min) | 364 | 364 | 0.0 [0.0, 0.0] (ns) | 0 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,480 | 1,480 | 0.0 [0.0, 0.0] (ns) | 0 / 0 of 8 |
| Left without being seen (% of arrivals) | 2.63 | 2.63 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 9.66 | 9.66 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 8.28 | 8.28 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Adverse events (per day) | 0.91 | 0.91 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Boarding (patient-h/day) | 202.4 | 202.4 | 0.00 [0.00, 0.00] (ns) | 0 / 0 of 8 |
| Labour cost ($k/day) | 104.44 | 104.44 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 1 (min) | 12.4 | 12.4 | 0.00 [0.00, 0.00] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 2 (min) | 17.6 | 17.6 | 0.00 [0.00, 0.00] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 3 (min) | 47.0 | 47.0 | 0.00 [0.00, 0.00] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 4 (min) | 64.8 | 64.8 | 0.00 [0.00, 0.00] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 88.0 | 88.0 | 0.00 [0.00, 0.00] (ns) | 0 / 0 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 9.60 | 9.60 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 88.7 | 88.7 | 0.00 [0.00, 0.00] (ns) | 0 / 0 of 8 |
| ESI 4-5 waiting (patient-h/day) | 114.6 | 114.6 | 0.00 [0.00, 0.00] (ns) | 0 / 0 of 8 |

**`dispatch_dispatch_only_linear` minus `rule:acuity_first+favor_new`** (patient index 1.000 vs 0.945; flow index 1.000 vs 0.979)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 46.8 | 42.4 | 4.34 [0.00, 11.20] (ns) | 0 / 2 of 8 |
| 95th-percentile wait (min) | 200 | 185 | 15.3 [0.0, 43.3] (ns) | 0 / 2 of 8 |
| Median ED length of stay (min) | 251 | 254 | -3.3 [-8.9, 0.0] (ns) | 2 / 0 of 8 |
| Mean ED length of stay (min) | 364 | 371 | -7.0 [-18.8, 0.0] (ns) | 2 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,480 | 1,512 | -32.1 [-85.8, 0.0] (ns) | 2 / 0 of 8 |
| Left without being seen (% of arrivals) | 2.63 | 2.47 | 0.154 [0.000, 0.413] (ns) | 0 / 2 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 9.66 | 8.88 | 0.776 [0.000, 1.816] (ns) | 0 / 2 of 8 |
| Deaths (per 10,000 arrivals) | 8.28 | 8.28 | 0.001 [-0.148, 0.150] (ns) | 1 / 1 of 8 |
| Adverse events (per day) | 0.91 | 0.90 | 0.009 [-0.003, 0.031] (ns) | 0 / 2 of 8 |
| Boarding (patient-h/day) | 202.4 | 208.4 | -5.98 [-18.27, 0.00] (ns) | 2 / 0 of 8 |
| Labour cost ($k/day) | 104.44 | 104.44 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 1 (min) | 12.4 | 11.5 | 0.90 [0.00, 2.17] (ns) | 0 / 2 of 8 |
| Mean wait, triage ESI 2 (min) | 17.6 | 16.7 | 0.91 [0.00, 2.13] (ns) | 0 / 2 of 8 |
| Mean wait, triage ESI 3 (min) | 47.0 | 44.9 | 2.06 [0.00, 6.04] (ns) | 0 / 2 of 8 |
| Mean wait, triage ESI 4 (min) | 64.8 | 56.1 | 8.65 [0.00, 22.21] (ns) | 0 / 2 of 8 |
| Mean wait, triage ESI 5 (min) | 88.0 | 68.9 | 19.03 [0.00, 47.12] (ns) | 0 / 2 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 9.60 | 8.82 | 0.775 [0.000, 1.807] (ns) | 0 / 2 of 8 |
| ESI 3 waiting (patient-h/day) | 88.7 | 85.2 | 3.52 [-0.46, 10.95] (ns) | 0 / 2 of 8 |
| ESI 4-5 waiting (patient-h/day) | 114.6 | 103.5 | 11.09 [0.00, 30.35] (ns) | 0 / 2 of 8 |

**`dispatch_joint_linear` minus `fixed`** (patient index 0.475 vs 1.000; flow index 0.460 vs 1.000)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 15.2 | 46.8 | -31.50 [-52.32, -15.68] | 8 / 0 of 8 |
| 95th-percentile wait (min) | 31 | 200 | -168.8 [-298.5, -77.8] | 8 / 0 of 8 |
| Median ED length of stay (min) | 194 | 251 | -56.5 [-81.6, -35.4] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 254 | 364 | -109.7 [-162.5, -64.3] | 8 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,020 | 1,480 | -459.7 [-681.8, -265.9] | 8 / 0 of 8 |
| Left without being seen (% of arrivals) | 0.76 | 2.63 | -1.867 [-3.232, -0.895] | 8 / 0 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 5.03 | 9.66 | -4.626 [-6.474, -2.991] | 8 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 5.60 | 8.28 | -2.679 [-4.823, -1.157] | 8 / 0 of 8 |
| Adverse events (per day) | 0.53 | 0.91 | -0.385 [-0.657, -0.201] | 8 / 0 of 8 |
| Boarding (patient-h/day) | 36.5 | 202.4 | -165.86 [-256.19, -89.47] | 8 / 0 of 8 |
| Labour cost ($k/day) | 102.28 | 104.44 | -2.154 [-4.493, -0.043] | 4 / 4 of 8 |
| Mean wait, triage ESI 1 (min) | 8.9 | 12.4 | -3.45 [-5.53, -1.81] | 8 / 0 of 8 |
| Mean wait, triage ESI 2 (min) | 11.2 | 17.6 | -6.39 [-9.44, -4.05] | 8 / 0 of 8 |
| Mean wait, triage ESI 3 (min) | 14.6 | 47.0 | -32.34 [-59.98, -14.40] | 8 / 0 of 8 |
| Mean wait, triage ESI 4 (min) | 18.5 | 64.8 | -46.34 [-74.73, -23.20] | 8 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 21.7 | 88.0 | -66.25 [-104.42, -33.11] | 8 / 0 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 4.92 | 9.60 | -4.673 [-6.481, -3.077] | 8 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 18.6 | 88.7 | -70.15 [-133.24, -30.43] | 8 / 0 of 8 |
| ESI 4-5 waiting (patient-h/day) | 18.8 | 114.6 | -95.80 [-164.32, -43.78] | 8 / 0 of 8 |

**`dispatch_joint_linear` minus `rule:acuity_first+favor_new`** (patient index 0.475 vs 0.945; flow index 0.460 vs 0.979)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 15.2 | 42.4 | -27.17 [-48.25, -12.69] | 8 / 0 of 8 |
| 95th-percentile wait (min) | 31 | 185 | -153.6 [-289.6, -65.5] | 8 / 0 of 8 |
| Median ED length of stay (min) | 194 | 254 | -59.8 [-83.9, -39.7] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 254 | 371 | -116.8 [-167.2, -72.9] | 8 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,020 | 1,512 | -491.8 [-713.1, -304.9] | 8 / 0 of 8 |
| Left without being seen (% of arrivals) | 0.76 | 2.47 | -1.713 [-3.131, -0.734] | 8 / 0 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 5.03 | 8.88 | -3.850 [-5.598, -2.504] | 8 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 5.60 | 8.28 | -2.678 [-4.840, -1.128] | 8 / 0 of 8 |
| Adverse events (per day) | 0.53 | 0.90 | -0.376 [-0.654, -0.190] | 8 / 0 of 8 |
| Boarding (patient-h/day) | 36.5 | 208.4 | -171.84 [-262.17, -93.78] | 8 / 0 of 8 |
| Labour cost ($k/day) | 102.28 | 104.44 | -2.154 [-4.493, -0.043] | 4 / 4 of 8 |
| Mean wait, triage ESI 1 (min) | 8.9 | 11.5 | -2.55 [-4.38, -1.43] | 8 / 0 of 8 |
| Mean wait, triage ESI 2 (min) | 11.2 | 16.7 | -5.47 [-8.39, -3.46] | 8 / 0 of 8 |
| Mean wait, triage ESI 3 (min) | 14.6 | 44.9 | -30.29 [-58.35, -12.32] | 8 / 0 of 8 |
| Mean wait, triage ESI 4 (min) | 18.5 | 56.1 | -37.69 [-64.82, -17.79] | 8 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 21.7 | 68.9 | -47.22 [-82.51, -21.74] | 8 / 0 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 4.92 | 8.82 | -3.899 [-5.597, -2.576] | 8 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 18.6 | 85.2 | -66.62 [-131.36, -26.19] | 8 / 0 of 8 |
| ESI 4-5 waiting (patient-h/day) | 18.8 | 103.5 | -84.71 [-155.34, -36.42] | 8 / 0 of 8 |

**`dispatch_joint_linear` minus `tuned_same_budget`** (patient index 0.475 vs 0.487; flow index 0.460 vs 0.495)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 15.2 | 15.8 | -0.55 [-1.05, -0.24] | 8 / 0 of 8 |
| 95th-percentile wait (min) | 31 | 35 | -3.6 [-6.9, -1.4] | 8 / 0 of 8 |
| Median ED length of stay (min) | 194 | 209 | -14.7 [-18.1, -11.3] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 254 | 261 | -6.9 [-9.6, -4.7] | 8 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,020 | 1,048 | -28.1 [-39.4, -19.0] | 8 / 0 of 8 |
| Left without being seen (% of arrivals) | 0.76 | 0.78 | -0.020 [-0.040, -0.002] | 7 / 1 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 5.03 | 5.21 | -0.180 [-0.293, -0.092] | 8 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 5.60 | 5.58 | 0.029 [-0.184, 0.252] (ns) | 3 / 5 of 8 |
| Adverse events (per day) | 0.53 | 0.53 | -0.004 [-0.016, 0.005] (ns) | 6 / 1 of 8 |
| Boarding (patient-h/day) | 36.5 | 48.7 | -12.14 [-19.11, -6.67] | 8 / 0 of 8 |
| Labour cost ($k/day) | 102.28 | 102.06 | 0.218 [0.119, 0.312] | 0 / 8 of 8 |
| Mean wait, triage ESI 1 (min) | 8.9 | 9.0 | -0.04 [-0.15, 0.13] (ns) | 7 / 1 of 8 |
| Mean wait, triage ESI 2 (min) | 11.2 | 11.4 | -0.22 [-0.34, -0.11] | 8 / 0 of 8 |
| Mean wait, triage ESI 3 (min) | 14.6 | 14.9 | -0.28 [-0.51, -0.11] | 8 / 0 of 8 |
| Mean wait, triage ESI 4 (min) | 18.5 | 19.6 | -1.11 [-2.21, -0.40] | 8 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 21.7 | 23.4 | -1.71 [-3.81, -0.49] | 8 / 0 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 4.92 | 5.09 | -0.163 [-0.254, -0.085] | 8 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 18.6 | 19.0 | -0.39 [-0.79, 0.01] (ns) | 7 / 1 of 8 |
| ESI 4-5 waiting (patient-h/day) | 18.8 | 20.7 | -1.81 [-3.60, -0.67] | 8 / 0 of 8 |

**`dispatch_joint_linear` minus `ablate:dispatch_joint_linear:levers_only`** (patient index 0.475 vs 0.484; flow index 0.460 vs 0.481)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 15.2 | 15.6 | -0.36 [-0.59, -0.17] | 8 / 0 of 8 |
| 95th-percentile wait (min) | 31 | 34 | -2.8 [-4.8, -1.2] | 8 / 0 of 8 |
| Median ED length of stay (min) | 194 | 208 | -14.4 [-18.0, -10.7] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 254 | 259 | -4.2 [-5.8, -2.9] | 8 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,020 | 1,037 | -17.2 [-23.2, -11.8] | 8 / 0 of 8 |
| Left without being seen (% of arrivals) | 0.76 | 0.77 | -0.011 [-0.029, 0.006] (ns) | 5 / 3 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 5.03 | 5.15 | -0.123 [-0.192, -0.061] | 8 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 5.60 | 5.55 | 0.051 [-0.141, 0.260] (ns) | 3 / 5 of 8 |
| Adverse events (per day) | 0.53 | 0.53 | -0.004 [-0.013, 0.005] (ns) | 7 / 1 of 8 |
| Boarding (patient-h/day) | 36.5 | 36.7 | -0.16 [-1.56, 1.14] (ns) | 6 / 2 of 8 |
| Labour cost ($k/day) | 102.28 | 102.29 | -0.004 [-0.024, 0.014] (ns) | 3 / 4 of 8 |
| Mean wait, triage ESI 1 (min) | 8.9 | 9.0 | -0.03 [-0.14, 0.15] (ns) | 7 / 1 of 8 |
| Mean wait, triage ESI 2 (min) | 11.2 | 11.4 | -0.15 [-0.23, -0.08] | 8 / 0 of 8 |
| Mean wait, triage ESI 3 (min) | 14.6 | 14.8 | -0.13 [-0.32, 0.05] (ns) | 5 / 3 of 8 |
| Mean wait, triage ESI 4 (min) | 18.5 | 19.3 | -0.82 [-1.46, -0.33] | 8 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 21.7 | 22.8 | -1.05 [-2.21, -0.31] | 8 / 0 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 4.92 | 5.04 | -0.113 [-0.178, -0.056] | 8 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 18.6 | 18.7 | -0.09 [-0.51, 0.44] (ns) | 5 / 3 of 8 |
| ESI 4-5 waiting (patient-h/day) | 18.8 | 20.2 | -1.31 [-2.35, -0.53] | 8 / 0 of 8 |

**`ablate:dispatch_joint_linear:index_on_tuned` minus `tuned_same_budget`** (patient index 0.478 vs 0.487; flow index 0.474 vs 0.495)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 15.4 | 15.8 | -0.39 [-0.64, -0.19] | 8 / 0 of 8 |
| 95th-percentile wait (min) | 32 | 35 | -3.3 [-5.9, -1.5] | 8 / 0 of 8 |
| Median ED length of stay (min) | 195 | 209 | -14.2 [-17.6, -10.9] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 257 | 261 | -4.1 [-5.4, -3.0] | 8 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,031 | 1,048 | -16.7 [-22.1, -11.7] | 8 / 0 of 8 |
| Left without being seen (% of arrivals) | 0.77 | 0.78 | -0.013 [-0.030, 0.004] (ns) | 5 / 3 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 5.09 | 5.21 | -0.121 [-0.208, -0.045] | 8 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 5.63 | 5.58 | 0.050 [-0.159, 0.258] (ns) | 3 / 5 of 8 |
| Adverse events (per day) | 0.53 | 0.53 | -0.004 [-0.014, 0.005] (ns) | 7 / 1 of 8 |
| Boarding (patient-h/day) | 48.5 | 48.7 | -0.17 [-2.68, 2.47] (ns) | 5 / 3 of 8 |
| Labour cost ($k/day) | 102.06 | 102.06 | -0.001 [-0.017, 0.015] (ns) | 4 / 4 of 8 |
| Mean wait, triage ESI 1 (min) | 8.9 | 9.0 | -0.07 [-0.14, 0.01] (ns) | 7 / 1 of 8 |
| Mean wait, triage ESI 2 (min) | 11.3 | 11.4 | -0.15 [-0.25, -0.06] | 8 / 0 of 8 |
| Mean wait, triage ESI 3 (min) | 14.9 | 14.9 | -0.04 [-0.29, 0.29] (ns) | 5 / 3 of 8 |
| Mean wait, triage ESI 4 (min) | 18.6 | 19.6 | -1.00 [-1.95, -0.40] | 8 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 22.0 | 23.4 | -1.38 [-3.09, -0.43] | 8 / 0 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 4.98 | 5.09 | -0.107 [-0.182, -0.035] | 8 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 19.2 | 19.0 | 0.19 [-0.45, 1.30] (ns) | 5 / 3 of 8 |
| ESI 4-5 waiting (patient-h/day) | 19.0 | 20.7 | -1.63 [-3.16, -0.66] | 8 / 0 of 8 |

**`tuned_same_budget` minus `fixed`** (patient index 0.487 vs 1.000; flow index 0.495 vs 1.000)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 15.8 | 46.8 | -30.95 [-51.46, -15.30] | 8 / 0 of 8 |
| 95th-percentile wait (min) | 35 | 200 | -165.2 [-294.7, -74.8] | 8 / 0 of 8 |
| Median ED length of stay (min) | 209 | 251 | -41.8 [-65.6, -22.6] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 261 | 364 | -102.8 [-153.2, -59.0] | 8 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,048 | 1,480 | -431.5 [-646.3, -245.1] | 8 / 0 of 8 |
| Left without being seen (% of arrivals) | 0.78 | 2.63 | -1.847 [-3.204, -0.886] | 8 / 0 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 5.21 | 9.66 | -4.446 [-6.283, -2.813] | 8 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 5.58 | 8.28 | -2.709 [-4.821, -1.225] | 8 / 0 of 8 |
| Adverse events (per day) | 0.53 | 0.91 | -0.381 [-0.645, -0.199] | 8 / 0 of 8 |
| Boarding (patient-h/day) | 48.7 | 202.4 | -153.72 [-238.24, -81.48] | 8 / 0 of 8 |
| Labour cost ($k/day) | 102.06 | 104.44 | -2.372 [-4.721, -0.206] | 5 / 3 of 8 |
| Mean wait, triage ESI 1 (min) | 9.0 | 12.4 | -3.40 [-5.49, -1.77] | 8 / 0 of 8 |
| Mean wait, triage ESI 2 (min) | 11.4 | 17.6 | -6.17 [-9.20, -3.84] | 8 / 0 of 8 |
| Mean wait, triage ESI 3 (min) | 14.9 | 47.0 | -32.07 [-59.64, -14.14] | 8 / 0 of 8 |
| Mean wait, triage ESI 4 (min) | 19.6 | 64.8 | -45.23 [-73.27, -22.45] | 8 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 23.4 | 88.0 | -64.54 [-102.38, -31.88] | 8 / 0 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 5.09 | 9.60 | -4.511 [-6.312, -2.914] | 8 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 19.0 | 88.7 | -69.76 [-132.60, -29.95] | 8 / 0 of 8 |
| ESI 4-5 waiting (patient-h/day) | 20.7 | 114.6 | -93.99 [-161.48, -42.42] | 8 / 0 of 8 |

**`rule:acuity_first+favor_new` minus `fixed`** (patient index 0.945 vs 1.000; flow index 0.979 vs 1.000)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 42.4 | 46.8 | -4.34 [-11.20, 0.00] (ns) | 2 / 0 of 8 |
| 95th-percentile wait (min) | 185 | 200 | -15.3 [-43.3, 0.0] (ns) | 2 / 0 of 8 |
| Median ED length of stay (min) | 254 | 251 | 3.3 [0.0, 8.9] (ns) | 0 / 2 of 8 |
| Mean ED length of stay (min) | 371 | 364 | 7.0 [0.0, 18.8] (ns) | 0 / 2 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,512 | 1,480 | 32.1 [0.0, 85.8] (ns) | 0 / 2 of 8 |
| Left without being seen (% of arrivals) | 2.47 | 2.63 | -0.154 [-0.413, 0.000] (ns) | 2 / 0 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 8.88 | 9.66 | -0.776 [-1.816, 0.000] (ns) | 2 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 8.28 | 8.28 | -0.001 [-0.150, 0.148] (ns) | 1 / 1 of 8 |
| Adverse events (per day) | 0.90 | 0.91 | -0.009 [-0.031, 0.003] (ns) | 2 / 0 of 8 |
| Boarding (patient-h/day) | 208.4 | 202.4 | 5.98 [0.00, 18.27] (ns) | 0 / 2 of 8 |
| Labour cost ($k/day) | 104.44 | 104.44 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 1 (min) | 11.5 | 12.4 | -0.90 [-2.17, 0.00] (ns) | 2 / 0 of 8 |
| Mean wait, triage ESI 2 (min) | 16.7 | 17.6 | -0.91 [-2.13, 0.00] (ns) | 2 / 0 of 8 |
| Mean wait, triage ESI 3 (min) | 44.9 | 47.0 | -2.06 [-6.04, 0.00] (ns) | 2 / 0 of 8 |
| Mean wait, triage ESI 4 (min) | 56.1 | 64.8 | -8.65 [-22.21, 0.00] (ns) | 2 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 68.9 | 88.0 | -19.03 [-47.12, 0.00] (ns) | 2 / 0 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 8.82 | 9.60 | -0.775 [-1.807, 0.000] (ns) | 2 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 85.2 | 88.7 | -3.52 [-10.95, 0.46] (ns) | 2 / 0 of 8 |
| ESI 4-5 waiting (patient-h/day) | 103.5 | 114.6 | -11.09 [-30.35, 0.00] (ns) | 2 / 0 of 8 |

### same_budget_better_flow on held-out episodes (no tuning margin)

| Arm | score on pooled means (higher is better) | feasible | members feasible | mean per-member score | violated |
|---|---:|---|---:|---:|---|
| `dispatch_dispatch_flow_context` | -0.0129 | False | 1 / 8 | -0.0162 | deaths_per_10k, adverse_events_per_day |
| `dispatch_dispatch_flow_linear` | -4.2664 | False | 1 / 8 | -4.2027 | deaths_per_10k, adverse_events_per_day, hi_acuity_wait_hours_per_day |
| `dispatch_dispatch_flow_mlp` | -0.1975 | False | 0 / 8 | -0.1720 | deaths_per_10k, adverse_events_per_day |
| `dispatch_dispatch_only_linear` | +0.0000 | True | 8 / 8 | -0.0000 | - |
| `dispatch_joint_linear` | +0.5077 | False | 3 / 8 | +0.3882 | transfers_per_day |
| `ablate:dispatch_joint_linear:levers_only` | +0.4984 | False | 3 / 8 | +0.3748 | transfers_per_day |
| `ablate:dispatch_joint_linear:index_on_tuned` | +0.4887 | False | 3 / 8 | +0.3811 | transfers_per_day |
| `rule:fcfs+favor_new` | -23.6576 | False | 0 / 8 | -22.5210 | deaths_per_10k, adverse_events_per_day, hi_acuity_wait_hours_per_day |
| `rule:fcfs+balanced` | -25.9386 | False | 0 / 8 | -25.0159 | deaths_per_10k, adverse_events_per_day, hi_acuity_wait_hours_per_day |
| `rule:fcfs+favor_dispositions` | -37.9713 | False | 0 / 8 | -38.2720 | deaths_per_10k, adverse_events_per_day, hi_acuity_wait_hours_per_day |
| `rule:acuity_first+favor_new` | +0.0297 | True | 7 / 8 | +0.0187 | - |
| `rule:acuity_first+balanced` | +0.0059 | False | 2 / 8 | -0.0386 | deaths_per_10k |
| `rule:acuity_first+favor_dispositions` | -3.1267 | False | 2 / 8 | -3.7703 | deaths_per_10k, hi_acuity_wait_hours_per_day |
| `rule:acuity_with_aging+favor_new` | -18.0237 | False | 0 / 8 | -16.7936 | deaths_per_10k, adverse_events_per_day, hi_acuity_wait_hours_per_day |
| `rule:acuity_with_aging+balanced` | -17.1918 | False | 0 / 8 | -16.0604 | deaths_per_10k, adverse_events_per_day, hi_acuity_wait_hours_per_day |
| `rule:acuity_with_aging+favor_dispositions` | -23.0766 | False | 0 / 8 | -22.9569 | deaths_per_10k, adverse_events_per_day, hi_acuity_wait_hours_per_day |
| `rule:shortest_first+favor_new` | -58.8901 | False | 0 / 8 | -56.5449 | deaths_per_10k, adverse_events_per_day, hi_acuity_wait_hours_per_day |
| `rule:shortest_first+balanced` | -62.4402 | False | 0 / 8 | -60.7273 | deaths_per_10k, adverse_events_per_day, hi_acuity_wait_hours_per_day |
| `rule:shortest_first+favor_dispositions` | -93.3845 | False | 0 / 8 | -94.2363 | deaths_per_10k, adverse_events_per_day, hi_acuity_wait_hours_per_day |
| `tuned_same_budget` | +0.4843 | False | 3 / 8 | +0.3714 | transfers_per_day |

### Patient index per ensemble member (1 = that member's baseline)

| Arm | m0 | m1 | m2 | m3 | m4 | m5 | m6 | m7 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `dispatch_dispatch_flow_context` | 0.875 | 0.840 | 0.710 | 0.940 | 0.851 | 0.622 | 0.847 | 0.934 |
| `dispatch_dispatch_flow_linear` | 0.945 | 1.269 | 0.954 | 0.940 | 1.214 | 0.699 | 1.088 | 0.933 |
| `dispatch_dispatch_flow_mlp` | 0.889 | 0.889 | 0.761 | 0.914 | 0.886 | 0.657 | 0.875 | 0.930 |
| `dispatch_dispatch_only_linear` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| `dispatch_joint_linear` | 0.619 | 0.305 | 0.346 | 0.724 | 0.398 | 0.327 | 0.514 | 0.568 |
| `rule:acuity_first+favor_new` | 1.000 | 1.000 | 0.841 | 1.000 | 1.000 | 0.721 | 1.000 | 1.000 |
| `tuned_same_budget` | 0.639 | 0.319 | 0.354 | 0.752 | 0.412 | 0.331 | 0.519 | 0.570 |

### Flow index per ensemble member (1 = that member's baseline)

| Arm | m0 | m1 | m2 | m3 | m4 | m5 | m6 | m7 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `dispatch_dispatch_flow_context` | 0.874 | 0.777 | 0.780 | 0.946 | 0.804 | 0.742 | 0.815 | 0.908 |
| `dispatch_dispatch_flow_linear` | 0.878 | 0.778 | 0.781 | 0.931 | 0.854 | 0.746 | 0.860 | 0.901 |
| `dispatch_dispatch_flow_mlp` | 0.876 | 0.801 | 0.815 | 0.921 | 0.829 | 0.767 | 0.832 | 0.899 |
| `dispatch_dispatch_only_linear` | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| `dispatch_joint_linear` | 0.551 | 0.317 | 0.402 | 0.660 | 0.387 | 0.390 | 0.453 | 0.518 |
| `rule:acuity_first+favor_new` | 1.000 | 1.000 | 0.944 | 1.000 | 1.000 | 0.885 | 1.000 | 1.000 |
| `tuned_same_budget` | 0.600 | 0.353 | 0.433 | 0.707 | 0.423 | 0.420 | 0.484 | 0.542 |

### All hard-coded rule arms

| Arm | wait | p95 | LOS median | LWBS % | ESI 1-2 waiting h/day | adverse/day | patient index | flow index |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `fixed` | 46.8 | 200 | 251 | 2.63 | 9.66 | 0.91 | 1.000 | 1.000 |
| `rule:fcfs+favor_new` | 42.6 | 167 | 270 | 1.93 | 32.01 | 1.03 | 1.609 | 0.956 |
| `rule:fcfs+balanced` | 44.3 | 169 | 265 | 1.99 | 34.15 | 1.03 | 1.706 | 0.971 |
| `rule:fcfs+favor_dispositions` | 61.5 | 227 | 230 | 2.76 | 45.42 | 1.08 | 2.321 | 1.109 |
| `rule:acuity_first+favor_new` | 42.4 | 185 | 254 | 2.47 | 8.88 | 0.90 | 0.945 | 0.979 |
| `rule:acuity_first+balanced` | 44.7 | 196 | 250 | 2.59 | 8.56 | 0.90 | 0.965 | 1.002 |
| `rule:acuity_first+favor_dispositions` | 63.6 | 269 | 227 | 3.51 | 12.54 | 0.90 | 1.345 | 1.185 |
| `rule:acuity_with_aging+favor_new` | 44.6 | 179 | 275 | 2.09 | 26.66 | 1.00 | 1.459 | 0.987 |
| `rule:acuity_with_aging+balanced` | 46.1 | 185 | 270 | 2.16 | 25.89 | 0.99 | 1.458 | 1.000 |
| `rule:acuity_with_aging+favor_dispositions` | 63.5 | 243 | 233 | 3.03 | 31.48 | 0.99 | 1.894 | 1.150 |
| `rule:shortest_first+favor_new` | 32.8 | 110 | 228 | 1.24 | 65.42 | 1.13 | 2.533 | 0.807 |
| `rule:shortest_first+balanced` | 33.9 | 113 | 225 | 1.26 | 68.74 | 1.15 | 2.672 | 0.813 |
| `rule:shortest_first+favor_dispositions` | 53.0 | 203 | 213 | 1.96 | 97.74 | 1.28 | 3.900 | 0.985 |

## pooled

### Means

| Metric | `fixed` | `rule:acuity_first+favor_new` | `tuned_same_budget` | `dispatch_dispatch_flow_context` | `dispatch_dispatch_flow_linear` | `dispatch_dispatch_flow_mlp` | `dispatch_dispatch_only_linear` | `dispatch_joint_linear` | `ablate:dispatch_joint_linear:levers_only` | `ablate:dispatch_joint_linear:index_on_tuned` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 32.7 | 28.9 | 14.9 | 22.4 | 23.0 | 24.1 | 32.7 | 14.6 | 14.8 | 14.7 |
| 95th-percentile wait (min) | 125 | 108 | 31 | 54 | 55 | 54 | 125 | 29 | 31 | 29 |
| Median ED length of stay (min) | 227 | 229 | 201 | 203 | 202 | 202 | 227 | 190 | 201 | 190 |
| Mean ED length of stay (min) | 308 | 312 | 248 | 298 | 299 | 300 | 308 | 243 | 246 | 245 |
| ED census (patient-hours per day) (patient-h/day) | 1,201 | 1,220 | 954 | 1,182 | 1,199 | 1,190 | 1,201 | 937 | 948 | 943 |
| Left without being seen (% of arrivals) | 1.75 | 1.61 | 0.73 | 1.39 | 1.37 | 1.34 | 1.75 | 0.73 | 0.73 | 0.73 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 7.37 | 6.75 | 4.67 | 6.36 | 8.90 | 6.46 | 7.37 | 4.56 | 4.64 | 4.59 |
| Deaths (per 10,000 arrivals) | 6.79 | 6.74 | 5.24 | 7.20 | 7.54 | 7.49 | 6.79 | 5.28 | 5.22 | 5.30 |
| Adverse events (per day) | 0.67 | 0.66 | 0.45 | 0.68 | 0.74 | 0.69 | 0.67 | 0.45 | 0.45 | 0.45 |
| Boarding (patient-h/day) | 109.1 | 112.1 | 27.8 | 111.7 | 114.6 | 112.4 | 109.1 | 21.2 | 21.3 | 27.7 |
| Labour cost ($k/day) | 105.15 | 105.15 | 102.22 | 105.15 | 105.15 | 105.15 | 105.15 | 102.25 | 102.25 | 102.21 |
| Mean wait, triage ESI 1 (min) | 11.0 | 10.3 | 8.8 | 11.4 | 30.2 | 11.1 | 11.0 | 8.7 | 8.8 | 8.7 |
| Mean wait, triage ESI 2 (min) | 14.8 | 14.0 | 11.0 | 15.4 | 13.5 | 16.3 | 14.8 | 10.9 | 11.0 | 10.9 |
| Mean wait, triage ESI 3 (min) | 31.5 | 29.6 | 14.0 | 24.5 | 23.1 | 29.9 | 31.5 | 13.8 | 13.9 | 14.0 |
| Mean wait, triage ESI 4 (min) | 45.2 | 37.6 | 18.5 | 22.1 | 26.3 | 20.6 | 45.2 | 17.9 | 18.3 | 17.9 |
| Mean wait, triage ESI 5 (min) | 63.0 | 45.6 | 21.6 | 38.1 | 34.8 | 31.1 | 63.0 | 20.7 | 21.3 | 20.9 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 7.33 | 6.71 | 4.58 | 6.32 | 8.83 | 6.41 | 7.33 | 4.49 | 4.56 | 4.51 |
| ESI 3 waiting (patient-h/day) | 54.0 | 50.8 | 16.6 | 73.2 | 73.4 | 81.5 | 54.0 | 16.3 | 16.4 | 16.6 |
| ESI 4-5 waiting (patient-h/day) | 71.2 | 61.0 | 18.5 | 27.9 | 40.4 | 24.4 | 71.2 | 17.7 | 18.2 | 17.8 |
| Walk-outs, triage ESI 3 (per day) | 1.90 | 1.83 | 0.86 | 2.12 | 1.82 | 2.13 | 1.90 | 0.86 | 0.85 | 0.87 |
| Walk-outs, triage ESI 4 (per day) | 1.50 | 1.33 | 0.57 | 0.69 | 0.95 | 0.63 | 1.50 | 0.56 | 0.57 | 0.56 |
| Walk-outs, triage ESI 5 (per day) | 0.63 | 0.53 | 0.19 | 0.37 | 0.34 | 0.29 | 0.63 | 0.18 | 0.19 | 0.18 |
| Patient index (1 = baseline) | 1.000 | 0.930 | 0.659 | 0.866 | 0.952 | 0.873 | 1.000 | 0.653 | 0.658 | 0.653 |
| Flow index (1 = baseline) | 1.000 | 0.962 | 0.649 | 0.877 | 0.876 | 0.879 | 1.000 | 0.618 | 0.634 | 0.632 |

### Paired differences (a minus b; negative = a is lower)

**`dispatch_dispatch_flow_context` minus `fixed`** (patient index 0.866 vs 1.000; flow index 0.877 vs 1.000)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 22.4 | 32.7 | -10.34 [-18.50, -3.79] | 8 / 0 of 8 |
| 95th-percentile wait (min) | 54 | 125 | -71.2 [-126.9, -29.1] | 8 / 0 of 8 |
| Median ED length of stay (min) | 203 | 227 | -24.7 [-36.1, -15.5] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 298 | 308 | -10.1 [-19.5, -1.8] | 7 / 1 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,182 | 1,201 | -18.7 [-44.0, 11.5] (ns) | 6 / 2 of 8 |
| Left without being seen (% of arrivals) | 1.39 | 1.75 | -0.362 [-0.641, -0.128] | 8 / 0 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 6.36 | 7.37 | -1.007 [-1.790, -0.406] | 8 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 7.20 | 6.79 | 0.416 [0.015, 0.974] | 1 / 7 of 8 |
| Adverse events (per day) | 0.68 | 0.67 | 0.007 [-0.022, 0.042] (ns) | 4 / 4 of 8 |
| Boarding (patient-h/day) | 111.7 | 109.1 | 2.68 [-2.01, 8.91] (ns) | 2 / 6 of 8 |
| Labour cost ($k/day) | 105.15 | 105.15 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 1 (min) | 11.4 | 11.0 | 0.43 [-0.97, 2.32] (ns) | 2 / 6 of 8 |
| Mean wait, triage ESI 2 (min) | 15.4 | 14.8 | 0.68 [-1.21, 3.64] (ns) | 4 / 4 of 8 |
| Mean wait, triage ESI 3 (min) | 24.5 | 31.5 | -6.99 [-17.14, -0.85] | 7 / 1 of 8 |
| Mean wait, triage ESI 4 (min) | 22.1 | 45.2 | -23.16 [-37.98, -10.05] | 8 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 38.1 | 63.0 | -24.88 [-49.12, -4.88] | 7 / 1 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 6.32 | 7.33 | -1.016 [-1.809, -0.409] | 8 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 73.2 | 54.0 | 19.24 [1.70, 45.19] | 1 / 7 of 8 |
| ESI 4-5 waiting (patient-h/day) | 27.9 | 71.2 | -43.37 [-75.61, -17.33] | 8 / 0 of 8 |

**`dispatch_dispatch_flow_context` minus `rule:acuity_first+favor_new`** (patient index 0.866 vs 0.930; flow index 0.877 vs 0.962)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 22.4 | 28.9 | -6.46 [-12.99, -2.28] | 8 / 0 of 8 |
| 95th-percentile wait (min) | 54 | 108 | -54.5 [-105.5, -19.8] | 8 / 0 of 8 |
| Median ED length of stay (min) | 203 | 229 | -26.7 [-36.7, -18.0] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 298 | 312 | -14.2 [-22.3, -8.4] | 8 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,182 | 1,220 | -37.6 [-53.8, -24.3] | 8 / 0 of 8 |
| Left without being seen (% of arrivals) | 1.39 | 1.61 | -0.218 [-0.435, -0.071] | 8 / 0 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 6.36 | 6.75 | -0.390 [-0.593, -0.218] | 8 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 7.20 | 6.74 | 0.463 [0.059, 1.001] | 1 / 7 of 8 |
| Adverse events (per day) | 0.68 | 0.66 | 0.016 [-0.006, 0.048] (ns) | 3 / 5 of 8 |
| Boarding (patient-h/day) | 111.7 | 112.1 | -0.41 [-3.71, 2.69] (ns) | 4 / 4 of 8 |
| Labour cost ($k/day) | 105.15 | 105.15 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 1 (min) | 11.4 | 10.3 | 1.15 [0.04, 2.79] | 0 / 8 of 8 |
| Mean wait, triage ESI 2 (min) | 15.4 | 14.0 | 1.45 [-0.21, 4.33] (ns) | 3 / 5 of 8 |
| Mean wait, triage ESI 3 (min) | 24.5 | 29.6 | -5.16 [-15.12, -0.04] | 7 / 1 of 8 |
| Mean wait, triage ESI 4 (min) | 22.1 | 37.6 | -15.52 [-27.74, -6.64] | 8 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 38.1 | 45.6 | -7.49 [-19.07, 0.71] (ns) | 6 / 2 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 6.32 | 6.71 | -0.393 [-0.595, -0.221] | 8 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 73.2 | 50.8 | 22.43 [6.07, 46.83] | 0 / 8 of 8 |
| ESI 4-5 waiting (patient-h/day) | 27.9 | 61.0 | -33.17 [-62.57, -12.04] | 8 / 0 of 8 |

**`dispatch_dispatch_flow_context` minus `tuned_same_budget`** (patient index 0.866 vs 0.659; flow index 0.877 vs 0.649)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 22.4 | 14.9 | 7.50 [3.57, 12.72] | 0 / 8 of 8 |
| 95th-percentile wait (min) | 54 | 31 | 22.5 [9.0, 41.1] | 0 / 8 of 8 |
| Median ED length of stay (min) | 203 | 201 | 1.3 [-3.9, 7.4] (ns) | 3 / 5 of 8 |
| Mean ED length of stay (min) | 298 | 248 | 50.0 [28.9, 75.4] | 0 / 8 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,182 | 954 | 228.3 [128.3, 354.7] | 0 / 8 of 8 |
| Left without being seen (% of arrivals) | 1.39 | 0.73 | 0.655 [0.265, 1.208] | 0 / 8 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 6.36 | 4.67 | 1.691 [0.852, 2.673] | 0 / 8 of 8 |
| Deaths (per 10,000 arrivals) | 7.20 | 5.24 | 1.967 [0.864, 3.515] | 0 / 8 of 8 |
| Adverse events (per day) | 0.68 | 0.45 | 0.228 [0.110, 0.399] | 0 / 8 of 8 |
| Boarding (patient-h/day) | 111.7 | 27.8 | 83.90 [42.72, 132.25] | 0 / 8 of 8 |
| Labour cost ($k/day) | 105.15 | 102.22 | 2.930 [0.817, 5.286] | 2 / 6 of 8 |
| Mean wait, triage ESI 1 (min) | 11.4 | 8.8 | 2.66 [1.19, 4.75] | 0 / 8 of 8 |
| Mean wait, triage ESI 2 (min) | 15.4 | 11.0 | 4.43 [1.75, 8.72] | 0 / 8 of 8 |
| Mean wait, triage ESI 3 (min) | 24.5 | 14.0 | 10.49 [4.86, 18.41] | 0 / 8 of 8 |
| Mean wait, triage ESI 4 (min) | 22.1 | 18.5 | 3.60 [1.45, 6.40] | 1 / 7 of 8 |
| Mean wait, triage ESI 5 (min) | 38.1 | 21.6 | 16.51 [9.68, 25.41] | 0 / 8 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 6.32 | 4.58 | 1.732 [0.934, 2.682] | 0 / 8 of 8 |
| ESI 3 waiting (patient-h/day) | 73.2 | 16.6 | 56.67 [19.05, 112.14] | 0 / 8 of 8 |
| ESI 4-5 waiting (patient-h/day) | 27.9 | 18.5 | 9.38 [4.30, 16.46] | 0 / 8 of 8 |

**`dispatch_dispatch_flow_linear` minus `fixed`** (patient index 0.952 vs 1.000; flow index 0.876 vs 1.000)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 23.0 | 32.7 | -9.76 [-17.94, -3.23] | 8 / 0 of 8 |
| 95th-percentile wait (min) | 55 | 125 | -70.1 [-128.3, -28.8] | 8 / 0 of 8 |
| Median ED length of stay (min) | 202 | 227 | -25.6 [-36.6, -16.5] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 299 | 308 | -9.0 [-17.3, -1.4] | 7 / 1 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,199 | 1,201 | -2.1 [-24.8, 26.8] (ns) | 5 / 3 of 8 |
| Left without being seen (% of arrivals) | 1.37 | 1.75 | -0.384 [-0.663, -0.155] | 8 / 0 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 8.90 | 7.37 | 1.532 [-0.685, 5.052] (ns) | 3 / 5 of 8 |
| Deaths (per 10,000 arrivals) | 7.54 | 6.79 | 0.748 [0.156, 1.569] | 0 / 8 of 8 |
| Adverse events (per day) | 0.74 | 0.67 | 0.073 [0.005, 0.172] | 3 / 5 of 8 |
| Boarding (patient-h/day) | 114.6 | 109.1 | 5.52 [1.05, 11.74] | 0 / 8 of 8 |
| Labour cost ($k/day) | 105.15 | 105.15 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 1 (min) | 30.2 | 11.0 | 19.21 [2.82, 47.99] | 1 / 7 of 8 |
| Mean wait, triage ESI 2 (min) | 13.5 | 14.8 | -1.28 [-2.62, -0.18] | 7 / 1 of 8 |
| Mean wait, triage ESI 3 (min) | 23.1 | 31.5 | -8.38 [-19.73, -1.61] | 8 / 0 of 8 |
| Mean wait, triage ESI 4 (min) | 26.3 | 45.2 | -18.88 [-32.45, -7.55] | 8 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 34.8 | 63.0 | -28.21 [-52.13, -8.95] | 8 / 0 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 8.83 | 7.33 | 1.501 [-0.711, 5.018] (ns) | 3 / 5 of 8 |
| ESI 3 waiting (patient-h/day) | 73.4 | 54.0 | 19.47 [0.64, 46.67] | 1 / 7 of 8 |
| ESI 4-5 waiting (patient-h/day) | 40.4 | 71.2 | -30.84 [-53.08, -11.68] | 8 / 0 of 8 |

**`dispatch_dispatch_flow_linear` minus `rule:acuity_first+favor_new`** (patient index 0.952 vs 0.930; flow index 0.876 vs 0.962)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 23.0 | 28.9 | -5.87 [-12.36, -2.06] | 8 / 0 of 8 |
| 95th-percentile wait (min) | 55 | 108 | -53.4 [-107.0, -19.2] | 8 / 0 of 8 |
| Median ED length of stay (min) | 202 | 229 | -27.6 [-37.4, -19.0] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 299 | 312 | -13.1 [-19.6, -8.4] | 8 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,199 | 1,220 | -20.9 [-36.2, -6.0] | 7 / 1 of 8 |
| Left without being seen (% of arrivals) | 1.37 | 1.61 | -0.240 [-0.457, -0.096] | 8 / 0 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 8.90 | 6.75 | 2.149 [0.114, 5.619] | 2 / 6 of 8 |
| Deaths (per 10,000 arrivals) | 7.54 | 6.74 | 0.796 [0.230, 1.588] | 0 / 8 of 8 |
| Adverse events (per day) | 0.74 | 0.66 | 0.083 [0.019, 0.177] | 2 / 6 of 8 |
| Boarding (patient-h/day) | 114.6 | 112.1 | 2.44 [-0.22, 5.85] (ns) | 1 / 7 of 8 |
| Labour cost ($k/day) | 105.15 | 105.15 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 1 (min) | 30.2 | 10.3 | 19.93 [3.44, 48.41] | 1 / 7 of 8 |
| Mean wait, triage ESI 2 (min) | 13.5 | 14.0 | -0.51 [-1.19, 0.10] (ns) | 7 / 1 of 8 |
| Mean wait, triage ESI 3 (min) | 23.1 | 29.6 | -6.54 [-17.84, -0.63] | 8 / 0 of 8 |
| Mean wait, triage ESI 4 (min) | 26.3 | 37.6 | -11.23 [-20.37, -4.85] | 8 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 34.8 | 45.6 | -10.82 [-21.85, -2.98] | 8 / 0 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 8.83 | 6.71 | 2.125 [0.097, 5.585] | 2 / 6 of 8 |
| ESI 3 waiting (patient-h/day) | 73.4 | 50.8 | 22.66 [5.07, 48.62] | 0 / 8 of 8 |
| ESI 4-5 waiting (patient-h/day) | 40.4 | 61.0 | -20.64 [-38.61, -7.89] | 8 / 0 of 8 |

**`dispatch_dispatch_flow_linear` minus `tuned_same_budget`** (patient index 0.952 vs 0.659; flow index 0.876 vs 0.649)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 23.0 | 14.9 | 8.09 [3.60, 14.04] | 0 / 8 of 8 |
| 95th-percentile wait (min) | 55 | 31 | 23.6 [8.6, 44.1] | 0 / 8 of 8 |
| Median ED length of stay (min) | 202 | 201 | 0.4 [-5.2, 6.9] (ns) | 3 / 5 of 8 |
| Mean ED length of stay (min) | 299 | 248 | 51.2 [28.9, 78.1] | 0 / 8 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,199 | 954 | 244.9 [131.3, 390.1] | 0 / 8 of 8 |
| Left without being seen (% of arrivals) | 1.37 | 0.73 | 0.633 [0.241, 1.188] | 0 / 8 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 8.90 | 4.67 | 4.231 [1.548, 8.490] | 0 / 8 of 8 |
| Deaths (per 10,000 arrivals) | 7.54 | 5.24 | 2.299 [0.981, 4.167] | 0 / 8 of 8 |
| Adverse events (per day) | 0.74 | 0.45 | 0.295 [0.133, 0.534] | 0 / 8 of 8 |
| Boarding (patient-h/day) | 114.6 | 27.8 | 86.75 [43.88, 138.01] | 0 / 8 of 8 |
| Labour cost ($k/day) | 105.15 | 102.22 | 2.930 [0.817, 5.286] | 2 / 6 of 8 |
| Mean wait, triage ESI 1 (min) | 30.2 | 8.8 | 21.44 [4.66, 50.97] | 0 / 8 of 8 |
| Mean wait, triage ESI 2 (min) | 13.5 | 11.0 | 2.46 [1.34, 3.81] | 0 / 8 of 8 |
| Mean wait, triage ESI 3 (min) | 23.1 | 14.0 | 9.10 [4.11, 15.82] | 0 / 8 of 8 |
| Mean wait, triage ESI 4 (min) | 26.3 | 18.5 | 7.89 [3.48, 13.45] | 0 / 8 of 8 |
| Mean wait, triage ESI 5 (min) | 34.8 | 21.6 | 13.18 [6.06, 22.00] | 0 / 8 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 8.83 | 4.58 | 4.249 [1.607, 8.472] | 0 / 8 of 8 |
| ESI 3 waiting (patient-h/day) | 73.4 | 16.6 | 56.90 [18.56, 114.17] | 0 / 8 of 8 |
| ESI 4-5 waiting (patient-h/day) | 40.4 | 18.5 | 21.91 [8.42, 40.76] | 0 / 8 of 8 |

**`dispatch_dispatch_flow_mlp` minus `fixed`** (patient index 0.873 vs 1.000; flow index 0.879 vs 1.000)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 24.1 | 32.7 | -8.64 [-15.13, -3.34] | 8 / 0 of 8 |
| 95th-percentile wait (min) | 54 | 125 | -70.7 [-123.3, -29.9] | 8 / 0 of 8 |
| Median ED length of stay (min) | 202 | 227 | -24.9 [-36.4, -15.7] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 300 | 308 | -8.2 [-15.7, -0.5] | 7 / 1 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,190 | 1,201 | -10.8 [-32.1, 18.1] (ns) | 6 / 2 of 8 |
| Left without being seen (% of arrivals) | 1.34 | 1.75 | -0.410 [-0.685, -0.170] | 8 / 0 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 6.46 | 7.37 | -0.911 [-1.667, -0.324] | 8 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 7.49 | 6.79 | 0.706 [0.180, 1.466] | 0 / 8 of 8 |
| Adverse events (per day) | 0.69 | 0.67 | 0.023 [-0.011, 0.070] (ns) | 2 / 6 of 8 |
| Boarding (patient-h/day) | 112.4 | 109.1 | 3.30 [-1.46, 9.88] (ns) | 3 / 5 of 8 |
| Labour cost ($k/day) | 105.15 | 105.15 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 1 (min) | 11.1 | 11.0 | 0.12 [-1.03, 1.59] (ns) | 3 / 5 of 8 |
| Mean wait, triage ESI 2 (min) | 16.3 | 14.8 | 1.53 [-0.91, 5.36] (ns) | 4 / 4 of 8 |
| Mean wait, triage ESI 3 (min) | 29.9 | 31.5 | -1.61 [-6.31, 2.20] (ns) | 5 / 3 of 8 |
| Mean wait, triage ESI 4 (min) | 20.6 | 45.2 | -24.63 [-39.93, -10.70] | 8 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 31.1 | 63.0 | -31.95 [-56.32, -11.31] | 8 / 0 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 6.41 | 7.33 | -0.926 [-1.676, -0.341] | 8 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 81.5 | 54.0 | 27.48 [4.27, 61.25] | 0 / 8 of 8 |
| ESI 4-5 waiting (patient-h/day) | 24.4 | 71.2 | -46.86 [-81.67, -18.81] | 8 / 0 of 8 |

**`dispatch_dispatch_flow_mlp` minus `rule:acuity_first+favor_new`** (patient index 0.873 vs 0.930; flow index 0.879 vs 0.962)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 24.1 | 28.9 | -4.76 [-8.67, -2.10] | 8 / 0 of 8 |
| 95th-percentile wait (min) | 54 | 108 | -54.1 [-103.8, -20.1] | 8 / 0 of 8 |
| Median ED length of stay (min) | 202 | 229 | -26.9 [-37.1, -18.1] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 300 | 312 | -12.3 [-18.0, -7.8] | 8 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,190 | 1,220 | -29.6 [-41.9, -18.0] | 8 / 0 of 8 |
| Left without being seen (% of arrivals) | 1.34 | 1.61 | -0.266 [-0.497, -0.105] | 8 / 0 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 6.46 | 6.75 | -0.294 [-0.512, -0.027] | 7 / 1 of 8 |
| Deaths (per 10,000 arrivals) | 7.49 | 6.74 | 0.754 [0.242, 1.497] | 0 / 8 of 8 |
| Adverse events (per day) | 0.69 | 0.66 | 0.033 [0.004, 0.077] | 1 / 7 of 8 |
| Boarding (patient-h/day) | 112.4 | 112.1 | 0.21 [-2.77, 3.15] (ns) | 5 / 3 of 8 |
| Labour cost ($k/day) | 105.15 | 105.15 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 1 (min) | 11.1 | 10.3 | 0.84 [0.08, 2.10] | 1 / 7 of 8 |
| Mean wait, triage ESI 2 (min) | 16.3 | 14.0 | 2.30 [-0.02, 6.02] (ns) | 3 / 5 of 8 |
| Mean wait, triage ESI 3 (min) | 29.9 | 29.6 | 0.23 [-3.00, 3.05] (ns) | 4 / 4 of 8 |
| Mean wait, triage ESI 4 (min) | 20.6 | 37.6 | -16.99 [-30.52, -7.22] | 8 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 31.1 | 45.6 | -14.56 [-28.27, -4.74] | 8 / 0 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 6.41 | 6.71 | -0.302 [-0.510, -0.034] | 7 / 1 of 8 |
| ESI 3 waiting (patient-h/day) | 81.5 | 50.8 | 30.67 [8.58, 63.78] | 0 / 8 of 8 |
| ESI 4-5 waiting (patient-h/day) | 24.4 | 61.0 | -36.66 [-69.10, -13.91] | 8 / 0 of 8 |

**`dispatch_dispatch_flow_mlp` minus `tuned_same_budget`** (patient index 0.873 vs 0.659; flow index 0.879 vs 0.649)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 24.1 | 14.9 | 9.20 [3.82, 16.63] | 0 / 8 of 8 |
| 95th-percentile wait (min) | 54 | 31 | 22.9 [8.3, 42.9] | 0 / 7 of 8 |
| Median ED length of stay (min) | 202 | 201 | 1.1 [-4.1, 7.3] (ns) | 3 / 5 of 8 |
| Mean ED length of stay (min) | 300 | 248 | 52.0 [29.5, 78.9] | 0 / 8 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,190 | 954 | 236.2 [130.3, 369.9] | 0 / 8 of 8 |
| Left without being seen (% of arrivals) | 1.34 | 0.73 | 0.607 [0.236, 1.140] | 0 / 8 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 6.46 | 4.67 | 1.788 [0.885, 2.920] | 0 / 8 of 8 |
| Deaths (per 10,000 arrivals) | 7.49 | 5.24 | 2.257 [1.011, 4.123] | 0 / 8 of 8 |
| Adverse events (per day) | 0.69 | 0.45 | 0.244 [0.117, 0.432] | 0 / 8 of 8 |
| Boarding (patient-h/day) | 112.4 | 27.8 | 84.52 [43.12, 133.52] | 0 / 8 of 8 |
| Labour cost ($k/day) | 105.15 | 102.22 | 2.930 [0.817, 5.286] | 2 / 6 of 8 |
| Mean wait, triage ESI 1 (min) | 11.1 | 8.8 | 2.35 [1.15, 4.18] | 0 / 8 of 8 |
| Mean wait, triage ESI 2 (min) | 16.3 | 11.0 | 5.28 [1.98, 10.39] | 0 / 8 of 8 |
| Mean wait, triage ESI 3 (min) | 29.9 | 14.0 | 15.87 [6.31, 29.43] | 0 / 8 of 8 |
| Mean wait, triage ESI 4 (min) | 20.6 | 18.5 | 2.13 [0.70, 3.92] | 1 / 7 of 8 |
| Mean wait, triage ESI 5 (min) | 31.1 | 21.6 | 9.44 [4.14, 16.14] | 1 / 7 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 6.41 | 4.58 | 1.822 [0.946, 2.933] | 0 / 8 of 8 |
| ESI 3 waiting (patient-h/day) | 81.5 | 16.6 | 64.91 [21.80, 128.09] | 0 / 8 of 8 |
| ESI 4-5 waiting (patient-h/day) | 24.4 | 18.5 | 5.89 [2.49, 10.72] | 1 / 7 of 8 |

**`dispatch_dispatch_only_linear` minus `fixed`** (patient index 1.000 vs 1.000; flow index 1.000 vs 1.000)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 32.7 | 32.7 | 0.00 [0.00, 0.00] (ns) | 0 / 0 of 8 |
| 95th-percentile wait (min) | 125 | 125 | 0.0 [0.0, 0.0] (ns) | 0 / 0 of 8 |
| Median ED length of stay (min) | 227 | 227 | 0.0 [0.0, 0.0] (ns) | 0 / 0 of 8 |
| Mean ED length of stay (min) | 308 | 308 | 0.0 [0.0, 0.0] (ns) | 0 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,201 | 1,201 | 0.0 [0.0, 0.0] (ns) | 0 / 0 of 8 |
| Left without being seen (% of arrivals) | 1.75 | 1.75 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 7.37 | 7.37 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 6.79 | 6.79 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Adverse events (per day) | 0.67 | 0.67 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Boarding (patient-h/day) | 109.1 | 109.1 | 0.00 [0.00, 0.00] (ns) | 0 / 0 of 8 |
| Labour cost ($k/day) | 105.15 | 105.15 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 1 (min) | 11.0 | 11.0 | 0.00 [0.00, 0.00] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 2 (min) | 14.8 | 14.8 | 0.00 [0.00, 0.00] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 3 (min) | 31.5 | 31.5 | 0.00 [0.00, 0.00] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 4 (min) | 45.2 | 45.2 | 0.00 [0.00, 0.00] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 63.0 | 63.0 | 0.00 [0.00, 0.00] (ns) | 0 / 0 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 7.33 | 7.33 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 54.0 | 54.0 | 0.00 [0.00, 0.00] (ns) | 0 / 0 of 8 |
| ESI 4-5 waiting (patient-h/day) | 71.2 | 71.2 | 0.00 [0.00, 0.00] (ns) | 0 / 0 of 8 |

**`dispatch_dispatch_only_linear` minus `rule:acuity_first+favor_new`** (patient index 1.000 vs 0.930; flow index 1.000 vs 0.962)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 32.7 | 28.9 | 3.88 [0.00, 9.55] (ns) | 0 / 2 of 8 |
| 95th-percentile wait (min) | 125 | 108 | 16.7 [0.0, 40.6] (ns) | 0 / 2 of 8 |
| Median ED length of stay (min) | 227 | 229 | -2.0 [-5.7, 0.0] (ns) | 2 / 0 of 8 |
| Mean ED length of stay (min) | 308 | 312 | -4.1 [-11.5, 0.0] (ns) | 2 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,201 | 1,220 | -18.8 [-52.4, 0.0] (ns) | 2 / 0 of 8 |
| Left without being seen (% of arrivals) | 1.75 | 1.61 | 0.144 [0.000, 0.354] (ns) | 0 / 2 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 7.37 | 6.75 | 0.617 [0.000, 1.489] (ns) | 0 / 2 of 8 |
| Deaths (per 10,000 arrivals) | 6.79 | 6.74 | 0.048 [-0.033, 0.170] (ns) | 0 / 2 of 8 |
| Adverse events (per day) | 0.67 | 0.66 | 0.010 [0.000, 0.026] (ns) | 0 / 2 of 8 |
| Boarding (patient-h/day) | 109.1 | 112.1 | -3.08 [-9.30, 0.00] (ns) | 2 / 0 of 8 |
| Labour cost ($k/day) | 105.15 | 105.15 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 1 (min) | 11.0 | 10.3 | 0.72 [0.00, 1.74] (ns) | 0 / 2 of 8 |
| Mean wait, triage ESI 2 (min) | 14.8 | 14.0 | 0.77 [0.00, 1.86] (ns) | 0 / 2 of 8 |
| Mean wait, triage ESI 3 (min) | 31.5 | 29.6 | 1.84 [0.00, 4.71] (ns) | 0 / 2 of 8 |
| Mean wait, triage ESI 4 (min) | 45.2 | 37.6 | 7.64 [0.00, 18.84] (ns) | 0 / 2 of 8 |
| Mean wait, triage ESI 5 (min) | 63.0 | 45.6 | 17.39 [0.00, 41.89] (ns) | 0 / 2 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 7.33 | 6.71 | 0.623 [0.000, 1.500] (ns) | 0 / 2 of 8 |
| ESI 3 waiting (patient-h/day) | 54.0 | 50.8 | 3.19 [0.00, 8.41] (ns) | 0 / 2 of 8 |
| ESI 4-5 waiting (patient-h/day) | 71.2 | 61.0 | 10.20 [0.00, 25.45] (ns) | 0 / 2 of 8 |

**`dispatch_joint_linear` minus `fixed`** (patient index 0.653 vs 1.000; flow index 0.618 vs 1.000)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 14.6 | 32.7 | -18.14 [-30.20, -8.25] | 8 / 0 of 8 |
| 95th-percentile wait (min) | 29 | 125 | -95.8 [-167.0, -41.5] | 8 / 0 of 8 |
| Median ED length of stay (min) | 190 | 227 | -37.4 [-54.4, -23.5] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 243 | 308 | -64.4 [-98.9, -37.1] | 8 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 937 | 1,201 | -263.8 [-407.8, -149.5] | 8 / 0 of 8 |
| Left without being seen (% of arrivals) | 0.73 | 1.75 | -1.025 [-1.757, -0.463] | 8 / 0 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 4.56 | 7.37 | -2.806 [-4.146, -1.634] | 8 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 5.28 | 6.79 | -1.506 [-2.694, -0.639] | 8 / 0 of 8 |
| Adverse events (per day) | 0.45 | 0.67 | -0.222 [-0.374, -0.120] | 8 / 0 of 8 |
| Boarding (patient-h/day) | 21.2 | 109.1 | -87.87 [-140.14, -43.94] | 8 / 0 of 8 |
| Labour cost ($k/day) | 102.25 | 105.15 | -2.895 [-5.278, -0.773] | 6 / 2 of 8 |
| Mean wait, triage ESI 1 (min) | 8.7 | 11.0 | -2.27 [-3.66, -1.11] | 8 / 0 of 8 |
| Mean wait, triage ESI 2 (min) | 10.9 | 14.8 | -3.87 [-5.77, -2.24] | 8 / 0 of 8 |
| Mean wait, triage ESI 3 (min) | 13.8 | 31.5 | -17.63 [-31.96, -7.57] | 8 / 0 of 8 |
| Mean wait, triage ESI 4 (min) | 17.9 | 45.2 | -27.34 [-44.23, -12.38] | 8 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 20.7 | 63.0 | -42.27 [-68.78, -17.68] | 8 / 0 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 4.49 | 7.33 | -2.844 [-4.165, -1.685] | 8 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 16.3 | 54.0 | -37.64 [-70.20, -15.38] | 8 / 0 of 8 |
| ESI 4-5 waiting (patient-h/day) | 17.7 | 71.2 | -53.50 [-93.01, -22.32] | 8 / 0 of 8 |

**`dispatch_joint_linear` minus `rule:acuity_first+favor_new`** (patient index 0.653 vs 0.930; flow index 0.618 vs 0.962)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 14.6 | 28.9 | -14.26 [-25.45, -6.40] | 8 / 0 of 8 |
| 95th-percentile wait (min) | 29 | 108 | -79.1 [-147.5, -31.2] | 8 / 0 of 8 |
| Median ED length of stay (min) | 190 | 229 | -39.4 [-55.8, -26.1] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 243 | 312 | -68.5 [-102.6, -41.0] | 8 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 937 | 1,220 | -282.6 [-422.7, -168.0] | 8 / 0 of 8 |
| Left without being seen (% of arrivals) | 0.73 | 1.61 | -0.881 [-1.643, -0.354] | 8 / 0 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 4.56 | 6.75 | -2.189 [-3.223, -1.321] | 8 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 5.28 | 6.74 | -1.458 [-2.641, -0.608] | 8 / 0 of 8 |
| Adverse events (per day) | 0.45 | 0.66 | -0.213 [-0.366, -0.109] | 8 / 0 of 8 |
| Boarding (patient-h/day) | 21.2 | 112.1 | -90.95 [-142.87, -46.31] | 8 / 0 of 8 |
| Labour cost ($k/day) | 102.25 | 105.15 | -2.895 [-5.278, -0.773] | 6 / 2 of 8 |
| Mean wait, triage ESI 1 (min) | 8.7 | 10.3 | -1.55 [-2.49, -0.83] | 8 / 0 of 8 |
| Mean wait, triage ESI 2 (min) | 10.9 | 14.0 | -3.10 [-4.75, -1.85] | 8 / 0 of 8 |
| Mean wait, triage ESI 3 (min) | 13.8 | 29.6 | -15.80 [-30.00, -6.31] | 8 / 0 of 8 |
| Mean wait, triage ESI 4 (min) | 17.9 | 37.6 | -19.70 [-34.67, -8.99] | 8 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 20.7 | 45.6 | -24.87 [-44.82, -10.46] | 8 / 0 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 4.49 | 6.71 | -2.220 [-3.222, -1.372] | 8 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 16.3 | 50.8 | -34.46 [-66.72, -13.12] | 8 / 0 of 8 |
| ESI 4-5 waiting (patient-h/day) | 17.7 | 61.0 | -43.30 [-80.19, -17.12] | 8 / 0 of 8 |

**`dispatch_joint_linear` minus `tuned_same_budget`** (patient index 0.653 vs 0.659; flow index 0.618 vs 0.649)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 14.6 | 14.9 | -0.29 [-0.57, -0.13] | 8 / 0 of 8 |
| 95th-percentile wait (min) | 29 | 31 | -2.1 [-4.1, -0.9] | 8 / 0 of 8 |
| Median ED length of stay (min) | 190 | 201 | -11.4 [-14.1, -8.8] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 243 | 248 | -4.3 [-6.0, -2.9] | 8 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 937 | 954 | -16.8 [-23.7, -10.9] | 8 / 0 of 8 |
| Left without being seen (% of arrivals) | 0.73 | 0.73 | -0.008 [-0.020, 0.004] (ns) | 6 / 2 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 4.56 | 4.67 | -0.107 [-0.176, -0.054] | 8 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 5.28 | 5.24 | 0.045 [-0.075, 0.171] (ns) | 3 / 5 of 8 |
| Adverse events (per day) | 0.45 | 0.45 | -0.001 [-0.008, 0.005] (ns) | 5 / 3 of 8 |
| Boarding (patient-h/day) | 21.2 | 27.8 | -6.64 [-10.63, -3.54] | 8 / 0 of 8 |
| Labour cost ($k/day) | 102.25 | 102.22 | 0.034 [-0.063, 0.129] (ns) | 1 / 7 of 8 |
| Mean wait, triage ESI 1 (min) | 8.7 | 8.8 | -0.04 [-0.11, 0.05] (ns) | 7 / 1 of 8 |
| Mean wait, triage ESI 2 (min) | 10.9 | 11.0 | -0.13 [-0.21, -0.07] | 8 / 0 of 8 |
| Mean wait, triage ESI 3 (min) | 13.8 | 14.0 | -0.15 [-0.27, -0.06] | 8 / 0 of 8 |
| Mean wait, triage ESI 4 (min) | 17.9 | 18.5 | -0.58 [-1.21, -0.20] | 8 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 20.7 | 21.6 | -0.88 [-2.01, -0.24] | 8 / 0 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 4.49 | 4.58 | -0.096 [-0.155, -0.051] | 8 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 16.3 | 16.6 | -0.22 [-0.41, 0.01] (ns) | 7 / 1 of 8 |
| ESI 4-5 waiting (patient-h/day) | 17.7 | 18.5 | -0.75 [-1.86, 0.22] (ns) | 6 / 2 of 8 |

**`dispatch_joint_linear` minus `ablate:dispatch_joint_linear:levers_only`** (patient index 0.653 vs 0.658; flow index 0.618 vs 0.634)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 14.6 | 14.8 | -0.21 [-0.34, -0.10] | 8 / 0 of 8 |
| 95th-percentile wait (min) | 29 | 31 | -1.7 [-3.0, -0.8] | 8 / 0 of 8 |
| Median ED length of stay (min) | 190 | 201 | -11.3 [-14.3, -8.6] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 243 | 246 | -3.0 [-4.1, -2.0] | 8 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 937 | 948 | -11.2 [-15.8, -7.0] | 8 / 0 of 8 |
| Left without being seen (% of arrivals) | 0.73 | 0.73 | -0.003 [-0.014, 0.006] (ns) | 5 / 3 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 4.56 | 4.64 | -0.079 [-0.124, -0.041] | 8 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 5.28 | 5.22 | 0.064 [-0.043, 0.194] (ns) | 1 / 7 of 8 |
| Adverse events (per day) | 0.45 | 0.45 | -0.002 [-0.007, 0.003] (ns) | 6 / 2 of 8 |
| Boarding (patient-h/day) | 21.2 | 21.3 | -0.06 [-0.77, 0.56] (ns) | 6 / 2 of 8 |
| Labour cost ($k/day) | 102.25 | 102.25 | -0.002 [-0.013, 0.010] (ns) | 4 / 4 of 8 |
| Mean wait, triage ESI 1 (min) | 8.7 | 8.8 | -0.04 [-0.10, 0.05] (ns) | 7 / 1 of 8 |
| Mean wait, triage ESI 2 (min) | 10.9 | 11.0 | -0.09 [-0.15, -0.05] | 8 / 0 of 8 |
| Mean wait, triage ESI 3 (min) | 13.8 | 13.9 | -0.08 [-0.19, 0.02] (ns) | 5 / 3 of 8 |
| Mean wait, triage ESI 4 (min) | 17.9 | 18.3 | -0.44 [-0.83, -0.17] | 8 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 20.7 | 21.3 | -0.56 [-1.16, -0.18] | 8 / 0 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 4.49 | 4.56 | -0.071 [-0.113, -0.037] | 8 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 16.3 | 16.4 | -0.07 [-0.31, 0.21] (ns) | 5 / 3 of 8 |
| ESI 4-5 waiting (patient-h/day) | 17.7 | 18.2 | -0.51 [-1.21, 0.38] (ns) | 6 / 2 of 8 |

**`ablate:dispatch_joint_linear:index_on_tuned` minus `tuned_same_budget`** (patient index 0.653 vs 0.659; flow index 0.632 vs 0.649)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 14.7 | 14.9 | -0.22 [-0.37, -0.11] | 8 / 0 of 8 |
| 95th-percentile wait (min) | 29 | 31 | -2.0 [-3.6, -0.9] | 8 / 0 of 8 |
| Median ED length of stay (min) | 190 | 201 | -11.1 [-13.9, -8.6] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 245 | 248 | -2.9 [-3.9, -2.1] | 8 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 943 | 954 | -11.0 [-14.9, -7.3] | 8 / 0 of 8 |
| Left without being seen (% of arrivals) | 0.73 | 0.73 | -0.004 [-0.015, 0.006] (ns) | 5 / 3 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 4.59 | 4.67 | -0.078 [-0.130, -0.036] | 8 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 5.30 | 5.24 | 0.059 [-0.065, 0.182] (ns) | 1 / 7 of 8 |
| Adverse events (per day) | 0.45 | 0.45 | -0.003 [-0.009, 0.002] (ns) | 6 / 2 of 8 |
| Boarding (patient-h/day) | 27.7 | 27.8 | -0.10 [-1.49, 1.11] (ns) | 5 / 3 of 8 |
| Labour cost ($k/day) | 102.21 | 102.22 | -0.002 [-0.012, 0.008] (ns) | 4 / 3 of 8 |
| Mean wait, triage ESI 1 (min) | 8.7 | 8.8 | -0.06 [-0.10, -0.01] | 8 / 0 of 8 |
| Mean wait, triage ESI 2 (min) | 10.9 | 11.0 | -0.10 [-0.15, -0.05] | 8 / 0 of 8 |
| Mean wait, triage ESI 3 (min) | 14.0 | 14.0 | -0.04 [-0.17, 0.14] (ns) | 5 / 3 of 8 |
| Mean wait, triage ESI 4 (min) | 17.9 | 18.5 | -0.54 [-1.06, -0.22] | 8 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 20.9 | 21.6 | -0.72 [-1.66, -0.20] | 8 / 0 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 4.51 | 4.58 | -0.070 [-0.115, -0.031] | 8 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 16.6 | 16.6 | 0.06 [-0.28, 0.65] (ns) | 5 / 3 of 8 |
| ESI 4-5 waiting (patient-h/day) | 17.8 | 18.5 | -0.67 [-1.60, 0.27] (ns) | 6 / 2 of 8 |

**`tuned_same_budget` minus `fixed`** (patient index 0.659 vs 1.000; flow index 0.649 vs 1.000)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 14.9 | 32.7 | -17.85 [-29.73, -8.02] | 8 / 0 of 8 |
| 95th-percentile wait (min) | 31 | 125 | -93.7 [-163.3, -39.1] | 8 / 0 of 8 |
| Median ED length of stay (min) | 201 | 227 | -26.1 [-41.6, -13.4] | 8 / 0 of 8 |
| Mean ED length of stay (min) | 248 | 308 | -60.1 [-93.2, -33.6] | 8 / 0 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 954 | 1,201 | -247.0 [-384.9, -136.9] | 8 / 0 of 8 |
| Left without being seen (% of arrivals) | 0.73 | 1.75 | -1.017 [-1.747, -0.458] | 8 / 0 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 4.67 | 7.37 | -2.699 [-4.053, -1.516] | 8 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 5.24 | 6.79 | -1.551 [-2.696, -0.720] | 8 / 0 of 8 |
| Adverse events (per day) | 0.45 | 0.67 | -0.221 [-0.369, -0.120] | 8 / 0 of 8 |
| Boarding (patient-h/day) | 27.8 | 109.1 | -81.23 [-131.21, -40.28] | 8 / 0 of 8 |
| Labour cost ($k/day) | 102.22 | 105.15 | -2.930 [-5.286, -0.817] | 6 / 2 of 8 |
| Mean wait, triage ESI 1 (min) | 8.8 | 11.0 | -2.23 [-3.63, -1.06] | 8 / 0 of 8 |
| Mean wait, triage ESI 2 (min) | 11.0 | 14.8 | -3.75 [-5.63, -2.09] | 8 / 0 of 8 |
| Mean wait, triage ESI 3 (min) | 14.0 | 31.5 | -17.48 [-31.73, -7.46] | 8 / 0 of 8 |
| Mean wait, triage ESI 4 (min) | 18.5 | 45.2 | -26.76 [-43.45, -11.89] | 8 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 21.6 | 63.0 | -41.39 [-68.23, -17.10] | 8 / 0 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 4.58 | 7.33 | -2.748 [-4.073, -1.586] | 8 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 16.6 | 54.0 | -37.43 [-69.90, -15.26] | 8 / 0 of 8 |
| ESI 4-5 waiting (patient-h/day) | 18.5 | 71.2 | -52.75 [-91.78, -21.62] | 8 / 0 of 8 |

**`rule:acuity_first+favor_new` minus `fixed`** (patient index 0.930 vs 1.000; flow index 0.962 vs 1.000)

| Metric | a | b | difference [95% CI] | members lower / higher |
|---|---:|---:|---:|---:|
| Mean door-to-provider wait (min) | 28.9 | 32.7 | -3.88 [-9.55, 0.00] (ns) | 2 / 0 of 8 |
| 95th-percentile wait (min) | 108 | 125 | -16.7 [-40.6, 0.0] (ns) | 2 / 0 of 8 |
| Median ED length of stay (min) | 229 | 227 | 2.0 [0.0, 5.7] (ns) | 0 / 2 of 8 |
| Mean ED length of stay (min) | 312 | 308 | 4.1 [0.0, 11.5] (ns) | 0 / 2 of 8 |
| ED census (patient-hours per day) (patient-h/day) | 1,220 | 1,201 | 18.8 [0.0, 52.4] (ns) | 0 / 2 of 8 |
| Left without being seen (% of arrivals) | 1.61 | 1.75 | -0.144 [-0.354, 0.000] (ns) | 2 / 0 of 8 |
| ESI 1-2 waiting (hourly census) (patient-h/day) | 6.75 | 7.37 | -0.617 [-1.489, 0.000] (ns) | 2 / 0 of 8 |
| Deaths (per 10,000 arrivals) | 6.74 | 6.79 | -0.048 [-0.170, 0.033] (ns) | 2 / 0 of 8 |
| Adverse events (per day) | 0.66 | 0.67 | -0.010 [-0.026, 0.000] (ns) | 2 / 0 of 8 |
| Boarding (patient-h/day) | 112.1 | 109.1 | 3.08 [0.00, 9.30] (ns) | 0 / 2 of 8 |
| Labour cost ($k/day) | 105.15 | 105.15 | 0.000 [0.000, 0.000] (ns) | 0 / 0 of 8 |
| Mean wait, triage ESI 1 (min) | 10.3 | 11.0 | -0.72 [-1.74, 0.00] (ns) | 2 / 0 of 8 |
| Mean wait, triage ESI 2 (min) | 14.0 | 14.8 | -0.77 [-1.86, 0.00] (ns) | 2 / 0 of 8 |
| Mean wait, triage ESI 3 (min) | 29.6 | 31.5 | -1.84 [-4.71, 0.00] (ns) | 2 / 0 of 8 |
| Mean wait, triage ESI 4 (min) | 37.6 | 45.2 | -7.64 [-18.84, 0.00] (ns) | 2 / 0 of 8 |
| Mean wait, triage ESI 5 (min) | 45.6 | 63.0 | -17.39 [-41.89, 0.00] (ns) | 2 / 0 of 8 |
| ESI 1-2 waiting (per tick) (patient-h/day) | 6.71 | 7.33 | -0.623 [-1.500, 0.000] (ns) | 2 / 0 of 8 |
| ESI 3 waiting (patient-h/day) | 50.8 | 54.0 | -3.19 [-8.41, 0.00] (ns) | 2 / 0 of 8 |
| ESI 4-5 waiting (patient-h/day) | 61.0 | 71.2 | -10.20 [-25.45, 0.00] (ns) | 2 / 0 of 8 |

### All hard-coded rule arms

| Arm | wait | p95 | LOS median | LWBS % | ESI 1-2 waiting h/day | adverse/day | patient index | flow index |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `fixed` | 32.7 | 125 | 227 | 1.75 | 7.37 | 0.67 | 1.000 | 1.000 |
| `rule:fcfs+favor_new` | 28.7 | 99 | 239 | 1.32 | 18.57 | 0.72 | 1.271 | 0.945 |
| `rule:fcfs+balanced` | 30.2 | 102 | 236 | 1.37 | 20.24 | 0.73 | 1.373 | 0.966 |
| `rule:fcfs+favor_dispositions` | 46.2 | 171 | 214 | 2.11 | 29.40 | 0.79 | 2.134 | 1.232 |
| `rule:acuity_first+favor_new` | 28.9 | 108 | 229 | 1.61 | 6.75 | 0.66 | 0.930 | 0.962 |
| `rule:acuity_first+balanced` | 30.7 | 117 | 227 | 1.70 | 6.59 | 0.66 | 0.959 | 0.991 |
| `rule:acuity_first+favor_dispositions` | 47.9 | 194 | 212 | 2.57 | 9.88 | 0.68 | 1.478 | 1.303 |
| `rule:acuity_with_aging+favor_new` | 29.8 | 105 | 242 | 1.41 | 15.63 | 0.71 | 1.182 | 0.966 |
| `rule:acuity_with_aging+balanced` | 31.2 | 111 | 239 | 1.48 | 15.27 | 0.71 | 1.203 | 0.991 |
| `rule:acuity_with_aging+favor_dispositions` | 47.6 | 183 | 216 | 2.29 | 20.19 | 0.73 | 1.794 | 1.274 |
| `rule:shortest_first+favor_new` | 23.7 | 70 | 214 | 0.97 | 35.43 | 0.78 | 1.740 | 0.859 |
| `rule:shortest_first+balanced` | 24.7 | 73 | 212 | 0.99 | 38.28 | 0.80 | 1.897 | 0.871 |
| `rule:shortest_first+favor_dispositions` | 41.3 | 159 | 204 | 1.63 | 59.62 | 0.91 | 3.153 | 1.137 |

## What the learned index does

Unit: acuity levels (one level = the gap between two adjacent triage levels under `acuity_first`). Negative = served sooner.

### `dispatch_dispatch_flow_context` (context index; unified provider queue: True)

Standing at zero wait, by queue and triage level:

| Queue | ESI 1 | ESI 2 | ESI 3 | ESI 4 | ESI 5 |
|---|---:|---:|---:|---:|---:|
| bay_queue | +1.10 | +2.01 | +3.33 | +3.57 | +4.95 |
| new_in_bay | +1.25 | +1.93 | +3.66 | +4.03 | +4.84 |
| disposition | +1.68 | +2.48 | +2.81 | +3.83 | +4.96 |
| scan_queue | +1.33 | +1.94 | +2.98 | +3.87 | +4.48 |

Aging, levels per hour since arrival: esi1 +0.53, esi2 +0.11, esi3 +0.53, esi4 +0.11, esi5 +0.79.
Aging, levels per hour in the current queue: bay_queue -0.06, new_in_bay -0.01, disposition +0.44, scan_queue +0.05.
Other weights: lwbs_pressure +0.22, deteriorated -0.14, walk_in -0.08, ambulance +0.01, transfer_in -0.43, age_0_17 -0.06, age_18_44 +0.01, age_45_64 +0.08, age_65_plus -0.08, cond0 -0.03, cond1 -0.12, cond2 -0.26, cond3 +0.12, cond4 -0.14, cond5 -0.10, cond6 +0.05, cond7 +0.28, cond8 +0.19.
Plus 220 context interaction weights.

### `dispatch_dispatch_flow_linear` (linear index; unified provider queue: True)

Standing at zero wait, by queue and triage level:

| Queue | ESI 1 | ESI 2 | ESI 3 | ESI 4 | ESI 5 |
|---|---:|---:|---:|---:|---:|
| bay_queue | +0.83 | +1.75 | +3.40 | +4.35 | +5.36 |
| new_in_bay | +0.57 | +1.68 | +3.92 | +4.14 | +5.18 |
| disposition | +1.25 | +2.06 | +3.16 | +4.50 | +5.27 |
| scan_queue | +0.48 | +2.12 | +3.21 | +4.41 | +5.39 |

Aging, levels per hour since arrival: esi1 +0.92, esi2 +1.16, esi3 +1.27, esi4 +0.99, esi5 +0.94.
Aging, levels per hour in the current queue: bay_queue -0.07, new_in_bay -0.37, disposition +0.62, scan_queue +0.03.
Other weights: lwbs_pressure -0.14, deteriorated +0.31, walk_in -0.28, ambulance +0.27, transfer_in +0.00, age_0_17 +0.08, age_18_44 -0.03, age_45_64 -0.20, age_65_plus +0.15, cond0 -0.03, cond1 -0.14, cond2 +0.01, cond3 -0.06, cond4 -0.06, cond5 -0.09, cond6 +0.07, cond7 +0.04, cond8 +0.15.
No context interactions.

### `dispatch_dispatch_flow_mlp` (mlp index; unified provider queue: True)

Standing at zero wait, by queue and triage level:

| Queue | ESI 1 | ESI 2 | ESI 3 | ESI 4 | ESI 5 |
|---|---:|---:|---:|---:|---:|
| bay_queue | +1.29 | +1.83 | +3.27 | +3.66 | +4.95 |
| new_in_bay | +1.20 | +1.91 | +3.68 | +4.10 | +4.88 |
| disposition | +1.64 | +2.69 | +2.85 | +3.93 | +4.98 |
| scan_queue | +1.15 | +1.92 | +3.01 | +4.18 | +4.58 |

Aging, levels per hour since arrival: esi1 +0.44, esi2 +0.29, esi3 +0.59, esi4 +0.17, esi5 +0.83.
Aging, levels per hour in the current queue: bay_queue -0.16, new_in_bay -0.11, disposition +0.73, scan_queue +0.02.
Other weights: lwbs_pressure +0.10, deteriorated -0.24, walk_in -0.37, ambulance +0.10, transfer_in -0.50, age_0_17 +0.07, age_18_44 +0.01, age_45_64 +0.10, age_65_plus -0.06, cond0 -0.06, cond1 -0.12, cond2 -0.21, cond3 +0.17, cond4 -0.16, cond5 -0.05, cond6 +0.04, cond7 +0.24, cond8 +0.31.
Plus 220 context interaction weights and a 16-unit network (not readable from this table).

### `dispatch_dispatch_only_linear` (linear index; unified provider queue: False)

Standing at zero wait, by queue and triage level:

| Queue | ESI 1 | ESI 2 | ESI 3 | ESI 4 | ESI 5 |
|---|---:|---:|---:|---:|---:|
| bay_queue | +1.00 | +2.00 | +3.00 | +4.00 | +5.00 |
| new_in_bay | +1.00 | +2.00 | +3.00 | +4.00 | +5.00 |
| disposition | +1.00 | +2.00 | +3.00 | +4.00 | +5.00 |
| scan_queue | +1.00 | +2.00 | +3.00 | +4.00 | +5.00 |

Aging, levels per hour since arrival: esi1 +0.00, esi2 +0.00, esi3 +0.00, esi4 +0.00, esi5 +0.00.
Aging, levels per hour in the current queue: bay_queue +0.00, new_in_bay +0.00, disposition +0.00, scan_queue +0.00.
Other weights: lwbs_pressure +0.00, deteriorated +0.00, walk_in +0.00, ambulance +0.00, transfer_in +0.00, age_0_17 +0.00, age_18_44 +0.00, age_45_64 +0.00, age_65_plus +0.00, cond0 +0.00, cond1 +0.00, cond2 +0.00, cond3 +0.00, cond4 +0.00, cond5 +0.00, cond6 +0.00, cond7 +0.00, cond8 +0.00.
No context interactions.

### `dispatch_joint_linear` (linear index; unified provider queue: False)

Standing at zero wait, by queue and triage level:

| Queue | ESI 1 | ESI 2 | ESI 3 | ESI 4 | ESI 5 |
|---|---:|---:|---:|---:|---:|
| bay_queue | +0.38 | +1.77 | +3.34 | +3.66 | +5.35 |
| new_in_bay | +0.50 | +1.66 | +2.93 | +3.86 | +4.88 |
| disposition | +0.75 | +2.11 | +2.91 | +4.39 | +4.71 |
| scan_queue | +0.35 | +1.60 | +2.99 | +3.81 | +5.18 |

Aging, levels per hour since arrival: esi1 +0.01, esi2 +0.67, esi3 +0.61, esi4 +0.31, esi5 +0.39.
Aging, levels per hour in the current queue: bay_queue +0.28, new_in_bay -0.02, disposition +0.29, scan_queue -0.05.
Other weights: lwbs_pressure +0.02, deteriorated +0.03, walk_in -0.04, ambulance +0.09, transfer_in +0.98, age_0_17 -0.17, age_18_44 +0.39, age_45_64 -0.04, age_65_plus -0.15, cond0 +0.08, cond1 +0.02, cond2 -0.02, cond3 +0.02, cond4 -0.06, cond5 +0.05, cond6 -0.02, cond7 +0.06, cond8 +0.00.
No context interactions.

## Where the choices are (baseline, tick-level census)

| Scenario | arm | share of pre-provider time: triage queue | in triage | bay queue | walking to bay | provider queue | mean new patients queued | mean ready dispositions queued | ticks with 2+ new queued | ticks with 2+ queued for a bay | ticks with a new patient AND a disposition waiting |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| normal_week | fixed (baseline) | 5% | 37% | 2% | 29% | 27% | 0.92 | 4.14 | 18% | 1% | 22% |
| flu_surge | fixed (baseline) | 4% | 26% | 21% | 20% | 29% | 1.69 | 9.52 | 25% | 9% | 30% |
| normal_week | dispatch_dispatch_flow_context (baseline levers) | 6% | 41% | 1% | 33% | 19% | 0.44 | 3.97 | 10% | 0% | 25% |
| flu_surge | dispatch_dispatch_flow_context (baseline levers) | 6% | 33% | 14% | 26% | 20% | 0.68 | 9.56 | 16% | 7% | 34% |

## Verdict

- SIMULATED. Verdict: entity-level learned dispatch beats the best hard-coded queue rule in this twin, but the gain is small where it is safe and unsafe where it is large. It does not come close to what the staffing levers buy.
- Dispatch alone, normal week (every lever at current practice; learned index vs the best of the 12 hard-coded rule x split combinations, acuity_first + favor_new): mean door-to-provider wait unchanged (-0.1 to -0.3 min), median ED length of stay -14 min [-18, -10], but MEAN length of stay only -5 min [-8, -3] (about 2%) and ED census -2%; ESI 1-2 waiting -0.1 patient-h/day; walk-outs, deaths and adverse events unchanged. Holds in 8 of 8 ensemble members. Most of the median gain is a reshuffle of who waits (the index serves freshly ready dispositions first and lets the longest-waiting ones wait longer), not extra throughput.
- Dispatch alone, flu surge: mean wait -9 to -13 min, 95th-percentile wait about -105 min, median length of stay -40 min, mean length of stay -20 to -23 min (about 6%), walk-outs -0.5 percentage points, in 8 of 8 members; but deaths +0.9 to +1.5 per 10,000 arrivals (interval excludes zero, worse in 7-8 of 8 members) and adverse events up. It fails the safety constraints of same_budget_better_flow under surge (feasible in 0-1 of 8 members). The hard-coded acuity_first rule stays feasible.
- The search on the plain patient-outcome objective (wait, walk-outs, ESI 1-2 waiting, adverse events; length of stay and boarding not allowed to worsen) returned the baseline rule: no candidate beat it on fresh tuning seeds, in two attempts (from the baseline rule, and warm-started from the flow-tuned index).
- Against the tuned rule manager (which re-plans staffing within the same budget), dispatch alone loses clearly: flow index 0.88 vs 0.65 pooled; in the surge mean wait +14 to +17 min and deaths +3.7 to +4.2 per 10,000.
- Joint (learned index + rule-manager levers) vs the tuned rule manager: median length of stay -8 min [-10, -6] normal and -15 min [-18, -11] surge, mean length of stay -1.7 and -7 min, wait -0.04 and -0.55 min, ESI 1-2 waiting slightly lower, deaths and adverse events unchanged, 8 of 8 members; flow index 0.776 vs 0.802 (normal) and 0.460 vs 0.495 (surge). Feasibility is the same as the tuned manager's (normal: feasible on pooled means, 7 vs 6 of 8 members; surge: both exceed the transfers-out limit on pooled means, 3 of 8 members each). The ablation shows the whole difference is the index: the tuned manager's own levers with the learned index give the same deltas.
- The 16-unit network and the context interactions did not beat the 50-weight linear index on flow; the context version was the least harmful under surge. A richer function class did not help.

## Why

- There is rarely a choice to make at the front door. Baseline tick census over 8 members: 71-79% of the time before first provider contact is triage service, the first-come triage queue and walking, which no ordering changes; on average 0.9 (normal) to 1.7 (surge) new patients are queued for a provider, and two or more are queued in only 18-25% of ticks. The bay queue is empty in 99% of ticks in a normal week (2% of pre-provider time; 21% in the surge).
- The contended queue is dispositions: 4 (normal) to 9.5 (surge) patients are ready for re-evaluation / disposition and waiting for a provider on average, and a new patient and a disposition compete in 22-30% of ticks. That is where the learned index gains: a unified provider queue that interleaves new patients and dispositions by an index instead of the three-way provider_split lever.
- Within a triage level patients are exchangeable. Condition group, age band and arrival mode change no service time, hazard or patience, so the index has nothing to learn beyond (queue, triage level, time waited). The learned weights on condition and age are noise-sized (|w| < 0.3 levels).
- Service times do not depend on order or on who serves, providers are identical, and work is conserved: an ordering can only move waiting between patients. Mean length of stay therefore moves by 2% while the median moves by 7%. The flow objective uses the median, which an index can improve by letting a tail wait.
- Under surge that tail contains sick patients. The index learned anti-aging (longer in the department = lower priority, +0.5 to +1.2 levels per hour) and deaths rose although ESI 1-2 patients were not seen later. Deaths are too rare for the tuner to see at its sample size (the safety terms carry small weights and slack), so the search bought flow with a harm it could not measure; the held-out run could.
- Walk-outs barely respond in a normal week: calibrated patience means are many hours while the wait is about 15 minutes.

## Held-out comparisons in one line each

- [normal_week] `dispatch_dispatch_flow_context` minus the best hard-coded rule `rule:acuity_first+favor_new`: mean wait -0.10 min [-0.61, +0.16] (ns); 95th-percentile wait -1.09 min [-3.57, +0.03] (ns); median ED length of stay -13.70 min [-17.53, -10.10]; mean ED length of stay -4.99 min [-7.89, -2.91]; walk-outs +0.01 % of arrivals [-0.02, +0.03] (ns); ESI 1-2 waiting -0.12 patient-h/day [-0.21, -0.06]; adverse events -0.00 /day [-0.02, +0.00] (ns); deaths -0.02 /10k [-0.17, +0.14] (ns). Patient index 0.904 vs 0.914, flow index 0.922 vs 0.945 (1 = baseline, lower is better).
- [normal_week] `dispatch_dispatch_flow_context` minus the tuned rule manager `tuned_same_budget`: mean wait +1.22 min [+0.34, +2.07]; 95th-percentile wait +2.94 min [-0.31, +6.17] (ns); median ED length of stay -2.68 min [-5.73, +0.26] (ns); mean ED length of stay +13.64 min [+5.59, +21.69]; walk-outs +0.06 % of arrivals [+0.02, +0.10]; ESI 1-2 waiting +0.39 patient-h/day [-0.02, +0.86] (ns); adverse events +0.05 /day [+0.02, +0.07]; deaths +0.28 /10k [+0.05, +0.57]. Patient index 0.904 vs 0.831, flow index 0.922 vs 0.802 (1 = baseline, lower is better).
- [normal_week] `dispatch_dispatch_flow_linear` minus the best hard-coded rule `rule:acuity_first+favor_new`: mean wait -0.33 min [-0.67, -0.11]; 95th-percentile wait -1.64 min [-3.70, -0.47]; median ED length of stay -14.69 min [-18.59, -10.86]; mean ED length of stay -5.58 min [-7.79, -3.56]; walk-outs -0.02 % of arrivals [-0.04, +0.01] (ns); ESI 1-2 waiting -0.11 patient-h/day [-0.17, -0.04]; adverse events +0.00 /day [-0.00, +0.01] (ns); deaths +0.07 /10k [-0.07, +0.23] (ns). Patient index 0.899 vs 0.914, flow index 0.911 vs 0.945 (1 = baseline, lower is better).
- [normal_week] `dispatch_dispatch_flow_linear` minus the tuned rule manager `tuned_same_budget`: mean wait +0.98 min [+0.07, +1.90]; 95th-percentile wait +2.40 min [-0.94, +5.70] (ns); median ED length of stay -3.67 min [-6.80, -0.68]; mean ED length of stay +13.05 min [+5.05, +21.21]; walk-outs +0.04 % of arrivals [-0.01, +0.08] (ns); ESI 1-2 waiting +0.41 patient-h/day [-0.01, +0.87] (ns); adverse events +0.05 /day [+0.03, +0.08]; deaths +0.37 /10k [+0.12, +0.67]. Patient index 0.899 vs 0.831, flow index 0.911 vs 0.802 (1 = baseline, lower is better).
- [normal_week] `dispatch_dispatch_flow_mlp` minus the best hard-coded rule `rule:acuity_first+favor_new`: mean wait -0.31 min [-0.69, -0.09]; 95th-percentile wait -1.48 min [-3.44, -0.42]; median ED length of stay -13.80 min [-17.58, -10.23]; mean ED length of stay -4.84 min [-6.84, -3.01]; walk-outs -0.01 % of arrivals [-0.03, +0.01] (ns); ESI 1-2 waiting -0.13 patient-h/day [-0.20, -0.07]; adverse events -0.00 /day [-0.01, +0.01] (ns); deaths -0.01 /10k [-0.16, +0.15] (ns). Patient index 0.897 vs 0.914, flow index 0.914 vs 0.945 (1 = baseline, lower is better).
- [normal_week] `dispatch_dispatch_flow_mlp` minus the tuned rule manager `tuned_same_budget`: mean wait +1.00 min [+0.11, +1.89]; 95th-percentile wait +2.55 min [-0.65, +5.73] (ns); median ED length of stay -2.79 min [-5.96, +0.29] (ns); mean ED length of stay +13.79 min [+5.55, +22.11]; walk-outs +0.04 % of arrivals [-0.01, +0.09] (ns); ESI 1-2 waiting +0.39 patient-h/day [-0.02, +0.85] (ns); adverse events +0.05 /day [+0.02, +0.08]; deaths +0.29 /10k [+0.05, +0.60]. Patient index 0.897 vs 0.831, flow index 0.914 vs 0.802 (1 = baseline, lower is better).
- [normal_week] `dispatch_dispatch_only_linear` minus the best hard-coded rule `rule:acuity_first+favor_new`: mean wait +3.43 min [+0.00, +8.23] (ns); 95th-percentile wait +18.10 min [+0.00, +43.28] (ns); median ED length of stay -0.76 min [-2.27, +0.00] (ns); mean ED length of stay -1.14 min [-3.54, +0.00] (ns); walk-outs +0.13 % of arrivals [+0.00, +0.33] (ns); ESI 1-2 waiting +0.47 patient-h/day [+0.00, +1.14] (ns); adverse events +0.01 /day [+0.00, +0.03] (ns); deaths +0.09 /10k [+0.00, +0.26] (ns). Patient index 1.000 vs 0.914, flow index 1.000 vs 0.945 (1 = baseline, lower is better).
- [normal_week] `dispatch_joint_linear` minus the best hard-coded rule `rule:acuity_first+favor_new`: mean wait -1.35 min [-2.51, -0.30]; 95th-percentile wait -4.69 min [-8.75, -1.02]; median ED length of stay -19.06 min [-25.00, -13.05]; mean ED length of stay -20.31 min [-30.81, -10.26]; walk-outs -0.05 % of arrivals [-0.10, +0.00] (ns); ESI 1-2 waiting -0.54 patient-h/day [-0.99, -0.12]; adverse events -0.05 /day [-0.08, -0.02]; deaths -0.24 /10k [-0.52, +0.01] (ns). Patient index 0.830 vs 0.914, flow index 0.776 vs 0.945 (1 = baseline, lower is better).
- [normal_week] `dispatch_joint_linear` minus the tuned rule manager `tuned_same_budget`: mean wait -0.04 min [-0.07, -0.01]; 95th-percentile wait -0.65 min [-1.25, -0.18]; median ED length of stay -8.05 min [-9.95, -6.20]; mean ED length of stay -1.68 min [-2.28, -1.10]; walk-outs +0.00 % of arrivals [-0.01, +0.02] (ns); ESI 1-2 waiting -0.03 patient-h/day [-0.05, -0.01]; adverse events +0.00 /day [-0.00, +0.01] (ns); deaths +0.06 /10k [-0.05, +0.19] (ns). Patient index 0.830 vs 0.831, flow index 0.776 vs 0.802 (1 = baseline, lower is better).
- [normal_week] `dispatch_joint_linear` minus its own levers without the learned index `ablate:dispatch_joint_linear:levers_only`: mean wait -0.05 min [-0.07, -0.02]; 95th-percentile wait -0.68 min [-1.25, -0.21]; median ED length of stay -8.23 min [-10.23, -6.33]; mean ED length of stay -1.67 min [-2.28, -1.13]; walk-outs +0.00 % of arrivals [-0.01, +0.02] (ns); ESI 1-2 waiting -0.03 patient-h/day [-0.04, -0.02]; adverse events -0.00 /day [-0.01, +0.00] (ns); deaths +0.08 /10k [-0.02, +0.21] (ns). Patient index 0.830 vs 0.833, flow index 0.776 vs 0.788 (1 = baseline, lower is better).
- [normal_week] `ablate:dispatch_joint_linear:index_on_tuned` minus the tuned rule manager `tuned_same_budget`: mean wait -0.05 min [-0.08, -0.02]; 95th-percentile wait -0.76 min [-1.38, -0.26]; median ED length of stay -8.07 min [-9.97, -6.22]; mean ED length of stay -1.65 min [-2.26, -1.11]; walk-outs +0.00 % of arrivals [-0.01, +0.02] (ns); ESI 1-2 waiting -0.03 patient-h/day [-0.05, -0.02]; adverse events -0.00 /day [-0.01, +0.00] (ns); deaths +0.07 /10k [-0.03, +0.20] (ns). Patient index 0.829 vs 0.831, flow index 0.790 vs 0.802 (1 = baseline, lower is better).
- [normal_week] same_budget_better_flow, `dispatch_dispatch_flow_context`: score +0.1070 on pooled means, feasible = True; feasible in 4 of 8 members; per-member mean score +0.0589.
- [normal_week] same_budget_better_flow, `dispatch_dispatch_flow_linear`: score +0.1164 on pooled means, feasible = True; feasible in 3 of 8 members; per-member mean score +0.0482.
- [normal_week] same_budget_better_flow, `dispatch_dispatch_flow_mlp`: score +0.1145 on pooled means, feasible = True; feasible in 4 of 8 members; per-member mean score +0.0775.
- [normal_week] same_budget_better_flow, `dispatch_dispatch_only_linear`: score +0.0000 on pooled means, feasible = True; feasible in 8 of 8 members; per-member mean score +0.0000.
- [normal_week] same_budget_better_flow, `dispatch_joint_linear`: score +0.2709 on pooled means, feasible = True; feasible in 7 of 8 members; per-member mean score +0.1033.
- [normal_week] same_budget_better_flow, `ablate:dispatch_joint_linear:levers_only`: score +0.2595 on pooled means, feasible = True; feasible in 7 of 8 members; per-member mean score +0.0844.
- [normal_week] same_budget_better_flow, `ablate:dispatch_joint_linear:index_on_tuned`: score +0.2570 on pooled means, feasible = True; feasible in 6 of 8 members; per-member mean score +0.0810.
- [normal_week] same_budget_better_flow, `rule:acuity_first+favor_new`: score +0.0821 on pooled means, feasible = True; feasible in 8 of 8 members; per-member mean score +0.0552.
- [normal_week] same_budget_better_flow, `tuned_same_budget`: score +0.2451 on pooled means, feasible = True; feasible in 6 of 8 members; per-member mean score +0.0599.
- [flu_surge] `dispatch_dispatch_flow_context` minus the best hard-coded rule `rule:acuity_first+favor_new`: mean wait -12.83 min [-25.28, -4.98]; 95th-percentile wait -107.92 min [-206.28, -43.38]; median ED length of stay -39.74 min [-54.40, -26.22]; mean ED length of stay -23.42 min [-36.90, -13.83]; walk-outs -0.45 % of arrivals [-0.85, -0.18]; ESI 1-2 waiting -0.66 patient-h/day [-0.97, -0.36]; adverse events +0.04 /day [-0.01, +0.10] (ns); deaths +0.94 /10k [+0.20, +1.88]. Patient index 0.827 vs 0.945, flow index 0.831 vs 0.979 (1 = baseline, lower is better).
- [flu_surge] `dispatch_dispatch_flow_context` minus the tuned rule manager `tuned_same_budget`: mean wait +13.78 min [+6.83, +23.35]; 95th-percentile wait +42.01 min [+17.73, +79.28]; median ED length of stay +5.36 min [-2.60, +15.34] (ns); mean ED length of stay +86.40 min [+52.42, +124.86]; walk-outs +1.25 % of arrivals [+0.53, +2.28]; ESI 1-2 waiting +3.07 patient-h/day [+1.80, +4.79]; adverse events +0.41 /day [+0.19, +0.73]; deaths +3.65 /10k [+1.63, +6.51]. Patient index 0.827 vs 0.487, flow index 0.831 vs 0.495 (1 = baseline, lower is better).
- [flu_surge] `dispatch_dispatch_flow_linear` minus the best hard-coded rule `rule:acuity_first+favor_new`: mean wait -11.42 min [-24.09, -4.08]; 95th-percentile wait -105.16 min [-207.57, -41.14]; median ED length of stay -40.60 min [-54.61, -27.50]; mean ED length of stay -20.52 min [-32.49, -12.91]; walk-outs -0.46 % of arrivals [-0.87, -0.20]; ESI 1-2 waiting +4.35 patient-h/day [+0.35, +11.24]; adverse events +0.16 /day [+0.04, +0.34]; deaths +1.52 /10k [+0.47, +3.03]. Patient index 1.005 vs 0.945, flow index 0.841 vs 0.979 (1 = baseline, lower is better).
- [flu_surge] `dispatch_dispatch_flow_linear` minus the tuned rule manager `tuned_same_budget`: mean wait +15.20 min [+7.17, +25.83]; 95th-percentile wait +44.77 min [+17.00, +85.19]; median ED length of stay +4.51 min [-4.04, +15.47] (ns); mean ED length of stay +89.31 min [+53.10, +130.42]; walk-outs +1.23 % of arrivals [+0.51, +2.23]; ESI 1-2 waiting +8.09 patient-h/day [+3.07, +16.58]; adverse events +0.54 /day [+0.23, +0.97]; deaths +4.23 /10k [+1.84, +7.69]. Patient index 1.005 vs 0.487, flow index 0.841 vs 0.495 (1 = baseline, lower is better).
- [flu_surge] `dispatch_dispatch_flow_mlp` minus the best hard-coded rule `rule:acuity_first+favor_new`: mean wait -9.21 min [-16.50, -4.41]; 95th-percentile wait -106.64 min [-203.10, -43.30]; median ED length of stay -40.03 min [-54.92, -26.41]; mean ED length of stay -19.70 min [-28.94, -12.83]; walk-outs -0.52 % of arrivals [-0.95, -0.23]; ESI 1-2 waiting -0.48 patient-h/day [-0.85, +0.06] (ns); adverse events +0.07 /day [+0.01, +0.15]; deaths +1.52 /10k [+0.56, +2.86]. Patient index 0.850 vs 0.945, flow index 0.843 vs 0.979 (1 = baseline, lower is better).
- [flu_surge] `dispatch_dispatch_flow_mlp` minus the tuned rule manager `tuned_same_budget`: mean wait +17.40 min [+7.54, +31.71]; 95th-percentile wait +43.28 min [+17.00, +82.82]; median ED length of stay +5.08 min [-2.89, +14.84] (ns); mean ED length of stay +90.12 min [+53.70, +131.50]; walk-outs +1.17 % of arrivals [+0.47, +2.18]; ESI 1-2 waiting +3.26 patient-h/day [+1.84, +5.32]; adverse events +0.44 /day [+0.21, +0.78]; deaths +4.23 /10k [+1.97, +7.50]. Patient index 0.850 vs 0.487, flow index 0.843 vs 0.495 (1 = baseline, lower is better).
- [flu_surge] `dispatch_dispatch_only_linear` minus the best hard-coded rule `rule:acuity_first+favor_new`: mean wait +4.34 min [+0.00, +11.20] (ns); 95th-percentile wait +15.26 min [+0.00, +43.26] (ns); median ED length of stay -3.26 min [-8.91, +0.00] (ns); mean ED length of stay -7.05 min [-18.80, +0.00] (ns); walk-outs +0.15 % of arrivals [+0.00, +0.41] (ns); ESI 1-2 waiting +0.77 patient-h/day [+0.00, +1.81] (ns); adverse events +0.01 /day [-0.00, +0.03] (ns); deaths +0.00 /10k [-0.15, +0.15] (ns). Patient index 1.000 vs 0.945, flow index 1.000 vs 0.979 (1 = baseline, lower is better).
- [flu_surge] `dispatch_joint_linear` minus the best hard-coded rule `rule:acuity_first+favor_new`: mean wait -27.17 min [-48.25, -12.69]; 95th-percentile wait -153.57 min [-289.65, -65.52]; median ED length of stay -59.77 min [-83.86, -39.68]; mean ED length of stay -116.77 min [-167.23, -72.89]; walk-outs -1.71 % of arrivals [-3.13, -0.73]; ESI 1-2 waiting -3.90 patient-h/day [-5.60, -2.58]; adverse events -0.38 /day [-0.65, -0.19]; deaths -2.68 /10k [-4.84, -1.13]. Patient index 0.475 vs 0.945, flow index 0.460 vs 0.979 (1 = baseline, lower is better).
- [flu_surge] `dispatch_joint_linear` minus the tuned rule manager `tuned_same_budget`: mean wait -0.55 min [-1.05, -0.24]; 95th-percentile wait -3.65 min [-6.88, -1.35]; median ED length of stay -14.66 min [-18.07, -11.28]; mean ED length of stay -6.95 min [-9.64, -4.72]; walk-outs -0.02 % of arrivals [-0.04, -0.00]; ESI 1-2 waiting -0.16 patient-h/day [-0.25, -0.09]; adverse events -0.00 /day [-0.02, +0.01] (ns); deaths +0.03 /10k [-0.18, +0.25] (ns). Patient index 0.475 vs 0.487, flow index 0.460 vs 0.495 (1 = baseline, lower is better).
- [flu_surge] `dispatch_joint_linear` minus its own levers without the learned index `ablate:dispatch_joint_linear:levers_only`: mean wait -0.36 min [-0.59, -0.17]; 95th-percentile wait -2.79 min [-4.77, -1.17]; median ED length of stay -14.38 min [-18.02, -10.73]; mean ED length of stay -4.25 min [-5.77, -2.89]; walk-outs -0.01 % of arrivals [-0.03, +0.01] (ns); ESI 1-2 waiting -0.11 patient-h/day [-0.18, -0.06]; adverse events -0.00 /day [-0.01, +0.01] (ns); deaths +0.05 /10k [-0.14, +0.26] (ns). Patient index 0.475 vs 0.484, flow index 0.460 vs 0.481 (1 = baseline, lower is better).
- [flu_surge] `ablate:dispatch_joint_linear:index_on_tuned` minus the tuned rule manager `tuned_same_budget`: mean wait -0.39 min [-0.64, -0.19]; 95th-percentile wait -3.31 min [-5.86, -1.48]; median ED length of stay -14.19 min [-17.58, -10.91]; mean ED length of stay -4.13 min [-5.36, -2.95]; walk-outs -0.01 % of arrivals [-0.03, +0.00] (ns); ESI 1-2 waiting -0.11 patient-h/day [-0.18, -0.03]; adverse events -0.00 /day [-0.01, +0.00] (ns); deaths +0.05 /10k [-0.16, +0.26] (ns). Patient index 0.478 vs 0.487, flow index 0.474 vs 0.495 (1 = baseline, lower is better).
- [flu_surge] same_budget_better_flow, `dispatch_dispatch_flow_context`: score -0.0129 on pooled means, feasible = False (violated: deaths_per_10k, adverse_events_per_day); feasible in 1 of 8 members; per-member mean score -0.0162.
- [flu_surge] same_budget_better_flow, `dispatch_dispatch_flow_linear`: score -4.2664 on pooled means, feasible = False (violated: deaths_per_10k, adverse_events_per_day, hi_acuity_wait_hours_per_day); feasible in 1 of 8 members; per-member mean score -4.2027.
- [flu_surge] same_budget_better_flow, `dispatch_dispatch_flow_mlp`: score -0.1975 on pooled means, feasible = False (violated: deaths_per_10k, adverse_events_per_day); feasible in 0 of 8 members; per-member mean score -0.1720.
- [flu_surge] same_budget_better_flow, `dispatch_dispatch_only_linear`: score +0.0000 on pooled means, feasible = True; feasible in 8 of 8 members; per-member mean score -0.0000.
- [flu_surge] same_budget_better_flow, `dispatch_joint_linear`: score +0.5077 on pooled means, feasible = False (violated: transfers_per_day); feasible in 3 of 8 members; per-member mean score +0.3882.
- [flu_surge] same_budget_better_flow, `ablate:dispatch_joint_linear:levers_only`: score +0.4984 on pooled means, feasible = False (violated: transfers_per_day); feasible in 3 of 8 members; per-member mean score +0.3748.
- [flu_surge] same_budget_better_flow, `ablate:dispatch_joint_linear:index_on_tuned`: score +0.4887 on pooled means, feasible = False (violated: transfers_per_day); feasible in 3 of 8 members; per-member mean score +0.3811.
- [flu_surge] same_budget_better_flow, `rule:acuity_first+favor_new`: score +0.0297 on pooled means, feasible = True; feasible in 7 of 8 members; per-member mean score +0.0187.
- [flu_surge] same_budget_better_flow, `tuned_same_budget`: score +0.4843 on pooled means, feasible = False (violated: transfers_per_day); feasible in 3 of 8 members; per-member mean score +0.3714.
- [pooled] `dispatch_dispatch_flow_context` minus the best hard-coded rule `rule:acuity_first+favor_new`: mean wait -6.46 min [-12.99, -2.28]; 95th-percentile wait -54.51 min [-105.46, -19.82]; median ED length of stay -26.72 min [-36.75, -17.95]; mean ED length of stay -14.21 min [-22.33, -8.39]; walk-outs -0.22 % of arrivals [-0.44, -0.07]; ESI 1-2 waiting -0.39 patient-h/day [-0.60, -0.22]; adverse events +0.02 /day [-0.01, +0.05] (ns); deaths +0.46 /10k [+0.06, +1.00]. Patient index 0.866 vs 0.930, flow index 0.877 vs 0.962 (1 = baseline, lower is better).
- [pooled] `dispatch_dispatch_flow_context` minus the tuned rule manager `tuned_same_budget`: mean wait +7.50 min [+3.57, +12.72]; 95th-percentile wait +22.47 min [+9.03, +41.10]; median ED length of stay +1.34 min [-3.95, +7.36] (ns); mean ED length of stay +50.02 min [+28.89, +75.35]; walk-outs +0.66 % of arrivals [+0.27, +1.21]; ESI 1-2 waiting +1.73 patient-h/day [+0.93, +2.68]; adverse events +0.23 /day [+0.11, +0.40]; deaths +1.97 /10k [+0.86, +3.52]. Patient index 0.866 vs 0.659, flow index 0.877 vs 0.649 (1 = baseline, lower is better).
- [pooled] `dispatch_dispatch_flow_linear` minus the best hard-coded rule `rule:acuity_first+favor_new`: mean wait -5.87 min [-12.36, -2.06]; 95th-percentile wait -53.40 min [-106.99, -19.20]; median ED length of stay -27.64 min [-37.41, -19.02]; mean ED length of stay -13.05 min [-19.65, -8.41]; walk-outs -0.24 % of arrivals [-0.46, -0.10]; ESI 1-2 waiting +2.12 patient-h/day [+0.10, +5.59]; adverse events +0.08 /day [+0.02, +0.18]; deaths +0.80 /10k [+0.23, +1.59]. Patient index 0.952 vs 0.930, flow index 0.876 vs 0.962 (1 = baseline, lower is better).
- [pooled] `dispatch_dispatch_flow_linear` minus the tuned rule manager `tuned_same_budget`: mean wait +8.09 min [+3.60, +14.04]; 95th-percentile wait +23.58 min [+8.61, +44.14]; median ED length of stay +0.42 min [-5.17, +6.93] (ns); mean ED length of stay +51.18 min [+28.87, +78.13]; walk-outs +0.63 % of arrivals [+0.24, +1.19]; ESI 1-2 waiting +4.25 patient-h/day [+1.61, +8.47]; adverse events +0.29 /day [+0.13, +0.53]; deaths +2.30 /10k [+0.98, +4.17]. Patient index 0.952 vs 0.659, flow index 0.876 vs 0.649 (1 = baseline, lower is better).
- [pooled] `dispatch_dispatch_flow_mlp` minus the best hard-coded rule `rule:acuity_first+favor_new`: mean wait -4.76 min [-8.67, -2.10]; 95th-percentile wait -54.06 min [-103.76, -20.14]; median ED length of stay -26.91 min [-37.11, -18.11]; mean ED length of stay -12.27 min [-17.98, -7.85]; walk-outs -0.27 % of arrivals [-0.50, -0.10]; ESI 1-2 waiting -0.30 patient-h/day [-0.51, -0.03]; adverse events +0.03 /day [+0.00, +0.08]; deaths +0.75 /10k [+0.24, +1.50]. Patient index 0.873 vs 0.930, flow index 0.879 vs 0.962 (1 = baseline, lower is better).
- [pooled] `dispatch_dispatch_flow_mlp` minus the tuned rule manager `tuned_same_budget`: mean wait +9.20 min [+3.82, +16.63]; 95th-percentile wait +22.92 min [+8.35, +42.87]; median ED length of stay +1.15 min [-4.13, +7.25] (ns); mean ED length of stay +51.95 min [+29.55, +78.85]; walk-outs +0.61 % of arrivals [+0.24, +1.14]; ESI 1-2 waiting +1.82 patient-h/day [+0.95, +2.93]; adverse events +0.24 /day [+0.12, +0.43]; deaths +2.26 /10k [+1.01, +4.12]. Patient index 0.873 vs 0.659, flow index 0.879 vs 0.649 (1 = baseline, lower is better).
- [pooled] `dispatch_dispatch_only_linear` minus the best hard-coded rule `rule:acuity_first+favor_new`: mean wait +3.88 min [+0.00, +9.55] (ns); 95th-percentile wait +16.68 min [+0.00, +40.56] (ns); median ED length of stay -2.01 min [-5.67, +0.00] (ns); mean ED length of stay -4.09 min [-11.47, +0.00] (ns); walk-outs +0.14 % of arrivals [+0.00, +0.35] (ns); ESI 1-2 waiting +0.62 patient-h/day [+0.00, +1.50] (ns); adverse events +0.01 /day [+0.00, +0.03] (ns); deaths +0.05 /10k [-0.03, +0.17] (ns). Patient index 1.000 vs 0.930, flow index 1.000 vs 0.962 (1 = baseline, lower is better).
- [pooled] `dispatch_joint_linear` minus the best hard-coded rule `rule:acuity_first+favor_new`: mean wait -14.26 min [-25.45, -6.40]; 95th-percentile wait -79.13 min [-147.51, -31.24]; median ED length of stay -39.41 min [-55.83, -26.09]; mean ED length of stay -68.54 min [-102.61, -41.04]; walk-outs -0.88 % of arrivals [-1.64, -0.35]; ESI 1-2 waiting -2.22 patient-h/day [-3.22, -1.37]; adverse events -0.21 /day [-0.37, -0.11]; deaths -1.46 /10k [-2.64, -0.61]. Patient index 0.653 vs 0.930, flow index 0.618 vs 0.962 (1 = baseline, lower is better).
- [pooled] `dispatch_joint_linear` minus the tuned rule manager `tuned_same_budget`: mean wait -0.29 min [-0.57, -0.13]; 95th-percentile wait -2.15 min [-4.09, -0.86]; median ED length of stay -11.35 min [-14.09, -8.82]; mean ED length of stay -4.31 min [-6.00, -2.93]; walk-outs -0.01 % of arrivals [-0.02, +0.00] (ns); ESI 1-2 waiting -0.10 patient-h/day [-0.15, -0.05]; adverse events -0.00 /day [-0.01, +0.00] (ns); deaths +0.05 /10k [-0.08, +0.17] (ns). Patient index 0.653 vs 0.659, flow index 0.618 vs 0.649 (1 = baseline, lower is better).
- [pooled] `dispatch_joint_linear` minus its own levers without the learned index `ablate:dispatch_joint_linear:levers_only`: mean wait -0.21 min [-0.34, -0.10]; 95th-percentile wait -1.73 min [-3.00, -0.78]; median ED length of stay -11.30 min [-14.26, -8.55]; mean ED length of stay -2.96 min [-4.07, -2.00]; walk-outs -0.00 % of arrivals [-0.01, +0.01] (ns); ESI 1-2 waiting -0.07 patient-h/day [-0.11, -0.04]; adverse events -0.00 /day [-0.01, +0.00] (ns); deaths +0.06 /10k [-0.04, +0.19] (ns). Patient index 0.653 vs 0.658, flow index 0.618 vs 0.634 (1 = baseline, lower is better).
- [pooled] `ablate:dispatch_joint_linear:index_on_tuned` minus the tuned rule manager `tuned_same_budget`: mean wait -0.22 min [-0.37, -0.11]; 95th-percentile wait -2.03 min [-3.61, -0.91]; median ED length of stay -11.13 min [-13.85, -8.58]; mean ED length of stay -2.89 min [-3.87, -2.07]; walk-outs -0.00 % of arrivals [-0.01, +0.01] (ns); ESI 1-2 waiting -0.07 patient-h/day [-0.11, -0.03]; adverse events -0.00 /day [-0.01, +0.00] (ns); deaths +0.06 /10k [-0.06, +0.18] (ns). Patient index 0.653 vs 0.659, flow index 0.632 vs 0.649 (1 = baseline, lower is better).

## How it was trained

- Engine hook: sim.set_dispatch_params (sim/engine.py), per-hospital parameter rows, so a population runs as one batch. The four hard-coded rules are exact special cases.
- Features (triage-desk knowledge only): triage ESI, minutes since arrival, catalog mean encounter time by triage level, which queue (bay / new in bay / disposition / scanner) x triage level, hours in the current queue, walk-out pressure (wait / catalog mean patience at that triage level, walk-ins not yet seen), deterioration flag, arrival mode, age band, condition group; context: queue lengths, boarding, bay and ward occupancy, providers free, hour of day, ESI 1-2 unseen. Not used: latent acuity, sampled patience, sampled service times, test needs, true disposition.
- Search: cross-entropy method, population 48-64, elite 10-12, 16-24 generations, 3 ensemble members x 2 scenarios x 4 seeds x 10 days per candidate per generation, baseline on the same seeds, robust score over members; final pick on fresh tuning seeds over 8 members x 8 seeds x 14 days, with the starting point among the finalists. Tuning seeds 320,000-399,999 only.
- Runs: dispatch_only linear (patient index; 24 generations, returned the baseline; a warm-started second attempt of 8 generations also failed to beat its start), dispatch_flow linear (51 dims), dispatch_flow context (161 dims), dispatch_flow mlp (1,153 dims, 16 hidden units, warm-started from the context index), joint linear (31 rule parameters + 51, warm-started from the tuned rule manager of the current calibration).
- Comparator `tuned_same_budget` is the tuned rule manager produced by the main pipeline for the current calibration (copy: rl/hospitals/rwjuh_nb/dispatch_comparator_tuned_same_budget.json).

## Decision-level gradient RL

Not attempted. Route (a) and the tick census show the headroom of ordering in this twin is a few percent of mean length of stay; a stochastic Plackett-Luce policy trained with PPO/REINFORCE on hourly reward would search the same index family with a noisier estimator, and the binding problem (rare-event safety invisible at training sample sizes) would be the same.

## What the simulator would need for dispatch to matter more

- Individual providers. Providers are a head-count per pool, identical and interchangeable; any free provider takes any patient and any disposition. Matching needs provider-level skill or speed differences (attending / resident / APP), specialty fit by condition group, and continuity (the provider who saw the patient does the re-evaluation faster than a colleague).
- Patient features that predict something. Condition group, age band and arrival mode change no service time, hazard or patience in the model; within a triage level every patient is statistically the same except for time already waited. An index over (queue, triage level, wait) is therefore already sufficient. Needed: service time, test need, admission probability and deterioration risk that depend on condition, age and vitals, so that two ESI-3 patients genuinely differ.
- Signals that arrive while waiting. The only thing that changes for a queued patient is the clock and a rare deterioration flag. Needed: repeat vitals, results coming back, a nurse's concern flag, detectable mis-triage.
- A binding bay decision. In the calibrated twin the bay queue is empty almost all the time, and bay eligibility is a fixed cascade (resus, peds, fast track, main, hallway). Needed: scarce bays with mismatch costs (monitored vs unmonitored, isolation, a resus bay held back for the next ambulance), so that giving a bay to one patient has an opportunity cost.
- Work that can be batched or sequenced. Imaging is one patient per scanner with independent durations; labs are independent draws. Needed: transport batching, scanner set-up times by study type, provider rounds (several dispositions in one pass), parallel work-ups.
- Consequences of waiting that depend on who waits. Walk-out patience in the calibration is very long (catalog means of many hours) and the hazards before first contact act over a wait of about a quarter of an hour, so re-ordering barely moves walk-outs or harm. Needed: calibrated patience and time-critical conditions (door-to-ECG, stroke and sepsis windows) with outcomes that depend on minutes.
- A contended front door. About 80% of the time before first provider contact is triage service and walking, which no ordering can change, and triage itself is first-come-first-served because acuity is not known before it. Needed: a twin whose provider queue is actually long at peak (or a triage-desk decision such as quick-look acuity or split-flow streaming).

