#!/bin/bash
# Runs ON deepstack inside tmux: full rebuild against the simulator code currently synced.
#   stop PPO, archive old runs, re-measure scales, re-tune 4 heuristics, evaluate + record them,
#   then start 4 PPO runs (HOURS each). Marker: runs/regen_done (written after the heuristics are evaluated).
cd ~/projects/hospitalgym_aryan
for w in $(tmux list-windows -t hospitalgym -F '#W' | grep '^rl_ppo_'); do tmux kill-window -t hospitalgym:$w; done
TS=$(date +%H%M%S); mkdir -p runs/old_$TS
mv runs/tune_* runs/ppo_* runs/scales runs/refresh runs/tune_done runs/regen_done runs/old_$TS/ 2>/dev/null
rm -f rl/policies/ppo_* rl/policies/tuned_*
REMEASURE=1 bash rl/scripts/remote_tune.sh ${TUNE_ARGS:-} || exit 1
HOURS=${HOURS:-2.5} bash rl/scripts/remote_train.sh
bash rl/scripts/remote_eval_record.sh
echo done > runs/regen_done
