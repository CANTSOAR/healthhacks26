"""Managers, recorded rollouts and evaluation results.

Everything produced by rl/ is re-read from disk per request (mtime cache), so new managers and rollouts
appear without a restart. When rl/ is missing or broken the server still offers `human` and a built-in
`fixed` manager, the fixture rollout and an empty results table.
"""
from __future__ import annotations

import datetime as _dt
import gzip
import importlib
import json
import re
import sys
import threading
from pathlib import Path

from . import cache
from .paths import FIXTURES, rl_dir, state_dir

HUMAN = dict(id="human", kind="human", label="You (human manager)", objective="none", reward_weights=None, available=True)
FIXED = dict(id="fixed", kind="fixed", label="Fixed staffing (default settings)", objective="none", reward_weights=None,
             available=True, builtin=True)
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,120}$")
_lock = threading.Lock()
last_rl_error: str | None = None


# ---------------------------------------------------------------- rl bridge
def rl_module():
    """The `rl` package if it exports the manager API, else None. Retries on every call until it does."""
    global last_rl_error
    mod = sys.modules.get("rl")
    if mod is not None and hasattr(mod, "list_managers") and hasattr(mod, "load_manager"):
        return mod
    try:
        sys.modules.pop("rl", None)
        importlib.invalidate_caches()
        mod = importlib.import_module("rl")
        if hasattr(mod, "list_managers") and hasattr(mod, "load_manager"):
            last_rl_error = None
            return mod
        sys.modules.pop("rl", None)   # empty namespace package: forget it so a later __init__.py is picked up
        last_rl_error = "rl package has no list_managers/load_manager yet"
    except Exception as e:  # noqa: BLE001
        sys.modules.pop("rl", None)
        last_rl_error = f"{type(e).__name__}: {str(e)[:200]}"
    return None


def _norm(m: dict) -> dict:
    out = dict(m)
    out["id"] = str(m.get("id"))
    out["kind"] = m.get("kind") or "fixed"
    out["label"] = str(m.get("label") or out["id"])
    out["objective"] = m.get("objective") if m.get("objective") is not None else "none"
    out["reward_weights"] = m.get("reward_weights")
    out["available"] = bool(m.get("available", True))
    return cache.clean(out)


def list_managers() -> list[dict]:
    global last_rl_error
    out = []
    rl = rl_module()
    if rl is not None:
        try:
            out = [_norm(m) for m in rl.list_managers() if isinstance(m, dict) and m.get("id") is not None]
        except Exception as e:  # noqa: BLE001
            last_rl_error = f"list_managers: {type(e).__name__}: {str(e)[:200]}"
            out = []
    ids = {m["id"] for m in out}
    if not any(m["kind"] == "fixed" and m["available"] for m in out) and "fixed" not in ids:
        out.insert(0, dict(FIXED))
    if "human" not in ids:
        out.insert(0, dict(HUMAN))
    return out


def manager_info(manager_id: str) -> dict | None:
    for m in list_managers():
        if m["id"] == manager_id:
            return m
    return None


class FixedPolicy:
    """Built-in fallback: the catalog's default settings every hour (the fixed-staffing baseline)."""
    id, kind, label, objective = "fixed", "fixed", FIXED["label"], "none"

    def reset(self, B, device) -> None:
        pass

    def act(self, obs, mask, sim=None):
        return sim.default_actions()


def load_manager(manager_id: str, device: str = "cpu"):
    """A Policy, or None for `human`. Raises KeyError / RuntimeError with a readable message."""
    if manager_id == "human":
        return None
    info = manager_info(manager_id)
    if info is None:
        raise KeyError(f"unknown manager '{manager_id}'")
    if info.get("builtin"):
        return FixedPolicy()
    if not info.get("available", True):
        raise RuntimeError(f"manager '{manager_id}' is listed but not available (no checkpoint yet)")
    rl = rl_module()
    if rl is None:
        raise RuntimeError(f"manager '{manager_id}' needs rl/, which is not importable: {last_rl_error}")
    return rl.load_manager(manager_id, device=device)


