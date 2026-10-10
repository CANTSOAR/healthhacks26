# Held-out evaluation of hospital managers (all numbers SIMULATED)

Generated 2026-10-10T03:19:16-0400; simulator behaviour fingerprint `6ee020eaaf7eca57` (hash of a fixed-seed trajectory; staleness is keyed on it), file hash `8f9f6cc4b1a47804` (information only).

Managers tuned or trained against a different simulator behaviour: none.

Protocol: 32 held-out seeds (9000000..9000031) x 30 days per manager per scenario; every manager faces the same seeds (paired). Tuning and training never used seeds at or above 1,000,000. Values are mean ± 95% CI half-width over seeds.

Kinds: `fixed`, `rule_based` and `random` are baselines; `tuned_heuristic` is the rule-based manager with parameters found by evolutionary search (NOT a learned agent); `learned` is a PPO network acting greedily.

Constrained objective: cheapest subject to episode p95 wait <= 60 min (a chosen service target; see rl/reward_scales.json). `labor cost/day` is the part of cost the manager controls directly (wages, overtime, agency); fixed and per-patient costs dominate `cost/day`.

## Scenario `normal_week`

| manager | kind | wait mean (min) | wait p95 (min) | LWBS % | cost/day ($k) | labor cost/day ($k) | margin/day ($k) | deaths/10k | boarding h/day | overtime h/day | diversion h/day |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `fixed` | fixed | 23.1 ± 0.8 | 63.0 ± 3.9 | 1.42 ± 0.07 | 579.8 ± 1.6 | 77.0 ± 0.0 | 447.1 ± 10.9 | 5.4 ± 1.0 | 5.8 ± 1.0 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `rule_based` | rule_based | 18.0 ± 0.3 | 43.9 ± 1.7 | 1.13 ± 0.05 | 581.9 ± 1.5 | 80.6 ± 0.3 | 446.6 ± 11.1 | 4.9 ± 1.1 | 4.6 ± 0.2 | 0.1 ± 0.0 | 0.00 ± 0.00 |
| `random` | random | 60.8 ± 3.7 | 235.9 ± 10.5 | 3.95 ± 0.24 | 578.8 ± 1.5 | 85.5 ± 0.6 | 392.1 ± 10.6 | 10.1 ± 1.5 | 4.3 ± 0.2 | 61.9 ± 0.5 | 12.06 ± 0.15 |
| `tuned_min_cost` | tuned_heuristic | 20.8 ± 1.0 | 58.0 ± 6.7 | 1.36 ± 0.08 | 558.7 ± 1.5 | 65.9 ± 0.3 | 471.1 ± 11.3 | 5.0 ± 1.1 | 4.5 ± 0.2 | 0.1 ± 0.1 | 0.00 ± 0.00 |
| `tuned_min_wait` | tuned_heuristic | 12.6 ± 0.0 | 24.1 ± 0.7 | 0.79 ± 0.03 | 586.9 ± 1.5 | 88.6 ± 0.4 | 439.5 ± 11.2 | 4.3 ± 1.0 | 4.5 ± 0.2 | 7.5 ± 0.3 | 0.00 ± 0.00 |
| `tuned_balanced` | tuned_heuristic | 12.7 ± 0.1 | 24.8 ± 0.3 | 0.79 ± 0.03 | 579.9 ± 1.5 | 82.8 ± 0.2 | 449.1 ± 11.2 | 4.4 ± 1.0 | 4.5 ± 0.2 | 0.0 ± 0.0 | 0.00 ± 0.01 |
| `tuned_cost_p95` | tuned_heuristic | 15.3 ± 0.3 | 31.7 ± 1.0 | 0.93 ± 0.04 | 565.6 ± 1.5 | 71.5 ± 0.3 | 462.8 ± 11.3 | 5.0 ± 1.1 | 4.5 ± 0.2 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `ppo_min_cost` | learned | 20.7 ± 1.0 | 57.5 ± 6.7 | 1.34 ± 0.07 | 558.7 ± 1.5 | 65.8 ± 0.3 | 470.7 ± 11.4 | 5.0 ± 1.1 | 4.5 ± 0.2 | 0.1 ± 0.1 | 0.00 ± 0.00 |
| `ppo_min_wait` | learned | 12.6 ± 0.0 | 23.9 ± 0.7 | 0.79 ± 0.04 | 586.4 ± 1.4 | 88.5 ± 0.5 | 437.2 ± 12.7 | 4.3 ± 1.0 | 4.5 ± 0.2 | 9.3 ± 3.5 | 0.74 ± 1.45 |
| `ppo_balanced` | learned | 12.8 ± 0.1 | 25.0 ± 0.0 | 0.80 ± 0.03 | 579.7 ± 1.5 | 82.6 ± 0.2 | 448.9 ± 11.2 | 4.4 ± 1.0 | 4.5 ± 0.2 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `ppo_cost_p95` | learned | 15.4 ± 0.3 | 32.2 ± 1.0 | 0.94 ± 0.04 | 565.4 ± 1.5 | 70.9 ± 0.3 | 462.4 ± 11.3 | 5.0 ± 1.1 | 4.5 ± 0.2 | 0.0 ± 0.0 | 0.00 ± 0.00 |

