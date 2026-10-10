"""The shared record: one per journey instance. Every entry carries who added it, in which stage and turn,
from which source, and its fact_id when it corresponds to case truth.

Later stages read this record, never the case. Discrepancies are derived only from authored case content
(a fact's cover_answer against the fact itself or against its authored confrontation evidence) or from two
roles writing different values for the same decision key. Nothing here invents a conflict.

Keys starting with '_' are server-side (they can name facts the team has not found) and are stripped from
every student view.
"""
from __future__ import annotations

from ..store import now_iso
from ..taxonomy import CATEGORY_SECTION

SOURCES = ("patient_statement", "chart_artifact", "measurement", "colleague", "inference", "simulation")
ACTORS = ("human", "ai", "sampled", "sim")
KINDS = ("fact", "patient_report", "order", "artifact", "decision", "note", "medication", "plan", "question", "handoff")

SOURCE_LABEL = {"patient_statement": "patient statement", "chart_artifact": "chart artifact", "measurement": "measurement",
                "colleague": "colleague", "inference": "clinician's inference", "simulation": "simulation"}


def section_for(category: str | None) -> tuple[str, str]:
    return CATEGORY_SECTION.get(category or "", ("notes", "Notes"))


def new_record() -> dict:
    return {"entries": [], "discrepancies": [], "seq": 0}


def by(stage: dict, actor: str, name: str | None = None) -> dict:
    """Who is writing: the stage's learner role, played by a person, an AI colleague, the sampler or the simulation."""
    role = stage["learner_role"]
    return {"staff_role": role["staff_role"], "role_label": role["label"], "actor": actor, "name": name}


def add(record: dict, stage: dict, stage_index: int, who: dict, kind: str, text: str, source: str, turn: int | None = None,
        **extra) -> dict:
    assert kind in KINDS and source in SOURCES and who["actor"] in ACTORS
    record["seq"] += 1
    e = {"entry_id": f"e{record['seq']:03d}", "kind": kind, "text": (text or "").strip(), "by": dict(who),
         "stage_id": stage["stage_id"], "stage_title": stage.get("title") or stage["stage_id"], "stage_index": stage_index,
         "turn": turn, "time": now_iso(), "source": source, "status": "established", "fact_id": None, "used_in": []}
    e.update(extra)
    record["entries"].append(e)
    return e


def fact_ids(record: dict) -> list[str]:
    return [e["fact_id"] for e in record["entries"] if e.get("fact_id")]


def has_fact(record: dict, fact_id: str) -> bool:
    return any(e.get("fact_id") == fact_id for e in record["entries"])


def artifact_ids(record: dict) -> list[str]:
    return [e["artifact_id"] for e in record["entries"] if e["kind"] == "artifact" and e.get("artifact_id")]


def find(record: dict, entry_id: str) -> dict | None:
    return next((e for e in record["entries"] if e["entry_id"] == entry_id), None)


def latest(record: dict, key: str) -> dict | None:
    hits = [e for e in record["entries"] if e["kind"] == "decision" and e.get("key") == key]
    return hits[-1] if hits else None


def mark_used(entry: dict, stage_id: str, turn: int | None, how: str, quote: str | None = None) -> None:
    if entry["stage_id"] == stage_id:
        return                                        # using your own entry is not continuity between stages
    if not any(u["stage_id"] == stage_id and u["how"] == how for u in entry["used_in"]):
        entry["used_in"].append({"stage_id": stage_id, "turn": turn, "how": how, "quote": (quote or "")[:200] or None})


def provenance(e: dict) -> dict:
    return {"entry_id": e["entry_id"], "text": e["text"], "kind": e["kind"], "by": e["by"], "stage_id": e["stage_id"],
            "stage_title": e["stage_title"], "turn": e["turn"], "source": e["source"], "time": e["time"], "status": e["status"]}


# ---------------------------------------------------------------- discrepancies (authored only)

def _disc(record: dict, a: dict, b: dict, kind: str, note: str, resolved: bool, basis: str, about: str | None) -> dict | None:
    did = f"d-{a['entry_id']}-{b['entry_id']}"
    cur = next((d for d in record["discrepancies"] if d["discrepancy_id"] == did), None)
    if cur:
        return None
    d = {"discrepancy_id": did, "kind": kind, "note": note, "entries": [provenance(a), provenance(b)], "resolved": resolved,
         "resolved_by": b["entry_id"] if resolved else None, "basis": basis, "flagged_in_stage": b["stage_id"], "time": now_iso(),
         "_about": about}
    record["discrepancies"].append(d)
    for e in (a, b):
        e.setdefault("discrepancy_ids", [])
        if did not in e["discrepancy_ids"]:
            e["discrepancy_ids"].append(did)
    return d


