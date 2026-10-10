"""Rubrics. Default = the organizers' Patient Encounter Performance Rubric, loaded from `.private/`
at run time when present; otherwise the built-in rubric shipped in encounter/rubrics/ (own wording,
same shape: 4-point scale, named domains, N/A allowed).
"""
from __future__ import annotations

import json
import re

from .paths import RUBRICS_DIR, organizer_rubric_json

BUILTIN_ID = "builtin_encounter_v1"
ORGANIZER_ID = "organizer_encounter"

# canonical grader signals -> keywords found in a rubric domain's key/name
_CANON = [
    ("opening", r"open|start|introduc|purpose|agenda"),
    ("rapport", r"rapport|empath|respect|compassion"),
    ("gathering", r"gather|history|information|interview|data"),
    ("listening", r"listen|cue|respons"),
    ("explanation", r"explain|explanation|shared|decision|plan|educat|counsel"),
    ("reasoning", r"reason|synthes|diagnos|assessment|clinical_judg"),
    ("closure", r"profession|safety|clos|ending|conduct"),
]


def canonical_key(text: str) -> str:
    t = (text or "").lower().replace(" ", "_")
    for name, pat in _CANON:
        if t == name or re.search(pat, t):
            return name
    return ""


def canonical_domain(domain: dict) -> str:
    return canonical_key(str(domain.get("key", ""))) or canonical_key(str(domain.get("name", "")))


def _load_file(path) -> dict | None:
    try:
        r = json.loads(path.read_text())
    except Exception:
        return None
    if not isinstance(r, dict) or not isinstance(r.get("domains"), list):
        return None
    return r


def list_rubrics() -> list[dict]:
    out = []
    for p in sorted(RUBRICS_DIR.glob("*.json")):
        r = _load_file(p)
        if r:
            r.setdefault("rubric_id", p.stem)
            r["source"] = "builtin"
            out.append(r)
    org = organizer_rubric_json()
    if org:
        r = _load_file(org)
        if r:
            r["rubric_id"] = ORGANIZER_ID
            r["source"] = "organizer_private"
            out.append(r)
    return out


def default_rubric_id() -> str:
    ids = [r["rubric_id"] for r in list_rubrics()]
    return ORGANIZER_ID if ORGANIZER_ID in ids else BUILTIN_ID


def get_rubric(rubric_id: str | None = None) -> dict:
    """Unknown or 'default' IDs resolve to the default rubric (never raises for a missing rubric)."""
    rubrics = {r["rubric_id"]: r for r in list_rubrics()}
    rid = rubric_id if rubric_id in rubrics else default_rubric_id()
    r = dict(rubrics[rid])
    r["is_default"] = rid == default_rubric_id()
    r["requested_id"] = rubric_id or "default"
    return r


def summaries() -> list[dict]:
    d = default_rubric_id()
    return [{"rubric_id": r["rubric_id"], "title": r.get("title"), "source": r.get("source"), "is_default": r["rubric_id"] == d,
             "n_domains": len(r.get("domains", [])), "domains": [{"key": x.get("key"), "name": x.get("name")} for x in r.get("domains", [])]}
            for r in list_rubrics()]
