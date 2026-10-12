"""Golden trajectories: freezes the M2 dynamics.

    .venv/bin/python -m sim.tests.golden            # compare with the stored file, print the result
    .venv/bin/python -m sim.tests.golden --write    # (re)generate the entry for this platform - only when a
                                                    # change of dynamics is intended and announced

Cases: normal_week and flu_surge x seeds 0 and 123 (B = 2 each: hospitals seed, seed + 1) x 5 days x
(a) default actions, (b) a fixed pseudo-random sequence over the hourly + daily heads.
The two seeds of a scenario run in one batch of 4 (hospitals are independent).
Stored per case: sha256 over the float32 bytes of every step metric of every hour, plus a few sums.
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
FILE = Path(__file__).resolve().parent / "golden_trajectories.json"
SCENARIOS = ["normal_week", "flu_surge"]
SEEDS = [0, 123]
DAYS = 5
SUMS = ["arrivals", "first_seen", "door_to_provider_sum_min", "lwbs", "admissions", "ed_departures", "deaths", "revenue", "cost_total"]


def platform_key(device: str) -> str:
    return f"{device}|{platform.machine()}|torch-{torch.__version__.split('+')[0]}"


def action_sequence(spec, hours: int):
    """Fixed pseudo-random actions for B = 2 over the hourly + daily heads (same for every seed)."""
    g = torch.Generator().manual_seed(20261010)
    heads = [h for h in spec if h["cadence"] in ("hourly", "daily")]
    return [{h["name"]: torch.randint(0, len(h["options"]), (2,), generator=g) for h in heads} for _ in range(hours)]


def compute(device: str = "cpu") -> dict:
    from sim import HospitalSim, load_scenario
    out = {}
    for sid in SCENARIOS:
        for mode in ("default", "random"):
            seeds = torch.tensor([s + i for s in SEEDS for i in range(2)])
            # Freeze simulator dynamics independently of a generated hospital calibration.  A calibration
            # intentionally changes the default roster and assumed service times; it has its own trajectory
            # and loader tests under twin/tests/.
            sim = HospitalSim(load_scenario(sid, overrides={"no_calibration": True}), batch_size=4, device=device, seed=seeds)
            seq = action_sequence(sim.action_spec(), 24 * DAYS) if mode == "random" else None
            rows = []
            for h in range(24 * DAYS):
                acts = sim.default_actions() if seq is None else {k: v.repeat(2).to(device) for k, v in seq[h].items()}
                m = sim.step(acts)
                rows.append(torch.stack([m[k] for k in sim.metric_names()], 1).to("cpu", torch.float32))
            traj = torch.stack(rows)                       # [hours, 4, metrics]
            names = sim.metric_names()
            for j, s in enumerate(SEEDS):
                part = traj[:, 2 * j:2 * j + 2].contiguous()
                out[f"{sid}|seed{s}|{mode}"] = dict(
                    sha256=hashlib.sha256(part.numpy().tobytes()).hexdigest(),
                    sums={k: round(float(part[:, :, names.index(k)].double().sum()), 3) for k in SUMS},
                    invalid_actions=int(sim.invalid_actions[2 * j:2 * j + 2].sum()),
                    generated=int(sim.next_ord[2 * j:2 * j + 2].sum()))
    return out


def load() -> dict:
    return json.loads(FILE.read_text()) if FILE.exists() else {}


if __name__ == "__main__":
    dev = "cuda" if "--cuda" in sys.argv else "cpu"
    got = compute(dev)
    store = load()
    key = platform_key(dev)
    if "--write" in sys.argv:
        store[key] = got
        FILE.write_text(json.dumps(store, indent=1, sort_keys=True))
        print("wrote", key, "->", FILE)
    else:
        for ref_key, ref in store.items():
            if ref_key.split("|")[0] != dev:
                continue
            same = all(ref[c]["sha256"] == got[c]["sha256"] for c in got)
            print(f"{key} vs stored {ref_key}: {'IDENTICAL' if same else 'DIFFERENT'}")
            if not same:
                for c in got:
                    if ref[c]["sha256"] != got[c]["sha256"]:
                        print("  ", c, got[c]["sums"], "stored", ref[c]["sums"])
