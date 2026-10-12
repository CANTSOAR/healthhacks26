# Marginal value of every resource: rwjuh_nb (SIMULATED)

> Every number here is SIMULATED: a model fitted to the hospital's published aggregates, not its operational data. Differences are paired on the same simulated patients; intervals are 95% Student-t over seeds.

Generated 2026-10-11T03:38:00+0000 by `rl/attribution.py`. Policy: **Current practice (calibrated baseline actions)** (`fixed`). 32 held-out seeds (9100000..9100031) x 30 simulated days per scenario, point calibration (ensemble member 0). Every row compares the twin with and without ONE unit on the same seeds (same patients), so the differences are paired; brackets are 95% intervals. Calibration fingerprint `13559aa34001a108`.

**How to read it.** *Value to the objective* is the unit's net effect on the `balanced` reward (cost, revenue, waiting, walk-outs, safety, boarding, staff strain; each term divided by its baseline level), expressed in dollars of daily cost at the objective's own exchange rate (change in reward per hour x $25,313/h x 24). It is already net of what the unit costs, and it is an exchange rate set by the chosen weights, not cash; the per-seed term differences in the JSON re-score it under any other weights. *Per $* divides it by what the unit costs per day, and the table is ranked on that. *Margin alone* = the cash margin the hospital would lose per day without the unit (its cost netted off); it counts no harm. *Next unit* = the same two numbers for adding one more. *Patient-flow index* is the money-free view: door-to-provider wait, median ED stay, walk-out rate and boarding, each as a share of its baseline (weights 0.3 / 0.3 / 0.2 / 0.2); +1% means flow got 1% worse.

## normal_week (simulated)

Baseline: mean door-to-provider wait 14.5 min, p95 30 min, median ED stay 207 min, 2.0 walk-outs/day, boarding 11 patient-hours/day, labour $104,730/day, margin $424,420/day.

### Ranked by net value per dollar of the existing unit (simulated)

| # | Resource | Costs $/day | Value to the objective, $-equivalent/day [95% CI] | per $ | Margin alone, net $/day [95% CI] | Patient-flow index if removed, % [95% CI] (+ = worse) | Removing it: biggest effects | Verdict if removed | Next unit: value to the objective, $-eq/day [95% CI] | Next unit: margin alone $/day | Flow index if added, % | Verdict if added |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | One triage station (room + nurse) | 1,996 | +81,259 [+76,689, +85,829] | +40.7 | -1,036 [-1,469, -604] | +6.89 [+5.73, +8.05] | ESI 1-2 patients waiting +1.05 patient-hours/day; 95th-percentile door-to-provider wait +5.16 min; Left without being seen +0.27 patients/day | needed | +3,687 [-6,786, +14,160] | -1,820 [-2,162, -1,478] | +0.66 [-2.48, +3.80] | not shown either way |
| 2 | One provider, night shift | 926 | +35,526 [+28,793, +42,259] | +38.4 | -3,190 [-4,086, -2,295] | +3.67 [+2.64, +4.71] | ESI 1-2 patients waiting +0.33 patient-hours/day; 95th-percentile door-to-provider wait +2.19 min; Adverse events +0.03 per day | needed | +29,818 [+4,478, +55,158] | -3,210 [-4,042, -2,379] | -5.57 [-12.64, +1.50] | worth adding |
| 3 | One X-ray room | 100 | +3,175 [-2,052, +8,402] | +31.8 | -449 [-1,016, +117] | +1.08 [+0.52, +1.64] | Median ED length of stay +4.69 min; Patients treated -0.11 per day | trade-off | +433 [-139, +1,006] | -69 [-115, -23] | -0.04 [-0.13, +0.04] | not shown either way |
| 4 | One provider, evening shift | 926 | +29,140 [+18,484, +39,796] | +31.5 | -2,218 [-2,771, -1,666] | +2.66 [+1.76, +3.56] | Adverse events +0.02 per day; ESI 1-2 patients waiting +0.21 patient-hours/day; Left without being seen +0.08 patients/day | needed | +13,134 [+6,614, +19,653] | -2,343 [-2,818, -1,868] | -1.98 [-3.06, -0.89] | worth adding |
| 5 | A block of 8 inpatient ward beds | 13,710 | +257,620 [-167,740, +682,980] | +18.8 | -3,848 [-9,976, +2,281] | +50.07 [-18.47, +118.61] | Revenue -10,502.0 $/day | inconclusive | +21,795 [-38,494, +82,084] | -7,098 [-9,123, -5,073] | -10.55 [-29.01, +7.90] | not shown either way |
| 6 | One provider, day shift | 926 | +14,794 [+9,034, +20,554] | +16.0 | -2,205 [-2,795, -1,615] | +1.70 [+0.86, +2.53] | Adverse events +0.01 per day; ESI 1-2 patients waiting +0.09 patient-hours/day; 95th-percentile door-to-provider wait +0.62 min | needed | +7,614 [+1,165, +14,063] | -2,282 [-2,702, -1,863] | -1.45 [-2.56, -0.34] | worth adding |
| 7 | One inpatient ward bed | 1,714 | +22,994 [-16,164, +62,152] | +13.4 | -491 [-1,535, +554] | +6.43 [-5.11, +17.97] | Revenue -1,341.7 $/day | inconclusive | +7,996 [-6,722, +22,715] | -576 [-1,366, +214] | -2.86 [-7.20, +1.49] | not shown either way |
| 8 | Second-CT staffing, an 8-hour block | 451 | +2,776 [-1,106, +6,659] | +6.2 | -617 [-995, -239] | +0.93 [+0.32, +1.54] | Median ED length of stay +5.16 min; Mean door-to-provider wait +0.05 min; Patients treated -0.06 per day | trade-off | -318 [-999, +364] | -443 [-449, -438] | -0.07 [-0.16, +0.02] | not shown either way |
| 9 | One nurse, night shift | 533 | +2,915 [+1,164, +4,667] | +5.5 | -417 [-571, -263] | +0.23 [-0.06, +0.52] | ESI 1-2 patients waiting +0.03 patient-hours/day; Left without being seen +0.01 patients/day; Mean door-to-provider wait +0.06 min | trade-off | -609 [-5,413, +4,195] | -557 [-618, -497] | +0.75 [-1.13, +2.63] | not shown either way |
| 10 | One CT scanner | 1,351 | +1,954 [-3,251, +7,158] | +1.4 | -1,647 [-2,318, -975] | +0.83 [-0.24, +1.91] | Median ED length of stay +10.9 min; Adverse events +0.01 per day; ESI 1-2 patients waiting +0.07 patient-hours/day | trade-off | -1,936 [-3,828, -43] | -1,267 [-1,418, -1,116] | -0.10 [-0.26, +0.07] | not worth adding |
| 11 | One hallway stretcher space | 319 | n/a (not in use at baseline) |  |  |  |  |  | -68 [-683, +547] | -318 [-327, -309] | +0.02 [-0.05, +0.09] | not shown either way |
| 12 | Hallway overflow, 8 spaces | 2,554 | n/a (not in use at baseline) |  |  |  |  |  | -1,058 [-2,382, +267] | -2,513 [-2,573, -2,452] | -0.08 [-0.20, +0.04] | not shown either way |
| 13 | One pediatric ED bay | 955 | -447 [-1,320, +427] | -0.5 | -952 [-956, -948] | +0.06 [+0.00, +0.11] | Patients treated -0.01 per day | slack | -393 [-933, +147] | -951 [-960, -942] | -0.03 [-0.09, +0.04] | not shown either way |
| 14 | A block of 4 main treatment bays | 3,821 | -2,600 [-3,646, -1,554] | -0.7 | -3,773 [-3,860, -3,685] | +0.09 [-0.03, +0.20] | Mean door-to-provider wait +0.03 min | slack | -3,380 [-4,457, -2,303] | -3,817 [-3,827, -3,808] | -0.02 [-0.09, +0.05] | not worth adding |
| 15 | One main treatment bay | 955 | -663 [-1,416, +90] | -0.7 | -953 [-958, -948] | +0.03 [-0.05, +0.11] | Mean door-to-provider wait +0.01 min | slack | -492 [-1,003, +18] | -953 [-962, -944] | -0.00 [-0.06, +0.05] | not shown either way |
| 16 | One nurse, evening shift | 533 | -519 [-525, -513] | -1.0 | -519 [-525, -513] | +0.00 [+0.00, +0.00] | none outside the intervals | slack | -519 [-525, -514] | -519 [-525, -514] | +0.00 [+0.00, +0.00] | not worth adding |
| 17 | One nurse, day shift | 533 | -520 [-526, -513] | -1.0 | -519 [-525, -513] | +0.00 [+0.00, +0.00] | none outside the intervals | slack | -517 [-524, -511] | -518 [-524, -512] | -0.00 [-0.00, +0.00] | not worth adding |
| 18 | One resuscitation bay | 2,546 | -2,537 [-2,551, -2,524] | -1.0 | -2,546 [-2,546, -2,546] | +0.00 [-0.00, +0.00] | none outside the intervals | slack | -2,530 [-2,563, -2,498] | -2,546 [-2,546, -2,546] | -0.00 [-0.00, +0.00] | not worth adding |
| 19 | One fast-track space | 557 | -4,733 [-7,173, -2,293] | -8.5 | -811 [-1,036, -587] | -0.74 [-1.02, -0.46] | Median ED length of stay -3.12 min; Mean door-to-provider wait -0.12 min; Revenue +270.6 $/day | slack | -7,196 [-10,740, -3,651] | -508 [-808, -207] | +1.06 [+0.28, +1.84] | not worth adding |
| 20 | Fast track (the whole stream) | 5,568 | -53,403 [-64,392, -42,414] | -9.6 | -7,938 [-8,727, -7,150] | -4.81 [-6.11, -3.52] | 95th-percentile door-to-provider wait -6.56 min; Mean door-to-provider wait -1.26 min; Left without being seen -0.16 patients/day | costs more than it returns | n/a |  |  |  |

