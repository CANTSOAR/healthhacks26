#!/bin/bash
# Pull RL artefacts (policies, results, rollouts, scales) from deepstack into the repo.
R="$(cd "$(dirname "$0")/../.." && pwd)"
rsync -az deepstack:~/projects/hospitalgym_aryan/rl/policies/ "$R/rl/policies/"
rsync -az deepstack:~/projects/hospitalgym_aryan/rl/results/ "$R/rl/results/"
rsync -az deepstack:~/projects/hospitalgym_aryan/rl/rollouts/ "$R/rl/rollouts/"
rsync -az deepstack:~/projects/hospitalgym_aryan/rl/reward_scales.json "$R/rl/reward_scales.json"
