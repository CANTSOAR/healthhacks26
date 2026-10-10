# Held-out evaluation of hospital managers (all numbers SIMULATED)

Generated 2026-10-10T02:14:37-0400; simulator fingerprint `81960cf933f447cf`.

Protocol: 32 held-out seeds (9000000..9000031) x 30 days per manager per scenario; every manager faces the same seeds (paired). Tuning and training never used seeds at or above 1,000,000. Values are mean ± 95% CI half-width over seeds.

Kinds: `fixed`, `rule_based` and `random` are baselines; `tuned_heuristic` is the rule-based manager with parameters found by evolutionary search (NOT a learned agent); `learned` is a PPO network acting greedily.

Constrained objective: cheapest subject to episode p95 wait <= 675 min (threshold = 0.75 x the fixed baseline's p95).

## Scenario `normal_week`

| manager | kind | wait mean (min) | wait p95 (min) | LWBS % | cost/day ($k) | margin/day ($k) | deaths/10k | boarding h/day | overtime h/day | diversion h/day |
|---|---|---|---|---|---|---|---|---|---|---|
| `fixed` | fixed | 23.1 ± 0.8 | 63.0 ± 3.9 | 1.42 ± 0.07 | 579.8 ± 1.6 | 447.1 ± 10.9 | 5.4 ± 1.0 | 5.8 ± 1.0 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `rule_based` | rule_based | 18.0 ± 0.3 | 43.9 ± 1.7 | 1.13 ± 0.05 | 581.9 ± 1.5 | 446.6 ± 11.1 | 4.9 ± 1.1 | 4.6 ± 0.2 | 0.1 ± 0.0 | 0.00 ± 0.00 |
| `random` | random | 60.8 ± 3.7 | 235.9 ± 10.5 | 3.95 ± 0.24 | 578.8 ± 1.5 | 392.1 ± 10.6 | 10.1 ± 1.5 | 4.3 ± 0.2 | 61.9 ± 0.5 | 12.06 ± 0.15 |
| `tuned_min_cost` | tuned_heuristic | 14.5 ± 0.2 | 29.7 ± 1.0 | 0.91 ± 0.04 | 567.4 ± 1.5 | 464.0 ± 11.2 | 4.7 ± 1.0 | 4.5 ± 0.2 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `tuned_min_wait` | tuned_heuristic | 12.6 ± 0.0 | 23.6 ± 0.8 | 0.79 ± 0.03 | 592.2 ± 1.5 | 435.2 ± 11.3 | 4.2 ± 1.0 | 4.5 ± 0.2 | 7.2 ± 0.3 | 0.00 ± 0.00 |
| `tuned_balanced` | tuned_heuristic | 11.9 ± 0.1 | 20.0 ± 0.0 | 0.75 ± 0.03 | 575.6 ± 1.6 | 456.8 ± 11.2 | 4.3 ± 1.0 | 4.5 ± 0.2 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `tuned_cost_p95` | tuned_heuristic | 120.5 ± 2.7 | 318.4 ± 8.2 | 7.89 ± 0.18 | 556.4 ± 1.5 | 433.1 ± 10.1 | 17.5 ± 1.9 | 4.1 ± 0.2 | 0.0 ± 0.0 | 0.00 ± 0.00 |

Objective scores (higher is better; each column is that objective's own score):

| manager | kind | min_cost | min_wait | balanced | cost_s.t._p95_wait | p95 within threshold (share of seeds) |
|---|---|---|---|---|---|---|
| `fixed` | fixed | -0.697 ± 0.002 | -0.166 ± 0.007 | 0.416 ± 0.014 | -0.679 ± 0.002 | 1.00 |
| `rule_based` | rule_based | -0.696 ± 0.002 | -0.140 ± 0.005 | 0.434 ± 0.014 | -0.682 ± 0.002 | 1.00 |
| `random` | random | -0.714 ± 0.003 | -0.334 ± 0.020 | 0.105 ± 0.018 | -0.678 ± 0.002 | 1.00 |
| `tuned_min_cost` | tuned_heuristic | -0.677 ± 0.002 | -0.121 ± 0.005 | 0.469 ± 0.014 | -0.665 ± 0.002 | 1.00 |
| `tuned_min_wait` | tuned_heuristic | -0.705 ± 0.002 | -0.111 ± 0.004 | 0.431 ± 0.014 | -0.694 ± 0.002 | 1.00 |
| `tuned_balanced` | tuned_heuristic | -0.685 ± 0.002 | -0.109 ± 0.004 | 0.470 ± 0.014 | -0.674 ± 0.002 | 1.00 |
| `tuned_cost_p95` | tuned_heuristic | -0.726 ± 0.003 | -0.645 ± 0.018 | 0.026 ± 0.018 | -0.652 ± 0.002 | 1.00 |

## Scenario `flu_surge`

| manager | kind | wait mean (min) | wait p95 (min) | LWBS % | cost/day ($k) | margin/day ($k) | deaths/10k | boarding h/day | overtime h/day | diversion h/day |
|---|---|---|---|---|---|---|---|---|---|---|
| `fixed` | fixed | 38.5 ± 3.9 | 149.1 ± 21.8 | 2.53 ± 0.36 | 587.5 ± 1.6 | 505.1 ± 13.4 | 7.0 ± 1.2 | 81.3 ± 48.1 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `rule_based` | rule_based | 22.4 ± 0.7 | 65.5 ± 4.2 | 1.42 ± 0.08 | 590.7 ± 1.5 | 524.0 ± 11.6 | 5.4 ± 0.9 | 9.7 ± 2.8 | 0.4 ± 0.2 | 0.00 ± 0.00 |
| `random` | random | 78.2 ± 5.0 | 288.8 ± 12.3 | 5.13 ± 0.33 | 584.6 ± 1.5 | 443.3 ± 10.9 | 12.2 ± 1.8 | 5.2 ± 0.4 | 61.9 ± 0.5 | 12.06 ± 0.15 |
| `tuned_min_cost` | tuned_heuristic | 15.6 ± 0.3 | 33.0 ± 1.0 | 0.97 ± 0.05 | 578.0 ± 1.6 | 534.2 ± 11.7 | 5.1 ± 1.0 | 6.9 ± 1.4 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `tuned_min_wait` | tuned_heuristic | 12.8 ± 0.0 | 24.8 ± 0.3 | 0.80 ± 0.04 | 601.8 ± 1.6 | 509.1 ± 11.8 | 4.4 ± 0.9 | 7.0 ± 1.5 | 8.9 ± 1.0 | 0.00 ± 0.00 |
| `tuned_balanced` | tuned_heuristic | 12.4 ± 0.2 | 20.2 ± 0.3 | 0.77 ± 0.03 | 587.2 ± 1.6 | 527.8 ± 11.8 | 4.5 ± 0.9 | 7.2 ± 1.6 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `tuned_cost_p95` | tuned_heuristic | 164.4 ± 3.4 | 399.4 ± 6.9 | 10.73 ± 0.20 | 562.8 ± 1.5 | 479.6 ± 10.1 | 21.9 ± 1.8 | 4.4 ± 0.2 | 0.0 ± 0.0 | 0.00 ± 0.00 |

Objective scores (higher is better; each column is that objective's own score):

| manager | kind | min_cost | min_wait | balanced | cost_s.t._p95_wait | p95 within threshold (share of seeds) |
|---|---|---|---|---|---|---|
| `fixed` | fixed | -0.718 ± 0.005 | -0.274 ± 0.031 | 0.387 ± 0.043 | -0.688 ± 0.002 | 1.00 |
| `rule_based` | rule_based | -0.712 ± 0.002 | -0.180 ± 0.010 | 0.492 ± 0.016 | -0.692 ± 0.002 | 1.00 |
| `random` | random | -0.735 ± 0.003 | -0.455 ± 0.027 | 0.073 ± 0.023 | -0.685 ± 0.002 | 1.00 |
| `tuned_min_cost` | tuned_heuristic | -0.692 ± 0.002 | -0.138 ± 0.006 | 0.536 ± 0.015 | -0.677 ± 0.002 | 1.00 |
| `tuned_min_wait` | tuned_heuristic | -0.718 ± 0.002 | -0.124 ± 0.006 | 0.503 ± 0.016 | -0.705 ± 0.002 | 1.00 |
| `tuned_balanced` | tuned_heuristic | -0.701 ± 0.002 | -0.122 ± 0.005 | 0.541 ± 0.015 | -0.688 ± 0.002 | 1.00 |
| `tuned_cost_p95` | tuned_heuristic | -0.765 ± 0.004 | -0.924 ± 0.021 | -0.136 ± 0.017 | -0.659 ± 0.002 | 1.00 |

## Verdicts (paired difference of the objective's own score, a minus b, on held-out seeds)

No learned (PPO) agent was available for this evaluation, so there is no learned-vs-heuristic verdict here.

| objective | scenario | a | b | a score | b score | a - b (± CI95) | verdict |
|---|---|---|---|---|---|---|---|
| min_cost | normal_week | `tuned_min_cost` | `rule_based` | -0.677 | -0.696 | +0.019 ± 0.001 | a beats b |
| min_cost | normal_week | `tuned_min_cost` | `fixed` | -0.677 | -0.697 | +0.020 ± 0.001 | a beats b |
| min_wait | normal_week | `tuned_min_wait` | `rule_based` | -0.111 | -0.140 | +0.029 ± 0.002 | a beats b |
| min_wait | normal_week | `tuned_min_wait` | `fixed` | -0.111 | -0.166 | +0.055 ± 0.004 | a beats b |
| balanced | normal_week | `tuned_balanced` | `rule_based` | 0.470 | 0.434 | +0.036 ± 0.003 | a beats b |
| balanced | normal_week | `tuned_balanced` | `fixed` | 0.470 | 0.416 | +0.054 ± 0.004 | a beats b |
| cost_s.t._p95_wait | normal_week | `tuned_cost_p95` | `rule_based` | -0.652 | -0.682 | +0.030 ± 0.000 | a beats b |
| cost_s.t._p95_wait | normal_week | `tuned_cost_p95` | `fixed` | -0.652 | -0.679 | +0.027 ± 0.000 | a beats b |
| min_cost | flu_surge | `tuned_min_cost` | `rule_based` | -0.692 | -0.712 | +0.020 ± 0.001 | a beats b |
| min_cost | flu_surge | `tuned_min_cost` | `fixed` | -0.692 | -0.718 | +0.026 ± 0.003 | a beats b |
| min_wait | flu_surge | `tuned_min_wait` | `rule_based` | -0.124 | -0.180 | +0.056 ± 0.005 | a beats b |
| min_wait | flu_surge | `tuned_min_wait` | `fixed` | -0.124 | -0.274 | +0.150 ± 0.032 | a beats b |
| balanced | flu_surge | `tuned_balanced` | `rule_based` | 0.541 | 0.492 | +0.049 ± 0.007 | a beats b |
| balanced | flu_surge | `tuned_balanced` | `fixed` | 0.541 | 0.387 | +0.154 ± 0.044 | a beats b |
| cost_s.t._p95_wait | flu_surge | `tuned_cost_p95` | `rule_based` | -0.659 | -0.692 | +0.033 ± 0.000 | a beats b |
| cost_s.t._p95_wait | flu_surge | `tuned_cost_p95` | `fixed` | -0.659 | -0.688 | +0.029 ± 0.000 | a beats b |

A verdict of 'beats' or 'loses to' means the 95% interval of the paired difference excludes zero; otherwise the two are reported as matching. Nothing outside this table should be read as a claim that a learned agent beats a baseline.
