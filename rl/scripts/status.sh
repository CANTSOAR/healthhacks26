#!/bin/bash
# What is running on deepstack and how each PPO run compares with its tuned heuristic on the paired validation rows.
ssh deepstack 'cd ~/projects/hospitalgym_aryan && tmux list-windows -t hospitalgym -F "#W" | tr "\n" " "; echo; for d in runs/ppo_*; do echo "== $d"; grep "^EP" $d/log.txt | tail -n ${N:-3} | python3 -c "
import sys,json
for l in sys.stdin:
    d=json.loads(l[3:]); print({k:d[k] for k in d if k in (\"ep\",\"minutes\",\"val\",\"train\",\"ref\",\"diff\",\"diff_ci95\",\"lag\",\"val_p95\",\"diff_min_cost\",\"diff_min_wait\",\"diff_balanced\")})"; grep "^it\|finished" $d/log.txt | tail -n 1 | cut -c1-160; python3 -c "
import json,sys
try:
    b=json.load(open(\"$d/progress.json\"))[\"best\"]; print(\"best:\", {k:b[k] for k in (\"ep\",\"sel\",\"val\",\"ref\") if k in b})
except Exception as e: print(\"no best yet\")"; done; date'
