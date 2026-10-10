"""/api/status: which services are live. Decided only by what is importable and which credentials are present."""
from __future__ import annotations

import os

from . import __version__, encounter_glue, managers, runs


def _env(name: str) -> bool:
    return bool((os.environ.get(name) or "").strip())


def status() -> dict:
    sim_ok, sim_err = runs.sim_available()
    llm = dict(live=False, provider="offline", model=None)
    voice_live = _env("ELEVENLABS_API_KEY")
    voice = dict(live=voice_live, provider="elevenlabs" if voice_live else "browser")
    enc_err = None
    try:
        import encounter
        st = encounter.status() or {}
        if isinstance(st.get("llm"), dict):
            llm.update(st["llm"])
        if isinstance(st.get("voice"), dict):
            voice.update(st["voice"])
        enc_ok = True
    except Exception as e:  # noqa: BLE001
        enc_ok, enc_err = False, f"{type(e).__name__}: {str(e)[:200]}"
    if llm.get("provider") not in ("bedrock", "anthropic", "offline"):
        llm["provider_name"], llm["provider"] = llm.get("provider"), "offline"
    llm["live"], voice["live"] = bool(llm.get("live")), bool(voice.get("live"))
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
    enc = dict(live=bool(encounter_glue.state["mounted"]), importable=enc_ok, sim_hook=encounter_glue.state["hook"])
    if enc_err or encounter_glue.state["error"]:
        enc["last_error"] = enc_err or encounter_glue.state["error"]
    rl = dict(live=rl_ok)
    if not rl_ok and managers.last_rl_error:
        rl["last_error"] = managers.last_rl_error
    return dict(services=dict(sim=sim, llm=llm, voice=voice, data=dict(live=data_live, provider="vlada" if data_live else "public_extracts"),
                              rl=rl, encounter=enc),
                encounter="available" if enc["live"] else "unavailable",
                torch=tv, device=dev, version=__version__)
