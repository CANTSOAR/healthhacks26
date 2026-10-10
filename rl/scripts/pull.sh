#!/bin/bash
# Pull RL artefacts (policies, results, rollouts, scales) from deepstack into the repo.
R="$(cd "$(dirname "$0")/../.." && pwd)"
rsync -az deepstack:~/projects/hospitalgym_aryan/rl/policies/ "$R/rl/policies/"
rsync -az deepstack:~/projects/hospitalgym_aryan/rl/results/ "$R/rl/results/"
rsync -az deepstack:~/projects/hospitalgym_aryan/rl/rollouts/ "$R/rl/rollouts/"
rsync -az deepstack:~/projects/hospitalgym_aryan/rl/reward_scales.json "$R/rl/reward_scales.json"
# drop local rollout files that the pulled index no longer lists (stale recordings from earlier calibrations)
python3 - "$R/rl/rollouts" <<'PY'
import json, pathlib, sys
d = pathlib.Path(sys.argv[1])
try:
    keep = {r["file"] for r in json.loads((d / "index.json").read_text())}
except Exception:
    keep = None
if keep:
    for f in d.glob("*.json.gz"):
        if f.name not in keep:
            f.unlink()
            print("removed stale", f.name)
PY