### Binding and slack (simulated)

- **Add first: One provider, night shift.** Value to the objective +29,818 [+4,478, +55,158] $-equivalent/day (reward +0.0491 [+0.0074, +0.0908] per hour); margin alone -3,210 [-4,042, -2,379] $/day.
- Also worth adding (reward interval above zero): One provider, evening shift (+0.0216 [+0.0109, +0.0323]); One provider, day shift (+0.0125 [+0.0019, +0.0231]).
- Needed (removing one measurably hurts flow or safety and lowers the reward): One triage station (room + nurse) (-0.1338 [-0.1413, -0.1262]); One provider, night shift (-0.0585 [-0.0696, -0.0474]); One provider, evening shift (-0.0480 [-0.0655, -0.0304]); One provider, day shift (-0.0244 [-0.0338, -0.0149]).
- Slack (removing one saves money and no flow or safety metric leaves its equivalence margin): A block of 4 main treatment bays (margin +3,773 [+3,685, +3,860] $/day); One resuscitation bay (margin +2,546 [+2,546, +2,546] $/day); One main treatment bay (margin +953 [+948, +958] $/day); One pediatric ED bay (margin +952 [+948, +956] $/day); One fast-track space (margin +811 [+587, +1,036] $/day); One nurse, day shift (margin +519 [+513, +525] $/day); One nurse, evening shift (margin +519 [+513, +525] $/day).
- Not shown either way: One nurse, night shift (trade-off); Fast track (the whole stream) (costs more than it returns); One inpatient ward bed (inconclusive); A block of 8 inpatient ward beds (inconclusive); One CT scanner (trade-off); One X-ray room (trade-off); Second-CT staffing, an 8-hour block (trade-off).
- Patient flow only (no money): the single additions that improve the flow index most are One provider, evening shift (-1.98 [-3.06, -0.89]%); One provider, day shift (-1.45 [-2.56, -0.34]%).
- Patient flow only: the single removals that hurt it most are One triage station (room + nurse) (+6.89 [+5.73, +8.05]%); One provider, night shift (+3.67 [+2.64, +4.71]%); One provider, evening shift (+2.66 [+1.76, +3.56]%); One provider, day shift (+1.70 [+0.86, +2.53]%); One X-ray room (+1.08 [+0.52, +1.64]%); Second-CT staffing, an 8-hour block (+0.93 [+0.32, +1.54]%).
- **Read the money columns with care.** For One provider, day shift (revenue +1,424 [+793, +2,055] $/day, admissions +0.064 [+0.039, +0.088]/day); One provider, evening shift (revenue +1,391 [+799, +1,984] $/day, admissions +0.040 [+0.008, +0.071]/day); One provider, night shift (revenue +2,498 [+1,569, +3,427] $/day, admissions +0.122 [+0.091, +0.153]/day) the model's revenue goes UP when the unit is removed although patient flow gets measurably worse: with slower care more patients end up admitted, and the model books inpatient revenue per admission with no penalty for avoidable admissions. That is a property of the cost model, not evidence that the unit loses money; the reward and flow columns are the ones to act on for these rows.

Rule: worth adding: the balanced reward rises with a 95% interval above zero. needed: removing it makes a flow or safety metric worse (interval above zero and not inside the equivalence margin) and lowers the balanced reward (interval below zero). slack: removing it saves money (interval above zero), every flow and safety metric's interval stays inside its equivalence margin, i.e. it is shown to get at most negligibly worse (margin: 2% of baseline for waits, stay, walk-outs and boarding; 5% for rare safety events), and the balanced reward does not measurably fall. Anything else is not shown either way.

### Effect of removing one unit on each headline metric (simulated; paired difference, 95% CI)

