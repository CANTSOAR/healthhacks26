#!/bin/bash
# Runs ON deepstack (inside tmux): the whole per-hospital pipeline against the code and catalog currently synced.
#   bash rl/scripts/remote_hospital.sh <hospital_id>
# Steps: measure scales -> tune the operator heuristics (and the legacy ones with LEGACY=1) -> [PPO on the operator
# objectives, PPO_HOURS each, 0 = skip] -> headline (selection on validation seeds, held-out evaluation over the
# calibration ensemble) -> legacy results table -> rollouts (baseline + selected policy; all managers with RECORD_ALL=1).
# Everything for the hospital lives under runs/<id>/ ; markers: runs/<id>/done (success) or runs/<id>/failed.
# Env: PPO_HOURS (default 0.9), LEGACY (default 0), GPU_WORKERS (2), CPU_WORKERS (10), TUNE_ARGS, PPO_ARGS, HEADLINE_ARGS,
#      EVAL_SEEDS (32), EVAL_DAYS (30), SKIP_TUNE=1 (reuse installed heuristics), SKIP_BUDGET_TUNE=1 (keep runs/<id>/tune_same_budget),
#      RECORD_ALL (0).
H=${1:?hospital id}
cd ~/projects/hospitalgym_aryan
PY=.venv/bin/python
export HOSPITAL_ID=$H
RUN=runs/$H
DEV=${DEVICE:-cuda}   # DEVICE=cpu GPU_WORKERS=0 CPU_WORKERS=<cores> TUNE_ARGS="--chunk 2" on a many-core CPU box
GW=${GPU_WORKERS:-2}; CW=${CPU_WORKERS:-10}
mkdir -p $RUN/scales
rm -f $RUN/done $RUN/failed
fail() { echo "FAILED: $1" | tee $RUN/failed; exit 1; }
step() { echo "[$(date +%H:%M:%S)] $1" | tee -a $RUN/pipeline.log; }
PD=$($PY -c "from rl.common import paths; print(paths('$H').policies)")
SC=$($PY -c "from rl.common import paths; print(paths('$H').scales)")
RO=$($PY -c "from rl.common import paths; print(paths('$H').rollouts)")
step "calibration: $($PY -c "from rl.common import calibration_status; print(calibration_status('$H'))")"

if [ "${SKIP_TUNE:-0}" != "1" ]; then
  step "measure scales"
  $PY -m rl.scripts.measure_scales --hospital $H --device $DEV --seeds 64 --days 30 > $RUN/scales/log.txt 2>&1 || fail "measure_scales"
  cp $SC $RUN/scales/reward_scales.json
  step "tune operator heuristics"
  # same_budget first; the cost objective then starts its search from that solution (already better flow at lower
  # labour cost) instead of from the baseline, where ten noisy constraints make the first generations a lottery.
  mkdir -p $RUN/tune_same_budget $RUN/tune_same_service
  [ "${SKIP_BUDGET_TUNE:-0}" = "1" ] && [ -f $RUN/tune_same_budget/best.json ] || \
  $PY -m rl.tune --hospital $H --objective same_budget_better_flow --gpu-workers $GW --cpu-workers $CW --run $RUN/tune_same_budget \
      --out $RUN/tune_same_budget/best.json ${TUNE_ARGS:-} > $RUN/tune_same_budget/stdout.txt 2>&1 || fail "tuning same_budget"
  $PY -m rl.tune --hospital $H --objective same_service_lower_cost --gpu-workers $GW --cpu-workers $CW --run $RUN/tune_same_service \
      --out $RUN/tune_same_service/best.json --init $RUN/tune_same_budget/best.json --std 0.12 --seeds 8 ${TUNE_ARGS:-} \
      > $RUN/tune_same_service/stdout.txt 2>&1 || fail "tuning same_service"
  if [ "${LEGACY:-0}" = "1" ]; then
    step "tune legacy weighted heuristics"
    for o in min_cost min_wait max_margin balanced cost_s.t._p95_wait; do
      s=${o//cost_s.t._p95_wait/cost_p95}
      mkdir -p $RUN/tune_$s
      $PY -m rl.tune --hospital $H --objective $o --device $DEV --run $RUN/tune_$s --out $RUN/tune_$s/best.json > $RUN/tune_$s/stdout.txt 2>&1 &
    done
    wait
  fi
  $PY -m rl.scripts.install_policies --hospital $H --runs $RUN > $RUN/install.log 2>&1
  for s in same_budget same_service; do [ -f $PD/tuned_$s.json ] || fail "tuning $s (see $RUN/tune_$s/stdout.txt)"; done
fi

PH=${PPO_HOURS:-0.9}
if [ "$PH" != "0" ]; then
  step "PPO on the operator objectives ($PH h each, in parallel)"
  for o in same_budget_better_flow same_service_lower_cost; do
    s=$($PY -c "from rl.objectives import OPERATOR_SLUG; print(OPERATOR_SLUG['$o'])")
    rm -rf $RUN/ppo_$s; mkdir -p $RUN/ppo_$s
    $PY -m rl.ppo --hospital $H --objective $o --device $DEV --run $RUN/ppo_$s --hours $PH --ref tuned_$s --bc --bc-hours 240 --bc-epochs 12 \
        --scenarios normal_week flu_surge nursing_absences --members 2 --episode-hours 480 --T 48 --envs 1152 --nv 32 ${PPO_ARGS:-} \
        > $RUN/ppo_$s/stdout.txt 2>&1 &
  done
  wait
  $PY -m rl.scripts.install_policies --hospital $H --runs $RUN >> $RUN/install.log 2>&1
fi

step "headline"
$PY -m rl.headline --hospital $H --device $DEV --gpu-workers $GW --cpu-workers $CW --seeds ${EVAL_SEEDS:-32} --days ${EVAL_DAYS:-30} \
    ${HEADLINE_ARGS:-} > $RUN/headline_stdout.txt 2>&1 || fail "headline (see $RUN/headline_stdout.txt)"

step "legacy results table"
$PY -m rl.evaluate --hospital $H --device $DEV --seeds ${EVAL_SEEDS:-32} --days ${EVAL_DAYS:-30} > $RUN/eval.log 2>&1 || fail "evaluate"

step "rollouts"
SEL=$($PY -c "
import json
from rl.common import paths
d = json.load(open(paths('$H').home / 'headline.json'))
print(' '.join(sorted({o['selected'] for o in d['objectives'].values() if o.get('selected')})))")
if [ "${RECORD_ALL:-0}" = "1" ]; then
  rm -f $RO/*.json.gz
  $PY -m rl.record --hospital $H --all --days ${EVAL_DAYS:-30} --jobs 20 > $RUN/record.log 2>&1 || fail "record"
else
  rm -f $RO/fixed__*.json.gz; for m in $SEL; do rm -f $RO/${m}__*.json.gz; done
  $PY -m rl.record --hospital $H --manager fixed $SEL --days ${EVAL_DAYS:-30} --jobs 8 > $RUN/record.log 2>&1 || fail "record"
  $PY -c "
from rl.record import write_index
from rl.common import paths
print(len(write_index(paths('$H').rollouts)), 'rollouts indexed')" >> $RUN/record.log 2>&1
fi
step "done"
date > $RUN/done
