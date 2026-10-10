#!/bin/bash
# Runs ON deepstack: start one tmux window per objective, each a PPO run on the shared GPU.
#   HOURS=3 bash rl/scripts/remote_train.sh [objective ...]        (default: all four)
# Logs: runs/ppo_<slug>/log.txt   Best export: runs/ppo_<slug>/best.{json,pt}   Latest: runs/ppo_<slug>/latest.{json,pt}
# Stop one: tmux kill-window -t hospitalgym:rl_ppo_<slug>     (exports stay valid; refresh_all.sh installs them)
cd ~/projects/hospitalgym_aryan
OBJS=("$@"); [ ${#OBJS[@]} -eq 0 ] && OBJS=(min_cost min_wait balanced cost_s.t._p95_wait)
for o in "${OBJS[@]}"; do
  s=${o//cost_s.t._p95_wait/cost_p95}
  mkdir -p runs/ppo_$s
  tmux new-window -d -t hospitalgym -n rl_ppo_$s \
    ".venv/bin/python -m rl.ppo --objective $o --device cuda --run runs/ppo_$s --ref tuned_$s --bc --hours ${HOURS:-3} ${PPO_ARGS:-} > runs/ppo_$s/stdout.txt 2>&1"
done
tmux list-windows -t hospitalgym
