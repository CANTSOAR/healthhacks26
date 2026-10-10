# Held-out evaluation of hospital managers (all numbers SIMULATED)

Generated 2026-10-10T09:16:54-0400; simulator behaviour fingerprint `6ee020eaaf7eca57` (hash of a fixed-seed trajectory; staleness is keyed on it), file hash `2d54b0d8fc49f8b1` (information only).

Managers tuned or trained against a different simulator behaviour: none.

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

Term scales (fixed-default manager, per hour): cost 2.42e+04, wait 163, lwbs 0.133, safety 0.02, boarding 0.404, staff 1, revenue 2.42e+04, labor 3.21e+03.

## Learned agents: how each was produced and how it did against its tuned heuristic (held-out)

- `ppo_min_cost` (normal_week): beats tuned_min_cost on the min_cost score (+0.0007 ± 0.0005). PPO, warm-started by behaviour cloning from tuned_min_cost, then 3,310,720 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_min_wait` (normal_week): matches (difference not significant) tuned_min_wait on the min_wait score (+0.0019 ± 0.0022). PPO, warm-started by behaviour cloning from tuned_min_wait, then 3,611,776 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_max_margin` (normal_week): matches (difference not significant) tuned_max_margin on the max_margin score (-0.0004 ± 0.0006). PPO, warm-started by behaviour cloning from tuned_max_margin, then 902,272 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_balanced` (normal_week): matches (difference not significant) tuned_balanced on the balanced score (+0.0006 ± 0.0008). PPO, warm-started by behaviour cloning from tuned_balanced, then 300,160 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_cost_p95` (normal_week): beats tuned_cost_p95 on the cost_s.t._p95_wait score (+0.0862 ± 0.0032). PPO, warm-started by behaviour cloning from tuned_cost_p95, then 1,805,440 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_scratch_min_cost` (normal_week): beats tuned_min_cost on the min_cost score (+0.0756 ± 0.0027). PPO, trained from scratch (no behaviour cloning), then 3,912,832 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_scratch_min_wait` (normal_week): matches (difference not significant) tuned_min_wait on the min_wait score (+0.0044 ± 0.0048). PPO, trained from scratch (no behaviour cloning), then 3,912,832 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_cond` (normal_week): no tuned heuristic to compare with. PPO, warm-started by behaviour cloning from the tuned heuristics of min_cost, min_wait, max_margin, balanced, then 257,280 PPO environment steps; acts greedily. One network conditioned on the reward weights in its observation. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_cond_min_cost` (normal_week): beats tuned_min_cost on the min_cost score (+0.0008 ± 0.0005). PPO, warm-started by behaviour cloning from the tuned heuristics of min_cost, min_wait, max_margin, balanced, then 257,280 PPO environment steps; acts greedily. One network conditioned on the reward weights in its observation. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_cond_min_wait` (normal_week): matches (difference not significant) tuned_min_wait on the min_wait score (-0.0005 ± 0.0005). PPO, warm-started by behaviour cloning from the tuned heuristics of min_cost, min_wait, max_margin, balanced, then 257,280 PPO environment steps; acts greedily. One network conditioned on the reward weights in its observation. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_cond_max_margin` (normal_week): matches (difference not significant) tuned_max_margin on the max_margin score (+0.0002 ± 0.0006). PPO, warm-started by behaviour cloning from the tuned heuristics of min_cost, min_wait, max_margin, balanced, then 257,280 PPO environment steps; acts greedily. One network conditioned on the reward weights in its observation. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_cond_balanced` (normal_week): beats tuned_balanced on the balanced score (+0.0021 ± 0.0017). PPO, warm-started by behaviour cloning from the tuned heuristics of min_cost, min_wait, max_margin, balanced, then 257,280 PPO environment steps; acts greedily. One network conditioned on the reward weights in its observation. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_min_cost` (flu_surge): beats tuned_min_cost on the min_cost score (+0.0029 ± 0.0012). PPO, warm-started by behaviour cloning from tuned_min_cost, then 3,310,720 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_min_wait` (flu_surge): matches (difference not significant) tuned_min_wait on the min_wait score (+0.0715 ± 0.1160). PPO, warm-started by behaviour cloning from tuned_min_wait, then 3,611,776 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_max_margin` (flu_surge): matches (difference not significant) tuned_max_margin on the max_margin score (+0.0002 ± 0.0012). PPO, warm-started by behaviour cloning from tuned_max_margin, then 902,272 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_balanced` (flu_surge): matches (difference not significant) tuned_balanced on the balanced score (+0.0006 ± 0.0022). PPO, warm-started by behaviour cloning from tuned_balanced, then 300,160 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_cost_p95` (flu_surge): loses to tuned_cost_p95 on the cost_s.t._p95_wait score (-0.3528 ± 0.2220). PPO, warm-started by behaviour cloning from tuned_cost_p95, then 1,805,440 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_scratch_min_cost` (flu_surge): beats tuned_min_cost on the min_cost score (+0.0762 ± 0.0027). PPO, trained from scratch (no behaviour cloning), then 3,912,832 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_scratch_min_wait` (flu_surge): matches (difference not significant) tuned_min_wait on the min_wait score (+0.0651 ± 0.1168). PPO, trained from scratch (no behaviour cloning), then 3,912,832 PPO environment steps; acts greedily. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_cond` (flu_surge): no tuned heuristic to compare with. PPO, warm-started by behaviour cloning from the tuned heuristics of min_cost, min_wait, max_margin, balanced, then 257,280 PPO environment steps; acts greedily. One network conditioned on the reward weights in its observation. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_cond_min_cost` (flu_surge): beats tuned_min_cost on the min_cost score (+0.0029 ± 0.0012). PPO, warm-started by behaviour cloning from the tuned heuristics of min_cost, min_wait, max_margin, balanced, then 257,280 PPO environment steps; acts greedily. One network conditioned on the reward weights in its observation. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_cond_min_wait` (flu_surge): matches (difference not significant) tuned_min_wait on the min_wait score (-0.0013 ± 0.0018). PPO, warm-started by behaviour cloning from the tuned heuristics of min_cost, min_wait, max_margin, balanced, then 257,280 PPO environment steps; acts greedily. One network conditioned on the reward weights in its observation. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_cond_max_margin` (flu_surge): matches (difference not significant) tuned_max_margin on the max_margin score (+0.0008 ± 0.0014). PPO, warm-started by behaviour cloning from the tuned heuristics of min_cost, min_wait, max_margin, balanced, then 257,280 PPO environment steps; acts greedily. One network conditioned on the reward weights in its observation. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.
- `ppo_cond_balanced` (flu_surge): beats tuned_balanced on the balanced score (+0.0065 ± 0.0040). PPO, warm-started by behaviour cloning from the tuned heuristics of min_cost, min_wait, max_margin, balanced, then 257,280 PPO environment steps; acts greedily. One network conditioned on the reward weights in its observation. All numbers simulated. Whether it beats, matches or loses to its tuned heuristic is stated in rl/results/RESULTS.md.

