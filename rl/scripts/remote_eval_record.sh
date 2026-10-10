#!/bin/bash
# Runs ON deepstack: held-out evaluation (GPU) and rollout recording (CPU, parallel) for every
# available manager, in parallel. Logs under runs/refresh/. Exit code 0 only if both succeed.
cd ~/projects/hospitalgym_aryan
PY=.venv/bin/python
mkdir -p runs/refresh
$PY -m rl.scripts.install_policies > runs/refresh/install.log 2>&1
$PY -m rl.evaluate --device cuda --seeds ${EVAL_SEEDS:-32} --days ${EVAL_DAYS:-30} > runs/refresh/eval.log 2>&1 &
E1=$!
$PY -m rl.record --all --days ${EVAL_DAYS:-30} --jobs ${RECORD_JOBS:-14} > runs/refresh/record.log 2>&1 &
E2=$!
wait $E1; R1=$?
wait $E2; R2=$?
tail -n 2 runs/refresh/eval.log runs/refresh/record.log
echo "eval exit $R1, record exit $R2"
[ $R1 -eq 0 ] && [ $R2 -eq 0 ]