def _weights_vector(policy, info: dict, k: int, like):
    import torch
    w = None
    for name in ("reward_weights_tensor", "weights_tensor", "reward_weights", "weights", "w"):
        v = getattr(policy, name, None)
        if v is not None:
            w = v
            break
    if w is None:
        w = (info or {}).get("reward_weights")
    if w is None or isinstance(w, dict):
        # the same vector rl.env.HospitalEnv appends: rl.common.weights_vec (rl.common.TERMS order)
        try:
            from rl.common import weights_vec
            w = weights_vec(w if w is not None else (info or {}).get("objective") or getattr(policy, "objective", None), like.device)
        except Exception:  # noqa: BLE001
            pass
    if isinstance(w, dict):
        w = list(w.values())
    if w is None:
        w = []
    w = torch.as_tensor(w, dtype=like.dtype, device=like.device).flatten()
    if w.numel() < k:
        w = torch.cat([w, torch.zeros(k - w.numel(), dtype=like.dtype, device=like.device)])
    return w[:k].unsqueeze(0).expand(like.shape[0], k)


def policy_act(policy, info: dict, sim):
    """Call policy.act the way rl's environment does.

    sim.observe() does not include the reward weights; learned policies expect them appended. Order of attempts:
    1. `rl.policy_obs(sim, policy)` / `rl.make_obs(sim, policy)` if rl exports such a helper;
    2. `policy.observe(sim)` if the policy has one;
    3. the plain observation when the policy declares no larger input size;
    4. the observation with the manager's reward weights appended (dict order) to reach the declared size, or,
       when no size is declared, as a retry after the plain observation is rejected.
    """
    import torch
    mask = sim.action_mask()
    obs = None
    rl = sys.modules.get("rl")
    for name in ("policy_obs", "make_obs", "build_obs"):
        fn = getattr(rl, name, None) if rl is not None else None
        if callable(fn):
            try:
                obs = fn(sim, policy)
                break
            except Exception:  # noqa: BLE001
                obs = None
    if obs is None and callable(getattr(policy, "observe", None)):
        try:
            obs = policy.observe(sim)
        except Exception:  # noqa: BLE001
            obs = None
    if obs is not None:
        return policy.act(obs, mask, sim)
    base = sim.observe()
    want = None
    for name in ("obs_dim", "input_dim", "in_dim"):
        v = getattr(policy, name, None)
        if isinstance(v, int):
            want = v
            break
    with torch.no_grad():
        if want is not None and want > base.shape[1]:
            return policy.act(torch.cat([base, _weights_vector(policy, info, want - base.shape[1], base)], 1), mask, sim)
        try:
            return policy.act(base, mask, sim)
        except (RuntimeError, ValueError, IndexError) as first:
            w = (info or {}).get("reward_weights")
            k = len(w) if isinstance(w, (dict, list)) else 0
            try:
                from rl.common import TERMS
                k = len(TERMS)
            except Exception:  # noqa: BLE001
                pass
            if k == 0:
                raise
            try:
                return policy.act(torch.cat([base, _weights_vector(policy, info, k, base)], 1), mask, sim)
            except Exception:  # noqa: BLE001
                raise first


# ---------------------------------------------------------------- rollouts
def _item(header: dict, has_segments: bool) -> dict:
    m = header.get("manager") or {}
    return cache.clean(dict(
        rollout_id=str(header.get("rollout_id")),
        manager=dict(id=str(m.get("id", "unknown")), kind=m.get("kind", "fixed"), label=str(m.get("label", m.get("id", "unknown"))),
                     objective=m.get("objective") if m.get("objective") is not None else "none"),
        scenario=str(header.get("scenario", "")), seed=int(header.get("seed", 0) or 0), days=int(header.get("days", 0) or 0),
        summary=header.get("summary") or {}, has_segments=bool(has_segments)))


def _norm_item(it: dict) -> dict | None:
    if not isinstance(it, dict):
        return None
    if "header" in it and isinstance(it["header"], dict):
        return _item(it["header"], bool(it.get("has_segments", it.get("segments"))))
    rid = it.get("rollout_id") or it.get("id")
    if rid is None:
        return None
    out = _item(dict(it, rollout_id=rid), bool(it.get("has_segments", True)))
    for k in ("hospital_id", "created", "file", "note"):
        if k in it:
            out[k] = cache.clean(it[k])
    return out


