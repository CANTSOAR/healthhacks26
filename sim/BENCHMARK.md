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
