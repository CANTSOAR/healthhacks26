#!/bin/bash
# Push the working tree to deepstack (never --delete). RL artefacts are produced ON deepstack and only ever pulled
# (pull.sh), so they are excluded here; pull right after anything is regenerated so both sides stay identical.
rsync -az --exclude .venv --exclude node_modules --exclude .git --exclude .private --exclude docs --exclude '*.zip' \
  --exclude data/raw --exclude web --exclude runs --exclude __pycache__ \
  --exclude rl/reward_scales.json --exclude 'rl/policies/*' --exclude 'rl/results/*' --exclude 'rl/rollouts/*' \
  "$(cd "$(dirname "$0")/../.." && pwd)/" deepstack:~/projects/hospitalgym_aryan/
