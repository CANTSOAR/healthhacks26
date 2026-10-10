"""Where everything lives. Overridable through env vars so tests can point at temp dirs."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts"
FIXTURES = CONTRACTS / "fixtures"


def catalog_dir() -> Path:
    return Path(os.environ.get("HG_CATALOG_DIR") or ROOT / "catalog")


def rl_dir() -> Path:
    return Path(os.environ.get("HG_RL_DIR") or ROOT / "rl")


def state_dir() -> Path:
    d = Path(os.environ.get("HG_STATE_DIR") or Path(__file__).resolve().parent / "state")
    d.mkdir(parents=True, exist_ok=True)
    return d