## Scenario `normal_week`

| manager | kind | wait mean (min) | wait p95 (min) | LWBS % | cost/day ($k) | labor cost/day ($k) | margin/day ($k) | deaths/10k | boarding h/day | overtime h/day | diversion h/day |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `fixed` | fixed | 23.1 ± 0.8 | 63.0 ± 3.9 | 1.42 ± 0.07 | 579.8 ± 1.6 | 77.0 ± 0.0 | 447.1 ± 10.9 | 5.4 ± 1.0 | 5.8 ± 1.0 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `rule_based` | rule_based | 18.0 ± 0.3 | 43.9 ± 1.7 | 1.13 ± 0.05 | 581.9 ± 1.5 | 80.6 ± 0.3 | 446.6 ± 11.1 | 4.9 ± 1.1 | 4.6 ± 0.2 | 0.1 ± 0.0 | 0.00 ± 0.00 |
| `random` | random | 60.8 ± 3.7 | 235.9 ± 10.5 | 3.95 ± 0.24 | 578.8 ± 1.5 | 85.5 ± 0.6 | 392.1 ± 10.6 | 10.1 ± 1.5 | 4.3 ± 0.2 | 61.9 ± 0.5 | 12.06 ± 0.15 |
| `tuned_min_cost` | tuned_heuristic | 130.6 ± 3.0 | 323.1 ± 9.2 | 8.65 ± 0.21 | 549.9 ± 1.5 | 56.2 ± 0.1 | 395.2 ± 10.2 | 16.2 ± 1.8 | 3.9 ± 0.2 | 0.0 ± 0.0 | 9.13 ± 0.31 |
| `tuned_min_wait` | tuned_heuristic | 12.2 ± 0.0 | 20.0 ± 0.0 | 0.77 ± 0.03 | 585.6 ± 1.5 | 91.5 ± 0.3 | 442.1 ± 11.4 | 4.4 ± 1.0 | 4.5 ± 0.2 | 0.4 ± 0.1 | 0.00 ± 0.00 |
| `tuned_max_margin` | tuned_heuristic | 23.5 ± 0.8 | 68.3 ± 3.8 | 1.46 ± 0.06 | 563.8 ± 1.6 | 66.6 ± 0.1 | 475.9 ± 11.3 | 5.4 ± 1.1 | 4.5 ± 0.2 | 0.3 ± 0.1 | 0.00 ± 0.00 |
| `tuned_balanced` | tuned_heuristic | 12.7 ± 0.1 | 24.8 ± 0.3 | 0.79 ± 0.03 | 579.9 ± 1.5 | 82.8 ± 0.2 | 449.1 ± 11.2 | 4.4 ± 1.0 | 4.5 ± 0.2 | 0.0 ± 0.0 | 0.00 ± 0.01 |
| `tuned_cost_p95` | tuned_heuristic | 15.7 ± 0.2 | 33.4 ± 0.9 | 0.99 ± 0.04 | 571.7 ± 1.6 | 69.6 ± 0.2 | 451.3 ± 11.1 | 4.8 ± 1.0 | 4.9 ± 0.4 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `ppo_min_cost` | learned | 131.0 ± 3.0 | 323.6 ± 9.0 | 8.66 ± 0.21 | 550.2 ± 1.5 | 56.1 ± 0.0 | 397.9 ± 10.3 | 16.2 ± 1.8 | 3.9 ± 0.2 | 0.0 ± 0.0 | 8.42 ± 0.31 |
| `ppo_min_wait` | learned | 12.4 ± 0.1 | 20.0 ± 0.0 | 0.79 ± 0.04 | 587.1 ± 1.4 | 93.1 ± 0.4 | 417.4 ± 11.8 | 4.3 ± 1.0 | 4.4 ± 0.2 | 14.6 ± 2.6 | 6.13 ± 1.10 |
| `ppo_max_margin` | learned | 23.7 ± 0.9 | 69.7 ± 4.7 | 1.48 ± 0.07 | 563.7 ± 1.6 | 66.6 ± 0.1 | 475.7 ± 11.3 | 5.4 ± 1.1 | 4.5 ± 0.2 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `ppo_balanced` | learned | 12.7 ± 0.1 | 24.5 ± 0.5 | 0.79 ± 0.04 | 579.9 ± 1.5 | 82.9 ± 0.2 | 449.1 ± 11.2 | 4.4 ± 1.0 | 4.5 ± 0.2 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `ppo_cost_p95` | learned | 17.8 ± 0.4 | 37.0 ± 1.3 | 1.20 ± 0.06 | 554.5 ± 1.4 | 63.0 ± 0.2 | 387.5 ± 10.1 | 5.0 ± 1.0 | 4.0 ± 0.2 | 34.1 ± 0.2 | 23.89 ± 0.03 |
| `ppo_scratch_min_cost` | learned | 694.7 ± 17.5 | 1430.8 ± 3.9 | 31.45 ± 0.50 | 525.4 ± 1.5 | 50.3 ± 0.2 | 217.6 ± 9.1 | 93.8 ± 4.0 | 2.9 ± 0.2 | 0.2 ± 0.1 | 7.34 ± 0.29 |
| `ppo_scratch_min_wait` | learned | 12.3 ± 0.1 | 20.3 ± 0.4 | 0.77 ± 0.04 | 590.7 ± 1.4 | 93.8 ± 0.2 | 406.7 ± 11.3 | 4.3 ± 1.1 | 5.6 ± 0.5 | 31.2 ± 0.2 | 3.44 ± 0.09 |
| `ppo_cond` | learned | 12.7 ± 0.1 | 24.5 ± 0.5 | 0.79 ± 0.03 | 579.4 ± 1.5 | 82.5 ± 0.2 | 450.1 ± 11.2 | 4.4 ± 1.0 | 4.5 ± 0.2 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `ppo_cond_min_cost` | learned | 131.4 ± 3.1 | 323.1 ± 9.2 | 8.68 ± 0.21 | 550.2 ± 1.5 | 56.1 ± 0.0 | 397.7 ± 10.2 | 16.4 ± 1.8 | 3.9 ± 0.2 | 0.0 ± 0.0 | 8.03 ± 0.29 |
| `ppo_cond_min_wait` | learned | 12.2 ± 0.0 | 20.0 ± 0.0 | 0.77 ± 0.03 | 585.3 ± 1.5 | 91.5 ± 0.2 | 443.0 ± 11.4 | 4.4 ± 1.0 | 4.5 ± 0.2 | 0.3 ± 0.1 | 0.00 ± 0.00 |
| `ppo_cond_max_margin` | learned | 23.6 ± 0.8 | 69.2 ± 4.2 | 1.47 ± 0.06 | 563.7 ± 1.6 | 66.5 ± 0.1 | 476.0 ± 11.2 | 5.3 ± 1.1 | 4.5 ± 0.2 | 0.1 ± 0.1 | 0.01 ± 0.01 |
| `ppo_cond_balanced` | learned | 12.7 ± 0.1 | 24.5 ± 0.5 | 0.79 ± 0.03 | 579.4 ± 1.5 | 82.5 ± 0.2 | 450.1 ± 11.2 | 4.4 ± 1.0 | 4.5 ± 0.2 | 0.0 ± 0.0 | 0.00 ± 0.00 |

