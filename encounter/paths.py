"""Filesystem locations used by the encounter package.

Nothing under `.private/` is ever copied into a tracked path; it is only read at run time.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = Path(__file__).resolve().parent
SEED_CASES_DIR = PACKAGE_DIR / "cases"
RUBRICS_DIR = PACKAGE_DIR / "rubrics"
TEMPLATES_DIR = REPO_ROOT / "catalog" / "conditions"
CONTRACTS_DIR = REPO_ROOT / "contracts"


def data_dir() -> Path:
    """Run-time store (gitignored). Override with ENCOUNTER_DATA_DIR."""
    p = Path(os.environ.get("ENCOUNTER_DATA_DIR") or (REPO_ROOT / "data" / "encounters"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def private_dir() -> Path:
    """Organizer material (gitignored). Override with ENCOUNTER_PRIVATE_DIR (tests point it at an empty dir)."""
    return Path(os.environ.get("ENCOUNTER_PRIVATE_DIR") or (REPO_ROOT / ".private"))


def _find(pattern: str) -> list[Path]:
    root = private_dir()
    if not root.is_dir():
        return []
    return sorted(root.glob(pattern))


def sample_patients_csv() -> Path | None:
    hits = _find("shp/**/faculty-provided-sample-patient-details.csv")
    return hits[0] if hits else None


def sample_patient_images() -> list[Path]:
    seen: dict[str, Path] = {}
    for p in _find("shp/**/patient images/*"):
        if p.suffix.lower() in (".png", ".jpg", ".jpeg") and p.name.lower() not in seen:
            seen[p.name.lower()] = p
    return list(seen.values())


def organizer_rubric_json() -> Path | None:
    hits = _find("shp/**/encounter_evaluation_rubric.json")
    return hits[0] if hits else None


def clinician_profile_jsons() -> list[Path]:
    return [p for p in _find("shp/**/*profiles/*.json")]
