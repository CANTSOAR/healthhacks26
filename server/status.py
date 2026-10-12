"""/api/status: which services are live. Decided only by what is importable and which credentials are present."""
from __future__ import annotations

import os

from . import __version__, managers, runs


def _env(name: str) -> bool:
    return bool((os.environ.get(name) or "").strip())


def status() -> dict:
    sim_ok, sim_err = runs.sim_available()
    data_live = _env("VLADA_API_KEY")
    try:
        import torch
        tv, dev = str(torch.__version__), "cpu"
    except Exception:  # noqa: BLE001
        tv, dev = None, None
    rl_ok = managers.rl_module() is not None
    sim = dict(live=sim_ok, active_runs=len(runs.list_runs()))
    if sim_err:
        sim["last_error"] = sim_err
    rl = dict(live=rl_ok)
    if not rl_ok and managers.last_rl_error:
        rl["last_error"] = managers.last_rl_error
    return dict(services=dict(sim=sim, rl=rl, data=dict(live=data_live, provider="vlada" if data_live else "public_extracts")),
                torch=tv, device=dev, version=__version__)
