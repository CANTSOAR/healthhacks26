"""Copy the newest tuner / trainer outputs from runs/*/best.{json,pt} into rl/policies/.

Training and tuning write under runs/ (never touched by code syncs); this installs them where
rl.load_manager looks. Run on the machine that holds runs/ (deepstack).
    python -m rl.scripts.install_policies [--runs runs]
"""
import argparse
import json
import shutil
from pathlib import Path

from rl.common import POLICY_DIR, write_json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="runs")
    a = ap.parse_args()
    POLICY_DIR.mkdir(parents=True, exist_ok=True)
    for f in sorted(Path(a.runs).glob("*/best.json")):
        try:
            d = json.loads(f.read_text())
        except Exception as e:                      # being written right now
            print("skip", f, e)
            continue
        if d.get("type") == "ppo":
            pt = f.with_suffix(".pt")
            if not pt.exists():
                continue
            shutil.copyfile(pt, POLICY_DIR / f"{d['id']}.pt.tmp")
            (POLICY_DIR / f"{d['id']}.pt.tmp").replace(POLICY_DIR / f"{d['id']}.pt")
            d["checkpoint"] = f"{d['id']}.pt"
        if "sim_behaviour_fingerprint" not in d and d.get("sim_fingerprint") == "8f9f6cc4b1a47804":
            d["sim_behaviour_fingerprint"] = "6ee020eaaf7eca57"      # M2 dynamics; stamped at install (run predates the field)
        d["installed_from"] = str(f)
        write_json(POLICY_DIR / f"{d['id']}.json", d, indent=1)
        print("installed", d["id"], "from", f)


if __name__ == "__main__":
    main()
