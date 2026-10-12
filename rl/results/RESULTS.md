# Held-out evaluation of hospital managers, hospital `rwjuh_nb` (all numbers SIMULATED)

The constrained operator objectives (same budget / same service against the calibrated baseline, over the calibration ensemble) are reported in `rl/hospitals/rwjuh_nb/HEADLINE.md`; this table is the unconstrained trade-off view.

Generated 2026-10-11T00:16:54-0400; simulator behaviour fingerprint `ed6420bf3cdf4b16` (hash of a fixed-seed trajectory; staleness is keyed on it), file hash `fb4e48d5e35aa606` (information only).

Managers tuned or trained against a different simulator behaviour: `ppo_balanced`, `ppo_cond_balanced`, `ppo_cond_max_margin`, `ppo_cond_min_cost`, `ppo_cond_min_wait`, `ppo_cond`, `ppo_cost_p95`, `ppo_max_margin`, `ppo_min_cost`, `ppo_min_wait`, `ppo_same_budget`, `ppo_same_service`, `ppo_scratch_min_cost`, `ppo_scratch_min_wait`, `tuned_balanced`, `tuned_cost_p95`, `tuned_max_margin`, `tuned_min_cost`, `tuned_min_wait`.

Protocol: 32 held-out seeds (9000000..9000031) x 30 days per manager per scenario; every manager faces the same seeds (paired). Tuning and training never used seeds at or above 1,000,000. Values are mean ± 95% CI half-width over seeds.

Kinds: `fixed`, `rule_based` and `random` are baselines; `tuned_heuristic` is the rule-based manager with parameters found by evolutionary search (NOT a learned agent); `learned` is a PPO network acting greedily.

Constrained objective: cheapest subject to episode p95 wait <= 60 min (a chosen service target; see rl/reward_scales.json). `labor cost/day` is the part of cost the manager controls directly (wages, overtime, agency); fixed and per-patient costs dominate `cost/day`.

## Objectives (exact weights on baseline-normalised reward terms; reward = -sum of weight x term)

| objective | weights | what it asks for |
|---|---|---|
| `min_cost` | labor 1 | lowest controllable (labour: wages + overtime + agency) cost, nothing else |
| `min_wait` | wait 1, lwbs 0.25 | least waiting and fewest walk-outs, at any cost |
| `max_margin` | cost 1, revenue 1 | revenue minus total cost |
| `balanced` | cost 1, revenue 1, wait 0.5, lwbs 0.25, safety 0.25, boarding 0.1, staff 0.1 | margin, waiting, walk-outs, safety, boarding and staff strain together |
| `cost_s.t._p95_wait` | labor 1 | lowest labour cost subject to episode p95 wait <= 60 min (score = -labour term - 5 x relative excess of p95 over the threshold) |

Term scales (fixed-default manager, per hour): cost 2.53e+04, wait 87.3, lwbs 0.0848, safety 0.02, boarding 0.423, staff 1, revenue 2.53e+04, labor 4.37e+03, los 38.4, opcost 2.07e+04.

## Learned agents: how each was produced and how it did against its tuned heuristic (held-out)

