#!/bin/bash
# One command per hospital, run from the Mac. Everything heavy happens on deepstack in tmux session `hospitalgym`.
#   bash rl/scripts/run_hospital.sh <hospital_id>
#   PPO_HOURS=0 bash rl/scripts/run_hospital.sh mount_sinai         # tuned heuristics only
#   LEGACY=1 RECORD_ALL=1 bash rl/scripts/run_hospital.sh rwjuh_nb   # also retune the legacy weighted heuristics, record every manager
# sync -> measure scales -> tune -> [PPO] -> headline (select on validation, evaluate held-out over the ensemble) ->
# results table -> record baseline + selected-policy rollouts -> pull. Prints the headline sentence at the end.
# The calibration (catalog/hospitals/<id>.calibration.yaml, .ensemble.json) is whatever is in the working tree now;
# its fingerprint is stamped on every artefact, so re-run this after the calibration changes.
set -u
H=${1:?usage: run_hospital.sh <hospital_id>}
R="$(cd "$(dirname "$0")/../.." && pwd)"
[ -f "$R/catalog/hospitals/$H.yaml" ] || { echo "catalog/hospitals/$H.yaml does not exist"; exit 1; }
bash "$R/rl/scripts/sync.sh" || { echo "sync failed"; exit 1; }
ENVV="PPO_HOURS=${PPO_HOURS:-0.9} LEGACY=${LEGACY:-0} RECORD_ALL=${RECORD_ALL:-0} SKIP_TUNE=${SKIP_TUNE:-0} SKIP_BUDGET_TUNE=${SKIP_BUDGET_TUNE:-0} GPU_WORKERS=${GPU_WORKERS:-2} CPU_WORKERS=${CPU_WORKERS:-10} EVAL_SEEDS=${EVAL_SEEDS:-32} EVAL_DAYS=${EVAL_DAYS:-30}"
[ -n "${TUNE_ARGS:-}" ] && ENVV="$ENVV TUNE_ARGS='${TUNE_ARGS}'"
[ -n "${PPO_ARGS:-}" ] && ENVV="$ENVV PPO_ARGS='${PPO_ARGS}'"
[ -n "${HEADLINE_ARGS:-}" ] && ENVV="$ENVV HEADLINE_ARGS='${HEADLINE_ARGS}'"
ssh deepstack "cd ~/projects/hospitalgym_aryan && mkdir -p runs/$H && rm -f runs/$H/done runs/$H/failed && tmux kill-window -t hospitalgym:rl_$H 2>/dev/null; tmux new-window -d -t hospitalgym -n rl_$H \"$ENVV bash rl/scripts/remote_hospital.sh $H > runs/$H/stdout.txt 2>&1\""
echo "started on deepstack (tmux window hospitalgym:rl_$H); polling runs/$H/pipeline.log"
if [ "${NOWAIT:-0}" = "1" ]; then exit 0; fi
while true; do
  sleep ${POLL:-60}
  ST=$(ssh deepstack "cd ~/projects/hospitalgym_aryan && tail -n 1 runs/$H/pipeline.log 2>/dev/null; [ -f runs/$H/done ] && echo __DONE__; [ -f runs/$H/failed ] && echo __FAILED__; tmux list-windows -t hospitalgym -F '#W' | grep -qx rl_$H || echo __GONE__")
  echo "$ST" | head -n 1
  echo "$ST" | grep -q __DONE__ && break
  echo "$ST" | grep -q "__FAILED__\|__GONE__" && { ssh deepstack "cat ~/projects/hospitalgym_aryan/runs/$H/failed 2>/dev/null; tail -n 20 ~/projects/hospitalgym_aryan/runs/$H/stdout.txt"; bash "$R/rl/scripts/pull.sh" "$H"; exit 1; }
done
bash "$R/rl/scripts/pull.sh" "$H"
"$R/.venv/bin/python" - <<PY
import json, pathlib
d = json.loads(pathlib.Path("$R/rl/hospitals/$H/headline.json").read_text())
print("\n" + d["sentence"] + "\n")
print("report: rl/hospitals/$H/HEADLINE.md   (calibration fingerprint %s, %d ensemble member(s))" % (d["calibration_fingerprint"], d["ensemble"]["n_members"]))
PY
