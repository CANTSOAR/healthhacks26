# Throughput (`python -m sim.bench`)

`normal_week`, default actions, one `step()` + one `observe()` per simulated hour, 1 warm-up day then 1 measured day.
Pool size P = 480 patient slots per hospital. hospital-days/s = B x simulated days / wall seconds.

## Local: MacBook, 4 cores, torch 2.2.2, CPU (4 threads) - measured 02:50 while other agents were running (load average ~10)

| B | ms/tick | hospital-days/s |
|---|---|---|
| 1 | 8.2 | 0.4 |
| 16 | 20.5 | 2.7 |
| 64 | 55.1 | 4.0 |

Enough for the viewer (one hospital advances ~120 ticks, i.e. 10 simulated hours, per wall second); not for training.

## deepstack: torch 2.8.0+cu128

CPU, 8 threads, load average ~10 (02:33):

| B | ms/tick | hospital-days/s |
|---|---|---|
| 1 | 3.8 | 0.9 |
| 16 | 6.6 | 8.4 |
| 64 | 15.1 | 14.8 |
| 256 | 24.5 | 36.3 |

CUDA (RTX A5500 16 GB). The GPU was shared with two RL training processes at 98-100 % utilisation for every
run after 01:50, so only the first row block is an uncontended measurement, and it predates two optimisations
(hourly pre-generation of arrivals, fewer dtype conversions: 3,400 -> 2,740 ATen calls per tick).

| When | GPU state | B | ms/tick | hospital-days/s | peak GPU MB |
|---|---|---|---|---|---|
| 01:46, earlier code | idle (9 MiB used, 0 %) | 64 | 19.4 | 11.5 | 23 |
| | | 1024 | 19.4 | 183 | 368 |
| | | 4096 | 39.1 | **364** | 1478 |
| 02:51, M2 code | shared, 98 % busy | 64 | 16.6 | 13.4 | 24 |
| | | 1024 | 18.6 | 191 | 398 |
| | | 4096 | 67.4 | 211 | 1574 |
| 02:51, M2 code, random hourly+daily actions | shared | 2048 | 35.8 | 199 | 786 |
| 02:33, M2 code | shared, 100 % busy | 8192 | 198.6 | 143 | 2905 |

Reading: the tick is latency-bound (about 1,000 small GPU kernels, ~17-19 ms) up to B of about 1,000-2,000 and
memory-bandwidth-bound above. Memory is not the limit: about 0.36 MB per hospital, so 16 GB would hold ~40,000.
The target of 300 hospital-days/s was met only on the idle GPU (364 at B = 4096); under the shared GPU it was
about 200-220. An uncontended re-measurement of the M2 code was not possible tonight and is not claimed.

Sizing: at ~200 hospital-days/s, a 30-day episode for 2,048 hospitals takes about 5 minutes; that is about
4,800 environment steps (hospital-hours) per second.

What would raise the ceiling (not done): fewer, larger kernels in the tick (stack the per-tick accumulators,
merge the five bay-class passes), int32 state tensors, or CUDA graphs / `torch.compile`.

## Round 2 (after M2; dynamics frozen by `sim/tests/test_golden.py`)

M2 code on deepstack CUDA, GPU shared with RL training (7 other processes, 6.3 GB in use, 100 % utilisation, host load ~13), 03:17:

| B | ms/tick | hospital-days/s | peak GPU MB |
|---|---|---|---|
| 1024 | 52.5 | 67.7 | 398 |
| 4096 | 155.6 | 91.4 | 1574 |
| 8192 | 273.9 | 103.9 | 3121 |

Trajectory-neutral op reduction (golden hashes identical on Mac CPU, deepstack CPU and deepstack CUDA):
in-place `masked_fill_` on tick-local tensors (41 sites) and `torch.where(mask, x, 0)` instead of `x * mask` in 8 accumulator sums.
ATen calls per tick (B = 4, CPU profiler, mid-hour ticks): 2,868 -> 2,664; calls that are real kernels: 1,592 -> 1,468 (-8 %).

Back-to-back on the shared GPU (0.5 simulated day each, 03:37-03:50, hospital-days/s):

| B | M2 tick, run 1 | reduced tick, run 1 | M2 tick, run 2 | reduced tick, run 2 |
|---|---|---|---|---|
| 1024 | 117.2 | 100.4 | 83.1 | 85.4 |
| 4096 | 130.9 | 117.4 | 92.3 | 97.8 |
| 8192 | 134.8 | 102.6 | 95.7 | 101.6 |

The spread between identical runs (117 vs 83) is larger than any effect of the change, so no speed-up can be claimed from
these measurements; only the 8 % lower kernel count is established. The tick remains latency-bound. An idle-GPU measurement
of the current code was still not possible.

### 1000-day run with structural actions (`python -m sim.scripts.long_run --days 1000 --batch 64 --device cpu --threads 8`)

deepstack CPU (host load ~14, shared with other agents). A random decision on every monthly head for every hospital at each
28-day boundary, default hourly/daily/weekly actions, conservation checked every simulated day.

Result (finished; raw progress log in `sim/scripts/long_run_1000d.json`): 64 hospitals x 1000 days in 5,224 s wall =
**12.25 hospital-days/s** on the shared CPU. Conservation residual 0 on every one of the 1000 days
(14,262,628 patients generated; 18,528 in the system at the end). Every hospital's layout version changed (mean 74 bumps).
Structural state at the end: main bays 28-92 (mean 67.9, start 68), ward beds 88-216 (mean 167.5, start 168), CT and X-ray
units at the cap of 8. 1,900 structural requests were rejected by rule (bounds). A random structural policy is a bad manager:
trailing LWBS was 21 %, p95 wait 629 min, and 1,142,781 arrivals (8 %) were turned away because a hospital's patient pool
was full; they are counted as `diverted`, so conservation still holds.

### Idle GPU, current code (09:18, 9 MiB in use and 0 % before the run; nothing else on the GPU)

`.venv/bin/python -m sim.bench --device cuda --batch 256 1024 4096 8192 16384 --days 1`

| B | ms/tick | hospital-days/s | peak GPU MB |
|---|---|---|---|
| 256 | 9.3 | 96 | 96 |
| 1024 | 10.2 | 348 | 392 |
| 4096 | 36.6 | **389** | 1543 |
| 8192 | 70.8 | 402 | 3063 |
| 16384 | 137.6 | 413 | 6117 |

The 300 hospital-days/s target is met on an idle GPU from B of about 1,000 upward. Per-tick latency at small batch is now
about 9-10 ms (it was 19.4 ms in the first idle measurement at 01:46); above B of about 2,000 the tick is bound by
memory bandwidth, so larger batches add little (389 -> 413 from 4,096 to 16,384). Minutes earlier, with two other
processes on the GPU, the same command gave 157 (B = 1024) and 173 (B = 4096).
