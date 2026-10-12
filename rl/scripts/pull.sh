#!/bin/bash
# Pull RL artefacts from deepstack into the repo.
#   bash rl/scripts/pull.sh            # the default hospital's policies, results, rollouts, scales + every rl/hospitals/<id>/
#   bash rl/scripts/pull.sh <id>       # same, but only that hospital's directory under rl/hospitals/
R="$(cd "$(dirname "$0")/../.." && pwd)"
D='deepstack:~/projects/hospitalgym_aryan'
rsync -az $D/rl/policies/ "$R/rl/policies/"
rsync -az $D/rl/results/ "$R/rl/results/"
rsync -az $D/rl/rollouts/ "$R/rl/rollouts/"
rsync -az $D/rl/reward_scales.json "$R/rl/reward_scales.json"
mkdir -p "$R/rl/hospitals"
if [ -n "${1:-}" ]; then
  mkdir -p "$R/rl/hospitals/$1"
  rsync -az $D/rl/hospitals/$1/ "$R/rl/hospitals/$1/" 2>/dev/null || true
else
  rsync -az $D/rl/hospitals/ "$R/rl/hospitals/" 2>/dev/null || true
fi
# drop local rollout files that the pulled index no longer lists (stale recordings from earlier calibrations)
for d in "$R/rl/rollouts" "$R"/rl/hospitals/*/rollouts; do
  [ -d "$d" ] || continue
  python3 - "$d" <<'PY'
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
done