| Resource | Mean door-to-provider wait (min) | 95th-percentile door-to-provider wait (min) | Median ED length of stay (min) | Left without being seen (patients/day) | Boarding (patient-hours/day) | Deaths (per day) | Adverse events (per day) | Labour cost ($/day) | Operating cost (labour + fixed) ($/day) | Revenue ($/day) | Margin ($/day) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| One provider, day shift | +0.28 [+0.20, +0.36] | +0.62 [+0.02, +1.23] | +2.81 [+1.90, +3.72] | +0.03 [+0.01, +0.06] | +0.22 [-0.15, +0.58] | -0.001 [-0.003, +0.001] | +0.014 [+0.006, +0.022] | -901 [-909, -893] | -901 [-909, -893] | +1,424 [+793, +2,055] | +2,205 [+1,615, +2,795] |
| One provider, evening shift | +0.54 [+0.38, +0.70] | +0.94 [+0.22, +1.65] | +4.06 [+3.35, +4.78] | +0.08 [+0.04, +0.12] | +0.10 [-0.26, +0.45] | +0.003 [-0.000, +0.007] | +0.022 [+0.009, +0.035] | -905 [-912, -897] | -905 [-912, -897] | +1,391 [+799, +1,984] | +2,218 [+1,666, +2,771] |
| One provider, night shift | +0.71 [+0.62, +0.79] | +2.19 [+1.28, +3.10] | +6.56 [+5.71, +7.41] | +0.08 [+0.05, +0.11] | +0.25 [-0.19, +0.69] | +0.002 [-0.002, +0.006] | +0.026 [+0.015, +0.037] | -905 [-913, -896] | -905 [-913, -896] | +2,498 [+1,569, +3,427] | +3,190 [+2,295, +4,086] |
| One nurse, day shift | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | -519 [-525, -513] | -519 [-525, -513] | +0 [+0, +0] | +519 [+513, +525] |
| One nurse, evening shift | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | -519 [-525, -513] | -519 [-525, -513] | +0 [+0, +0] | +519 [+513, +525] |
| One nurse, night shift | +0.06 [+0.03, +0.10] | +0.16 [-0.16, +0.47] | +0.00 [+0.00, +0.00] | +0.01 [+0.00, +0.02] | -0.01 [-0.13, +0.11] | +0.000 [+0.000, +0.000] | +0.001 [-0.005, +0.007] | -523 [-527, -518] | -523 [-527, -518] | -114 [-275, +48] | +417 [+263, +571] |
| One triage station (room + nurse) | +1.81 [+1.74, +1.88] | +5.16 [+4.84, +5.47] | +1.25 [+0.46, +2.04] | +0.27 [+0.22, +0.31] | +0.17 [-0.44, +0.77] | +0.004 [-0.001, +0.009] | +0.011 [+0.002, +0.021] | -1,598 [-1,598, -1,598] | -1,996 [-1,996, -1,996] | -1,076 [-1,550, -603] | +1,036 [+604, +1,469] |
| One resuscitation bay | +0.00 [-0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | -0.00 [-0.00, +0.00] | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | +0 [+0, +0] | -2,546 [-2,546, -2,546] | +0 [+0, +0] | +2,546 [+2,546, +2,546] |
| One main treatment bay | +0.01 [+0.00, +0.01] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.00 [-0.01, +0.01] | +0.01 [-0.00, +0.02] | +0.001 [-0.001, +0.003] | +0.000 [-0.003, +0.003] | +0 [+0, +0] | -955 [-955, -955] | -2 [-8, +4] | +953 [+948, +958] |
| A block of 4 main treatment bays | +0.03 [+0.01, +0.05] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.00 [-0.01, +0.01] | -0.01 [-0.04, +0.03] | +0.000 [+0.000, +0.000] | -0.000 [-0.003, +0.003] | +0 [+0, +0] | -3,821 [-3,821, -3,821] | -60 [-169, +49] | +3,773 [+3,685, +3,860] |
| One fast-track space | -0.12 [-0.14, -0.09] | -0.31 [-0.76, +0.13] | -3.12 [-4.01, -2.24] | -0.00 [-0.02, +0.02] | -0.01 [-0.06, +0.05] | -0.001 [-0.003, +0.001] | -0.000 [-0.006, +0.006] | +0 [+0, +0] | -557 [-557, -557] | +271 [+39, +502] | +811 [+587, +1,036] |
| One pediatric ED bay | +0.00 [-0.00, +0.01] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.00 [-0.00, +0.01] | +0.00 [-0.00, +0.01] | +0.001 [-0.001, +0.003] | +0.000 [-0.003, +0.003] | +0 [+0, +0] | -955 [-955, -955] | -4 [-9, +1] | +952 [+948, +956] |
| Fast track (the whole stream) | -1.26 [-1.45, -1.07] | -6.56 [-7.41, -5.71] | -7.34 [-8.26, -6.43] | -0.16 [-0.21, -0.10] | +0.22 [-0.24, +0.69] | -0.001 [-0.005, +0.003] | +0.013 [+0.002, +0.023] | +0 [+0, +0] | -5,568 [-5,568, -5,568] | +2,546 [+1,724, +3,368] | +7,938 [+7,150, +8,727] |
| One inpatient ward bed | +0.02 [-0.04, +0.09] | +0.16 [-0.40, +0.71] | +0.00 [+0.00, +0.00] | +0.02 [-0.03, +0.06] | +3.31 [-2.76, +9.38] | +0.001 [-0.003, +0.005] | +0.007 [-0.004, +0.019] | +0 [+0, +0] | -1,714 [-1,714, -1,714] | -1,342 [-2,411, -272] | +491 [-554, +1,535] |
| A block of 8 inpatient ward beds | +1.80 [-1.73, +5.34] | +13.44 [-14.30, +41.18] | +1.09 [-0.41, +2.59] | +0.37 [-0.39, +1.12] | +22.77 [-6.19, +51.73] | +0.007 [-0.003, +0.017] | +0.025 [-0.009, +0.059] | +0 [+0, +0] | -13,710 [-13,710, -13,710] | -10,502 [-16,896, -4,108] | +3,848 [-2,281, +9,976] |
| One CT scanner | +0.06 [-0.01, +0.14] | -0.16 [-0.71, +0.40] | +10.94 [+9.97, +11.90] | -0.01 [-0.04, +0.01] | -0.39 [-1.00, +0.21] | +0.002 [-0.002, +0.006] | +0.015 [+0.005, +0.024] | -902 [-902, -902] | -1,351 [-1,351, -1,351] | +258 [-448, +964] | +1,647 [+975, +2,318] |
| One X-ray room | +0.04 [-0.02, +0.11] | +0.16 [-0.40, +0.71] | +4.69 [+4.05, +5.32] | +0.02 [-0.01, +0.05] | +0.06 [-0.16, +0.28] | -0.001 [-0.005, +0.003] | -0.000 [-0.009, +0.009] | +0 [+0, +0] | -100 [-100, -100] | +344 [-262, +950] | +449 [-117, +1,016] |
| Second-CT staffing, an 8-hour block | +0.05 [+0.01, +0.09] | +0.16 [-0.16, +0.47] | +5.16 [+4.43, +5.88] | +0.01 [-0.01, +0.03] | -0.01 [-0.28, +0.26] | +0.001 [-0.001, +0.003] | +0.003 [-0.003, +0.009] | -451 [-451, -451] | -451 [-451, -451] | +172 [-229, +572] | +617 [+239, +995] |

### Effect of adding one unit (simulated; paired difference, 95% CI)

| Resource | Mean door-to-provider wait (min) | 95th-percentile door-to-provider wait (min) | Median ED length of stay (min) | Left without being seen (patients/day) | Boarding (patient-hours/day) | Deaths (per day) | Adverse events (per day) | Labour cost ($/day) | Operating cost (labour + fixed) ($/day) | Revenue ($/day) | Margin ($/day) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| One provider, day shift | -0.16 [-0.21, -0.11] | -0.47 [-1.00, +0.07] | -2.66 [-3.57, -1.74] | -0.00 [-0.02, +0.02] | -0.37 [-0.94, +0.21] | -0.002 [-0.005, +0.001] | -0.007 [-0.017, +0.002] | +903 [+894, +912] | +903 [+894, +912] | -1,519 [-1,961, -1,076] | -2,282 [-2,702, -1,863] |
| One provider, evening shift | -0.26 [-0.35, -0.18] | -0.47 [-1.00, +0.07] | -3.28 [-4.15, -2.41] | -0.03 [-0.05, -0.01] | -0.35 [-0.91, +0.21] | -0.001 [-0.003, +0.001] | -0.008 [-0.017, +0.000] | +906 [+895, +916] | +906 [+895, +916] | -1,551 [-2,049, -1,053] | -2,343 [-2,818, -1,868] |
| One provider, night shift | -0.40 [-0.46, -0.35] | -1.25 [-2.04, -0.46] | -5.47 [-6.00, -4.93] | -0.04 [-0.06, -0.02] | -1.90 [-5.58, +1.79] | -0.004 [-0.009, +0.001] | -0.020 [-0.033, -0.007] | +907 [+898, +915] | +907 [+898, +915] | -2,534 [-3,396, -1,673] | -3,210 [-4,042, -2,379] |
| One nurse, day shift | -0.00 [-0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | +518 [+512, +524] | +518 [+512, +524] | +0 [+0, +0] | -518 [-524, -512] |
| One nurse, evening shift | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | +519 [+514, +525] | +519 [+514, +525] | +0 [+0, +0] | -519 [-525, -514] |
| One nurse, night shift | -0.06 [-0.09, -0.03] | -0.16 [-0.47, +0.16] | +0.00 [+0.00, +0.00] | -0.01 [-0.02, +0.00] | +0.50 [-0.52, +1.52] | -0.001 [-0.003, +0.001] | -0.001 [-0.003, +0.001] | +523 [+518, +528] | +523 [+518, +528] | -39 [-97, +20] | -557 [-618, -497] |
| One triage station (room + nurse) | -0.22 [-0.25, -0.19] | -0.31 [-0.76, +0.13] | -0.31 [-0.76, +0.13] | -0.04 [-0.06, -0.01] | +0.82 [-0.83, +2.47] | +0.001 [-0.001, +0.003] | -0.001 [-0.008, +0.006] | +1,598 [+1,598, +1,598] | +1,996 [+1,996, +1,996] | +191 [-181, +563] | -1,820 [-2,162, -1,478] |
| One resuscitation bay | -0.00 [-0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | -0.00 [-0.00, +0.00] | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | +0 [+0, +0] | +2,546 [+2,546, +2,546] | +0 [+0, +0] | -2,546 [-2,546, -2,546] |
| One main treatment bay | -0.01 [-0.01, +0.00] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.00 [-0.01, +0.01] | +0.00 [-0.00, +0.01] | +0.000 [+0.000, +0.000] | -0.001 [-0.003, +0.001] | +0 [+0, +0] | +955 [+955, +955] | -2 [-9, +5] | -953 [-962, -944] |
| A block of 4 main treatment bays | -0.01 [-0.03, +0.01] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | -0.00 [-0.01, +0.01] | +0.02 [-0.01, +0.04] | +0.000 [+0.000, +0.000] | +0.000 [-0.003, +0.003] | +0 [+0, +0] | +3,821 [+3,821, +3,821] | +0 [-4, +5] | -3,817 [-3,827, -3,808] |
| One fast-track space | +0.14 [+0.11, +0.16] | +0.31 [-0.13, +0.76] | +2.34 [+1.43, +3.26] | +0.01 [-0.02, +0.03] | +0.20 [-0.18, +0.58] | -0.001 [-0.005, +0.003] | +0.002 [-0.005, +0.010] | +0 [+0, +0] | +557 [+557, +557] | +68 [-256, +392] | -508 [-808, -207] |
| One pediatric ED bay | -0.00 [-0.01, +0.00] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | -0.00 [-0.01, +0.01] | +0.00 [-0.00, +0.01] | +0.000 [+0.000, +0.000] | -0.001 [-0.003, +0.001] | +0 [+0, +0] | +955 [+955, +955] | +1 [-6, +7] | -951 [-960, -942] |
| One hallway stretcher space | -0.00 [-0.01, +0.00] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | +0.00 [-0.01, +0.01] | +0.00 [-0.00, +0.01] | +0.000 [+0.000, +0.000] | -0.001 [-0.003, +0.001] | +0 [+0, +0] | +319 [+319, +319] | -2 [-9, +5] | -318 [-327, -309] |
| Hallway overflow, 8 spaces | -0.03 [-0.05, +0.00] | -0.16 [-0.47, +0.16] | +0.00 [+0.00, +0.00] | -0.01 [-0.02, +0.00] | +0.02 [-0.01, +0.05] | +0.000 [+0.000, +0.000] | -0.001 [-0.003, +0.001] | +0 [+0, +0] | +2,554 [+2,554, +2,554] | +44 [-18, +107] | -2,513 [-2,573, -2,452] |
| One inpatient ward bed | +0.02 [-0.02, +0.05] | +0.00 [-0.46, +0.46] | -0.16 [-0.71, +0.40] | -0.01 [-0.05, +0.03] | -1.48 [-3.78, +0.81] | +0.001 [-0.003, +0.005] | -0.000 [-0.008, +0.008] | +0 [+0, +0] | +1,714 [+1,714, +1,714] | +1,249 [+449, +2,049] | -576 [-1,366, +214] |
| A block of 8 inpatient ward beds | +0.00 [-0.06, +0.06] | +0.16 [-0.40, +0.71] | -0.31 [-0.95, +0.32] | +0.02 [-0.04, +0.07] | -5.70 [-15.42, +4.02] | -0.001 [-0.005, +0.003] | +0.007 [-0.004, +0.019] | +0 [+0, +0] | +13,710 [+13,710, +13,710] | +7,403 [+5,396, +9,409] | -7,098 [-9,123, -5,073] |
| One CT scanner | +0.01 [-0.00, +0.02] | +0.16 [-0.16, +0.47] | -1.09 [-1.85, -0.34] | +0.00 [-0.01, +0.02] | +0.00 [-0.02, +0.02] | +0.000 [-0.003, +0.003] | -0.000 [-0.005, +0.005] | +902 [+902, +902] | +1,351 [+1,351, +1,351] | +82 [-79, +243] | -1,267 [-1,418, -1,116] |
| One X-ray room | -0.00 [-0.01, +0.01] | +0.00 [+0.00, +0.00] | +0.00 [+0.00, +0.00] | -0.00 [-0.01, +0.01] | -0.01 [-0.04, +0.01] | -0.001 [-0.003, +0.001] | -0.001 [-0.003, +0.001] | +0 [+0, +0] | +100 [+100, +100] | +44 [-16, +104] | -69 [-115, -23] |
| Second-CT staffing, an 8-hour block | +0.01 [-0.00, +0.02] | +0.00 [+0.00, +0.00] | -0.16 [-0.47, +0.16] | -0.00 [-0.01, +0.00] | -0.01 [-0.03, +0.01] | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | +451 [+451, +451] | +451 [+451, +451] | +6 [+1, +11] | -443 [-449, -438] |

### When each unit matters (simulated)

Value of the unit to the objective ($-equivalent per hour, mean over seeds; for rows marked *adding*, the value of adding it) by block of the day, the same per day over the three thirds of the month, and how busy the resource is at baseline. Hour-by-hour and day-by-day series with intervals, for margin and every other profile metric too, are in the JSON (`by_hour`, `by_day`).

| Resource | 07-15 $-eq/h | 15-23 | 23-07 | Days 1-10 $-eq/day | Days 11-20 | Days 21-30 | Utilisation | Share of hours every unit is in use |
|---|---|---|---|---|---|---|---|---|
| One provider, day shift | +567 | +619 | +664 | +15,053 | +12,942 | +16,386 | 63% | 4% |
| One provider, evening shift | +217 | +1,426 | +2,000 | +35,258 | +23,739 | +28,425 | 77% | 10% |
| One provider, night shift | +724 | +443 | +3,273 | +32,717 | +37,760 | +36,099 | 84% | 25% |
| One nurse, day shift | -65 | +0 | +0 | -526 | -518 | -514 | 22% | 0% |
| One nurse, evening shift | +0 | -65 | +0 | -514 | -518 | -524 | 31% | 0% |
| One nurse, night shift | +27 | +9 | +328 | +3,626 | +2,943 | +2,175 | 42% | 0% |
| One triage station (room + nurse) | +4,719 | +5,388 | +51 | +83,647 | +72,641 | +87,493 | 32% | 10% |
| One resuscitation bay | -103 | -108 | -106 | -2,535 | -2,531 | -2,547 | 22% | 0% |
| One main treatment bay | -63 | -55 | +35 | -1,412 | +320 | -899 | 30% | 0% |
| A block of 4 main treatment bays | -155 | -15 | -155 | -3,127 | -3,214 | -1,460 | 30% | 0% |
| One fast-track space | -417 | -146 | -28 | -6,750 | -5,872 | -1,577 | 58% | 12% |
| One pediatric ED bay | -35 | -39 | +18 | -1,020 | +293 | -614 | 57% | 2% |
| One hallway stretcher space (adding) | -12 | +71 | -67 | +267 | -62 | -407 | n/a | n/a |
| Hallway overflow, 8 spaces (adding) | -88 | +144 | -188 | +450 | -1,921 | -1,700 | n/a | n/a |
| Fast track (the whole stream) | -4,151 | -2,632 | +109 | -54,728 | -51,913 | -53,579 | 58% | 12% |
| One inpatient ward bed | +1,014 | +698 | +1,161 | +3,787 | +17,398 | +47,796 | 84% | 3% |
| A block of 8 inpatient ward beds | +8,498 | +11,078 | +12,626 | +23,667 | +159,260 | +589,953 | 84% | 3% |
| One CT scanner | -358 | -117 | +720 | +1,007 | +5,993 | -1,141 | 39% | 27% |
| One X-ray room | -111 | -139 | +647 | +443 | +6,572 | +2,511 | 23% | 9% |
| Second-CT staffing, an 8-hour block | +2 | +110 | +235 | +2,960 | -211 | +5,580 | 41% | 23% |

## flu_surge (simulated)

Baseline: mean door-to-provider wait 24.0 min, p95 73 min, median ED stay 234 min, 3.9 walk-outs/day, boarding 98 patient-hours/day, labour $103,770/day, margin $491,450/day.

### Ranked by net value per dollar of the existing unit (simulated)

| # | Resource | Costs $/day | Value to the objective, $-equivalent/day [95% CI] | per $ | Margin alone, net $/day [95% CI] | Patient-flow index if removed, % [95% CI] (+ = worse) | Removing it: biggest effects | Verdict if removed | Next unit: value to the objective, $-eq/day [95% CI] | Next unit: margin alone $/day | Flow index if added, % | Verdict if added |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | One provider, night shift | 926 | +242,210 [+143,950, +340,470] | +261.6 | -1,991 [-3,700, -283] | +10.46 [+7.10, +13.82] | 95th-percentile door-to-provider wait +16.1 min; ESI 1-2 patients waiting +1.34 patient-hours/day; Mean door-to-provider wait +4.05 min | needed | +191,900 [+103,560, +280,230] | -1,374 [-3,905, +1,158] | -8.04 [-11.20, -4.87] | worth adding |
| 2 | One provider, evening shift | 926 | +212,610 [+113,080, +312,140] | +229.6 | -2,774 [-4,330, -1,217] | +9.77 [+6.42, +13.12] | 95th-percentile door-to-provider wait +17.8 min; Mean door-to-provider wait +4.29 min; Left without being seen +0.67 patients/day | needed | +148,260 [+78,909, +217,600] | -1,081 [-3,054, +893] | -6.33 [-8.72, -3.93] | worth adding |
| 3 | A block of 8 inpatient ward beds | 13,710 | +2,505,200 [+1,086,200, +3,924,300] | +182.7 | +24,817 [+10,102, +39,532] | +81.26 [+36.06, +126.46] | 95th-percentile door-to-provider wait +118.9 min; Boarding +148.4 patient-hours/day; Left without being seen +4.56 patients/day | needed | +680,230 [+125,230, +1,235,200] | +5,185 [-3,075, +13,444] | -23.04 [-41.07, -5.01] | worth adding |
| 4 | One provider, day shift | 926 | +167,740 [+73,700, +261,780] | +181.2 | -2,449 [-4,453, -445] | +7.40 [+4.13, +10.68] | 95th-percentile door-to-provider wait +11.7 min; Mean door-to-provider wait +3.01 min; Left without being seen +0.47 patients/day | needed | +149,900 [+47,801, +252,010] | -1,489 [-3,696, +719] | -6.30 [-9.96, -2.65] | worth adding |
| 5 | One inpatient ward bed | 1,714 | +204,500 [+20,644, +388,360] | +119.3 | +2,494 [+138, +4,850] | +7.01 [+1.07, +12.95] | Boarding +13.6 patient-hours/day; ESI 1-2 patients waiting +0.46 patient-hours/day; Median ED length of stay +1.41 min | needed | +168,590 [+21,284, +315,900] | +1,868 [-533, +4,270] | -5.49 [-10.14, -0.84] | worth adding |
| 6 | One nurse, night shift | 533 | +45,265 [-9,592, +100,120] | +85.0 | -517 [-1,103, +68] | +1.57 [-0.24, +3.39] | ESI 1-2 patients waiting +0.45 patient-hours/day; Mean door-to-provider wait +0.95 min; Left without being seen +0.15 patients/day | trade-off | -7,393 [-47,059, +32,272] | -671 [-1,626, +285] | +0.11 [-1.00, +1.22] | not shown either way |
| 7 | Fast track (the whole stream) | 5,568 | +459,090 [+116,560, +801,610] | +82.5 | -6,971 [-8,983, -4,960] | +12.33 [+5.15, +19.50] | Left without being seen +1.26 patients/day; Mean door-to-provider wait +3.86 min; ESI 1-2 patients waiting -0.44 patient-hours/day | needed | n/a |  |  |  |
| 8 | One CT scanner | 1,351 | +92,781 [+26,222, +159,340] | +68.7 | -866 [-2,366, +635] | +5.37 [+2.81, +7.93] | 95th-percentile door-to-provider wait +7.03 min; Left without being seen +0.36 patients/day; Mean door-to-provider wait +1.98 min | needed | -32,482 [-108,440, +43,473] | -2,014 [-2,991, -1,038] | +1.01 [-1.45, +3.47] | not shown either way |
| 9 | One triage station (room + nurse) | 1,996 | +132,680 [-16,278, +281,630] | +66.5 | -670 [-2,922, +1,583] | +5.80 [+0.55, +11.05] | ESI 1-2 patients waiting +1.86 patient-hours/day; Left without being seen +0.45 patients/day; Mean door-to-provider wait +2.68 min | trade-off | -20,033 [-173,420, +133,350] | -2,046 [-4,094, +3] | +0.32 [-5.06, +5.71] | not shown either way |
| 10 | Second-CT staffing, an 8-hour block | 451 | +27,668 [-88,461, +143,800] | +61.3 | -665 [-2,498, +1,167] | +1.73 [-2.37, +5.82] | Median ED length of stay +6.09 min | trade-off | -23,431 [-60,597, +13,736] | -814 [-1,461, -168] | +0.72 [-0.41, +1.85] | not shown either way |
| 11 | One X-ray room | 100 | +5,178 [-97,201, +107,560] | +51.9 | -937 [-2,436, +562] | +0.85 [-2.61, +4.32] | Median ED length of stay +6.72 min | trade-off | -44,814 [-117,110, +27,483] | -756 [-1,709, +198] | +1.38 [-0.97, +3.73] | not shown either way |
| 12 | One fast-track space | 557 | +22,439 [-17,761, +62,640] | +40.3 | -546 [-1,288, +197] | +0.60 [-0.86, +2.05] | Median ED length of stay -2.34 min | inconclusive | -14,263 [-75,482, +46,956] | -852 [-1,610, -93] | +0.75 [-1.05, +2.55] | not shown either way |
| 13 | One pediatric ED bay | 955 | +36,832 [-23,678, +97,342] | +38.6 | -670 [-1,495, +156] | +1.40 [-0.73, +3.53] | none outside the intervals | inconclusive | -8,075 [-22,371, +6,220] | -1,102 [-1,620, -584] | +0.19 [-0.34, +0.72] | not shown either way |
| 14 | One main treatment bay | 955 | +22,809 [-7,315, +52,933] | +23.9 | -922 [-1,284, -560] | +0.90 [-0.16, +1.96] | Patients treated -0.09 per day | inconclusive | -19,130 [-58,240, +19,980] | -1,172 [-1,736, -608] | +0.58 [-0.69, +1.84] | not shown either way |
| 15 | A block of 4 main treatment bays | 3,821 | +48,616 [-37,443, +134,680] | +12.7 | -3,435 [-4,555, -2,316] | +2.54 [-0.62, +5.70] | none outside the intervals | inconclusive | +12,796 [-41,085, +66,678] | -3,392 [-4,154, -2,630] | -0.80 [-2.56, +0.96] | not shown either way |
| 16 | One nurse, day shift | 533 | +6,245 [-7,742, +20,232] | +11.7 | -645 [-983, -307] | +0.12 [-0.29, +0.54] | none outside the intervals | slack | -2,192 [-5,478, +1,093] | -401 [-558, -245] | +0.06 [-0.05, +0.18] | not shown either way |
| 17 | One resuscitation bay | 2,546 | +25,254 [-15,088, +65,596] | +9.9 | -2,152 [-2,689, -1,615] | +0.93 [-0.40, +2.27] | none outside the intervals | inconclusive | -30,618 [-81,339, +20,103] | -2,932 [-3,610, -2,253] | +0.83 [-0.62, +2.27] | not shown either way |
| 18 | One nurse, evening shift | 533 | -2,501 [-9,368, +4,366] | -4.7 | -678 [-1,014, -341] | -0.11 [-0.42, +0.20] | none outside the intervals | slack | -2,991 [-6,822, +840] | -413 [-618, -208] | +0.09 [-0.04, +0.22] | not shown either way |
| 19 | Hallway overflow, 8 spaces | 2,554 | n/a (not in use at baseline) |  |  |  |  |  | -33,292 [-140,580, +73,996] | -2,682 [-3,827, -1,538] | +0.60 [-2.64, +3.84] | not shown either way |
| 20 | One hallway stretcher space | 319 | n/a (not in use at baseline) |  |  |  |  |  | -14,366 [-43,530, +14,798] | -451 [-916, +14] | +0.35 [-0.51, +1.21] | not shown either way |

### Binding and slack (simulated)

- **Add first: One provider, night shift.** Value to the objective +191,900 [+103,560, +280,230] $-equivalent/day (reward +0.3159 [+0.1705, +0.4613] per hour); margin alone -1,374 [-3,905, +1,158] $/day.
- Also worth adding (reward interval above zero): One inpatient ward bed (+0.2775 [+0.0350, +0.5200]); One provider, day shift (+0.2467 [+0.0787, +0.4148]); One provider, evening shift (+0.2440 [+0.1299, +0.3582]); A block of 8 inpatient ward beds (+1.1197 [+0.2061, +2.0332]).
- Needed (removing one measurably hurts flow or safety and lowers the reward): A block of 8 inpatient ward beds (-4.1237 [-6.4595, -1.7879]); Fast track (the whole stream) (-0.7557 [-1.3195, -0.1919]); One provider, night shift (-0.3987 [-0.5604, -0.2369]); One provider, evening shift (-0.3500 [-0.5138, -0.1861]); One inpatient ward bed (-0.3366 [-0.6393, -0.0340]); One provider, day shift (-0.2761 [-0.4309, -0.1213]); One CT scanner (-0.1527 [-0.2623, -0.0432]).
- Slack (removing one saves money and no flow or safety metric leaves its equivalence margin): One nurse, evening shift (margin +678 [+341, +1,014] $/day); One nurse, day shift (margin +645 [+307, +983] $/day).
- Not shown either way: One nurse, night shift (trade-off); One triage station (room + nurse) (trade-off); One resuscitation bay (inconclusive); One main treatment bay (inconclusive); A block of 4 main treatment bays (inconclusive); One fast-track space (inconclusive); One pediatric ED bay (inconclusive); One X-ray room (trade-off); Second-CT staffing, an 8-hour block (trade-off).
- Patient flow only (no money): the single additions that improve the flow index most are A block of 8 inpatient ward beds (-23.04 [-41.07, -5.01]%); One provider, night shift (-8.04 [-11.20, -4.87]%); One provider, evening shift (-6.33 [-8.72, -3.93]%); One provider, day shift (-6.30 [-9.96, -2.65]%); One inpatient ward bed (-5.49 [-10.14, -0.84]%).
- Patient flow only: the single removals that hurt it most are A block of 8 inpatient ward beds (+81.26 [+36.06, +126.46]%); Fast track (the whole stream) (+12.33 [+5.15, +19.50]%); One provider, night shift (+10.46 [+7.10, +13.82]%); One provider, evening shift (+9.77 [+6.42, +13.12]%); One provider, day shift (+7.40 [+4.13, +10.68]%); One inpatient ward bed (+7.01 [+1.07, +12.95]%).
- **Read the money columns with care.** For One provider, evening shift (revenue +1,880 [+303, +3,457] $/day, admissions +0.032 [-0.005, +0.070]/day) the model's revenue goes UP when the unit is removed although patient flow gets measurably worse: with slower care more patients end up admitted, and the model books inpatient revenue per admission with no penalty for avoidable admissions. That is a property of the cost model, not evidence that the unit loses money; the reward and flow columns are the ones to act on for these rows.

Rule: worth adding: the balanced reward rises with a 95% interval above zero. needed: removing it makes a flow or safety metric worse (interval above zero and not inside the equivalence margin) and lowers the balanced reward (interval below zero). slack: removing it saves money (interval above zero), every flow and safety metric's interval stays inside its equivalence margin, i.e. it is shown to get at most negligibly worse (margin: 2% of baseline for waits, stay, walk-outs and boarding; 5% for rare safety events), and the balanced reward does not measurably fall. Anything else is not shown either way.

### Effect of removing one unit on each headline metric (simulated; paired difference, 95% CI)

| Resource | Mean door-to-provider wait (min) | 95th-percentile door-to-provider wait (min) | Median ED length of stay (min) | Left without being seen (patients/day) | Boarding (patient-hours/day) | Deaths (per day) | Adverse events (per day) | Labour cost ($/day) | Operating cost (labour + fixed) ($/day) | Revenue ($/day) | Margin ($/day) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| One provider, day shift | +3.01 [+2.02, +4.00] | +11.72 [+6.25, +17.19] | +10.47 [+9.07, +11.87] | +0.47 [+0.28, +0.67] | -0.56 [-7.55, +6.43] | -0.002 [-0.010, +0.006] | +0.052 [+0.033, +0.072] | -889 [-901, -878] | -889 [-901, -878] | +1,675 [-350, +3,700] | +2,449 [+445, +4,453] |
| One provider, evening shift | +4.29 [+2.97, +5.61] | +17.81 [+13.05, +22.57] | +12.66 [+11.14, +14.17] | +0.67 [+0.44, +0.90] | -3.17 [-7.77, +1.44] | +0.003 [-0.006, +0.012] | +0.047 [+0.026, +0.068] | -897 [-906, -888] | -897 [-906, -888] | +1,880 [+303, +3,457] | +2,774 [+1,217, +4,330] |
| One provider, night shift | +4.05 [+2.78, +5.32] | +16.09 [+10.06, +22.13] | +12.97 [+11.61, +14.33] | +0.63 [+0.39, +0.87] | +2.65 [-1.66, +6.97] | +0.002 [-0.005, +0.009] | +0.065 [+0.039, +0.091] | -892 [-902, -882] | -892 [-902, -882] | +1,216 [-524, +2,957] | +1,991 [+283, +3,700] |
| One nurse, day shift | +0.09 [-0.12, +0.31] | -1.41 [-3.41, +0.60] | +0.00 [+0.00, +0.00] | +0.00 [-0.02, +0.03] | -0.08 [-0.58, +0.43] | -0.001 [-0.003, +0.001] | +0.006 [-0.000, +0.013] | -514 [-521, -508] | -514 [-521, -508] | +131 [-208, +469] | +645 [+307, +983] |
| One nurse, evening shift | -0.03 [-0.14, +0.07] | -0.78 [-2.37, +0.81] | +0.00 [+0.00, +0.00] | -0.01 [-0.03, +0.02] | -0.20 [-0.57, +0.18] | -0.001 [-0.003, +0.001] | +0.001 [-0.001, +0.003] | -512 [-518, -506] | -512 [-518, -506] | +166 [-172, +505] | +678 [+341, +1,014] |
| One nurse, night shift | +0.95 [+0.19, +1.71] | +4.06 [-0.53, +8.65] | +0.00 [-0.46, +0.46] | +0.15 [+0.03, +0.27] | -1.83 [-4.88, +1.22] | +0.002 [-0.004, +0.008] | +0.016 [+0.003, +0.028] | -517 [-523, -511] | -517 [-523, -511] | -48 [-647, +552] | +517 [-68, +1,103] |
| One triage station (room + nurse) | +2.68 [+1.14, +4.22] | +7.19 [-2.08, +16.46] | +2.03 [+0.83, +3.23] | +0.45 [+0.16, +0.74] | -0.49 [-9.70, +8.72] | -0.001 [-0.015, +0.012] | +0.013 [-0.007, +0.032] | -1,598 [-1,598, -1,598] | -1,996 [-1,996, -1,996] | -1,509 [-3,799, +781] | +670 [-1,583, +2,922] |
| One resuscitation bay | +0.44 [-0.16, +1.04] | +3.12 [-1.72, +7.97] | +0.31 [-0.13, +0.76] | +0.06 [-0.03, +0.15] | +0.13 [-1.01, +1.26] | +0.001 [-0.001, +0.003] | +0.014 [-0.001, +0.028] | +0 [+0, +0] | -2,546 [-2,546, -2,546] | -399 [-942, +145] | +2,152 [+1,615, +2,689] |
| One main treatment bay | +0.46 [-0.04, +0.96] | +2.19 [-0.74, +5.12] | -0.16 [-0.71, +0.40] | +0.07 [-0.00, +0.15] | -0.19 [-0.93, +0.55] | -0.003 [-0.007, +0.000] | -0.002 [-0.011, +0.007] | +0 [+0, +0] | -955 [-955, -955] | -38 [-406, +330] | +922 [+560, +1,284] |
| A block of 4 main treatment bays | +1.25 [-0.01, +2.51] | +5.47 [-0.54, +11.48] | +0.94 [-0.31, +2.19] | +0.19 [-0.03, +0.42] | -0.56 [-4.43, +3.30] | -0.001 [-0.006, +0.004] | -0.001 [-0.013, +0.011] | +0 [+0, +0] | -3,821 [-3,821, -3,821] | -420 [-1,568, +727] | +3,435 [+2,316, +4,555] |
| One fast-track space | +0.26 [-0.17, +0.69] | +1.56 [-1.88, +5.00] | -2.34 [-3.37, -1.32] | +0.08 [-0.02, +0.18] | +0.80 [-1.37, +2.97] | -0.005 [-0.012, +0.002] | -0.003 [-0.018, +0.012] | +0 [+0, +0] | -557 [-557, -557] | -41 [-805, +723] | +546 [-197, +1,288] |
| One pediatric ED bay | +0.45 [-0.18, +1.08] | +2.34 [-1.88, +6.56] | +0.16 [-0.40, +0.71] | +0.09 [-0.05, +0.23] | +1.76 [-1.29, +4.81] | -0.002 [-0.005, +0.001] | +0.004 [-0.008, +0.017] | +0 [+0, +0] | -955 [-955, -955] | -281 [-1,122, +560] | +670 [-156, +1,495] |
| Fast track (the whole stream) | +3.86 [+1.38, +6.35] | +12.50 [-0.43, +25.43] | -0.78 [-2.16, +0.60] | +1.26 [+0.39, +2.12] | +5.97 [-3.50, +15.44] | -0.009 [-0.018, -0.001] | +0.009 [-0.016, +0.035] | +0 [+0, +0] | -5,568 [-5,568, -5,568] | +1,604 [-471, +3,679] | +6,971 [+4,960, +8,983] |
| One inpatient ward bed | +1.65 [-0.30, +3.61] | +9.53 [-1.66, +20.72] | +1.41 [+0.01, +2.80] | +0.39 [-0.06, +0.84] | +13.62 [+5.96, +21.28] | -0.001 [-0.009, +0.007] | +0.017 [-0.013, +0.046] | +0 [+0, +0] | -1,714 [-1,714, -1,714] | -4,398 [-6,845, -1,951] | -2,494 [-4,850, -138] |
| A block of 8 inpatient ward beds | +21.11 [+5.98, +36.23] | +118.91 [+39.66, +198.15] | +10.94 [+4.09, +17.78] | +4.56 [+1.41, +7.71] | +148.39 [+84.23, +212.55] | +0.050 [+0.015, +0.085] | +0.186 [+0.054, +0.319] | +0 [+0, +0] | -13,710 [-13,710, -13,710] | -40,352 [-55,710, -24,994] | -24,817 [-39,532, -10,102] |
| One CT scanner | +1.98 [+1.10, +2.85] | +7.03 [+3.23, +10.83] | +13.59 [+11.81, +15.38] | +0.36 [+0.15, +0.56] | -3.22 [-7.78, +1.35] | +0.001 [-0.005, +0.008] | +0.013 [-0.001, +0.026] | -902 [-902, -902] | -1,351 [-1,351, -1,351] | -599 [-2,119, +920] | +866 [-635, +2,366] |
| One X-ray room | +0.41 [-0.55, +1.37] | +1.88 [-5.43, +9.18] | +6.72 [+5.85, +7.59] | +0.08 [-0.12, +0.28] | -4.53 [-11.55, +2.49] | -0.008 [-0.019, +0.003] | +0.004 [-0.014, +0.022] | +0 [+0, +0] | -100 [-100, -100] | +802 [-723, +2,328] | +937 [-562, +2,436] |
| Second-CT staffing, an 8-hour block | +0.52 [-0.72, +1.76] | +2.81 [-5.17, +10.79] | +6.09 [+4.74, +7.45] | +0.10 [-0.14, +0.34] | -1.08 [-7.71, +5.54] | -0.006 [-0.016, +0.003] | +0.001 [-0.019, +0.021] | -451 [-451, -451] | -451 [-451, -451] | +188 [-1,665, +2,041] | +665 [-1,167, +2,498] |

### Effect of adding one unit (simulated; paired difference, 95% CI)

| Resource | Mean door-to-provider wait (min) | 95th-percentile door-to-provider wait (min) | Median ED length of stay (min) | Left without being seen (patients/day) | Boarding (patient-hours/day) | Deaths (per day) | Adverse events (per day) | Labour cost ($/day) | Operating cost (labour + fixed) ($/day) | Revenue ($/day) | Margin ($/day) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| One provider, day shift | -1.91 [-2.94, -0.88] | -7.81 [-14.09, -1.54] | -6.88 [-8.06, -5.69] | -0.34 [-0.55, -0.13] | -6.43 [-14.50, +1.64] | -0.015 [-0.025, -0.004] | -0.044 [-0.064, -0.024] | +890 [+878, +902] | +890 [+878, +902] | -723 [-2,958, +1,512] | -1,489 [-3,696, +719] |
| One provider, evening shift | -2.02 [-2.70, -1.35] | -8.12 [-12.16, -4.09] | -8.75 [-9.77, -7.73] | -0.37 [-0.47, -0.27] | -3.91 [-10.43, +2.61] | -0.006 [-0.012, -0.001] | -0.053 [-0.075, -0.032] | +898 [+887, +909] | +898 [+887, +909] | -295 [-2,287, +1,697] | -1,081 [-3,054, +893] |
| One provider, night shift | -2.32 [-3.27, -1.37] | -9.84 [-16.01, -3.68] | -10.62 [-11.81, -9.44] | -0.38 [-0.56, -0.19] | -9.08 [-16.95, -1.21] | -0.017 [-0.027, -0.007] | -0.065 [-0.085, -0.044] | +895 [+885, +905] | +895 [+885, +905] | -724 [-3,277, +1,829] | -1,374 [-3,905, +1,158] |
| One nurse, day shift | -0.00 [-0.05, +0.04] | -0.47 [-1.42, +0.49] | +0.00 [+0.00, +0.00] | +0.01 [-0.00, +0.02] | +0.14 [-0.21, +0.49] | +0.000 [+0.000, +0.000] | +0.003 [-0.002, +0.008] | +513 [+505, +520] | +513 [+505, +520] | +110 [-47, +267] | -401 [-558, -245] |
| One nurse, evening shift | +0.01 [-0.02, +0.04] | -0.16 [-0.47, +0.16] | +0.00 [+0.00, +0.00] | +0.01 [-0.01, +0.02] | +0.25 [-0.21, +0.70] | +0.000 [+0.000, +0.000] | +0.002 [-0.002, +0.006] | +513 [+506, +519] | +513 [+506, +519] | +99 [-104, +301] | -413 [-618, -208] |
| One nurse, night shift | -0.16 [-0.53, +0.21] | +1.88 [-4.64, +8.39] | +0.16 [-0.40, +0.71] | -0.03 [-0.10, +0.04] | +2.14 [-0.55, +4.84] | -0.000 [-0.003, +0.003] | +0.000 [-0.017, +0.017] | +519 [+514, +524] | +519 [+514, +524] | -126 [-1,081, +830] | -671 [-1,626, +285] |
| One triage station (room + nurse) | +0.12 [-1.56, +1.80] | +1.25 [-8.82, +11.32] | +0.00 [-1.21, +1.21] | +0.04 [-0.27, +0.35] | -0.13 [-8.26, +8.00] | -0.004 [-0.015, +0.006] | +0.006 [-0.020, +0.032] | +1,598 [+1,598, +1,598] | +1,996 [+1,996, +1,996] | -49 [-2,126, +2,029] | -2,046 [-4,094, +3] |
| One resuscitation bay | +0.42 [-0.20, +1.04] | +2.19 [-1.67, +6.04] | -0.16 [-0.71, +0.40] | +0.04 [-0.05, +0.14] | +0.50 [-0.91, +1.92] | -0.000 [-0.003, +0.003] | +0.007 [-0.006, +0.021] | +0 [+0, +0] | +2,546 [+2,546, +2,546] | -396 [-1,084, +291] | -2,932 [-3,610, -2,253] |
| One main treatment bay | +0.15 [-0.30, +0.59] | +1.25 [-3.35, +5.85] | +0.31 [-0.13, +0.76] | +0.01 [-0.07, +0.09] | +1.45 [-0.40, +3.30] | -0.002 [-0.006, +0.002] | +0.005 [-0.003, +0.014] | +0 [+0, +0] | +955 [+955, +955] | -207 [-787, +373] | -1,172 [-1,736, -608] |
| A block of 4 main treatment bays | -0.40 [-0.99, +0.19] | -2.50 [-6.41, +1.41] | -0.31 [-0.95, +0.32] | -0.08 [-0.18, +0.01] | +0.77 [-2.99, +4.53] | -0.003 [-0.008, +0.002] | -0.001 [-0.010, +0.008] | +0 [+0, +0] | +3,821 [+3,821, +3,821] | +445 [-331, +1,220] | -3,392 [-4,154, -2,630] |
| One fast-track space | +0.11 [-0.43, +0.65] | +0.00 [-2.67, +2.67] | +3.28 [+2.41, +4.15] | +0.05 [-0.09, +0.19] | -0.36 [-2.91, +2.19] | -0.002 [-0.005, +0.001] | +0.006 [-0.007, +0.020] | +0 [+0, +0] | +557 [+557, +557] | -320 [-1,100, +459] | -852 [-1,610, -93] |
| One pediatric ED bay | +0.00 [-0.16, +0.17] | -0.47 [-1.79, +0.86] | +0.00 [+0.00, +0.00] | -0.01 [-0.04, +0.02] | +1.25 [-0.37, +2.87] | -0.001 [-0.005, +0.003] | +0.002 [-0.007, +0.011] | +0 [+0, +0] | +955 [+955, +955] | -136 [-668, +396] | -1,102 [-1,620, -584] |
| One hallway stretcher space | +0.03 [-0.23, +0.29] | -0.47 [-1.87, +0.93] | +0.00 [+0.00, +0.00] | +0.00 [-0.06, +0.06] | +1.56 [-0.15, +3.28] | -0.001 [-0.007, +0.005] | +0.003 [-0.007, +0.013] | +0 [+0, +0] | +319 [+319, +319] | -120 [-595, +356] | -451 [-916, +14] |
| Hallway overflow, 8 spaces | -0.02 [-0.97, +0.93] | +2.50 [-8.59, +13.59] | +0.16 [-0.40, +0.71] | -0.06 [-0.21, +0.10] | +4.40 [-3.21, +12.02] | -0.000 [-0.006, +0.006] | +0.021 [-0.007, +0.049] | +0 [+0, +0] | +2,554 [+2,554, +2,554] | -126 [-1,291, +1,040] | -2,682 [-3,827, -1,538] |
| One inpatient ward bed | -1.09 [-2.31, +0.13] | -7.50 [-15.82, +0.82] | -0.47 [-1.62, +0.69] | -0.27 [-0.59, +0.05] | -13.26 [-22.75, -3.77] | -0.014 [-0.025, -0.002] | -0.024 [-0.052, +0.004] | +0 [+0, +0] | +1,714 [+1,714, +1,714] | +3,758 [+1,294, +6,223] | +1,868 [-533, +4,270] |
| A block of 8 inpatient ward beds | -3.94 [-8.49, +0.61] | -22.19 [-48.39, +4.02] | -3.91 [-6.90, -0.91] | -0.82 [-1.92, +0.28] | -66.25 [-112.03, -20.45] | -0.032 [-0.060, -0.004] | -0.082 [-0.142, -0.023] | +0 [+0, +0] | +13,710 [+13,710, +13,710] | +19,900 [+11,488, +28,311] | +5,185 [-3,075, +13,444] |
| One CT scanner | +0.36 [-0.31, +1.03] | +1.41 [-3.15, +5.97] | -1.56 [-2.63, -0.49] | +0.07 [-0.11, +0.24] | +2.00 [-1.38, +5.37] | -0.001 [-0.003, +0.001] | +0.009 [-0.008, +0.027] | +902 [+902, +902] | +1,351 [+1,351, +1,351] | -701 [-1,702, +301] | -2,014 [-2,991, -1,038] |
| One X-ray room | +0.41 [-0.40, +1.22] | +2.66 [-2.86, +8.17] | +0.00 [-0.46, +0.46] | +0.08 [-0.07, +0.23] | +2.37 [-0.94, +5.69] | -0.003 [-0.008, +0.002] | +0.008 [-0.008, +0.025] | +0 [+0, +0] | +100 [+100, +100] | -643 [-1,611, +325] | -756 [-1,709, +198] |
| Second-CT staffing, an 8-hour block | +0.32 [-0.13, +0.76] | +2.34 [-1.62, +6.31] | -0.16 [-0.47, +0.16] | +0.04 [-0.05, +0.13] | +0.77 [-0.10, +1.64] | -0.002 [-0.005, +0.001] | +0.003 [-0.008, +0.014] | +451 [+451, +451] | +451 [+451, +451] | -361 [-1,017, +295] | -814 [-1,461, -168] |

### When each unit matters (simulated)

Value of the unit to the objective ($-equivalent per hour, mean over seeds; for rows marked *adding*, the value of adding it) by block of the day, the same per day over the three thirds of the month, and how busy the resource is at baseline. Hour-by-hour and day-by-day series with intervals, for margin and every other profile metric too, are in the JSON (`by_hour`, `by_day`).

| Resource | 07-15 $-eq/h | 15-23 | 23-07 | Days 1-10 $-eq/day | Days 11-20 | Days 21-30 | Utilisation | Share of hours every unit is in use |
|---|---|---|---|---|---|---|---|---|
| One provider, day shift | +4,743 | +8,482 | +7,741 | +121,034 | +153,095 | +229,085 | 74% | 14% |
| One provider, evening shift | +2,689 | +8,673 | +15,214 | +151,984 | +225,106 | +260,714 | 86% | 31% |
| One provider, night shift | +6,225 | +8,294 | +15,757 | +131,396 | +235,563 | +359,668 | 90% | 34% |
| One nurse, day shift | +251 | +375 | +154 | -476 | +2,214 | +16,995 | 29% | 0% |
| One nurse, evening shift | +33 | -168 | -177 | -497 | +2,489 | -9,496 | 40% | 0% |
| One nurse, night shift | +1,058 | +468 | +4,132 | +16,798 | +59,335 | +59,656 | 56% | 6% |
| One triage station (room + nurse) | +8,284 | +7,958 | +342 | +114,230 | +97,402 | +186,388 | 35% | 13% |
| One resuscitation bay | +1,005 | +1,066 | +1,086 | -1,112 | +13,618 | +63,259 | 28% | 2% |
| One main treatment bay | +968 | +1,246 | +637 | +1,931 | +30,123 | +36,369 | 43% | 0% |
| A block of 4 main treatment bays | +1,092 | +3,382 | +1,603 | +1,814 | +68,384 | +75,650 | 43% | 0% |
| One fast-track space | +700 | +1,132 | +972 | -1,353 | +21,293 | +47,371 | 63% | 17% |
| One pediatric ED bay | +1,130 | +2,136 | +1,338 | +4,106 | +21,807 | +84,571 | 69% | 8% |
| One hallway stretcher space (adding) | -798 | +60 | -1,058 | +2,194 | -24,616 | -20,674 | n/a | n/a |
| Hallway overflow, 8 spaces (adding) | -2,530 | +1,104 | -2,735 | +12,855 | -1,617 | -111,102 | n/a | n/a |
| Fast track (the whole stream) | +10,347 | +23,957 | +23,080 | +86,045 | +330,374 | +960,861 | 63% | 17% |
| One inpatient ward bed | +7,190 | +9,206 | +9,167 | +4,161 | +150,812 | +458,535 | 91% | 20% |
| A block of 8 inpatient ward beds | +93,092 | +111,834 | +108,227 | +84,341 | +1,474,553 | +5,956,641 | 91% | 20% |
| One CT scanner | +1,044 | +2,815 | +7,738 | +19,283 | +168,048 | +91,024 | 42% | 29% |
| One X-ray room | -128 | -276 | +1,051 | +11,591 | +14,974 | -11,030 | 25% | 10% |
| Second-CT staffing, an 8-hour block | +1,375 | +879 | +1,205 | +1,851 | +1,977 | +79,183 | 45% | 25% |

## What cannot be told apart (identifiability)

- Providers of a role are interchangeable in the model: a named provider has the value of one provider on that shift. The model has no individual skill, speed or specialty, so no per-person differences are reported.
- A 'provider' is costed at the blended wage of the attending / resident / APP mix; the model does not move patients differently by role (except the fast-track provider's productivity).
- Bays of a class differ only by position, and the simulator walks patients between zone centroids, so every bay of a class has the same simulated value. `location` gives the per-bay distances it ignores.
- A ward bed is one bed of the pooled inpatient capacity the ED admits to (ward, step-down and ICU rooms pooled); beds are not distinguished.
- Removing a ward bed also changes the starting census (the pool starts at a fixed occupancy share), so its effect includes that.
- Staff the model holds constant (technicians, registration, pharmacist, transport, EVS, charge nurse) cannot be removed in it and have no marginal value here.
- Scanner purchase price and bay construction cost are capital, outside the daily figures.
- Nurses constrain the model only through a cap on staffed spaces per nurse and through care minutes; the nurse and provider head-counts are calibration parameters fitted to public aggregates, not the hospital's roster. 'Slack' and 'needed' describe that fitted model.
- The dollar 'value to the objective' is the reward change at the objective's own exchange rate between cost and waiting, walk-outs, safety and boarding. It moves with the weights; it is not cash. Margin alone is the cash figure, and in this cost model slower care can raise it (more admissions, each booked as revenue).

Per-bay position, geometry only (not simulated): seconds one walk in plus one leg to CT would gain or lose against the class centroid.

| Bay class | Bays | Class centroid to waiting room (m) | to CT (m) | Nearest bay (s) | Farthest bay (s) |
|---|---|---|---|---|---|
| resuscitation bay | 6 | 51.3 | 43.2 | -27 | +27 |
| main treatment bay | 68 | 75.7 | 24.8 | -43 | +87 |
| fast-track space | 10 | 24.0 | 32.1 | -4 | +16 |
| pediatric ED bay | 17 | 40.3 | 41.3 | -9 | +23 |

## Manipulations (each asserted against the counts the simulator used)

| Resource | Removed | Added | Largest change in a zone walking distance (m) |
|---|---|---|---|
| One provider, day shift | 15 -> 14 providers on the day shift | 15 -> 16 providers on the day shift | 0.00 |
| One provider, evening shift | 16 -> 15 providers on the evening shift | 16 -> 17 providers on the evening shift | 0.00 |
| One provider, night shift | 7 -> 6 providers on the night shift | 7 -> 8 providers on the night shift | 0.00 |
| One nurse, day shift | 37 -> 36 nurses on the day shift | 37 -> 38 nurses on the day shift | 0.00 |
| One nurse, evening shift | 37 -> 36 nurses on the evening shift | 37 -> 38 nurses on the evening shift | 0.00 |
| One nurse, night shift | 18 -> 17 nurses on the night shift | 18 -> 19 nurses on the night shift | 0.00 |
| One triage station (room + nurse) | 3 -> 2 staffed triage stations | 3 -> 4 staffed triage stations (a station is added to the layout) | 0.00 |
| One resuscitation bay | 6 -> 5 resuscitation bays | 6 -> 7 resuscitation bays | 0.64 |
| One main treatment bay | 68 -> 67 main treatment bays | 68 -> 69 main treatment bays | 0.15 |
| A block of 4 main treatment bays | 68 -> 64 main treatment bays | 68 -> 72 main treatment bays | 0.31 |
| One fast-track space | 10 -> 9 fast-track spaces | 10 -> 11 fast-track spaces | 0.31 |
| One pediatric ED bay | 17 -> 16 pediatric ED bays | 17 -> 18 pediatric ED bays | 0.34 |
| One hallway stretcher space | n/a | 0 -> 1 hallway spaces open round the clock | 0.00 |
| Hallway overflow, 8 spaces | n/a | 0 -> 8 hallway spaces open round the clock | 0.00 |
| Fast track (the whole stream) | fast track closed: its spaces shut, its provider rejoins the main pool | n/a | 0.00 |
| One inpatient ward bed | 168 -> 167 inpatient beds | 168 -> 169 inpatient beds | 0.00 |
| A block of 8 inpatient ward beds | 168 -> 160 inpatient beds | 168 -> 176 inpatient beds | 0.00 |
| One CT scanner | 2 -> 1 CT scanners | 2 -> 3 CT scanners | 0.00 |
| One X-ray room | 2 -> 1 X-ray rooms | 2 -> 3 X-ray rooms | 0.00 |
| Second-CT staffing, an 8-hour block | second CT staffed 07:00-15:00 instead of 07:00-23:00 | second CT staffed 00:00-00:00 instead of 07:00-23:00 | 0.00 |

Reward weights and scales, per-seed term differences (for re-scoring under any weights), per-day and per-hour profiles and utilisation by hour are in `attribution.json`. Served at `GET /api/attribution/{hospital_id}`.
