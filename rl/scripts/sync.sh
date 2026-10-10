#!/bin/bash
# Push the working tree to deepstack (same command as the simulator agent; never --delete).
rsync -az --exclude .venv --exclude node_modules --exclude .git --exclude .private --exclude docs --exclude '*.zip' \
  --exclude data/raw --exclude web --exclude runs --exclude __pycache__ \
  "$(cd "$(dirname "$0")/../.." && pwd)/" deepstack:~/projects/hospitalgym_aryan/
