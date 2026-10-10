"""Journey definitions as data. No journey-specific code anywhere: a new JSON file here is a new journey."""
from __future__ import annotations

import json
from pathlib import Path

from ..paths import PACKAGE_DIR

JOURNEYS_DIR = PACKAGE_DIR / "journeys"

# interaction types (contracts/enums.yaml) a journey stage may map to, and the engine that runs each
PATIENT_TYPES = ("triage", "clinician_encounter", "nursing_assessment", "disposition", "discharge_planning")
HANDOFF_TYPES = ("handoff",)
STAFF_ROLES = ("attending", "resident", "app", "rn", "charge_rn", "tech", "registration", "pharmacist", "imaging_tech", "transport", "evs")
CATEGORIES = ("identity", "chief_complaint", "hpi", "pmh", "medications", "allergies", "social", "family", "ros", "exam", "vitals",
              "lab", "imaging", "diagnosis", "risk", "concealed")
WRITE_KEYS = ("acuity", "note", "orders", "disposition", "med_list", "plan", "open_questions", "sbar")
OBJECTIVE_KINDS = ("elicit", "use_prior", "request", "write", "decision_match", "resolve_discrepancy", "identify_open", "sbar",
                   "no_unsupported")
COMPLETION_RULES = ("all_stages", "required_stages")
DEFAULT_MINUTES = {"triage": 5, "clinician_encounter": 15, "nursing_assessment": 10, "disposition": 8, "discharge_planning": 12, "handoff": 10}


class JourneyDefinitionError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def stage_kind(stage: dict) -> str:
    return "handoff" if stage.get("interaction_type") in HANDOFF_TYPES else "patient"


def validate_definition(d: dict) -> list[str]:
    """Returns a list of problems (empty = valid)."""
    errs: list[str] = []
    if not isinstance(d, dict):
        return ["definition must be an object"]
    for k in ("journey_id", "title"):
        if not isinstance(d.get(k), str) or not d.get(k).strip():
            errs.append(f"{k} is required")
    if not isinstance(d.get("version"), int) or d.get("version", 0) < 1:
        errs.append("version must be a positive integer")
    if d.get("schema_version") != 1:
        errs.append("schema_version must be 1")
    base = d.get("base_case")
    if not isinstance(base, dict) or not isinstance(base.get("case_id"), str) or not base.get("case_id"):
        errs.append("base_case.case_id is required ('*' = any published case)")
    stages = d.get("stages")
    if not isinstance(stages, list) or not stages:
        return errs + ["stages must be a non-empty list"]
    seen: set[str] = set()
    for i, s in enumerate(stages):
        w = f"stages[{i}]"
        if not isinstance(s, dict):
            errs.append(f"{w} must be an object")
            continue
        sid = s.get("stage_id")
        if not isinstance(sid, str) or not sid.replace("_", "").replace("-", "").isalnum():
            errs.append(f"{w}.stage_id must be a short identifier")
        elif sid in seen:
            errs.append(f"{w}.stage_id '{sid}' is used twice")
        else:
            seen.add(sid)
        it = s.get("interaction_type")
        if it not in PATIENT_TYPES + HANDOFF_TYPES:
            errs.append(f"{w}.interaction_type '{it}' is not one of {', '.join(PATIENT_TYPES + HANDOFF_TYPES)}")
        role = s.get("learner_role")
        if not isinstance(role, dict) or role.get("staff_role") not in STAFF_ROLES or not role.get("label"):
            errs.append(f"{w}.learner_role needs a staff_role from contracts/enums.yaml and a label")
        cps = s.get("counterparts")
        if not isinstance(cps, list) or not cps:
            errs.append(f"{w}.counterparts must name at least one AI counterpart")
            cps = []
        kinds = [c.get("kind") for c in cps if isinstance(c, dict)]
        if any(k not in ("patient", "colleague") for k in kinds) or len(kinds) != len(cps):
            errs.append(f"{w}.counterparts[].kind must be 'patient' or 'colleague'")
        if it in HANDOFF_TYPES:
            if "colleague" not in kinds:
                errs.append(f"{w}: a handoff needs a colleague counterpart")
            if i == 0:
                errs.append(f"{w}: a handoff cannot be the first stage (there is nothing to hand over)")
            sb = s.get("sbar") or {}
            if not isinstance(sb.get("max_questions", 3), int) or not 0 <= sb.get("max_questions", 3) <= 6:
                errs.append(f"{w}.sbar.max_questions must be 0..6")
        elif it in PATIENT_TYPES:
            if "patient" not in kinds:
                errs.append(f"{w}: a patient-facing stage needs the patient as a counterpart")
            sc = s.get("scope")
            if not isinstance(sc, dict):
                errs.append(f"{w}.scope is required (fact_categories, requests)")
            else:
                cats = sc.get("fact_categories")
                if cats != "all" and (not isinstance(cats, list) or any(c not in CATEGORIES for c in cats)):
                    errs.append(f"{w}.scope.fact_categories must be 'all' or a list of case fact categories")
                reqs = sc.get("requests", [])
                if not isinstance(reqs, list) or any(not isinstance(r, str) or ":" not in r for r in reqs):
                    errs.append(f"{w}.scope.requests must be a list like ['exam:*', 'order:ecg']")
        for c in cps:
            if isinstance(c, dict) and c.get("kind") == "colleague" and c.get("staff_role") not in STAFF_ROLES:
                errs.append(f"{w}: colleague counterpart needs a staff_role")
        wr = s.get("writes")
        if not isinstance(wr, dict) or not isinstance(wr.get("required"), list):
            errs.append(f"{w}.writes.required is required (what the stage must add to the shared record)")
        else:
            for k in list(wr.get("required") or []) + list(wr.get("optional") or []):
                if k not in WRITE_KEYS:
                    errs.append(f"{w}.writes: '{k}' is not one of {', '.join(WRITE_KEYS)}")
            if it in HANDOFF_TYPES and "sbar" not in wr["required"]:
                errs.append(f"{w}: a handoff must write 'sbar'")
            if it in PATIENT_TYPES and "sbar" in wr.get("required", []):
                errs.append(f"{w}: only a handoff stage writes 'sbar'")
        oseen: set[str] = set()
        for j, o in enumerate(s.get("objectives") or []):
            ow = f"{w}.objectives[{j}]"
            if not isinstance(o, dict) or not o.get("objective_id") or not o.get("criterion"):
                errs.append(f"{ow} needs objective_id and criterion")
                continue
            if o["objective_id"] in oseen:
                errs.append(f"{ow}.objective_id is used twice in the stage")
            oseen.add(o["objective_id"])
            if o.get("kind") not in OBJECTIVE_KINDS:
                errs.append(f"{ow}.kind must be one of {', '.join(OBJECTIVE_KINDS)}")
            if o.get("kind") in ("write", "decision_match") and o.get("key") not in WRITE_KEYS:
                errs.append(f"{ow}.key must be a writes key")
            if o.get("kind") == "elicit" and (not isinstance(o.get("categories"), list) or any(c not in CATEGORIES for c in o["categories"])):
                errs.append(f"{ow}.categories must list case fact categories")
            if o.get("kind") == "request" and not isinstance(o.get("requests"), list):
                errs.append(f"{ow}.requests must be a list")
    comp = d.get("completion")
    if not isinstance(comp, dict) or comp.get("rule") not in COMPLETION_RULES:
        errs.append(f"completion.rule must be one of {', '.join(COMPLETION_RULES)}")
    elif comp["rule"] == "required_stages":
        req = comp.get("stages")
        if not isinstance(req, list) or not req or any(x not in seen for x in req):
            errs.append("completion.stages must list existing stage_ids")
    return errs