Objective scores (higher is better; each column is that objective's own score):

| manager | kind | min_cost | min_wait | balanced | cost_s.t._p95_wait | p95 within threshold (share of seeds) |
|---|---|---|---|---|---|---|
| `fixed` | fixed | -1.019 ± 0.004 | -1.479 ± 0.069 | -0.295 ± 0.052 | -1.469 ± 0.248 | 0.50 |
| `rule_based` | rule_based | -1.020 ± 0.003 | -1.116 ± 0.038 | -0.053 ± 0.040 | -1.004 ± 0.003 | 1.00 |
| `random` | random | -1.029 ± 0.004 | -3.917 ± 0.255 | -2.174 ± 0.166 | -15.660 ± 0.875 | 0.00 |
| `tuned_min_cost` | tuned_heuristic | -0.982 ± 0.004 | -1.334 ± 0.083 | -0.156 ± 0.060 | -1.498 ± 0.393 | 0.75 |
| `tuned_min_wait` | tuned_heuristic | -1.025 ± 0.004 | -0.725 ± 0.022 | 0.163 ± 0.032 | -1.012 ± 0.003 | 1.00 |
| `tuned_balanced` | tuned_heuristic | -1.014 ± 0.004 | -0.733 ± 0.024 | 0.204 ± 0.033 | -1.000 ± 0.003 | 1.00 |
| `tuned_cost_p95` | tuned_heuristic | -0.992 ± 0.003 | -0.925 ± 0.032 | 0.096 ± 0.037 | -0.976 ± 0.003 | 1.00 |
| `ppo_min_cost` | learned | -0.982 ± 0.004 | -1.327 ± 0.080 | -0.151 ± 0.058 | -1.485 ± 0.390 | 0.75 |
| `ppo_min_wait` | learned | -1.024 ± 0.003 | -0.722 ± 0.020 | 0.154 ± 0.043 | -1.012 ± 0.002 | 1.00 |
| `ppo_balanced` | learned | -1.013 ± 0.004 | -0.741 ± 0.024 | 0.199 ± 0.034 | -1.000 ± 0.003 | 1.00 |
| `ppo_cost_p95` | learned | -0.992 ± 0.003 | -0.931 ± 0.033 | 0.090 ± 0.037 | -0.975 ± 0.003 | 1.00 |

## Scenario `flu_surge`

| manager | kind | wait mean (min) | wait p95 (min) | LWBS % | cost/day ($k) | labor cost/day ($k) | margin/day ($k) | deaths/10k | boarding h/day | overtime h/day | diversion h/day |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `fixed` | fixed | 38.5 ± 3.9 | 149.1 ± 21.8 | 2.53 ± 0.36 | 587.5 ± 1.6 | 76.3 ± 0.1 | 505.1 ± 13.4 | 7.0 ± 1.2 | 81.3 ± 48.1 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `rule_based` | rule_based | 22.4 ± 0.7 | 65.5 ± 4.2 | 1.42 ± 0.08 | 590.7 ± 1.5 | 82.2 ± 0.4 | 524.0 ± 11.6 | 5.4 ± 0.9 | 9.7 ± 2.8 | 0.4 ± 0.2 | 0.00 ± 0.00 |
| `random` | random | 78.2 ± 5.0 | 288.8 ± 12.3 | 5.13 ± 0.33 | 584.6 ± 1.5 | 84.8 ± 0.6 | 443.3 ± 10.9 | 12.2 ± 1.8 | 5.2 ± 0.4 | 61.9 ± 0.5 | 12.06 ± 0.15 |
| `tuned_min_cost` | tuned_heuristic | 30.8 ± 1.3 | 121.4 ± 7.4 | 1.96 ± 0.10 | 568.2 ± 1.6 | 67.9 ± 0.3 | 541.4 ± 11.4 | 5.8 ± 1.1 | 6.8 ± 1.3 | 0.5 ± 0.2 | 0.00 ± 0.00 |
| `tuned_min_wait` | tuned_heuristic | 12.8 ± 0.1 | 24.8 ± 0.3 | 0.81 ± 0.04 | 596.9 ± 1.6 | 91.1 ± 0.2 | 513.0 ± 11.7 | 4.4 ± 0.9 | 7.0 ± 1.5 | 9.2 ± 1.0 | 0.00 ± 0.00 |
| `tuned_balanced` | tuned_heuristic | 13.0 ± 0.1 | 25.0 ± 0.0 | 0.81 ± 0.04 | 590.6 ± 1.7 | 85.3 ± 0.2 | 521.5 ± 11.8 | 4.4 ± 0.9 | 7.1 ± 1.5 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `tuned_cost_p95` | tuned_heuristic | 18.4 ± 0.4 | 43.3 ± 1.7 | 1.07 ± 0.05 | 575.0 ± 1.6 | 73.5 ± 0.3 | 538.3 ± 11.4 | 5.9 ± 1.2 | 8.1 ± 1.9 | 0.1 ± 0.0 | 0.00 ± 0.00 |
| `ppo_min_cost` | learned | 31.3 ± 1.3 | 124.7 ± 7.6 | 2.00 ± 0.10 | 568.0 ± 1.6 | 67.6 ± 0.2 | 540.9 ± 11.4 | 5.9 ± 1.1 | 6.9 ± 1.4 | 0.5 ± 0.1 | 0.00 ± 0.00 |
| `ppo_min_wait` | learned | 12.8 ± 0.1 | 24.7 ± 0.4 | 0.81 ± 0.04 | 596.2 ± 1.5 | 90.8 ± 0.4 | 510.5 ± 13.1 | 4.4 ± 0.9 | 7.0 ± 1.5 | 11.0 ± 3.4 | 0.74 ± 1.45 |
| `ppo_balanced` | learned | 13.1 ± 0.1 | 25.0 ± 0.0 | 0.82 ± 0.04 | 590.4 ± 1.6 | 85.0 ± 0.2 | 521.6 ± 11.9 | 4.4 ± 0.9 | 7.1 ± 1.5 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `ppo_cost_p95` | learned | 19.0 ± 0.5 | 44.7 ± 1.8 | 1.09 ± 0.05 | 574.5 ± 1.6 | 72.6 ± 0.3 | 539.4 ± 11.6 | 6.2 ± 1.1 | 8.8 ± 2.3 | 0.0 ± 0.0 | 0.00 ± 0.00 |

Objective scores (higher is better; each column is that objective's own score):

| manager | kind | min_cost | min_wait | balanced | cost_s.t._p95_wait | p95 within threshold (share of seeds) |
|---|---|---|---|---|---|---|
| `fixed` | fixed | -1.042 ± 0.005 | -2.959 ± 0.455 | -1.938 ± 0.776 | -8.435 ± 1.821 | 0.00 |
| `rule_based` | rule_based | -1.041 ± 0.004 | -1.598 ± 0.124 | -0.299 ± 0.088 | -1.566 ± 0.318 | 0.41 |
| `random` | random | -1.050 ± 0.004 | -5.571 ± 0.369 | -3.170 ± 0.238 | -20.071 ± 1.022 | 0.00 |
| `tuned_min_cost` | tuned_heuristic | -1.004 ± 0.004 | -2.238 ± 0.118 | -0.644 ± 0.082 | -6.097 ± 0.614 | 0.00 |
| `tuned_min_wait` | tuned_heuristic | -1.045 ± 0.004 | -0.846 ± 0.068 | 0.167 ± 0.058 | -1.030 ± 0.003 | 1.00 |
| `tuned_balanced` | tuned_heuristic | -1.035 ± 0.004 | -0.865 ± 0.072 | 0.203 ± 0.058 | -1.019 ± 0.003 | 1.00 |
| `tuned_cost_p95` | tuned_heuristic | -1.014 ± 0.004 | -1.269 ± 0.053 | -0.056 ± 0.052 | -0.992 ± 0.003 | 1.00 |
| `ppo_min_cost` | learned | -1.004 ± 0.004 | -2.278 ± 0.121 | -0.671 ± 0.085 | -6.371 ± 0.636 | 0.00 |
| `ppo_min_wait` | learned | -1.044 ± 0.003 | -0.844 ± 0.068 | 0.157 ± 0.064 | -1.029 ± 0.003 | 1.00 |
| `ppo_balanced` | learned | -1.035 ± 0.004 | -0.872 ± 0.072 | 0.199 ± 0.058 | -1.018 ± 0.003 | 1.00 |
| `ppo_cost_p95` | learned | -1.014 ± 0.004 | -1.313 ± 0.059 | -0.092 ± 0.056 | -0.991 ± 0.003 | 1.00 |

## Verdicts (paired difference of the objective's own score, a minus b, on held-out seeds)

| objective | scenario | a | b | a score | b score | a - b (± CI95) | verdict |
|---|---|---|---|---|---|---|---|
| min_cost | normal_week | `ppo_min_cost` | `tuned_min_cost` | -0.982 | -0.982 | -0.000 ± 0.000 | a matches (difference not significant) b |
| min_cost | normal_week | `ppo_min_cost` | `rule_based` | -0.982 | -1.020 | +0.039 ± 0.001 | a beats b |
| min_cost | normal_week | `ppo_min_cost` | `fixed` | -0.982 | -1.019 | +0.038 ± 0.001 | a beats b |
| min_cost | normal_week | `tuned_min_cost` | `rule_based` | -0.982 | -1.020 | +0.039 ± 0.001 | a beats b |
| min_cost | normal_week | `tuned_min_cost` | `fixed` | -0.982 | -1.019 | +0.038 ± 0.001 | a beats b |
| min_wait | normal_week | `ppo_min_wait` | `tuned_min_wait` | -0.722 | -0.725 | +0.002 ± 0.006 | a matches (difference not significant) b |
| min_wait | normal_week | `ppo_min_wait` | `rule_based` | -0.722 | -1.116 | +0.394 ± 0.023 | a beats b |
| min_wait | normal_week | `ppo_min_wait` | `fixed` | -0.722 | -1.479 | +0.756 ± 0.057 | a beats b |
| min_wait | normal_week | `tuned_min_wait` | `rule_based` | -0.725 | -1.116 | +0.391 ± 0.022 | a beats b |
| min_wait | normal_week | `tuned_min_wait` | `fixed` | -0.725 | -1.479 | +0.754 ± 0.055 | a beats b |
| balanced | normal_week | `ppo_balanced` | `tuned_balanced` | 0.199 | 0.204 | -0.006 ± 0.002 | a loses to b |
| balanced | normal_week | `ppo_balanced` | `rule_based` | 0.199 | -0.053 | +0.252 ± 0.016 | a beats b |
| balanced | normal_week | `ppo_balanced` | `fixed` | 0.199 | -0.295 | +0.493 ± 0.035 | a beats b |
| balanced | normal_week | `tuned_balanced` | `rule_based` | 0.204 | -0.053 | +0.258 ± 0.016 | a beats b |
| balanced | normal_week | `tuned_balanced` | `fixed` | 0.204 | -0.295 | +0.499 ± 0.036 | a beats b |
| cost_s.t._p95_wait | normal_week | `ppo_cost_p95` | `tuned_cost_p95` | -0.975 | -0.976 | +0.000 ± 0.000 | a beats b |
| cost_s.t._p95_wait | normal_week | `ppo_cost_p95` | `rule_based` | -0.975 | -1.004 | +0.028 ± 0.000 | a beats b |
| cost_s.t._p95_wait | normal_week | `ppo_cost_p95` | `fixed` | -0.975 | -1.469 | +0.493 ± 0.248 | a beats b |
| cost_s.t._p95_wait | normal_week | `tuned_cost_p95` | `rule_based` | -0.976 | -1.004 | +0.028 ± 0.000 | a beats b |
| cost_s.t._p95_wait | normal_week | `tuned_cost_p95` | `fixed` | -0.976 | -1.469 | +0.493 ± 0.248 | a beats b |
| min_cost | flu_surge | `ppo_min_cost` | `tuned_min_cost` | -1.004 | -1.004 | +0.000 ± 0.001 | a matches (difference not significant) b |
| min_cost | flu_surge | `ppo_min_cost` | `rule_based` | -1.004 | -1.041 | +0.037 ± 0.001 | a beats b |
| min_cost | flu_surge | `ppo_min_cost` | `fixed` | -1.004 | -1.042 | +0.038 ± 0.002 | a beats b |
| min_cost | flu_surge | `tuned_min_cost` | `rule_based` | -1.004 | -1.041 | +0.037 ± 0.001 | a beats b |
| min_cost | flu_surge | `tuned_min_cost` | `fixed` | -1.004 | -1.042 | +0.038 ± 0.002 | a beats b |
| min_wait | flu_surge | `ppo_min_wait` | `tuned_min_wait` | -0.844 | -0.846 | +0.002 ± 0.005 | a matches (difference not significant) b |
| min_wait | flu_surge | `ppo_min_wait` | `rule_based` | -0.844 | -1.598 | +0.754 ± 0.061 | a beats b |
| min_wait | flu_surge | `ppo_min_wait` | `fixed` | -0.844 | -2.959 | +2.115 ± 0.465 | a beats b |
| min_wait | flu_surge | `tuned_min_wait` | `rule_based` | -0.846 | -1.598 | +0.752 ± 0.061 | a beats b |
| min_wait | flu_surge | `tuned_min_wait` | `fixed` | -0.846 | -2.959 | +2.113 ± 0.465 | a beats b |
| balanced | flu_surge | `ppo_balanced` | `tuned_balanced` | 0.199 | 0.203 | -0.004 ± 0.003 | a loses to b |
| balanced | flu_surge | `ppo_balanced` | `rule_based` | 0.199 | -0.299 | +0.498 ± 0.042 | a beats b |
| balanced | flu_surge | `ppo_balanced` | `fixed` | 0.199 | -1.938 | +2.137 ± 0.777 | a beats b |
| balanced | flu_surge | `tuned_balanced` | `rule_based` | 0.203 | -0.299 | +0.502 ± 0.042 | a beats b |
| balanced | flu_surge | `tuned_balanced` | `fixed` | 0.203 | -1.938 | +2.141 ± 0.778 | a beats b |
| cost_s.t._p95_wait | flu_surge | `ppo_cost_p95` | `tuned_cost_p95` | -0.991 | -0.992 | +0.001 ± 0.000 | a beats b |
| cost_s.t._p95_wait | flu_surge | `ppo_cost_p95` | `rule_based` | -0.991 | -1.566 | +0.575 ± 0.318 | a beats b |
| cost_s.t._p95_wait | flu_surge | `ppo_cost_p95` | `fixed` | -0.991 | -8.435 | +7.444 ± 1.820 | a beats b |
| cost_s.t._p95_wait | flu_surge | `tuned_cost_p95` | `rule_based` | -0.992 | -1.566 | +0.574 ± 0.318 | a beats b |
| cost_s.t._p95_wait | flu_surge | `tuned_cost_p95` | `fixed` | -0.992 | -8.435 | +7.444 ± 1.820 | a beats b |

A verdict of 'beats' or 'loses to' means the 95% interval of the paired difference excludes zero; otherwise the two are reported as matching. Nothing outside this table should be read as a claim that a learned agent beats a baseline.
