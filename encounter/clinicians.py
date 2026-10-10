"""Named fictional clinicians (AI colleagues / named staff).

Profiles are read from the organizers' pack under `.private/` when present; otherwise the built-in
fictional stand-ins below (authored for this project) are used. Nobody here is a real clinician.
"""
from __future__ import annotations

import json
import re

from .paths import clinician_profile_jsons

BUILTIN = [
    {"id": "amelia-okafor", "name": "Dr. Amelia Okafor", "credentials": "MD", "role": "Emergency Medicine Attending", "staff_role": "attending",
     "specialty": "Emergency Medicine", "years_in_role": 12,
     "communication_style": "Calm and direct. Asks residents for a one-line summary and a plan before giving her own.",
     "scope": "Supervises the department, resuscitations, final disposition decisions."},
    {"id": "jun-watanabe", "name": "Dr. Jun Watanabe", "credentials": "MD", "role": "Emergency Medicine Resident (PGY-2)", "staff_role": "resident",
     "specialty": "Emergency Medicine", "years_in_role": 2,
     "communication_style": "Curious and quick; thinks aloud and checks his reasoning with the nurse in charge.",
     "scope": "Sees undifferentiated patients, presents to the attending, performs procedures under supervision."},
    {"id": "rosa-delgado", "name": "Rosa Delgado", "credentials": "RN, CEN", "role": "Charge Nurse, Emergency Department", "staff_role": "charge_rn",
     "specialty": "Emergency Nursing", "years_in_role": 15,
     "communication_style": "Brisk, protective of her patients, hands over in a structured format.",
     "scope": "Runs patient flow, triage escalation, staffing on the shift."},
    {"id": "samuel-adeyemi", "name": "Samuel Adeyemi", "credentials": "PharmD", "role": "Emergency Department Pharmacist", "staff_role": "pharmacist",
     "specialty": "Clinical Pharmacy", "years_in_role": 7,
     "communication_style": "Precise and unhurried; always asks about allergies and what the patient actually takes.",
     "scope": "Medication reconciliation, dosing advice, interaction checks."},
    {"id": "helen-brandt", "name": "Dr. Helen Brandt", "credentials": "MD", "role": "Hospital Medicine Attending", "staff_role": "attending",
     "specialty": "Internal Medicine", "years_in_role": 9,
     "communication_style": "Thorough; wants to know why now and what has changed at home.",
     "scope": "Accepts admissions from the emergency department and plans inpatient care."},
]

_ROLE_MAP = [("attending", r"attending|hospitalist|cardiolog|surgeon|physician"), ("resident", r"resident|fellow"), ("app", r"nurse practitioner|physician assistant|\bnp\b|\bpa\b"),
             ("charge_rn", r"charge"), ("rn", r"nurse|\brn\b"), ("pharmacist", r"pharmac"), ("tech", r"tech|therap|social work|case manag|dietit")]


def _from_private(path) -> dict | None:
    try:
        d = json.loads(path.read_text())
    except Exception:
        return None
    if not isinstance(d, dict):
        return None
    ov = d.get("clinician_overview") or {}
    if not ov.get("name"):
        return None
    role = str(ov.get("role") or "")
    staff_role = next((k for k, pat in _ROLE_MAP if re.search(pat, role.lower())), "attending")
    prof = d.get("professional_profile") or {}
    pc = d.get("personality_and_communication") or {}
    comm = pc.get("communication_style") or d.get("communication_style") or prof.get("communication_style") or ""
    if isinstance(comm, dict):
        comm = "; ".join(f"{k.replace('_', ' ')}: {v}" for k, v in comm.items() if isinstance(v, str))[:600]
    elif isinstance(comm, list):
        comm = "; ".join(str(x) for x in comm)[:600]
    return {"id": path.stem.replace("_", "-"), "name": ov.get("full_title") or ov.get("name"), "credentials": ov.get("credentials"),
            "role": role, "staff_role": staff_role, "specialty": ov.get("specialty"), "years_in_role": ov.get("years_in_role"),
            "communication_style": comm, "scope": prof.get("scope_of_practice"), "institution": ov.get("institution"),
            "profile": d, "source": "organizer_private"}


def list_clinicians() -> dict:
    private = [c for c in (_from_private(p) for p in clinician_profile_jsons()) if c]
    if private:
        return {"source": "organizer_private", "fictional": True, "clinicians": private}
    return {"source": "builtin", "fictional": True, "clinicians": [dict(c, source="builtin") for c in BUILTIN]}
