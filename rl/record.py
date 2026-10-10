"""Record rollouts for the viewer (contracts/rollout.schema.json). All numbers simulated.

    python -m rl.record --all                      # every available manager x {normal_week, flu_surge}
    python -m rl.record --manager fixed --scenario normal_week

Every manager is recorded on the SAME held-out seed (common.RECORD_SEED), so by the simulator's
common random numbers they face the same patients (arrivals + diverted is identical hour by
hour). Each rollout holds hourly metrics for the whole episode, every decision with a readable
label, and full snapshots (every tick) for two windows: day 1 08:00-20:00 and the busiest day
(most exogenous arrivals) 10:00-22:00. Runs one hospital on CPU; --all fans out over processes.
"""
from __future__ import annotations

import argparse
import gzip
import json
import subprocess
import sys
from pathlib import Path

import torch

from .common import IMPULSE_HEADS, RECORD_SEED, RESULTS_DIR, ROLLOUT_DIR, ROOT, TERMS, load_scales, now_iso, sim_fingerprint, write_json
from .env import HospitalEnv
from .managers import list_managers, load_manager

HEAD_LABEL = {
    "priority_rule": "Queue priority rule", "overflow_bays": "Overflow hallway spaces", "divert": "Ambulance diversion",
    "call_in": "Call in extra staff", "fast_track": "Fast track", "provider_split": "Provider time split",
    "md_day": "Providers, day shift", "md_evening": "Providers, evening shift", "md_night": "Providers, night shift",
    "rn_day": "Nurses, day shift", "rn_evening": "Nurses, evening shift", "rn_night": "Nurses, night shift",
    "triage_nurses": "Triage nurses", "admission_cap": "Admission cap", "discharge_push": "Ward discharge rounds",
    "agency_contract": "Agency nurses per shift", "imaging_hours": "Second CT/MRI staffed hours", "bays_delta": "Treatment bays",
    "ward_beds_delta": "Inpatient beds", "equipment_buy": "Buy scanner", "relocate": "Relocate zone", "headcount": "Permanent headcount",
}
NUMERIC_HEADS = {"overflow_bays", "md_day", "md_evening", "md_night", "rn_day", "rn_evening", "rn_night", "triage_nurses", "agency_contract"}
STRUCT_DELAY = {"bays_delta": "bays", "ward_beds_delta": "ward", "equipment_buy": "equip", "relocate": "reloc", "headcount": "head"}


def option_text(h: dict, i: int) -> str:
    if h["name"] in NUMERIC_HEADS and isinstance(h.get("values", [None])[i], (int, float)):
        return str(h["values"][i])
    if h["name"] == "imaging_hours" and isinstance(h.get("values", [None])[i], (list, tuple)):
        a, b = h["values"][i]
        return f"{int(a):02d}:00-{int(b):02d}:00"
    return str(h["options"][i]).replace("_", " ")


def decision_label(h: dict, prev: int, new: int) -> str:
    name = HEAD_LABEL.get(h["name"], h["name"])
    if h["name"] in IMPULSE_HEADS:
        return f"{name}: {option_text(h, new)}"
    return f"{name}: {option_text(h, prev)} -> {option_text(h, new)}"


def busiest_day(scenario: str, seed: int, days: int) -> int:
    """Day (>= 2) with the most exogenous arrivals on this seed; from the evaluation part file when
    it covers the seed, else from a hourly-only pass of the fixed manager."""
    part = RESULTS_DIR / "parts" / f"{scenario}.json"
    if part.exists():
        d = json.loads(part.read_text())
        if seed in d["seeds"] and d["days"] >= days and d.get("sim_fingerprint") == sim_fingerprint():
            arr = d["daily_exogenous_arrivals"][d["seeds"].index(seed)][:days]
            return max(range(min(2, days - 1), days), key=lambda i: arr[i])
    env = HospitalEnv(scenario, 1, "cpu", seed, days * 24, auto_reset=False, scales={"scales": {k: 1.0 for k in TERMS}})
    pol = load_manager("fixed")
    obs, arr = env.reset(), []
    for h in range(days * 24):
        obs, r, d, info = env.step(pol.act(obs, env.action_mask()))
        arr.append(float(info["metrics"]["arrivals"][0] + info["metrics"]["diverted"][0]))
    daily = [sum(arr[i * 24:(i + 1) * 24]) for i in range(days)]
    return max(range(min(2, days - 1), days), key=lambda i: daily[i])


