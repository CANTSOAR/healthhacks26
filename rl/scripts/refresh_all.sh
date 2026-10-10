#!/bin/bash
# One command for the morning wrap-up (run from the Mac, unattended, ~10 minutes):
#   1. push the current code (simulator + rl) to deepstack
#   2. pull the newest learned-policy exports that training has written on deepstack is implicit:
#      evaluation runs there against rl/policies/ on deepstack (tuned heuristics + latest PPO exports)
#   3. re-run held-out evaluation and re-record rollouts for every available manager
#   4. pull policies, results and rollouts back into the repo
# It does NOT retune or retrain. If the simulator changed since tuning/training, the artefacts say so:
# compare `sim_fingerprint` in rl/policies/*.json against rl/results/results.json.
set -u
R="$(cd "$(dirname "$0")/../.." && pwd)"
# Tuning and training write under runs/ on deepstack (code syncs never touch it); the remote script
# installs runs/*/best.* into rl/policies/ before evaluating, and pull.sh brings them back.
bash "$R/rl/scripts/sync.sh" || { echo "sync failed"; exit 1; }
ssh deepstack 'bash ~/projects/hospitalgym_aryan/rl/scripts/remote_eval_record.sh'
RC=$?
bash "$R/rl/scripts/pull.sh"
"$R/.venv/bin/python" - <<PY
import json, pathlib
r = json.loads(pathlib.Path("$R/rl/results/results.json").read_text())
i = json.loads(pathlib.Path("$R/rl/rollouts/index.json").read_text())
print("results:", r["generated"], "fingerprint", r["sim_fingerprint"], len(r["rows"]), "rows;", len(i), "rollouts")
PY
[ $RC -eq 0 ] && [ -f "$R/rl/results/results.json" ] && [ $(ls "$R/rl/rollouts/"*.json.gz 2>/dev/null | wc -l) -ge 4 ] && touch "$R/rl/R1_READY"
exit $RC