Objective scores (higher is better; each column is that objective's own score):

| manager | kind | min_cost | min_wait | max_margin | balanced | cost_s.t._p95_wait | p95 within threshold (share of seeds) |
|---|---|---|---|---|---|---|---|
| `fixed` | fixed | -1.001 ± 0.001 | -1.286 ± 0.059 | 0.771 ± 0.019 | -0.295 ± 0.052 | -1.469 ± 0.248 | 0.50 |
| `rule_based` | rule_based | -1.048 ± 0.004 | -0.938 ± 0.025 | 0.770 ± 0.019 | -0.053 ± 0.040 | -1.048 ± 0.004 | 1.00 |
| `random` | random | -1.111 ± 0.008 | -3.692 ± 0.239 | 0.676 ± 0.018 | -2.174 ± 0.166 | -15.772 ± 0.874 | 0.00 |
| `tuned_min_cost` | tuned_heuristic | -0.730 ± 0.001 | -8.131 ± 0.201 | 0.682 ± 0.018 | -4.875 ± 0.142 | -22.657 ± 0.765 | 0.00 |
| `tuned_min_wait` | tuned_heuristic | -1.189 ± 0.004 | -0.542 ± 0.007 | 0.763 ± 0.020 | 0.214 ± 0.033 | -1.189 ± 0.004 | 1.00 |
| `tuned_max_margin` | tuned_heuristic | -0.866 ± 0.001 | -1.313 ± 0.057 | 0.821 ± 0.020 | -0.274 ± 0.053 | -1.634 ± 0.277 | 0.28 |
| `tuned_balanced` | tuned_heuristic | -1.076 ± 0.003 | -0.578 ± 0.009 | 0.775 ± 0.019 | 0.204 ± 0.033 | -1.076 ± 0.003 | 1.00 |
| `tuned_cost_p95` | tuned_heuristic | -0.905 ± 0.002 | -0.779 ± 0.017 | 0.779 ± 0.019 | 0.053 ± 0.034 | -0.905 ± 0.002 | 1.00 |
| `ppo_min_cost` | learned | -0.729 ± 0.001 | -8.197 ± 0.200 | 0.686 ± 0.018 | -4.915 ± 0.142 | -22.695 ± 0.752 | 0.00 |
| `ppo_min_wait` | learned | -1.210 ± 0.005 | -0.540 ± 0.007 | 0.720 ± 0.020 | 0.121 ± 0.040 | -1.210 ± 0.005 | 1.00 |
| `ppo_max_margin` | learned | -0.865 ± 0.001 | -1.330 ± 0.065 | 0.821 ± 0.019 | -0.282 ± 0.055 | -1.764 ± 0.354 | 0.28 |
| `ppo_balanced` | learned | -1.077 ± 0.003 | -0.578 ± 0.009 | 0.775 ± 0.019 | 0.205 ± 0.033 | -1.077 ± 0.003 | 1.00 |
| `ppo_cost_p95` | learned | -0.819 ± 0.002 | -0.830 ± 0.033 | 0.668 ± 0.017 | -0.208 ± 0.040 | -0.819 ± 0.002 | 1.00 |
| `ppo_scratch_min_cost` | learned | -0.654 ± 0.003 | -39.064 ± 0.836 | 0.375 ± 0.016 | -25.943 ± 0.586 | -114.886 ± 0.322 | 0.00 |
| `ppo_scratch_min_wait` | learned | -1.219 ± 0.003 | -0.537 ± 0.008 | 0.702 ± 0.019 | 0.019 ± 0.036 | -1.219 ± 0.003 | 1.00 |
| `ppo_cond` | learned | -1.072 ± 0.002 | -0.578 ± 0.008 | 0.776 ± 0.019 | 0.207 ± 0.033 | -1.072 ± 0.002 | 1.00 |
| `ppo_cond_min_cost` | learned | -0.729 ± 0.001 | -8.228 ± 0.205 | 0.686 ± 0.018 | -4.941 ± 0.147 | -22.656 ± 0.763 | 0.00 |
| `ppo_cond_min_wait` | learned | -1.189 ± 0.003 | -0.542 ± 0.007 | 0.764 ± 0.020 | 0.215 ± 0.033 | -1.189 ± 0.003 | 1.00 |
| `ppo_cond_max_margin` | learned | -0.865 ± 0.001 | -1.324 ± 0.056 | 0.821 ± 0.019 | -0.277 ± 0.051 | -1.711 ± 0.310 | 0.25 |
| `ppo_cond_balanced` | learned | -1.072 ± 0.002 | -0.578 ± 0.008 | 0.776 ± 0.019 | 0.207 ± 0.033 | -1.072 ± 0.002 | 1.00 |

## Scenario `flu_surge`

| manager | kind | wait mean (min) | wait p95 (min) | LWBS % | cost/day ($k) | labor cost/day ($k) | margin/day ($k) | deaths/10k | boarding h/day | overtime h/day | diversion h/day |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `fixed` | fixed | 38.5 ± 3.9 | 149.1 ± 21.8 | 2.53 ± 0.36 | 587.5 ± 1.6 | 76.3 ± 0.1 | 505.1 ± 13.4 | 7.0 ± 1.2 | 81.3 ± 48.1 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `rule_based` | rule_based | 22.4 ± 0.7 | 65.5 ± 4.2 | 1.42 ± 0.08 | 590.7 ± 1.5 | 82.2 ± 0.4 | 524.0 ± 11.6 | 5.4 ± 0.9 | 9.7 ± 2.8 | 0.4 ± 0.2 | 0.00 ± 0.00 |
| `random` | random | 78.2 ± 5.0 | 288.8 ± 12.3 | 5.13 ± 0.33 | 584.6 ± 1.5 | 84.8 ± 0.6 | 443.3 ± 10.9 | 12.2 ± 1.8 | 5.2 ± 0.4 | 61.9 ± 0.5 | 12.06 ± 0.15 |
| `tuned_min_cost` | tuned_heuristic | 192.9 ± 4.6 | 423.8 ± 9.2 | 12.69 ± 0.29 | 552.2 ± 1.5 | 55.9 ± 0.1 | 415.2 ± 9.4 | 23.2 ± 2.1 | 4.0 ± 0.2 | 0.0 ± 0.0 | 15.15 ± 0.39 |
| `tuned_min_wait` | tuned_heuristic | 12.5 ± 0.0 | 20.8 ± 0.6 | 0.79 ± 0.05 | 594.0 ± 1.6 | 91.9 ± 0.2 | 518.1 ± 11.9 | 4.5 ± 0.9 | 7.1 ± 1.5 | 1.2 ± 1.2 | 0.00 ± 0.00 |
| `tuned_max_margin` | tuned_heuristic | 35.2 ± 1.1 | 122.0 ± 5.1 | 2.19 ± 0.10 | 572.6 ± 1.6 | 66.8 ± 0.1 | 550.3 ± 11.1 | 6.1 ± 1.0 | 8.1 ± 2.2 | 1.3 ± 0.3 | 0.00 ± 0.00 |
| `tuned_balanced` | tuned_heuristic | 13.0 ± 0.1 | 25.0 ± 0.0 | 0.81 ± 0.04 | 590.6 ± 1.7 | 85.3 ± 0.2 | 521.5 ± 11.8 | 4.4 ± 0.9 | 7.1 ± 1.5 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `tuned_cost_p95` | tuned_heuristic | 18.3 ± 0.5 | 42.7 ± 1.9 | 1.14 ± 0.07 | 582.3 ± 1.6 | 72.0 ± 0.3 | 523.6 ± 11.8 | 6.0 ± 1.2 | 18.9 ± 7.6 | 0.1 ± 0.1 | 0.00 ± 0.00 |
| `ppo_min_cost` | learned | 194.3 ± 4.6 | 426.1 ± 9.0 | 12.75 ± 0.28 | 552.4 ± 1.5 | 55.7 ± 0.1 | 417.4 ± 9.3 | 23.5 ± 2.1 | 4.0 ± 0.2 | 0.0 ± 0.0 | 14.27 ± 0.40 |
| `ppo_min_wait` | learned | 12.5 ± 0.1 | 20.2 ± 0.3 | 0.78 ± 0.04 | 594.5 ± 1.4 | 93.4 ± 0.3 | 497.4 ± 12.8 | 4.5 ± 0.9 | 6.7 ± 1.5 | 11.6 ± 2.3 | 4.91 ± 0.96 |
| `ppo_max_margin` | learned | 36.6 ± 1.1 | 128.0 ± 5.2 | 2.28 ± 0.09 | 572.2 ± 1.6 | 66.5 ± 0.1 | 550.4 ± 11.1 | 6.0 ± 1.0 | 7.6 ± 1.8 | 0.3 ± 0.1 | 0.00 ± 0.00 |
| `ppo_balanced` | learned | 13.0 ± 0.1 | 25.0 ± 0.0 | 0.81 ± 0.04 | 590.6 ± 1.7 | 85.3 ± 0.2 | 521.5 ± 11.8 | 4.4 ± 0.9 | 7.1 ± 1.5 | 0.0 ± 0.0 | 0.00 ± 0.00 |
| `ppo_cost_p95` | learned | 24.1 ± 0.9 | 62.8 ± 3.6 | 1.65 ± 0.09 | 562.5 ± 1.5 | 63.1 ± 0.2 | 453.5 ± 10.5 | 5.7 ± 1.1 | 5.6 ± 1.3 | 34.1 ± 0.2 | 23.59 ± 0.08 |
| `ppo_scratch_min_cost` | learned | 820.5 ± 17.7 | 1435.0 ± 0.0 | 35.94 ± 0.47 | 526.0 ± 1.5 | 50.0 ± 0.2 | 220.0 ± 8.2 | 114.5 ± 4.6 | 2.9 ± 0.2 | 0.2 ± 0.1 | 9.64 ± 0.32 |
| `ppo_scratch_min_wait` | learned | 12.5 ± 0.1 | 20.8 ± 0.6 | 0.78 ± 0.04 | 597.7 ± 1.2 | 93.5 ± 0.2 | 451.6 ± 12.5 | 4.5 ± 0.9 | 8.3 ± 0.8 | 31.7 ± 0.3 | 3.77 ± 0.07 |
| `ppo_cond` | learned | 12.9 ± 0.1 | 24.8 ± 0.3 | 0.81 ± 0.04 | 589.7 ± 1.6 | 84.4 ± 0.2 | 522.5 ± 11.8 | 4.4 ± 0.9 | 7.1 ± 1.5 | 0.3 ± 0.6 | 0.00 ± 0.00 |
| `ppo_cond_min_cost` | learned | 194.8 ± 4.6 | 427.0 ± 9.5 | 12.78 ± 0.29 | 552.4 ± 1.5 | 55.7 ± 0.1 | 416.5 ± 9.2 | 23.3 ± 2.2 | 4.0 ± 0.2 | 0.0 ± 0.0 | 14.15 ± 0.40 |
| `ppo_cond_min_wait` | learned | 12.5 ± 0.1 | 20.8 ± 0.6 | 0.80 ± 0.05 | 593.7 ± 1.6 | 91.7 ± 0.2 | 518.6 ± 12.0 | 4.5 ± 0.9 | 7.2 ± 1.6 | 0.9 ± 1.2 | 0.00 ± 0.00 |
| `ppo_cond_max_margin` | learned | 36.3 ± 1.2 | 126.6 ± 5.6 | 2.27 ± 0.10 | 572.3 ± 1.7 | 66.5 ± 0.1 | 550.8 ± 11.5 | 6.2 ± 1.1 | 8.0 ± 2.0 | 0.5 ± 0.2 | 0.03 ± 0.03 |
| `ppo_cond_balanced` | learned | 12.9 ± 0.1 | 24.8 ± 0.3 | 0.81 ± 0.04 | 589.7 ± 1.6 | 84.4 ± 0.2 | 522.5 ± 11.8 | 4.4 ± 0.9 | 7.1 ± 1.5 | 0.3 ± 0.6 | 0.00 ± 0.00 |

Objective scores (higher is better; each column is that objective's own score):

| manager | kind | min_cost | min_wait | max_margin | balanced | cost_s.t._p95_wait | p95 within threshold (share of seeds) |
|---|---|---|---|---|---|---|---|
| `fixed` | fixed | -0.992 ± 0.001 | -2.717 ± 0.449 | 0.871 ± 0.023 | -1.938 ± 0.776 | -8.414 ± 1.820 | 0.00 |
| `rule_based` | rule_based | -1.068 ± 0.005 | -1.380 ± 0.114 | 0.904 ± 0.020 | -0.299 ± 0.088 | -1.615 ± 0.318 | 0.41 |
| `random` | random | -1.102 ± 0.008 | -5.290 ± 0.352 | 0.765 ± 0.019 | -3.170 ± 0.238 | -20.165 ± 1.020 | 0.00 |
| `tuned_min_cost` | tuned_heuristic | -0.726 ± 0.001 | -12.627 ± 0.300 | 0.716 ± 0.016 | -7.842 ± 0.200 | -31.039 ± 0.768 | 0.00 |
| `tuned_min_wait` | tuned_heuristic | -1.195 ± 0.003 | -0.670 ± 0.118 | 0.894 ± 0.020 | 0.203 ± 0.091 | -1.195 ± 0.003 | 1.00 |
| `tuned_max_margin` | tuned_heuristic | -0.869 ± 0.001 | -2.325 ± 0.091 | 0.949 ± 0.019 | -0.900 ± 0.079 | -6.038 ± 0.425 | 0.00 |
| `tuned_balanced` | tuned_heuristic | -1.109 ± 0.003 | -0.680 ± 0.061 | 0.900 ± 0.020 | 0.203 ± 0.058 | -1.109 ± 0.003 | 1.00 |
| `tuned_cost_p95` | tuned_heuristic | -0.936 ± 0.004 | -1.074 ± 0.087 | 0.903 ± 0.020 | -0.223 ± 0.108 | -0.936 ± 0.004 | 1.00 |
| `ppo_min_cost` | learned | -0.723 ± 0.001 | -12.781 ± 0.299 | 0.720 ± 0.016 | -7.952 ± 0.198 | -31.231 ± 0.753 | 0.00 |
| `ppo_min_wait` | learned | -1.214 ± 0.004 | -0.599 ± 0.009 | 0.858 ± 0.022 | 0.175 ± 0.038 | -1.214 ± 0.004 | 1.00 |
| `ppo_max_margin` | learned | -0.865 ± 0.001 | -2.437 ± 0.093 | 0.949 ± 0.019 | -0.961 ± 0.079 | -6.529 ± 0.431 | 0.00 |
| `ppo_balanced` | learned | -1.109 ± 0.003 | -0.679 ± 0.061 | 0.900 ± 0.020 | 0.204 ± 0.058 | -1.109 ± 0.003 | 1.00 |
| `ppo_cost_p95` | learned | -0.820 ± 0.003 | -1.353 ± 0.070 | 0.782 ± 0.018 | -0.481 ± 0.061 | -1.289 ± 0.223 | 0.56 |
| `ppo_scratch_min_cost` | learned | -0.650 ± 0.003 | -48.014 ± 0.865 | 0.379 ± 0.014 | -31.872 ± 0.590 | -115.234 ± 0.003 | 0.00 |
| `ppo_scratch_min_wait` | learned | -1.215 ± 0.002 | -0.605 ± 0.010 | 0.779 ± 0.022 | -0.007 ± 0.042 | -1.215 ± 0.002 | 1.00 |
| `ppo_cond` | learned | -1.097 ± 0.003 | -0.675 ± 0.059 | 0.901 ± 0.020 | 0.210 ± 0.056 | -1.097 ± 0.003 | 1.00 |
| `ppo_cond_min_cost` | learned | -0.723 ± 0.001 | -12.816 ± 0.302 | 0.718 ± 0.016 | -7.972 ± 0.200 | -31.309 ± 0.791 | 0.00 |
| `ppo_cond_min_wait` | learned | -1.192 ± 0.003 | -0.671 ± 0.118 | 0.895 ± 0.021 | 0.202 ± 0.091 | -1.192 ± 0.003 | 1.00 |
| `ppo_cond_max_margin` | learned | -0.865 ± 0.001 | -2.411 ± 0.103 | 0.950 ± 0.020 | -0.949 ± 0.082 | -6.412 ± 0.466 | 0.00 |
| `ppo_cond_balanced` | learned | -1.097 ± 0.003 | -0.675 ± 0.059 | 0.901 ± 0.020 | 0.210 ± 0.056 | -1.097 ± 0.003 | 1.00 |

## Verdicts (paired difference of the objective's own score, a minus b, on held-out seeds)

| objective | scenario | a | b | a score | b score | a - b (± CI95) | verdict |
|---|---|---|---|---|---|---|---|
| min_cost | normal_week | `ppo_min_cost` | `tuned_min_cost` | -0.7292 | -0.7300 | +0.0007 ± 0.0005 | a beats b |
| min_cost | normal_week | `ppo_min_cost` | `rule_based` | -0.7292 | -1.0478 | +0.3185 ± 0.0036 | a beats b |
| min_cost | normal_week | `ppo_min_cost` | `fixed` | -0.7292 | -1.0006 | +0.2714 ± 0.0004 | a beats b |
| min_cost | normal_week | `ppo_scratch_min_cost` | `tuned_min_cost` | -0.6543 | -0.7300 | +0.0756 ± 0.0027 | a beats b |
| min_cost | normal_week | `ppo_scratch_min_cost` | `rule_based` | -0.6543 | -1.0478 | +0.3934 ± 0.0047 | a beats b |
| min_cost | normal_week | `ppo_scratch_min_cost` | `ppo_min_cost` | -0.6543 | -0.7292 | +0.0749 ± 0.0026 | a beats b |
| min_cost | normal_week | `tuned_min_cost` | `rule_based` | -0.7300 | -1.0478 | +0.3178 ± 0.0033 | a beats b |
| min_cost | normal_week | `tuned_min_cost` | `fixed` | -0.7300 | -1.0006 | +0.2707 ± 0.0006 | a beats b |
| min_cost | normal_week | `ppo_cond_min_cost` | `tuned_min_cost` | -0.7292 | -0.7300 | +0.0008 ± 0.0005 | a beats b |
| min_cost | normal_week | `ppo_cond_min_cost` | `rule_based` | -0.7292 | -1.0478 | +0.3186 ± 0.0036 | a beats b |
| min_cost | normal_week | `ppo_cond_min_cost` | `ppo_min_cost` | -0.7292 | -0.7292 | +0.0001 ± 0.0000 | a beats b |
| min_wait | normal_week | `ppo_min_wait` | `tuned_min_wait` | -0.5400 | -0.5418 | +0.0019 ± 0.0022 | a matches (difference not significant) b |
| min_wait | normal_week | `ppo_min_wait` | `rule_based` | -0.5400 | -0.9383 | +0.3984 ± 0.0226 | a beats b |
| min_wait | normal_week | `ppo_min_wait` | `fixed` | -0.5400 | -1.2863 | +0.7463 ± 0.0557 | a beats b |
| min_wait | normal_week | `ppo_scratch_min_wait` | `tuned_min_wait` | -0.5374 | -0.5418 | +0.0044 ± 0.0048 | a matches (difference not significant) b |
| min_wait | normal_week | `ppo_scratch_min_wait` | `rule_based` | -0.5374 | -0.9383 | +0.4009 ± 0.0225 | a beats b |
| min_wait | normal_week | `ppo_scratch_min_wait` | `ppo_min_wait` | -0.5374 | -0.5400 | +0.0026 ± 0.0054 | a matches (difference not significant) b |
| min_wait | normal_week | `tuned_min_wait` | `rule_based` | -0.5418 | -0.9383 | +0.3965 ± 0.0221 | a beats b |
| min_wait | normal_week | `tuned_min_wait` | `fixed` | -0.5418 | -1.2863 | +0.7445 ± 0.0551 | a beats b |
| min_wait | normal_week | `ppo_cond_min_wait` | `tuned_min_wait` | -0.5423 | -0.5418 | -0.0005 ± 0.0005 | a matches (difference not significant) b |
| min_wait | normal_week | `ppo_cond_min_wait` | `rule_based` | -0.5423 | -0.9383 | +0.3960 ± 0.0219 | a beats b |
| min_wait | normal_week | `ppo_cond_min_wait` | `ppo_min_wait` | -0.5423 | -0.5400 | -0.0023 ± 0.0022 | a loses to b |
| max_margin | normal_week | `ppo_max_margin` | `tuned_max_margin` | 0.8207 | 0.8210 | -0.0004 ± 0.0006 | a matches (difference not significant) b |
| max_margin | normal_week | `ppo_max_margin` | `rule_based` | 0.8207 | 0.7703 | +0.0503 ± 0.0023 | a beats b |
| max_margin | normal_week | `ppo_max_margin` | `fixed` | 0.8207 | 0.7713 | +0.0493 ± 0.0027 | a beats b |
| max_margin | normal_week | `tuned_max_margin` | `rule_based` | 0.8210 | 0.7703 | +0.0507 ± 0.0025 | a beats b |
| max_margin | normal_week | `tuned_max_margin` | `fixed` | 0.8210 | 0.7713 | +0.0497 ± 0.0027 | a beats b |
| max_margin | normal_week | `ppo_cond_max_margin` | `tuned_max_margin` | 0.8212 | 0.8210 | +0.0002 ± 0.0006 | a matches (difference not significant) b |
| max_margin | normal_week | `ppo_cond_max_margin` | `rule_based` | 0.8212 | 0.7703 | +0.0508 ± 0.0024 | a beats b |
| max_margin | normal_week | `ppo_cond_max_margin` | `ppo_max_margin` | 0.8212 | 0.8207 | +0.0005 ± 0.0006 | a matches (difference not significant) b |
| balanced | normal_week | `ppo_balanced` | `tuned_balanced` | 0.2051 | 0.2045 | +0.0006 ± 0.0008 | a matches (difference not significant) b |
| balanced | normal_week | `ppo_balanced` | `rule_based` | 0.2051 | -0.0531 | +0.2582 ± 0.0166 | a beats b |
| balanced | normal_week | `ppo_balanced` | `fixed` | 0.2051 | -0.2948 | +0.4999 ± 0.0355 | a beats b |
| balanced | normal_week | `tuned_balanced` | `rule_based` | 0.2045 | -0.0531 | +0.2576 ± 0.0165 | a beats b |
| balanced | normal_week | `tuned_balanced` | `fixed` | 0.2045 | -0.2948 | +0.4993 ± 0.0356 | a beats b |
| balanced | normal_week | `ppo_cond_balanced` | `tuned_balanced` | 0.2066 | 0.2045 | +0.0021 ± 0.0017 | a beats b |
| balanced | normal_week | `ppo_cond_balanced` | `rule_based` | 0.2066 | -0.0531 | +0.2597 ± 0.0163 | a beats b |
| balanced | normal_week | `ppo_cond_balanced` | `ppo_balanced` | 0.2066 | 0.2051 | +0.0015 ± 0.0020 | a matches (difference not significant) b |
| cost_s.t._p95_wait | normal_week | `ppo_cost_p95` | `tuned_cost_p95` | -0.8186 | -0.9047 | +0.0862 ± 0.0032 | a beats b |
| cost_s.t._p95_wait | normal_week | `ppo_cost_p95` | `rule_based` | -0.8186 | -1.0478 | +0.2292 ± 0.0045 | a beats b |
| cost_s.t._p95_wait | normal_week | `ppo_cost_p95` | `fixed` | -0.8186 | -1.4694 | +0.6508 ± 0.2471 | a beats b |
| cost_s.t._p95_wait | normal_week | `tuned_cost_p95` | `rule_based` | -0.9047 | -1.0478 | +0.1430 ± 0.0030 | a beats b |
| cost_s.t._p95_wait | normal_week | `tuned_cost_p95` | `fixed` | -0.9047 | -1.4694 | +0.5646 ± 0.2469 | a beats b |
| min_cost | flu_surge | `ppo_min_cost` | `tuned_min_cost` | -0.7235 | -0.7264 | +0.0029 ± 0.0012 | a beats b |
| min_cost | flu_surge | `ppo_min_cost` | `rule_based` | -0.7235 | -1.0679 | +0.3444 ± 0.0051 | a beats b |
| min_cost | flu_surge | `ppo_min_cost` | `fixed` | -0.7235 | -0.9920 | +0.2685 ± 0.0006 | a beats b |
| min_cost | flu_surge | `ppo_scratch_min_cost` | `tuned_min_cost` | -0.6502 | -0.7264 | +0.0762 ± 0.0027 | a beats b |
| min_cost | flu_surge | `ppo_scratch_min_cost` | `rule_based` | -0.6502 | -1.0679 | +0.4177 ± 0.0053 | a beats b |
| min_cost | flu_surge | `ppo_scratch_min_cost` | `ppo_min_cost` | -0.6502 | -0.7235 | +0.0733 ± 0.0025 | a beats b |
| min_cost | flu_surge | `tuned_min_cost` | `rule_based` | -0.7264 | -1.0679 | +0.3415 ± 0.0045 | a beats b |
| min_cost | flu_surge | `tuned_min_cost` | `fixed` | -0.7264 | -0.9920 | +0.2657 ± 0.0013 | a beats b |
| min_cost | flu_surge | `ppo_cond_min_cost` | `tuned_min_cost` | -0.7234 | -0.7264 | +0.0029 ± 0.0012 | a beats b |
| min_cost | flu_surge | `ppo_cond_min_cost` | `rule_based` | -0.7234 | -1.0679 | +0.3444 ± 0.0051 | a beats b |
| min_cost | flu_surge | `ppo_cond_min_cost` | `ppo_min_cost` | -0.7234 | -0.7235 | +0.0001 ± 0.0000 | a beats b |
| min_wait | flu_surge | `ppo_min_wait` | `tuned_min_wait` | -0.5987 | -0.6702 | +0.0715 ± 0.1160 | a matches (difference not significant) b |
| min_wait | flu_surge | `ppo_min_wait` | `rule_based` | -0.5987 | -1.3798 | +0.7812 ± 0.1111 | a beats b |
| min_wait | flu_surge | `ppo_min_wait` | `fixed` | -0.5987 | -2.7173 | +2.1187 ± 0.4523 | a beats b |
| min_wait | flu_surge | `ppo_scratch_min_wait` | `tuned_min_wait` | -0.6050 | -0.6702 | +0.0651 ± 0.1168 | a matches (difference not significant) b |
| min_wait | flu_surge | `ppo_scratch_min_wait` | `rule_based` | -0.6050 | -1.3798 | +0.7748 ± 0.1112 | a beats b |
| min_wait | flu_surge | `ppo_scratch_min_wait` | `ppo_min_wait` | -0.6050 | -0.5987 | -0.0064 ± 0.0060 | a loses to b |
| min_wait | flu_surge | `tuned_min_wait` | `rule_based` | -0.6702 | -1.3798 | +0.7097 ± 0.0306 | a beats b |
| min_wait | flu_surge | `tuned_min_wait` | `fixed` | -0.6702 | -2.7173 | +2.0471 ± 0.4740 | a beats b |
| min_wait | flu_surge | `ppo_cond_min_wait` | `tuned_min_wait` | -0.6714 | -0.6702 | -0.0013 ± 0.0018 | a matches (difference not significant) b |
| min_wait | flu_surge | `ppo_cond_min_wait` | `rule_based` | -0.6714 | -1.3798 | +0.7084 ± 0.0310 | a beats b |
| min_wait | flu_surge | `ppo_cond_min_wait` | `ppo_min_wait` | -0.6714 | -0.5987 | -0.0728 ± 0.1160 | a matches (difference not significant) b |
| max_margin | flu_surge | `ppo_max_margin` | `tuned_max_margin` | 0.9495 | 0.9493 | +0.0002 ± 0.0012 | a matches (difference not significant) b |
| max_margin | flu_surge | `ppo_max_margin` | `rule_based` | 0.9495 | 0.9039 | +0.0456 ± 0.0031 | a beats b |
| max_margin | flu_surge | `ppo_max_margin` | `fixed` | 0.9495 | 0.8713 | +0.0782 ± 0.0156 | a beats b |
| max_margin | flu_surge | `tuned_max_margin` | `rule_based` | 0.9493 | 0.9039 | +0.0454 ± 0.0027 | a beats b |
| max_margin | flu_surge | `tuned_max_margin` | `fixed` | 0.9493 | 0.8713 | +0.0780 ± 0.0161 | a beats b |
| max_margin | flu_surge | `ppo_cond_max_margin` | `tuned_max_margin` | 0.9501 | 0.9493 | +0.0008 ± 0.0014 | a matches (difference not significant) b |
| max_margin | flu_surge | `ppo_cond_max_margin` | `rule_based` | 0.9501 | 0.9039 | +0.0462 ± 0.0027 | a beats b |
| max_margin | flu_surge | `ppo_cond_max_margin` | `ppo_max_margin` | 0.9501 | 0.9495 | +0.0006 ± 0.0017 | a matches (difference not significant) b |
| balanced | flu_surge | `ppo_balanced` | `tuned_balanced` | 0.2040 | 0.2034 | +0.0006 ± 0.0022 | a matches (difference not significant) b |
| balanced | flu_surge | `ppo_balanced` | `rule_based` | 0.2040 | -0.2989 | +0.5028 ± 0.0422 | a beats b |
| balanced | flu_surge | `ppo_balanced` | `fixed` | 0.2040 | -1.9378 | +2.1418 ± 0.7773 | a beats b |
| balanced | flu_surge | `tuned_balanced` | `rule_based` | 0.2034 | -0.2989 | +0.5023 ± 0.0420 | a beats b |
| balanced | flu_surge | `tuned_balanced` | `fixed` | 0.2034 | -1.9378 | +2.1412 ± 0.7777 | a beats b |
| balanced | flu_surge | `ppo_cond_balanced` | `tuned_balanced` | 0.2099 | 0.2034 | +0.0065 ± 0.0040 | a beats b |
| balanced | flu_surge | `ppo_cond_balanced` | `rule_based` | 0.2099 | -0.2989 | +0.5088 ± 0.0426 | a beats b |
| balanced | flu_surge | `ppo_cond_balanced` | `ppo_balanced` | 0.2099 | 0.2040 | +0.0059 ± 0.0050 | a beats b |
| cost_s.t._p95_wait | flu_surge | `ppo_cost_p95` | `tuned_cost_p95` | -1.2888 | -0.9360 | -0.3528 ± 0.2220 | a loses to b |
| cost_s.t._p95_wait | flu_surge | `ppo_cost_p95` | `rule_based` | -1.2888 | -1.6147 | +0.3260 ± 0.2746 | a beats b |
| cost_s.t._p95_wait | flu_surge | `ppo_cost_p95` | `fixed` | -1.2888 | -8.4139 | +7.1251 ± 1.8165 | a beats b |
| cost_s.t._p95_wait | flu_surge | `tuned_cost_p95` | `rule_based` | -0.9360 | -1.6147 | +0.6787 ± 0.3183 | a beats b |
| cost_s.t._p95_wait | flu_surge | `tuned_cost_p95` | `fixed` | -0.9360 | -8.4139 | +7.4779 ± 1.8180 | a beats b |

A verdict of 'beats' or 'loses to' means the 95% interval of the paired difference excludes zero; otherwise the two are reported as matching. The verdict is statistical, not practical: because seeds are paired, differences of a fraction of a percent of the score can be significant; read the size of the difference. The learned agents are warm-started by behaviour cloning from the tuned heuristic of the same objective and then fine-tuned with PPO, so a learned agent that 'matches' is largely reproducing that heuristic. Nothing outside this table should be read as a claim that a learned agent beats a baseline.