@torch.no_grad()
def record(manager_id: str, scenario: str, seed: int = RECORD_SEED, days: int = 30, busy_day: int | None = None,
           every_ticks: int = 1, out_dir: Path = ROLLOUT_DIR, validate: bool = True) -> dict:
    pol = load_manager(manager_id, "cpu")
    scales = load_scales()
    w = torch.tensor([float((pol.reward_weights or {}).get(k, 0.0)) for k in TERMS])
    env = HospitalEnv(scenario, 1, "cpu", seed, days * 24, stage="stage_3", weights=w, scales=scales, auto_reset=False)
    sim = env.sim
    spec = sim.action_spec()
    by_name = {h["name"]: h for h in spec}
    if busy_day is None:
        busy_day = busiest_day(scenario, seed, days)
    tph = 60 // sim.tick_minutes
    windows = [("Day 1, 08:00-20:00", 1 * 24 + 8, 12)]
    if days > 2:
        windows.append((f"Busiest day (day {busy_day}), 10:00-22:00", busy_day * 24 + 10, 12))
    windows = [(lab, h0, n) for lab, h0, n in windows if h0 + n <= days * 24]
    segs = [dict(label=lab, start_t=h0 * tph, every_ticks=every_ticks, snapshots=[]) for lab, h0, n in windows]
    pol.reset(1, "cpu")
    obs = env.reset()
    layout0 = sim.layout(0)
    hourly = {k: [] for k in sim.metric_names()}
    decisions, structural = [], []
    lv = int(sim.layout_version[0])
    for h in range(days * 24):
        seg = next((s for s, (lab, h0, n) in zip(segs, windows) if h0 <= h < h0 + n), None)
        if seg is not None and h * tph == seg["start_t"]:
            seg["snapshots"].append(sim.snapshot(0))
        prev = {n: int(v[0]) for n, v in sim.settings.items()}
        acts = pol.act(obs, env.action_mask())
        sm = sim.action_mask()
        send = {n: acts[n] for n in env.head_names if bool(sm[n][0])}
        t = int(sim.t[0])
        for i in range(sim.ticks_per_step):
            sim.tick(send if i == 0 else None)
            if i == 0:
                for n in env.head_names:
                    new = int(sim.settings[n][0])
                    hd = by_name[n]
                    changed = (new != hd["default"]) if n in IMPULSE_HEADS else (new != prev[n])
                    if not changed or not bool(sm[n][0]):
                        continue
                    decisions.append(dict(t=t, head=n, value=new, prev=prev[n], cadence=hd["cadence"], label=decision_label(hd, prev[n], new)))
                    if n in STRUCT_DELAY:
                        delay = int(getattr(sim, "delay_days", {}).get(STRUCT_DELAY[n], 0))
                        immediate = n in ("bays_delta", "ward_beds_delta", "headcount") and new == 0
                        structural.append(dict(t_decided=t, t_effective=t if immediate else t + delay * 24 * tph, kind=n,
                                               label=decision_label(hd, prev[n], new)))
            if seg is not None and ((int(sim.t[0]) - seg["start_t"]) % every_ticks == 0):
                seg["snapshots"].append(sim.snapshot(0))
            if int(sim.layout_version[0]) != lv:
                lv = int(sim.layout_version[0])
                structural.append(dict(t_decided=int(sim.t[0]), t_effective=int(sim.t[0]), kind="layout_change",
                                       label=f"Layout changed (version {lv})", layout=sim.layout(0)))
        m = sim.metrics_last_hour()
        for k in hourly:
            hourly[k].append(round(float(m[k][0]), 4))
        obs = env.observe()
    summary = {k: float(v[0]) for k, v in sim.episode_summary().items()}
    summary["labor_cost_per_day"] = sum(hourly["cost_labor"]) / days          # extra key: controllable cost
    rid = f"{manager_id}__{scenario}__s{seed}"
    man = {k: v for k, v in pol.info().items() if v is not None}
    if getattr(pol, "config", None):
        man["checkpoint"] = str(pol.config.get("checkpoint"))
    roll = dict(schema_version=1,
                header=dict(rollout_id=rid, manager=man, scenario=scenario, hospital_id=str(getattr(sim.scn, "hospital_id", "rwjuh_nb")),
                            seed=int(seed), tick_minutes=int(sim.tick_minutes), days=int(days), created=now_iso(), synthetic=True,
                            enums=sim.enums, layout=layout0, action_spec=spec, summary=summary,
                            sim_fingerprint=sim_fingerprint(), policy_fingerprint=getattr(pol, "file_fingerprint", None),
                            invalid_actions=int(sim.invalid_actions[0])),
                hourly=hourly, decisions=decisions, structural_changes=structural, segments=segs)
    if validate:
        validate_rollout(roll)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{rid}.json.gz"
    with gzip.open(path, "wt", compresslevel=6) as f:
        json.dump(roll, f, separators=(",", ":"))
    return dict(rollout_id=rid, manager={k: man.get(k) for k in ("id", "kind", "label", "objective")}, scenario=scenario, seed=int(seed),
                days=int(days), summary=summary, has_segments=bool(segs and segs[0]["snapshots"]), file=path.name,
                bytes=path.stat().st_size, sim_fingerprint=sim_fingerprint(), n_decisions=len(decisions))