def detect_discrepancies(record: dict, case: dict) -> list[dict]:
    """Flag conflicts between entries. Returns the newly flagged ones."""
    facts = {f["fact_id"]: f for f in case.get("facts") or []}
    new: list[dict] = []
    entries = record["entries"]
    for p in [e for e in entries if e["kind"] == "patient_report" and e.get("_about")]:
        f = facts.get(p["_about"])
        if not f:
            continue
        truth = next((e for e in entries if e.get("fact_id") == p["_about"]), None)
        evidence = []
        for c in (f.get("disclosure") or {}).get("confront_with") or []:
            evidence += [e for e in entries if e.get("artifact_id") == c and e["kind"] == "artifact"]
            evidence += [e for e in entries if e.get("fact_id") == c]
        for ev in evidence:
            d = _disc(record, p, ev, "self_report_vs_record",
                      f"The patient's own account and \"{ev.get('title') or ev['text'][:80]}\" do not agree.", False,
                      "authored: the case names this item as evidence against the patient's first account", p["_about"])
            if d:
                new.append(d)
        if truth:
            d = _disc(record, p, truth, "self_report_changed", "The patient later gave a different account from the first one.", True,
                      "authored: the case defines the first answer as a misreport of this fact", p["_about"])
            if d:
                new.append(d)
            p["status"] = "superseded"
            for d0 in record["discrepancies"]:          # the corrected account settles the open conflicts about the same fact
                if d0.get("_about") == p["_about"] and not d0["resolved"]:
                    d0["resolved"], d0["resolved_by"] = True, truth["entry_id"]
        elif evidence:
            p["status"] = "disputed"
    # two roles, same decision key, different values
    by_key: dict[str, list[dict]] = {}
    for e in entries:
        if e["kind"] == "decision" and e.get("key"):
            by_key.setdefault(e["key"], []).append(e)
    for key, es in by_key.items():
        for i, a in enumerate(es):
            for b in es[i + 1:]:
                if a["stage_id"] != b["stage_id"] and a.get("value") != b.get("value"):
                    d = _disc(record, a, b, "role_disagreement",
                              f"Two roles recorded a different {key.replace('_', ' ')}: {a.get('value')} and {b.get('value')}.", False,
                              "two recorded decisions", None)
                    if d:
                        new.append(d)
    return new


def unresolved(record: dict) -> list[dict]:
    return [d for d in record["discrepancies"] if not d["resolved"]]


# ---------------------------------------------------------------- views

def public(obj):
    """Deep copy without server-side keys."""
    if isinstance(obj, dict):
        return {k: public(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [public(v) for v in obj]
    return obj


def student_view(record: dict) -> dict:
    entries = public(record["entries"])
    for e in entries:
        e["source_label"] = SOURCE_LABEL.get(e["source"], e["source"])
    counts: dict[str, int] = {}
    for e in entries:
        counts[e["kind"]] = counts.get(e["kind"], 0) + 1
    return {"entries": entries, "discrepancies": public(record["discrepancies"]), "counts": counts,
            "n_unresolved": len(unresolved(record))}


def handover_text(record: dict, upto_index: int) -> str:
    """What a stage is shown about earlier stages that is not a case fact (facts appear in the chart as known to the team)."""
    lines: list[str] = []
    for e in record["entries"]:
        if e["stage_index"] >= upto_index or e.get("fact_id") or e["kind"] in ("artifact", "handoff"):
            continue
        who = e["by"]["role_label"]
        if e["kind"] == "decision":
            lines.append(f"{e['text']} ({who})")
        elif e["kind"] == "patient_report":
            lines.append(f"Patient told the {who.lower()}: \"{e['text']}\"")
        elif e["kind"] == "order":
            lines.append(f"{e['text']} [{e.get('order_status') or 'requested'}] ({who})")
        elif e["kind"] == "question":
            lines.append(f"Open question from the {who.lower()}: {e['text']}")
        else:
            lines.append(f"{e['kind'].capitalize()} ({who}): {e['text']}")
    for d in unresolved(record):
        lines.append(f"Flagged: {d['note']}")
    return "\n".join(lines)
