#!/bin/bash
# Runs ON deepstack: one tmux window per PPO run, all on the shared GPU.
#   HOURS=1.4 bash rl/scripts/remote_train.sh            # 5 cloned+fine-tuned agents, 2 from scratch, 1 weight-conditioned
#   HOURS=1.4 bash rl/scripts/remote_train.sh min_wait   # only the cloned+fine-tuned agent(s) named
# Logs: runs/<run>/log.txt   Best export: runs/<run>/best.{json,pt}   Latest: runs/<run>/latest.{json,pt}
# Stop one: tmux kill-window -t hospitalgym:rl_<run>   (exports stay valid; refresh_all.sh installs runs/*/best.*)
cd ~/projects/hospitalgym_aryan
H=${HOURS:-1.4}
OBJS=("$@"); ALL=0
[ ${#OBJS[@]} -eq 0 ] && { OBJS=(min_cost min_wait max_margin balanced cost_s.t._p95_wait); ALL=1; }
start() { name=$1; shift; mkdir -p runs/$name; tmux new-window -d -t hospitalgym -n rl_$name ".venv/bin/python -m rl.ppo --device cuda --run runs/$name --hours $H $* > runs/$name/stdout.txt 2>&1"; }
for o in "${OBJS[@]}"; do
  s=${o//cost_s.t._p95_wait/cost_p95}
  start ppo_$s --objective $o --ref tuned_$s --bc --bc-hours 168 ${PPO_ARGS:-}
done
if [ $ALL -eq 1 ]; then
  for o in min_cost min_wait; do   # from scratch: no behaviour cloning; the tuned heuristic only rides along as the paired reference
    start ppo_scratch_$o --objective $o --id ppo_scratch_$o --ref tuned_$o --lr 3e-4 --ent 0.01 --ent-final 0.001 --clip 0.2 --critic-warmup 1
  done
  start ppo_cond --conditioned --bc --bc-hours 168 --nv 16
fi
tmux list-windows -t hospitalgym -F "#W" | tr "\n" " "
