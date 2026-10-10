"""/api/validation: baseline simulator output against catalog/validation_targets.yaml.

The baseline (default settings, normal_week) is simulated lazily in a background thread and cached by a
hash of the catalog, in memory and in server/state/validation_baseline.json. Until it is ready the route
answers `status: "pending"`. Every simulated number comes from the simulator; nothing is typed in here.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess
import sys
import threading

from . import cache, catalog
from .paths import ROOT, catalog_dir, state_dir

# target attribute -> (simulated quantity, how comparable the two are)
MAP = {
    "median_ed_time_discharged_min": ("ed_los_median_min", "simulated median covers all ED departures, the target only discharged patients"),
    "length_of_visit_median_min": ("ed_los_median_min", "both are the median over all ED visits"),
    "lwbs_rate": ("lwbs_rate", "same definition: left without being seen / arrivals"),
    "ed_visits_per_year": ("ed_visits_per_year", "simulated arrivals per day x 365"),
    "admission_rate": ("admission_rate", "simulated admit decisions / arrivals"),
}
PRIMARY = "rwjuh_nb"
_lock = threading.Lock()
_state: dict = {"running": None, "results": {}, "errors": {}}


def settings() -> dict:
    return dict(scenario="normal_week", days=int(os.environ.get("HG_VALIDATION_DAYS", "14")), batch=int(os.environ.get("HG_VALIDATION_BATCH", "4")),
                seed=int(os.environ.get("HG_VALIDATION_SEED", "1000")))


def compute_baseline(scenario: str, days: int, batch: int, seed: int) -> dict:
    """Run the default policy and return mean-over-hospitals episode numbers. Pure simulator output."""
    from sim import HospitalSim, load_scenario
    sim = HospitalSim(load_scenario(scenario), batch_size=batch, device="cpu", seed=seed)
    sums = {"arrivals": 0.0, "admissions": 0.0}
    for _ in range(days * 24):
        m = sim.step(sim.default_actions())
        for k in sums:
            if k in m:
                sums[k] += float(m[k].float().mean())
    out = {k: float(v.float().mean()) for k, v in sim.episode_summary().items()}
    out["arrivals_per_day"] = sums["arrivals"] / max(days, 1)
    out["ed_visits_per_year"] = out["arrivals_per_day"] * 365.0
    out["admission_rate"] = sums["admissions"] / max(sums["arrivals"], 1.0)
    return out


def run_baseline(s: dict) -> dict:
    """The baseline in a separate low-priority process, so it never slows a live simulation (the simulator's
    python loop holds the GIL). Falls back to this process when the child fails. HG_VALIDATION_INPROCESS=1 skips the child."""
    if not os.environ.get("HG_VALIDATION_INPROCESS"):
        try:
            p = subprocess.run([sys.executable, "-m", "server.validation", json.dumps(s)], cwd=str(ROOT), capture_output=True, text=True,
                               timeout=3600)
            if p.returncode == 0:
                return json.loads(p.stdout.strip().splitlines()[-1])
        except Exception:  # noqa: BLE001
            pass
    return compute_baseline(**s)


def _cache_file():
    return state_dir() / "validation_baseline.json"


def _key() -> str:
    s = settings()
    scen = ROOT / "sim" / "scenarios"
    h = catalog.content_hash(extra=[scen / "normal_week.yaml", scen / "_defaults.yaml"])
    return f"{h}-{s['scenario']}-{s['days']}d-b{s['batch']}-s{s['seed']}"


def _worker(key: str, s: dict) -> None:
    try:
        sim = run_baseline(s)
        res = dict(simulated=cache.clean(sim), baseline=dict(s, policy="default settings (fixed staffing)", catalog_hash=key.split("-")[0],
                                                             computed=_dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
                                                             seeds=[s["seed"] + i for i in range(s["batch"])], synthetic=True))
        with _lock:
            _state["results"][key] = res
            _state["last"] = res
        try:
            _cache_file().write_text(json.dumps({key: res}, indent=1))
        except OSError:
            pass
    except Exception as e:  # noqa: BLE001
        with _lock:
            _state["errors"][key] = f"{type(e).__name__}: {str(e)[:300]}"
    finally:
        with _lock:
            _state["running"] = None


def baseline(start: bool = True) -> tuple[str, dict | None, str | None]:
    """(status, result, error): status is ready | pending | error."""
    key = _key()
    with _lock:
        res = _state["results"].get(key)
        if res is None:
            disk = cache.load(_cache_file())
            if isinstance(disk, dict):
                if key in disk:
                    res = _state["results"][key] = disk[key]
                elif disk and "last" not in _state:
                    _state["last"] = next(iter(disk.values()))
        if res is not None:
            return "ready", res, None
        if key in _state["errors"]:
            return "error", None, _state["errors"][key]
        if _state["running"] is None and start:
            _state["running"] = key
            threading.Thread(target=_worker, args=(key, settings()), name="validation-baseline", daemon=True).start()
        return "pending", _state.get("last"), None


def targets() -> list[dict]:
    doc = cache.load(catalog_dir() / "validation_targets.yaml")
    out = []
    if not isinstance(doc, dict):
        return out
    variants = doc.get("variants") or {}
    for var in sorted(variants, key=lambda v: (v != PRIMARY, v)):
        v = variants[var] or {}
        for name, a in (v.get("attributes") or {}).items():
            if not isinstance(a, dict) or isinstance(a.get("value"), bool) or not isinstance(a.get("value"), (int, float)):
                continue
            rng = a.get("range") if isinstance(a.get("range"), list) and len(a.get("range")) == 2 else None
            t = dict(name=name if var == PRIMARY else f"{var}.{name}", value=a["value"], range=rng, source=a.get("source"),
                     url=a.get("url"), unit=a.get("unit"), variant=var, variant_label=v.get("label"), attribute=name,
                     citation=a.get("citation"), note=a.get("note"))
            if name in MAP:
                t["simulated_metric"], t["comparability"] = MAP[name]
            out.append(t)
    return out


def report() -> dict:
    tg = targets()
    try:
        status, res, err = baseline(start=bool(tg))
    except Exception as e:  # noqa: BLE001
        status, res, err = "error", None, f"{type(e).__name__}: {str(e)[:300]}"
    sim = (res or {}).get("simulated") or {}
    simulated, within = {}, {}
    for t in tg:
        key = t.get("simulated_metric")
        if key is None or sim.get(key) is None:
            continue
        simulated[t["name"]] = sim[key]
        if t["range"] and all(isinstance(x, (int, float)) for x in t["range"]):
            within[t["name"]] = bool(t["range"][0] <= sim[key] <= t["range"][1])
    out = dict(status=status if tg else "no_targets", targets=tg, simulated=simulated, within=within, baseline=(res or {}).get("baseline"),
               summary=sim, synthetic=True)
    if status == "pending" and res is not None:
        out["stale"] = True   # values are from the previous catalog version while the new baseline is computed
    if err:
        out["error"] = err
    if not tg:
        out["note"] = "catalog/validation_targets.yaml has not been written yet"
    return out


def reset() -> None:
    with _lock:
        _state.update(running=None, results={}, errors={})
        _state.pop("last", None)


if __name__ == "__main__":   # child process of run_baseline: prints one JSON line
    with __import__("contextlib").suppress(Exception):
        os.nice(10)
    print(json.dumps(cache.clean(compute_baseline(**json.loads(sys.argv[1])))))