def validate_rollout(roll: dict):
    """Validate against contracts/rollout.schema.json (+ referenced layout and snapshot schemas)."""
    import jsonschema
    from referencing import Registry, Resource
    cdir = ROOT / "contracts"
    reg = Registry()
    for name in ("layout.schema.json", "snapshot.schema.json", "rollout.schema.json"):
        sch = json.loads((cdir / name).read_text())
        res = Resource.from_contents(sch)
        reg = reg.with_resource(name, res)
        if sch.get("$id"):
            reg = reg.with_resource(sch["$id"], res)
    schema = json.loads((cdir / "rollout.schema.json").read_text())
    jsonschema.Draft202012Validator(schema, registry=reg).validate(roll)


def write_index(out_dir: Path = ROLLOUT_DIR):
    """Rebuild index.json (the /api/rollouts list shape) from the rollout files on disk."""
    rows = []
    for f in sorted(out_dir.glob("*.json.gz")):
        with gzip.open(f, "rt") as fh:
            r = json.load(fh)
        h = r["header"]
        rows.append(dict(rollout_id=h["rollout_id"], manager={k: h["manager"].get(k) for k in ("id", "kind", "label", "objective")},
                         scenario=h["scenario"], seed=h["seed"], days=h["days"], summary=h.get("summary", {}),
                         has_segments=bool(r["segments"] and r["segments"][0]["snapshots"]), file=f.name, bytes=f.stat().st_size,
                         sim_fingerprint=h.get("sim_fingerprint"), created=h.get("created"), synthetic=True))
    write_json(out_dir / "index.json", rows, indent=1)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--manager", nargs="+", default=None)
    ap.add_argument("--scenario", nargs="+", default=["normal_week", "flu_surge"])
    ap.add_argument("--seed", type=int, default=RECORD_SEED)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--every-ticks", type=int, default=1)
    ap.add_argument("--jobs", type=int, default=12)
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--out", default=str(ROLLOUT_DIR))
    ap.add_argument("--busy-day", type=int, default=None)
    ap.add_argument("--single", action="store_true", help="internal: record exactly one manager x scenario in this process")
    a = ap.parse_args()
    out = Path(a.out)
    torch.set_num_threads(a.threads)
    ids = a.manager or [m["id"] for m in list_managers() if m["available"]]
    if a.single:
        r = record(ids[0], a.scenario[0], a.seed, a.days, a.busy_day, a.every_ticks, out)
        print(f"recorded {r['rollout_id']} {r['bytes'] / 1e6:.2f} MB, {r['n_decisions']} decisions")
        return
    jobs = []
    for s in a.scenario:
        bd = a.busy_day if a.busy_day is not None else busiest_day(s, a.seed, a.days)
        for m in ids:
            jobs.append([sys.executable, "-m", "rl.record", "--single", "--manager", m, "--scenario", s, "--seed", str(a.seed),
                         "--days", str(a.days), "--every-ticks", str(a.every_ticks), "--threads", str(a.threads), "--out", str(out),
                         "--busy-day", str(bd)])
    running, failed = [], 0
    while jobs or running:
        while jobs and len(running) < a.jobs:
            running.append(subprocess.Popen(jobs.pop(0)))
        p = running.pop(0)
        failed += int(p.wait() != 0)
    rows = write_index(out)
    print(f"index: {len(rows)} rollouts, {failed} failed jobs, total {sum(r['bytes'] for r in rows) / 1e6:.1f} MB")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