- `ppo_min_cost` (normal_week): beats tuned_min_cost on the min_cost score (+0.0018 ± 0.0008). PPO, warm-started by behaviour cloning from tuned_min_cost, then 3,310,720 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_min_wait` (normal_week): loses to tuned_min_wait on the min_wait score (-0.0155 ± 0.0070). PPO, warm-started by behaviour cloning from tuned_min_wait, then 3,611,776 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_max_margin` (normal_week): matches (difference not significant) tuned_max_margin on the max_margin score (-0.0003 ± 0.0007). PPO, warm-started by behaviour cloning from tuned_max_margin, then 902,272 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_balanced` (normal_week): loses to tuned_balanced on the balanced score (-0.1590 ± 0.0193). PPO, warm-started by behaviour cloning from tuned_balanced, then 300,160 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_cost_p95` (normal_week): loses to tuned_cost_p95 on the cost_s.t._p95_wait score (-4.3415 ± 1.1303). PPO, warm-started by behaviour cloning from tuned_cost_p95, then 1,805,440 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_same_budget` (normal_week): no tuned heuristic to compare with. PPO, warm-started by behaviour cloning from tuned_same_budget, then 275,904 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/hospitals/rwjuh_nb/HEADLINE.md. Trained on the constrained operator objective with one Lagrange multiplier per constraint; diversion and the admission cap are locked at baseline.
- `ppo_same_service` (normal_week): no tuned heuristic to compare with. PPO, warm-started by behaviour cloning from tuned_same_service, then 275,904 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/hospitals/rwjuh_nb/HEADLINE.md. Trained on the constrained operator objective with one Lagrange multiplier per constraint; diversion and the admission cap are locked at baseline.
- `ppo_scratch_min_cost` (normal_week): matches (difference not significant) tuned_min_cost on the min_cost score (+0.0138 ± 0.0269). PPO, trained from scratch (no behaviour cloning), then 3,912,832 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_scratch_min_wait` (normal_week): loses to tuned_min_wait on the min_wait score (-0.0609 ± 0.0355). PPO, trained from scratch (no behaviour cloning), then 3,912,832 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_cond` (normal_week): no tuned heuristic to compare with. PPO, warm-started by behaviour cloning from the tuned heuristics of min_cost, min_wait, max_margin, balanced, then 257,280 PPO environment steps; acts greedily. One network conditioned on the reward weights in its observation. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_cond_min_cost` (normal_week): matches (difference not significant) tuned_min_cost on the min_cost score (+0.0001 ± 0.0001). PPO, warm-started by behaviour cloning from the tuned heuristics of min_cost, min_wait, max_margin, balanced, then 257,280 PPO environment steps; acts greedily. One network conditioned on the reward weights in its observation. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_cond_min_wait` (normal_week): matches (difference not significant) tuned_min_wait on the min_wait score (+0.0007 ± 0.0012). PPO, warm-started by behaviour cloning from the tuned heuristics of min_cost, min_wait, max_margin, balanced, then 257,280 PPO environment steps; acts greedily. One network conditioned on the reward weights in its observation. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_cond_max_margin` (normal_week): matches (difference not significant) tuned_max_margin on the max_margin score (-0.0003 ± 0.0012). PPO, warm-started by behaviour cloning from the tuned heuristics of min_cost, min_wait, max_margin, balanced, then 257,280 PPO environment steps; acts greedily. One network conditioned on the reward weights in its observation. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_cond_balanced` (normal_week): beats tuned_balanced on the balanced score (+0.0500 ± 0.0135). PPO, warm-started by behaviour cloning from the tuned heuristics of min_cost, min_wait, max_margin, balanced, then 257,280 PPO environment steps; acts greedily. One network conditioned on the reward weights in its observation. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_min_cost` (flu_surge): beats tuned_min_cost on the min_cost score (+0.0030 ± 0.0010). PPO, warm-started by behaviour cloning from tuned_min_cost, then 3,310,720 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_min_wait` (flu_surge): beats tuned_min_wait on the min_wait score (+0.0208 ± 0.0065). PPO, warm-started by behaviour cloning from tuned_min_wait, then 3,611,776 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_max_margin` (flu_surge): loses to tuned_max_margin on the max_margin score (-0.0033 ± 0.0020). PPO, warm-started by behaviour cloning from tuned_max_margin, then 902,272 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_balanced` (flu_surge): loses to tuned_balanced on the balanced score (-0.2449 ± 0.0265). PPO, warm-started by behaviour cloning from tuned_balanced, then 300,160 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_cost_p95` (flu_surge): loses to tuned_cost_p95 on the cost_s.t._p95_wait score (-13.7830 ± 1.3029). PPO, warm-started by behaviour cloning from tuned_cost_p95, then 1,805,440 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_same_budget` (flu_surge): no tuned heuristic to compare with. PPO, warm-started by behaviour cloning from tuned_same_budget, then 275,904 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/hospitals/rwjuh_nb/HEADLINE.md. Trained on the constrained operator objective with one Lagrange multiplier per constraint; diversion and the admission cap are locked at baseline.
- `ppo_same_service` (flu_surge): no tuned heuristic to compare with. PPO, warm-started by behaviour cloning from tuned_same_service, then 275,904 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/hospitals/rwjuh_nb/HEADLINE.md. Trained on the constrained operator objective with one Lagrange multiplier per constraint; diversion and the admission cap are locked at baseline.
- `ppo_scratch_min_cost` (flu_surge): matches (difference not significant) tuned_min_cost on the min_cost score (+0.0118 ± 0.0223). PPO, trained from scratch (no behaviour cloning), then 3,912,832 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_scratch_min_wait` (flu_surge): matches (difference not significant) tuned_min_wait on the min_wait score (-0.0339 ± 0.0419). PPO, trained from scratch (no behaviour cloning), then 3,912,832 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_cond` (flu_surge): no tuned heuristic to compare with. PPO, warm-started by behaviour cloning from the tuned heuristics of min_cost, min_wait, max_margin, balanced, then 257,280 PPO environment steps; acts greedily. One network conditioned on the reward weights in its observation. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_cond_min_cost` (flu_surge): beats tuned_min_cost on the min_cost score (+0.0010 ± 0.0006). PPO, warm-started by behaviour cloning from the tuned heuristics of min_cost, min_wait, max_margin, balanced, then 257,280 PPO environment steps; acts greedily. One network conditioned on the reward weights in its observation. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_cond_min_wait` (flu_surge): loses to tuned_min_wait on the min_wait score (-0.0018 ± 0.0016). PPO, warm-started by behaviour cloning from the tuned heuristics of min_cost, min_wait, max_margin, balanced, then 257,280 PPO environment steps; acts greedily. One network conditioned on the reward weights in its observation. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_cond_max_margin` (flu_surge): matches (difference not significant) tuned_max_margin on the max_margin score (-0.0003 ± 0.0016). PPO, warm-started by behaviour cloning from the tuned heuristics of min_cost, min_wait, max_margin, balanced, then 257,280 PPO environment steps; acts greedily. One network conditioned on the reward weights in its observation. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_cond_balanced` (flu_surge): beats tuned_balanced on the balanced score (+0.0364 ± 0.0165). PPO, warm-started by behaviour cloning from the tuned heuristics of min_cost, min_wait, max_margin, balanced, then 257,280 PPO environment steps; acts greedily. One network conditioned on the reward weights in its observation. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.

## Scenario `normal_week`

| manager | kind | wait mean (min) | wait p95 (min) | LWBS % | cost/day ($k) | labor cost/day ($k) | margin/day ($k) | deaths/10k | boarding h/day | overtime h/day | diversion h/day |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `fixed` | fixed | 14.5 ± 0.2 | 30.2 ± 0.3 | 0.91 ± 0.04 | 608.3 ± 1.6 | 104.9 ± 0.1 | 422.5 ± 11.1 | 4.8 ± 1.0 | 6.2 ± 1.2 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `rule_based` | rule_based | 17.1 ± 0.2 | 38.8 ± 0.9 | 1.10 ± 0.04 | 619.3 ± 1.5 | 117.9 ± 0.3 | 412.8 ± 11.4 | 5.0 ± 1.0 | 4.5 ± 0.2 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `random` | random | 81.4 ± 5.3 | 304.5 ± 16.5 | 5.22 ± 0.34 | 606.0 ± 1.8 | 113.3 ± 1.2 | 359.2 ± 10.4 | 13.1 ± 1.9 | 4.2 ± 0.2 | 61.9 ± 0.5 | 12.06 ± 0.15 |
| `tuned_min_cost` | tuned_heuristic | 210.9 ± 4.7 | 439.7 ± 14.7 | 13.29 ± 0.31 | 551.3 ± 1.5 | 61.8 ± 0.1 | 343.1 ± 8.9 | 25.8 ± 2.4 | 3.5 ± 0.2 | 0.0 ± 0.0 | 15.30 ± 0.35 |
| `tuned_min_wait` | tuned_heuristic | 12.5 ± 0.1 | 21.1 ± 0.7 | 0.78 ± 0.04 | 627.6 ± 1.5 | 133.3 ± 0.3 | 400.5 ± 11.4 | 4.7 ± 1.0 | 4.5 ± 0.2 | 0.6 ± 0.1 | 0.00 ± 0.00 |
| `tuned_max_margin` | tuned_heuristic | 31.9 ± 1.2 | 111.2 ± 6.2 | 2.01 ± 0.09 | 575.9 ± 1.5 | 78.8 ± 0.1 | 462.3 ± 11.3 | 6.2 ± 1.1 | 4.4 ± 0.2 | 0.5 ± 0.2 | 0.00 ± 0.00 |
| `tuned_balanced` | tuned_heuristic | 14.1 ± 0.2 | 28.4 ± 0.8 | 0.87 ± 0.04 | 605.0 ± 1.6 | 107.9 ± 0.4 | 423.5 ± 11.3 | 4.9 ± 1.1 | 4.5 ± 0.2 | 0.0 ± 0.0 | 0.02 ± 0.01 |
| `tuned_cost_p95` | tuned_heuristic | 19.6 ± 0.4 | 48.8 ± 2.0 | 1.19 ± 0.04 | 589.9 ± 1.7 | 87.5 ± 0.3 | 435.9 ± 11.3 | 5.7 ± 1.1 | 5.0 ± 0.4 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `tuned_same_budget` | tuned_heuristic | 14.2 ± 0.1 | 30.0 ± 0.0 | 0.90 ± 0.04 | 599.8 ± 1.6 | 97.0 ± 0.1 | 428.2 ± 11.1 | 4.7 ± 1.0 | 4.9 ± 0.4 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `tuned_same_service` | tuned_heuristic | 14.5 ± 0.2 | 30.2 ± 0.3 | 0.91 ± 0.04 | 608.3 ± 1.6 | 104.9 ± 0.1 | 422.5 ± 11.1 | 4.8 ± 1.0 | 6.2 ± 1.2 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `ppo_min_cost` | learned | 226.8 ± 6.8 | 490.3 ± 25.8 | 14.34 ± 0.47 | 550.8 ± 1.6 | 61.6 ± 0.1 | 341.6 ± 9.7 | 27.3 ± 2.3 | 3.5 ± 0.2 | 3.6 ± 0.9 | 14.30 ± 0.34 |
| `ppo_min_wait` | learned | 12.9 ± 0.1 | 24.1 ± 0.7 | 0.83 ± 0.04 | 628.7 ± 1.3 | 133.6 ± 0.3 | 366.0 ± 14.5 | 4.7 ± 1.0 | 4.3 ± 0.2 | 19.6 ± 2.9 | 7.96 ± 1.19 |
| `ppo_max_margin` | learned | 32.6 ± 1.4 | 114.2 ± 7.0 | 2.07 ± 0.09 | 575.7 ± 1.5 | 78.7 ± 0.1 | 462.2 ± 11.2 | 6.2 ± 1.1 | 4.4 ± 0.2 | 0.1 ± 0.0 | 0.01 ± 0.00 |
| `ppo_balanced` | learned | 13.8 ± 0.2 | 24.8 ± 0.7 | 0.93 ± 0.05 | 595.5 ± 1.5 | 104.3 ± 0.4 | 343.4 ± 10.0 | 5.0 ± 0.9 | 4.0 ± 0.2 | 33.7 ± 0.2 | 23.97 ± 0.00 |
| `ppo_cost_p95` | learned | 32.7 ± 2.0 | 113.6 ± 13.6 | 2.34 ± 0.16 | 565.9 ± 1.5 | 74.4 ± 0.3 | 375.7 ± 9.9 | 5.9 ± 1.1 | 3.9 ± 0.2 | 34.5 ± 0.3 | 23.16 ± 0.15 |
| `ppo_same_budget` | learned | 14.4 ± 0.1 | 30.0 ± 0.0 | 0.90 ± 0.04 | 598.9 ± 1.6 | 95.6 ± 0.1 | 430.7 ± 11.0 | 4.7 ± 1.0 | 5.8 ± 1.0 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `ppo_same_service` | learned | 12.4 ± 0.1 | 20.8 ± 0.6 | 0.78 ± 0.03 | 595.3 ± 1.6 | 97.5 ± 0.1 | 433.8 ± 11.0 | 4.6 ± 1.0 | 6.1 ± 1.1 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `ppo_scratch_min_cost` | learned | 788.5 ± 54.7 | 1435.0 ± 0.0 | 34.96 ± 1.74 | 529.8 ± 4.8 | 60.4 ± 2.8 | 164.0 ± 13.1 | 127.6 ± 8.2 | 2.7 ± 0.2 | 1.1 ± 0.3 | 9.60 ± 0.52 |
| `ppo_scratch_min_wait` | learned | 13.2 ± 0.3 | 23.8 ± 1.0 | 0.84 ± 0.04 | 630.2 ± 1.4 | 132.7 ± 0.5 | 363.5 ± 10.8 | 4.8 ± 1.0 | 5.5 ± 0.4 | 30.6 ± 0.4 | 3.95 ± 0.20 |
| `ppo_cond` | learned | 13.3 ± 0.0 | 25.0 ± 0.0 | 0.84 ± 0.04 | 609.4 ± 1.6 | 112.5 ± 0.4 | 419.9 ± 11.2 | 4.7 ± 1.0 | 4.5 ± 0.2 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `ppo_cond_min_cost` | learned | 214.9 ± 4.7 | 445.2 ± 14.5 | 13.39 ± 0.30 | 551.6 ± 1.5 | 61.8 ± 0.0 | 345.8 ± 8.9 | 26.1 ± 2.4 | 3.5 ± 0.2 | 0.0 ± 0.0 | 14.25 ± 0.36 |
| `ppo_cond_min_wait` | learned | 12.5 ± 0.1 | 20.9 ± 0.7 | 0.78 ± 0.03 | 627.7 ± 1.5 | 133.5 ± 0.3 | 400.4 ± 11.4 | 4.7 ± 1.0 | 4.5 ± 0.2 | 0.3 ± 0.1 | 0.00 ± 0.00 |
| `ppo_cond_max_margin` | learned | 30.6 ± 1.1 | 104.2 ± 5.6 | 1.93 ± 0.08 | 576.1 ± 1.5 | 79.0 ± 0.1 | 462.1 ± 11.2 | 6.1 ± 1.0 | 4.5 ± 0.2 | 0.2 ± 0.1 | 0.01 ± 0.01 |
| `ppo_cond_balanced` | learned | 13.3 ± 0.0 | 25.0 ± 0.0 | 0.84 ± 0.04 | 609.4 ± 1.6 | 112.5 ± 0.4 | 419.9 ± 11.2 | 4.7 ± 1.0 | 4.5 ± 0.2 | 0.0 ± 0.0 | 0.00 ± 0.00 |

Objective scores (higher is better; each column is that objective's own score):

| manager | kind | min_cost | min_wait | max_margin | balanced | cost_s.t._p95_wait | p95 within threshold (share of seeds) |
|---|---|---|---|---|---|---|---|
| `fixed` | fixed | -1.001 ± 0.001 | -1.259 ± 0.028 | 0.694 ± 0.018 | -0.334 ± 0.036 | -1.001 ± 0.001 | 1.00 |
| `rule_based` | rule_based | -1.125 ± 0.003 | -1.587 ± 0.028 | 0.679 ± 0.019 | -0.531 ± 0.039 | -1.125 ± 0.003 | 1.00 |
| `random` | random | -1.081 ± 0.011 | -9.124 ± 0.610 | 0.590 ± 0.017 | -5.446 ± 0.391 | -21.459 ± 1.370 | 0.00 |
| `tuned_min_cost` | tuned_heuristic | -0.590 ± 0.000 | -22.534 ± 0.530 | 0.564 ± 0.015 | -13.817 ± 0.340 | -32.230 ± 1.223 | 0.00 |
| `tuned_min_wait` | tuned_heuristic | -1.272 ± 0.003 | -1.012 ± 0.013 | 0.658 ± 0.019 | -0.170 ± 0.033 | -1.272 ± 0.003 | 1.00 |
| `tuned_max_margin` | tuned_heuristic | -0.752 ± 0.001 | -3.450 ± 0.162 | 0.760 ± 0.019 | -1.636 ± 0.108 | -5.023 ± 0.518 | 0.00 |
| `tuned_balanced` | tuned_heuristic | -1.030 ± 0.004 | -1.199 ± 0.023 | 0.696 ± 0.019 | -0.249 ± 0.038 | -1.030 ± 0.004 | 1.00 |
| `tuned_cost_p95` | tuned_heuristic | -0.835 ± 0.003 | -1.875 ± 0.046 | 0.717 ± 0.019 | -0.684 ± 0.049 | -0.835 ± 0.003 | 1.00 |
| `tuned_same_budget` | tuned_heuristic | -0.925 ± 0.001 | -1.220 ± 0.016 | 0.704 ± 0.018 | -0.279 ± 0.034 | -0.925 ± 0.001 | 1.00 |
| `tuned_same_service` | tuned_heuristic | -1.001 ± 0.001 | -1.259 ± 0.028 | 0.694 ± 0.018 | -0.334 ± 0.036 | -1.001 ± 0.001 | 1.00 |
| `ppo_min_cost` | learned | -0.588 ± 0.001 | -24.604 ± 0.816 | 0.562 ± 0.016 | -15.109 ± 0.508 | -36.447 ± 2.153 | 0.00 |
| `ppo_min_wait` | learned | -1.275 ± 0.003 | -1.027 ± 0.012 | 0.602 ± 0.024 | -0.309 ± 0.044 | -1.275 ± 0.003 | 1.00 |
| `ppo_max_margin` | learned | -0.751 ± 0.001 | -3.555 ± 0.186 | 0.760 ± 0.018 | -1.697 ± 0.122 | -5.269 ± 0.587 | 0.00 |
| `ppo_balanced` | learned | -0.995 ± 0.004 | -1.048 ± 0.024 | 0.565 ± 0.017 | -0.408 ± 0.032 | -0.995 ± 0.004 | 1.00 |
| `ppo_cost_p95` | learned | -0.710 ± 0.003 | -3.329 ± 0.265 | 0.618 ± 0.016 | -1.773 ± 0.155 | -5.176 ± 1.131 | 0.03 |
| `ppo_same_budget` | learned | -0.912 ± 0.001 | -1.241 ± 0.020 | 0.708 ± 0.018 | -0.302 ± 0.036 | -0.912 ± 0.001 | 1.00 |
| `ppo_same_service` | learned | -0.931 ± 0.001 | -1.001 ± 0.015 | 0.713 ± 0.018 | -0.155 ± 0.035 | -0.931 ± 0.001 | 1.00 |
| `ppo_scratch_min_cost` | learned | -0.576 ± 0.027 | -82.976 ± 4.517 | 0.270 ± 0.021 | -50.844 ± 2.781 | -115.159 ± 0.027 | 0.00 |
| `ppo_scratch_min_wait` | learned | -1.266 ± 0.005 | -1.073 ± 0.034 | 0.598 ± 0.018 | -0.407 ± 0.036 | -1.266 ± 0.005 | 1.00 |
| `ppo_cond` | learned | -1.073 ± 0.004 | -1.110 ± 0.013 | 0.690 ± 0.018 | -0.199 ± 0.033 | -1.073 ± 0.004 | 1.00 |
| `ppo_cond_min_cost` | learned | -0.590 ± 0.000 | -23.040 ± 0.533 | 0.568 ± 0.015 | -14.120 ± 0.342 | -32.686 ± 1.211 | 0.00 |
| `ppo_cond_min_wait` | learned | -1.274 ± 0.002 | -1.011 ± 0.013 | 0.658 ± 0.019 | -0.169 ± 0.033 | -1.274 ± 0.002 | 1.00 |
| `ppo_cond_max_margin` | learned | -0.753 ± 0.001 | -3.278 ± 0.145 | 0.760 ± 0.018 | -1.532 ± 0.099 | -4.438 ± 0.466 | 0.00 |
| `ppo_cond_balanced` | learned | -1.073 ± 0.004 | -1.110 ± 0.013 | 0.690 ± 0.018 | -0.199 ± 0.033 | -1.073 ± 0.004 | 1.00 |

## Scenario `flu_surge`

| manager | kind | wait mean (min) | wait p95 (min) | LWBS % | cost/day ($k) | labor cost/day ($k) | margin/day ($k) | deaths/10k | boarding h/day | overtime h/day | diversion h/day |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `fixed` | fixed | 27.1 ± 6.8 | 95.9 ± 44.8 | 1.91 ± 0.63 | 616.5 ± 1.6 | 103.8 ± 0.1 | 479.8 ± 14.9 | 6.4 ± 1.3 | 129.8 ± 68.3 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `rule_based` | rule_based | 19.7 ± 0.3 | 47.7 ± 1.6 | 1.24 ± 0.05 | 628.5 ± 1.6 | 119.6 ± 0.5 | 492.5 ± 12.0 | 5.4 ± 0.9 | 11.4 ± 3.8 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `random` | random | 105.3 ± 7.4 | 371.4 ± 20.5 | 6.70 ± 0.45 | 611.3 ± 1.8 | 112.3 ± 1.2 | 408.9 ± 10.6 | 15.9 ± 2.0 | 5.1 ± 0.4 | 61.9 ± 0.5 | 12.06 ± 0.15 |
| `tuned_min_cost` | tuned_heuristic | 303.9 ± 6.9 | 615.9 ± 19.2 | 18.58 ± 0.36 | 552.9 ± 1.5 | 61.4 ± 0.1 | 354.1 ± 8.0 | 35.2 ± 2.6 | 3.5 ± 0.2 | 0.0 ± 0.0 | 20.72 ± 0.26 |
| `tuned_min_wait` | tuned_heuristic | 12.8 ± 0.0 | 24.4 ± 0.6 | 0.79 ± 0.04 | 635.2 ± 1.6 | 133.1 ± 0.2 | 477.0 ± 11.8 | 4.8 ± 0.9 | 7.0 ± 1.5 | 0.9 ± 0.1 | 0.00 ± 0.00 |
| `tuned_max_margin` | tuned_heuristic | 55.6 ± 2.0 | 208.8 ± 8.1 | 3.51 ± 0.14 | 584.3 ± 1.6 | 78.9 ± 0.1 | 531.6 ± 10.7 | 8.2 ± 1.1 | 7.1 ± 1.7 | 3.7 ± 0.5 | 0.00 ± 0.00 |
| `tuned_balanced` | tuned_heuristic | 14.0 ± 0.2 | 27.2 ± 0.9 | 0.85 ± 0.04 | 619.4 ± 1.8 | 114.1 ± 0.5 | 492.6 ± 11.9 | 4.9 ± 0.9 | 7.1 ± 1.5 | 0.0 ± 0.0 | 0.02 ± 0.02 |
| `tuned_cost_p95` | tuned_heuristic | 23.4 ± 0.8 | 63.4 ± 3.7 | 1.37 ± 0.07 | 602.6 ± 1.8 | 91.9 ± 0.4 | 510.4 ± 11.4 | 7.4 ± 1.3 | 25.5 ± 12.0 | 0.3 ± 0.1 | 0.00 ± 0.00 |
| `tuned_same_budget` | tuned_heuristic | 16.1 ± 0.5 | 34.8 ± 1.5 | 0.99 ± 0.04 | 608.1 ± 1.6 | 96.9 ± 0.3 | 509.2 ± 11.6 | 5.1 ± 1.0 | 23.8 ± 10.5 | 0.2 ± 0.1 | 0.00 ± 0.00 |
| `tuned_same_service` | tuned_heuristic | 26.7 ± 6.4 | 96.4 ± 44.9 | 1.85 ± 0.56 | 616.6 ± 1.6 | 103.9 ± 0.1 | 479.8 ± 14.9 | 6.3 ± 1.3 | 132.1 ± 70.4 | 0.2 ± 0.3 | 0.00 ± 0.00 |
| `ppo_min_cost` | learned | 323.8 ± 9.9 | 677.3 ± 34.0 | 19.86 ± 0.63 | 551.8 ± 1.7 | 61.1 ± 0.1 | 348.5 ± 9.7 | 37.4 ± 2.6 | 3.5 ± 0.2 | 4.4 ± 1.5 | 20.01 ± 0.25 |
| `ppo_min_wait` | learned | 12.9 ± 0.1 | 23.6 ± 0.8 | 0.81 ± 0.04 | 635.4 ± 1.4 | 133.4 ± 0.2 | 450.5 ± 13.4 | 4.8 ± 0.9 | 6.6 ± 1.4 | 14.2 ± 2.0 | 5.84 ± 0.89 |
| `ppo_max_margin` | learned | 63.4 ± 2.9 | 245.5 ± 12.2 | 4.05 ± 0.20 | 583.3 ± 1.6 | 78.4 ± 0.1 | 529.6 ± 10.6 | 8.9 ± 1.2 | 6.2 ± 1.1 | 1.0 ± 0.3 | 0.01 ± 0.00 |
| `ppo_balanced` | learned | 15.2 ± 0.3 | 29.7 ± 1.2 | 1.00 ± 0.06 | 603.7 ± 1.6 | 104.9 ± 0.5 | 409.5 ± 10.7 | 5.2 ± 0.9 | 5.1 ± 1.0 | 34.0 ± 0.2 | 23.97 ± 0.00 |
| `ppo_cost_p95` | learned | 52.7 ± 2.5 | 232.5 ± 16.0 | 3.76 ± 0.22 | 575.7 ± 1.7 | 76.2 ± 0.3 | 436.6 ± 10.0 | 7.7 ± 1.1 | 5.3 ± 1.0 | 32.6 ± 0.3 | 21.44 ± 0.29 |
| `ppo_same_budget` | learned | 17.7 ± 0.7 | 40.2 ± 2.8 | 1.09 ± 0.06 | 607.3 ± 1.6 | 95.4 ± 0.2 | 506.0 ± 11.5 | 5.3 ± 1.0 | 42.0 ± 19.0 | 0.2 ± 0.1 | 0.00 ± 0.00 |
| `ppo_same_service` | learned | 22.9 ± 6.8 | 78.4 ± 41.9 | 1.64 ± 0.60 | 604.1 ± 1.7 | 96.8 ± 0.1 | 492.8 ± 13.9 | 6.0 ± 1.3 | 115.1 ± 59.3 | 0.8 ± 0.5 | 0.00 ± 0.00 |
| `ppo_scratch_min_cost` | learned | 889.8 ± 56.6 | 1435.0 ± 0.0 | 38.11 ± 1.52 | 530.8 ± 4.5 | 60.2 ± 2.4 | 171.0 ± 17.3 | 149.6 ± 8.5 | 2.8 ± 0.2 | 1.2 ± 0.3 | 10.53 ± 0.44 |
| `ppo_scratch_min_wait` | learned | 13.3 ± 0.3 | 23.4 ± 0.9 | 0.83 ± 0.04 | 637.7 ± 1.2 | 132.9 ± 0.3 | 406.2 ± 12.3 | 4.8 ± 0.9 | 8.7 ± 1.0 | 30.9 ± 0.3 | 4.03 ± 0.14 |
| `ppo_cond` | learned | 13.5 ± 0.1 | 25.5 ± 0.5 | 0.83 ± 0.04 | 621.6 ± 1.7 | 116.4 ± 0.3 | 490.8 ± 11.9 | 4.8 ± 0.9 | 7.1 ± 1.5 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `ppo_cond_min_cost` | learned | 307.4 ± 6.9 | 623.3 ± 19.1 | 18.69 ± 0.35 | 552.7 ± 1.5 | 61.3 ± 0.1 | 354.6 ± 8.0 | 35.9 ± 2.5 | 3.6 ± 0.2 | 0.0 ± 0.0 | 19.99 ± 0.29 |
| `ppo_cond_min_wait` | learned | 12.9 ± 0.0 | 24.5 ± 0.5 | 0.80 ± 0.04 | 635.1 ± 1.6 | 133.0 ± 0.1 | 477.2 ± 12.0 | 4.8 ± 0.9 | 7.2 ± 1.5 | 0.4 ± 0.1 | 0.00 ± 0.00 |
| `ppo_cond_max_margin` | learned | 52.1 ± 2.2 | 194.2 ± 8.7 | 3.29 ± 0.15 | 584.6 ± 1.7 | 79.2 ± 0.1 | 531.4 ± 10.9 | 7.9 ± 0.9 | 7.5 ± 2.0 | 2.2 ± 0.5 | 0.06 ± 0.04 |
| `ppo_cond_balanced` | learned | 13.5 ± 0.1 | 25.5 ± 0.5 | 0.83 ± 0.04 | 621.6 ± 1.7 | 116.4 ± 0.3 | 490.8 ± 11.9 | 4.8 ± 0.9 | 7.1 ± 1.5 | 0.0 ± 0.0 | 0.00 ± 0.00 |

Objective scores (higher is better; each column is that objective's own score):

| manager | kind | min_cost | min_wait | max_margin | balanced | cost_s.t._p95_wait | p95 within threshold (share of seeds) |
|---|---|---|---|---|---|---|---|
| `fixed` | fixed | -0.991 ± 0.001 | -3.657 ± 1.474 | 0.789 ± 0.025 | -2.958 ± 1.507 | -5.053 ± 3.573 | 0.69 |
| `rule_based` | rule_based | -1.141 ± 0.005 | -2.075 ± 0.053 | 0.810 ± 0.020 | -0.821 ± 0.062 | -1.141 ± 0.005 | 1.00 |
| `random` | random | -1.071 ± 0.011 | -13.033 ± 0.924 | 0.672 ± 0.017 | -7.789 ± 0.566 | -27.022 ± 1.705 | 0.00 |
| `tuned_min_cost` | tuned_heuristic | -0.586 ± 0.001 | -33.772 ± 0.787 | 0.582 ± 0.013 | -20.777 ± 0.490 | -46.914 ± 1.604 | 0.00 |
| `tuned_min_wait` | tuned_heuristic | -1.270 ± 0.001 | -1.144 ± 0.015 | 0.784 ± 0.019 | -0.187 ± 0.038 | -1.270 ± 0.001 | 1.00 |
| `tuned_max_margin` | tuned_heuristic | -0.753 ± 0.001 | -7.078 ± 0.301 | 0.874 ± 0.018 | -3.896 ± 0.204 | -13.149 ± 0.675 | 0.00 |
| `tuned_balanced` | tuned_heuristic | -1.089 ± 0.004 | -1.295 ± 0.029 | 0.810 ± 0.019 | -0.253 ± 0.042 | -1.089 ± 0.004 | 1.00 |
| `tuned_cost_p95` | tuned_heuristic | -0.877 ± 0.004 | -2.550 ± 0.115 | 0.839 ± 0.019 | -1.263 ± 0.169 | -1.319 ± 0.266 | 0.62 |
| `tuned_same_budget` | tuned_heuristic | -0.925 ± 0.003 | -1.580 ± 0.069 | 0.837 ± 0.019 | -0.609 ± 0.117 | -0.925 ± 0.003 | 1.00 |
| `tuned_same_service` | tuned_heuristic | -0.991 ± 0.001 | -3.488 ± 1.266 | 0.789 ± 0.024 | -2.889 ± 1.427 | -5.093 ± 3.580 | 0.69 |
| `ppo_min_cost` | learned | -0.583 ± 0.001 | -36.354 ± 1.259 | 0.573 ± 0.016 | -22.375 ± 0.750 | -52.028 ± 2.831 | 0.00 |
| `ppo_min_wait` | learned | -1.273 ± 0.002 | -1.123 ± 0.015 | 0.740 ± 0.022 | -0.262 ± 0.041 | -1.273 ± 0.002 | 1.00 |
| `ppo_max_margin` | learned | -0.748 ± 0.001 | -8.270 ± 0.449 | 0.871 ± 0.017 | -4.588 ± 0.282 | -16.204 ± 1.016 | 0.00 |
| `ppo_balanced` | learned | -1.001 ± 0.004 | -1.306 ± 0.044 | 0.673 ± 0.018 | -0.498 ± 0.049 | -1.001 ± 0.004 | 1.00 |
| `ppo_cost_p95` | learned | -0.727 ± 0.003 | -6.284 ± 0.365 | 0.718 ± 0.016 | -3.505 ± 0.226 | -15.102 ± 1.337 | 0.00 |
| `ppo_same_budget` | learned | -0.910 ± 0.002 | -1.814 ± 0.109 | 0.832 ± 0.019 | -0.949 ± 0.214 | -0.910 ± 0.002 | 1.00 |
| `ppo_same_service` | learned | -0.923 ± 0.001 | -3.016 ± 1.353 | 0.810 ± 0.023 | -2.402 ± 1.375 | -4.621 ± 3.177 | 0.81 |
| `ppo_scratch_min_cost` | learned | -0.574 ± 0.023 | -99.658 ± 4.377 | 0.281 ± 0.028 | -60.892 ± 2.685 | -115.157 ± 0.023 | 0.00 |
| `ppo_scratch_min_wait` | learned | -1.268 ± 0.003 | -1.178 ± 0.043 | 0.668 ± 0.020 | -0.466 ± 0.046 | -1.268 ± 0.003 | 1.00 |
| `ppo_cond` | learned | -1.110 ± 0.003 | -1.236 ± 0.015 | 0.807 ± 0.020 | -0.216 ± 0.039 | -1.110 ± 0.003 | 1.00 |
| `ppo_cond_min_cost` | learned | -0.585 ± 0.001 | -34.225 ± 0.772 | 0.583 ± 0.013 | -21.059 ± 0.479 | -47.525 ± 1.595 | 0.00 |
| `ppo_cond_min_wait` | learned | -1.269 ± 0.001 | -1.146 ± 0.015 | 0.784 ± 0.020 | -0.188 ± 0.038 | -1.269 ± 0.001 | 1.00 |
| `ppo_cond_max_margin` | learned | -0.756 ± 0.001 | -6.605 ± 0.331 | 0.874 ± 0.018 | -3.576 ± 0.209 | -11.941 ± 0.729 | 0.00 |
| `ppo_cond_balanced` | learned | -1.110 ± 0.003 | -1.236 ± 0.015 | 0.807 ± 0.020 | -0.216 ± 0.039 | -1.110 ± 0.003 | 1.00 |

## Verdicts (paired difference of the objective's own score, a minus b, on held-out seeds)

| objective | scenario | a | b | a score | b score | a - b (± CI95) | verdict |
|---|---|---|---|---|---|---|---|
| min_cost | normal_week | `ppo_min_cost` | `tuned_min_cost` | -0.5881 | -0.5898 | +0.0018 ± 0.0008 | a beats b |
| min_cost | normal_week | `ppo_min_cost` | `rule_based` | -0.5881 | -1.1246 | +0.5365 ± 0.0034 | a beats b |
| min_cost | normal_week | `ppo_min_cost` | `fixed` | -0.5881 | -1.0005 | +0.4124 ± 0.0008 | a beats b |
| min_cost | normal_week | `ppo_scratch_min_cost` | `tuned_min_cost` | -0.5760 | -0.5898 | +0.0138 ± 0.0269 | a matches (difference not significant) b |
| min_cost | normal_week | `ppo_scratch_min_cost` | `rule_based` | -0.5760 | -1.1246 | +0.5486 ± 0.0263 | a beats b |
| min_cost | normal_week | `ppo_scratch_min_cost` | `ppo_min_cost` | -0.5760 | -0.5881 | +0.0121 ± 0.0268 | a matches (difference not significant) b |
| min_cost | normal_week | `tuned_min_cost` | `rule_based` | -0.5898 | -1.1246 | +0.5348 ± 0.0032 | a beats b |
| min_cost | normal_week | `tuned_min_cost` | `fixed` | -0.5898 | -1.0005 | +0.4107 ± 0.0004 | a beats b |
| min_cost | normal_week | `ppo_cond_min_cost` | `tuned_min_cost` | -0.5897 | -0.5898 | +0.0001 ± 0.0001 | a matches (difference not significant) b |
| min_cost | normal_week | `ppo_cond_min_cost` | `rule_based` | -0.5897 | -1.1246 | +0.5349 ± 0.0033 | a beats b |
| min_cost | normal_week | `ppo_cond_min_cost` | `ppo_min_cost` | -0.5897 | -0.5881 | -0.0016 ± 0.0008 | a loses to b |
| min_wait | normal_week | `ppo_min_wait` | `tuned_min_wait` | -1.0271 | -1.0116 | -0.0155 ± 0.0070 | a loses to b |
| min_wait | normal_week | `ppo_min_wait` | `rule_based` | -1.0271 | -1.5871 | +0.5600 ± 0.0250 | a beats b |
| min_wait | normal_week | `ppo_min_wait` | `fixed` | -1.0271 | -1.2593 | +0.2322 ± 0.0251 | a beats b |
| min_wait | normal_week | `ppo_scratch_min_wait` | `tuned_min_wait` | -1.0725 | -1.0116 | -0.0609 ± 0.0355 | a loses to b |
| min_wait | normal_week | `ppo_scratch_min_wait` | `rule_based` | -1.0725 | -1.5871 | +0.5145 ± 0.0425 | a beats b |
| min_wait | normal_week | `ppo_scratch_min_wait` | `ppo_min_wait` | -1.0725 | -1.0271 | -0.0454 ± 0.0371 | a loses to b |
| min_wait | normal_week | `tuned_min_wait` | `rule_based` | -1.0116 | -1.5871 | +0.5755 ± 0.0220 | a beats b |
| min_wait | normal_week | `tuned_min_wait` | `fixed` | -1.0116 | -1.2593 | +0.2477 ± 0.0233 | a beats b |
| min_wait | normal_week | `ppo_cond_min_wait` | `tuned_min_wait` | -1.0109 | -1.0116 | +0.0007 ± 0.0012 | a matches (difference not significant) b |
| min_wait | normal_week | `ppo_cond_min_wait` | `rule_based` | -1.0109 | -1.5871 | +0.5761 ± 0.0221 | a beats b |
| min_wait | normal_week | `ppo_cond_min_wait` | `ppo_min_wait` | -1.0109 | -1.0271 | +0.0162 ± 0.0070 | a beats b |
| max_margin | normal_week | `ppo_max_margin` | `tuned_max_margin` | 0.7598 | 0.7600 | -0.0003 ± 0.0007 | a matches (difference not significant) b |
| max_margin | normal_week | `ppo_max_margin` | `rule_based` | 0.7598 | 0.6786 | +0.0812 ± 0.0026 | a beats b |
| max_margin | normal_week | `ppo_max_margin` | `fixed` | 0.7598 | 0.6945 | +0.0653 ± 0.0027 | a beats b |
| max_margin | normal_week | `tuned_max_margin` | `rule_based` | 0.7600 | 0.6786 | +0.0815 ± 0.0024 | a beats b |
| max_margin | normal_week | `tuned_max_margin` | `fixed` | 0.7600 | 0.6945 | +0.0655 ± 0.0025 | a beats b |
| max_margin | normal_week | `ppo_cond_max_margin` | `tuned_max_margin` | 0.7597 | 0.7600 | -0.0003 ± 0.0012 | a matches (difference not significant) b |
| max_margin | normal_week | `ppo_cond_max_margin` | `rule_based` | 0.7597 | 0.6786 | +0.0812 ± 0.0024 | a beats b |
| max_margin | normal_week | `ppo_cond_max_margin` | `ppo_max_margin` | 0.7597 | 0.7598 | -0.0001 ± 0.0010 | a matches (difference not significant) b |
| balanced | normal_week | `ppo_balanced` | `tuned_balanced` | -0.4076 | -0.2486 | -0.1590 ± 0.0193 | a loses to b |
| balanced | normal_week | `ppo_balanced` | `rule_based` | -0.4076 | -0.5314 | +0.1238 ± 0.0210 | a beats b |
| balanced | normal_week | `ppo_balanced` | `fixed` | -0.4076 | -0.3338 | -0.0738 ± 0.0248 | a loses to b |
| balanced | normal_week | `tuned_balanced` | `rule_based` | -0.2486 | -0.5314 | +0.2829 ± 0.0187 | a beats b |
| balanced | normal_week | `tuned_balanced` | `fixed` | -0.2486 | -0.3338 | +0.0852 ± 0.0234 | a beats b |
| balanced | normal_week | `ppo_cond_balanced` | `tuned_balanced` | -0.1986 | -0.2486 | +0.0500 ± 0.0135 | a beats b |
| balanced | normal_week | `ppo_cond_balanced` | `rule_based` | -0.1986 | -0.5314 | +0.3328 ± 0.0175 | a beats b |
| balanced | normal_week | `ppo_cond_balanced` | `ppo_balanced` | -0.1986 | -0.4076 | +0.2090 ± 0.0170 | a beats b |
| cost_s.t._p95_wait | normal_week | `ppo_cost_p95` | `tuned_cost_p95` | -5.1764 | -0.8349 | -4.3415 ± 1.1303 | a loses to b |
| cost_s.t._p95_wait | normal_week | `ppo_cost_p95` | `rule_based` | -5.1764 | -1.1246 | -4.0518 ± 1.1315 | a loses to b |
| cost_s.t._p95_wait | normal_week | `ppo_cost_p95` | `fixed` | -5.1764 | -1.0005 | -4.1759 ± 1.1313 | a loses to b |
| cost_s.t._p95_wait | normal_week | `tuned_cost_p95` | `rule_based` | -0.8349 | -1.1246 | +0.2897 ± 0.0035 | a beats b |
| cost_s.t._p95_wait | normal_week | `tuned_cost_p95` | `fixed` | -0.8349 | -1.0005 | +0.1656 ± 0.0028 | a beats b |
| min_cost | flu_surge | `ppo_min_cost` | `tuned_min_cost` | -0.5829 | -0.5859 | +0.0030 ± 0.0010 | a beats b |
| min_cost | flu_surge | `ppo_min_cost` | `rule_based` | -0.5829 | -1.1414 | +0.5585 ± 0.0045 | a beats b |
| min_cost | flu_surge | `ppo_min_cost` | `fixed` | -0.5829 | -0.9909 | +0.4080 ± 0.0012 | a beats b |
| min_cost | flu_surge | `ppo_scratch_min_cost` | `tuned_min_cost` | -0.5741 | -0.5859 | +0.0118 ± 0.0223 | a matches (difference not significant) b |
| min_cost | flu_surge | `ppo_scratch_min_cost` | `rule_based` | -0.5741 | -1.1414 | +0.5674 ± 0.0222 | a beats b |
| min_cost | flu_surge | `ppo_scratch_min_cost` | `ppo_min_cost` | -0.5741 | -0.5829 | +0.0088 ± 0.0222 | a matches (difference not significant) b |
| min_cost | flu_surge | `tuned_min_cost` | `rule_based` | -0.5859 | -1.1414 | +0.5556 ± 0.0043 | a beats b |
| min_cost | flu_surge | `tuned_min_cost` | `fixed` | -0.5859 | -0.9909 | +0.4050 ± 0.0008 | a beats b |
| min_cost | flu_surge | `ppo_cond_min_cost` | `tuned_min_cost` | -0.5848 | -0.5859 | +0.0010 ± 0.0006 | a beats b |
| min_cost | flu_surge | `ppo_cond_min_cost` | `rule_based` | -0.5848 | -1.1414 | +0.5566 ± 0.0045 | a beats b |
| min_cost | flu_surge | `ppo_cond_min_cost` | `ppo_min_cost` | -0.5848 | -0.5829 | -0.0019 ± 0.0010 | a loses to b |
| min_wait | flu_surge | `ppo_min_wait` | `tuned_min_wait` | -1.1233 | -1.1441 | +0.0208 ± 0.0065 | a beats b |
| min_wait | flu_surge | `ppo_min_wait` | `rule_based` | -1.1233 | -2.0750 | +0.9517 ± 0.0454 | a beats b |
| min_wait | flu_surge | `ppo_min_wait` | `fixed` | -1.1233 | -3.6568 | +2.5335 ± 1.4786 | a beats b |
| min_wait | flu_surge | `ppo_scratch_min_wait` | `tuned_min_wait` | -1.1780 | -1.1441 | -0.0339 ± 0.0419 | a matches (difference not significant) b |
| min_wait | flu_surge | `ppo_scratch_min_wait` | `rule_based` | -1.1780 | -2.0750 | +0.8970 ± 0.0606 | a beats b |
| min_wait | flu_surge | `ppo_scratch_min_wait` | `ppo_min_wait` | -1.1780 | -1.1233 | -0.0547 ± 0.0408 | a loses to b |
| min_wait | flu_surge | `tuned_min_wait` | `rule_based` | -1.1441 | -2.0750 | +0.9309 ± 0.0442 | a beats b |
| min_wait | flu_surge | `tuned_min_wait` | `fixed` | -1.1441 | -3.6568 | +2.5127 ± 1.4785 | a beats b |
| min_wait | flu_surge | `ppo_cond_min_wait` | `tuned_min_wait` | -1.1459 | -1.1441 | -0.0018 ± 0.0016 | a loses to b |
| min_wait | flu_surge | `ppo_cond_min_wait` | `rule_based` | -1.1459 | -2.0750 | +0.9291 ± 0.0442 | a beats b |
| min_wait | flu_surge | `ppo_cond_min_wait` | `ppo_min_wait` | -1.1459 | -1.1233 | -0.0226 ± 0.0066 | a loses to b |
| max_margin | flu_surge | `ppo_max_margin` | `tuned_max_margin` | 0.8706 | 0.8739 | -0.0033 ± 0.0020 | a loses to b |
| max_margin | flu_surge | `ppo_max_margin` | `rule_based` | 0.8706 | 0.8096 | +0.0610 ± 0.0047 | a beats b |
| max_margin | flu_surge | `ppo_max_margin` | `fixed` | 0.8706 | 0.7887 | +0.0819 ± 0.0221 | a beats b |
| max_margin | flu_surge | `tuned_max_margin` | `rule_based` | 0.8739 | 0.8096 | +0.0643 ± 0.0051 | a beats b |
| max_margin | flu_surge | `tuned_max_margin` | `fixed` | 0.8739 | 0.7887 | +0.0852 ± 0.0216 | a beats b |
| max_margin | flu_surge | `ppo_cond_max_margin` | `tuned_max_margin` | 0.8736 | 0.8739 | -0.0003 ± 0.0016 | a matches (difference not significant) b |
| max_margin | flu_surge | `ppo_cond_max_margin` | `rule_based` | 0.8736 | 0.8096 | +0.0640 ± 0.0046 | a beats b |
| max_margin | flu_surge | `ppo_cond_max_margin` | `ppo_max_margin` | 0.8736 | 0.8706 | +0.0031 ± 0.0023 | a beats b |
| balanced | flu_surge | `ppo_balanced` | `tuned_balanced` | -0.4976 | -0.2526 | -0.2449 ± 0.0265 | a loses to b |
| balanced | flu_surge | `ppo_balanced` | `rule_based` | -0.4976 | -0.8207 | +0.3232 ± 0.0460 | a beats b |
| balanced | flu_surge | `ppo_balanced` | `fixed` | -0.4976 | -2.9580 | +2.4605 ± 1.5150 | a beats b |
| balanced | flu_surge | `tuned_balanced` | `rule_based` | -0.2526 | -0.8207 | +0.5681 ± 0.0428 | a beats b |
| balanced | flu_surge | `tuned_balanced` | `fixed` | -0.2526 | -2.9580 | +2.7054 ± 1.5057 | a beats b |
| balanced | flu_surge | `ppo_cond_balanced` | `tuned_balanced` | -0.2163 | -0.2526 | +0.0364 ± 0.0165 | a beats b |
| balanced | flu_surge | `ppo_cond_balanced` | `rule_based` | -0.2163 | -0.8207 | +0.6045 ± 0.0387 | a beats b |
| balanced | flu_surge | `ppo_cond_balanced` | `ppo_balanced` | -0.2163 | -0.4976 | +0.2813 ± 0.0256 | a beats b |
| cost_s.t._p95_wait | flu_surge | `ppo_cost_p95` | `tuned_cost_p95` | -15.1023 | -1.3193 | -13.7830 ± 1.3029 | a loses to b |
| cost_s.t._p95_wait | flu_surge | `ppo_cost_p95` | `rule_based` | -15.1023 | -1.1414 | -13.9609 ± 1.3369 | a loses to b |
| cost_s.t._p95_wait | flu_surge | `ppo_cost_p95` | `fixed` | -15.1023 | -5.0534 | -10.0489 ± 3.9887 | a loses to b |
| cost_s.t._p95_wait | flu_surge | `tuned_cost_p95` | `rule_based` | -1.3193 | -1.1414 | -0.1779 ± 0.2642 | a matches (difference not significant) b |
| cost_s.t._p95_wait | flu_surge | `tuned_cost_p95` | `fixed` | -1.3193 | -5.0534 | +3.7341 ± 3.5084 | a beats b |

A verdict of 'beats' or 'loses to' means the 95% interval of the paired difference excludes zero; otherwise the two are reported as matching. The verdict is statistical, not practical: because seeds are paired, differences of a fraction of a percent of the score can be significant; read the size of the difference. The learned agents are warm-started by behaviour cloning from the tuned heuristic of the same objective and then fine-tuned with PPO, so a learned agent that 'matches' is largely reproducing that heuristic. Nothing outside this table should be read as a claim that a learned agent beats a baseline.
