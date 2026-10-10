#!/bin/bash
# Runs ON deepstack (inside tmux): measure reward scales, then tune the four heuristics in parallel.
#   REMEASURE=1 re-measures rl/reward_scales.json first. Extra args are passed to rl.tune.
cd ~/projects/hospitalgym_aryan
PY=.venv/bin/python
mkdir -p runs/scales
if [ "${REMEASURE:-0}" = "1" ] || [ ! -f rl/reward_scales.json ]; then
  $PY -m rl.scripts.measure_scales --device cuda --seeds 64 --days 30 > runs/scales/log.txt 2>&1 || exit 1
fi
for o in min_cost min_wait balanced cost_s.t._p95_wait; do
  s=${o//cost_s.t._p95_wait/cost_p95}
  mkdir -p runs/tune_$s
  $PY -m rl.tune --objective $o --device cuda --run runs/tune_$s --out runs/tune_$s/best.json "$@" > runs/tune_$s/stdout.txt 2>&1 &
done
wait
$PY -m rl.scripts.install_policies
echo TUNING_DONE > runs/tune_done