def _rollout_file(rollout_id: str) -> Path | None:
    if not ID_RE.match(rollout_id):
        return None
    d = rl_dir() / "rollouts"
    for name in (f"{rollout_id}.json.gz", f"{rollout_id}.json"):
        if (d / name).is_file():
            return d / name
    return None


def list_rollouts() -> list[dict]:
    d = rl_dir() / "rollouts"
    out: list[dict] = []
    idx = cache.load(d / "index.json")
    if isinstance(idx, dict):
        idx = idx.get("rollouts") or idx.get("items") or []
    if isinstance(idx, list):
        out = [x for x in (_norm_item(i) for i in idx) if x and _rollout_file(x["rollout_id"]) is not None]
    elif d.exists():
        for f in sorted(list(d.glob("*.json.gz")) + list(d.glob("*.json"))):
            if f.name == "index.json":
                continue
            r = cache.load(f)
            if isinstance(r, dict) and isinstance(r.get("header"), dict):
                h = dict(r["header"])
                h.setdefault("rollout_id", f.name.split(".json")[0])
                out.append(_item(h, bool(r.get("segments"))))
    if not out:
        fx = cache.load(FIXTURES / "rollout.fixture.json")
        if isinstance(fx, dict):
            it = _item(fx["header"], bool(fx.get("segments")))
            it["fixture"] = True
            out.append(it)
    return out


_gz: dict[str, tuple[tuple, bytes]] = {}


def rollout_gzip(rollout_id: str) -> bytes | None:
    """Gzip-compressed JSON of a rollout, or None when unknown."""
    f = _rollout_file(rollout_id)
    if f is None:
        fx = FIXTURES / "rollout.fixture.json"
        data = cache.load(fx)
        if not (isinstance(data, dict) and data.get("header", {}).get("rollout_id") == rollout_id):
            return None
        f = fx
    try:
        st = f.stat()
        key = (st.st_mtime_ns, st.st_size)
        with _lock:
            hit = _gz.get(str(f))
            if hit and hit[0] == key:
                return hit[1]
        raw = f.read_bytes()
        if not f.name.endswith(".gz"):
            raw = gzip.compress(raw, compresslevel=5)
        with _lock:
            _gz[str(f)] = (key, raw)
            while len(_gz) > 8:
                _gz.pop(next(iter(_gz)))
        return raw
    except OSError:
        return None


# ---------------------------------------------------------------- results
def _human_file() -> Path:
    return state_dir() / "human_runs.json"


def human_runs() -> list[dict]:
    d = cache.load(_human_file(), default=[])
    return [r for r in d if isinstance(r, dict)] if isinstance(d, list) else []


def add_human_run(run: dict) -> list[dict]:
    """Keep the last run per (label, scenario)."""
    run = cache.clean(dict(run))
    run["created"] = run.get("created") or _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    run["kind"] = "human"
    with _lock:
        runs = [r for r in human_runs() if not (r.get("label") == run.get("label") and r.get("scenario") == run.get("scenario"))]
        runs.append(run)
        runs = runs[-200:]
        tmp = _human_file().with_suffix(".tmp")
        tmp.write_text(json.dumps(runs, indent=1))
        tmp.replace(_human_file())
    return runs


def results() -> dict:
    d = cache.load(rl_dir() / "results" / "results.json")
    if isinstance(d, dict) and isinstance(d.get("rows"), list):
        out = cache.clean(dict(d))
        out.setdefault("generated", None)
        out.setdefault("protocol", dict(seeds=[], days=0, scenarios=[]))
    else:
        out = dict(generated=None, protocol=dict(seeds=[], days=0, scenarios=[]), rows=[],
                   note="No evaluation results yet: rl/results/results.json has not been written.")
    own = [r for r in (out.get("human_runs") or []) if isinstance(r, dict)]
    out["human_runs"] = own + human_runs()
    return out