def _load(path: Path) -> dict | None:
    try:
        d = json.loads(path.read_text())
    except Exception:
        return None
    return d if isinstance(d, dict) else None


def list_definitions(directory: Path | None = None) -> list[dict]:
    """Valid definitions, highest version of each id, default template first."""
    best: dict[str, dict] = {}
    for p in sorted((directory or JOURNEYS_DIR).glob("*.json")):
        d = _load(p)
        if d is None or validate_definition(d):
            continue
        cur = best.get(d["journey_id"])
        if cur is None or d["version"] > cur["version"]:
            best[d["journey_id"]] = d
    return sorted(best.values(), key=lambda d: (d["base_case"]["case_id"] != "*", d["journey_id"]))


def get_definition(journey_id: str, directory: Path | None = None) -> dict:
    for d in list_definitions(directory):
        if d["journey_id"] == journey_id:
            return d
    raise KeyError(journey_id)


def applies_to(d: dict, case_id: str) -> bool:
    return d["base_case"]["case_id"] in ("*", case_id)


def default_for(case_id: str, directory: Path | None = None) -> dict:
    """The journey written for this case if there is one, otherwise the template that works with any case."""
    defs = list_definitions(directory)
    for d in defs:
        if d["base_case"]["case_id"] == case_id:
            return d
    for d in defs:
        if d["base_case"]["case_id"] == "*":
            return d
    raise KeyError("no journey template is installed")


def summary(d: dict) -> dict:
    return {"journey_id": d["journey_id"], "version": d["version"], "title": d["title"], "description": d.get("description"),
            "base_case": d["base_case"], "any_case": d["base_case"]["case_id"] == "*", "completion": d["completion"],
            "stages": [{"stage_id": s["stage_id"], "title": s.get("title") or s["stage_id"], "interaction_type": s["interaction_type"],
                        "kind": stage_kind(s), "learner_role": s["learner_role"],
                        "counterparts": [{k: c.get(k) for k in ("kind", "staff_role", "label") if c.get(k)} for c in s["counterparts"]],
                        "writes": s["writes"], "n_objectives": len(s.get("objectives") or []) } for s in d["stages"]]}
