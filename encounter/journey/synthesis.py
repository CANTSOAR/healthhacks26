"""Care plan and debrief. The care plan is assembled ONLY from the shared record: if the team did not record it,
it is not in the plan. Entries written by a SAMPLED stage were copied from the case by the sampler (nobody spoke to
the patient), so the plan says how many of its entries are of that kind rather than claiming none of it is case content.

Sections hold only what belongs in them:
  problems   recorded facts: the presenting complaint, diagnoses, and what the patient first held back
  notes      clinicians' notes, as written; an unsupported one keeps its flag and is never a problem, evidence or action
  plan       plan lines a stage wrote, and the Recommendation given at handoff (not replies to the colleague)
  orders     requests; one with a result on the record (including a default-normal synthetic result) is resulted

The debrief (available once the journey is complete) may additionally say what the case
held that nobody found, the way encounter feedback does.
"""
from __future__ import annotations

from ..patient import _stems, filler_stems
from . import claims
from . import record as rec
from .definition import stage_kind

BEHAVIORS = ("use", "contribute", "identify", "communicate")


def _content(text: str) -> set[str]:
    return {s for s in _stems(text) if len(s) >= 4 and s not in filler_stems()}


def _row(e: dict) -> dict:
    out = rec.provenance(e)
    for k in ("fact_id", "category", "section", "section_title", "key", "value", "order_status", "request", "title", "artifact_id",
              "unsupported", "flag", "element_label", "used_in", "discrepancy_ids", "after_confrontation", "default_normal", "synthetic"):
        if e.get(k) not in (None, [], ""):
            out[k] = e[k]
    out["source_label"] = rec.SOURCE_LABEL.get(e["source"], e["source"])
    if e["by"].get("actor") == "sampled":
        out["copied_from_case"] = True
    return out


def care_plan(j: dict) -> dict:
    record = j["record"]
    es = record["entries"]
    prof = j["case"].get("profile") or {}
    facts = [e for e in es if e["kind"] == "fact"]
    sections: dict[str, dict] = {}
    for e in facts:
        s = sections.setdefault(e.get("section") or "notes", {"section": e.get("section") or "notes", "title": e.get("section_title") or "Notes", "items": []})
        s["items"].append(_row(e))
    # problems are recorded facts. A note (a demographic line, a whole triage note, an unsupported claim) is not a problem.
    problems, seen_p = [], set()
    for e in ([x for x in facts if x.get("category") == "chief_complaint"] + [x for x in facts if x.get("category") == "diagnosis"]
              + [x for x in facts if x.get("rule") in ("after_rapport", "denied_until_confronted")]):
        if e["entry_id"] not in seen_p:
            seen_p.add(e["entry_id"])
            problems.append(_row(e))
    notes = [_row(e) for e in es if e["kind"] == "note"]
    orders = []
    for e in es:
        if e["kind"] == "order":
            orders.append(dict(_row(e), results=[_row(a) for a in es if a["kind"] == "artifact" and e.get("order_status") == "resulted" and
                                                 (a.get("request") == e.get("request") or
                                                  (a["stage_id"] == e["stage_id"] and _content(a.get("title") or "") & _content(e["text"])))]))
    results = [_row(e) for e in es if e["kind"] == "artifact"] + [_row(e) for e in facts if e.get("category") in ("lab", "imaging", "exam")]
    acuity, disp = rec.latest(record, "acuity"), rec.latest(record, "disposition")
    open_q = [{"text": e["text"], "why": "recorded as an open question", "provenance": rec.provenance(e)} for e in es if e["kind"] == "question"]
    open_q += [{"text": f"Result not back: {e['text'].split(': ', 1)[-1]}", "why": "ordered, no result in the record", "provenance": rec.provenance(e)}
               for e in es if e["kind"] == "order" and e.get("is_order") and e.get("order_status") not in ("resulted", "no result defined")]
    open_q += [{"text": f"No result exists for: {e['text'].split(': ', 1)[-1]}", "why": "the scenario defines no result for this request",
                "provenance": rec.provenance(e)}
               for e in es if e["kind"] == "order" and e.get("is_order") and e.get("order_status") == "no result defined"]
    open_q += [{"text": d["note"], "why": "conflict flagged and not settled", "provenance": d["entries"][0], "discrepancy_id": d["discrepancy_id"]}
               for d in rec.unresolved(record)]
    open_q += [{"text": f"Stated without support in the record: \"{u['quote']}\"", "why": u["reason"], "provenance": rec.provenance(e)}
               for e in es for u in e.get("unsupported") or []]
    if not disp:
        open_q.append({"text": "No disposition has been recorded.", "why": "missing decision", "provenance": None})
    # plan lines a stage wrote, and the Recommendation part of the SBAR. A reply to the colleague is not a plan row.
    plan_items = [e for e in es if e["kind"] == "plan"] + [e for e in es if e["kind"] == "handoff" and e.get("element") == "R"
                                                           and not e.get("in_reply_to") and e.get("status") != "unsupported"]
    # coordinated plan: each problem with the recorded evidence and the actions that speak to it
    coordinated, used_actions = [], set()
    actions = plan_items + [e for e in es if e["kind"] == "order" and e.get("is_order")]
    for p in problems[:6]:
        words = _content(p["text"])
        ev = [_row(e) for e in facts if e["entry_id"] not in seen_p and len(_content(e["text"]) & words) >= 2][:4]
        acts = [e for e in actions if len(_content(e["text"]) & words) >= 1]
        used_actions |= {e["entry_id"] for e in acts}
        coordinated.append({"problem": p, "evidence": ev, "actions": [_row(e) for e in acts],
                            "roles": sorted({p["by"]["role_label"]} | {e["by"]["role_label"] for e in acts} | {x["by"]["role_label"] for x in ev})})
    rest = [_row(e) for e in actions if e["entry_id"] not in used_actions]
    contributions = []
    for i, sdef in enumerate(j["definition"]["stages"]):
        sst = j["stages"][i]
        mine = [e for e in es if e["stage_id"] == sdef["stage_id"]]
        counts: dict[str, int] = {}
        for e in mine:
            counts[e["kind"]] = counts.get(e["kind"], 0) + 1
        contributions.append({"stage_id": sdef["stage_id"], "stage_title": sdef.get("title") or sdef["stage_id"], "role": sdef["learner_role"],
                              "played_by": sst["played_by"], "player": sst["player"], "status": sst["status"], "counts": counts,
                              "highlights": [_row(e) for e in mine if e["kind"] in ("fact", "decision", "note", "medication", "plan", "question")][:6]})
    flow = []
    for e in es:
        for u in e.get("used_in") or []:
            flow.append({"entry": rec.provenance(e), "used_in_stage": u["stage_id"], "how": u["how"], "quote": u.get("quote"), "turn": u.get("turn")})
    n_sampled = len([e for e in es if e["by"].get("actor") == "sampled"])
    n_sim = len([e for e in es if e["by"].get("actor") == "sim"])
    origin = "the shared record only"
    if n_sampled or n_sim:
        bits = ([f"{n_sampled} were written by sampled stages, which copy them from the case file rather than asking the patient"] if n_sampled else []) + \
               ([f"{n_sim} came from the running simulation"] if n_sim else [])
        origin += f". Of those, {' and '.join(bits)}; the rest are what a played stage elicited or wrote"
    else:
        origin += ": every entry is something a played stage elicited or wrote"
    return {"journey_id": j["journey_id"], "status": j["status"], "complete": j["status"] == "complete",
            "assembled_from": origin, "n_entries": len(es), "n_sampled_entries": n_sampled, "notes": notes,
            "unsupported_check": claims.SCOPE_NOTE,
            "patient": {"name": prof.get("name"), "age": prof.get("age"), "gender": prof.get("gender")},
            "problems": problems, "findings": list(sections.values()),
            "medications": [_row(e) for e in es if e["kind"] == "medication" or e.get("category") == "medications"],
            "allergies": [_row(e) for e in facts if e.get("category") == "allergies"],
            "orders": orders, "results": results,
            "decisions": {"acuity": _row(acuity) if acuity else None, "disposition": _row(disp) if disp else None},
            "plan": [_row(e) for e in plan_items], "coordinated_plan": coordinated, "other_actions": rest,
            "open_questions": open_q, "discrepancies": rec.public(record["discrepancies"]), "contributions": contributions,
            "information_flow": flow}


def _behaviors(j: dict, idx: int, sdef: dict, objs: list[dict]) -> dict:
    """USE / CONTRIBUTE / IDENTIFY / COMMUNICATE for one stage, counted from the record."""
    sid = sdef["stage_id"]
    es = j["record"]["entries"]
    mine = [e for e in es if e["stage_id"] == sid]
    used = [(e, u) for e in es for u in e.get("used_in") or [] if u["stage_id"] == sid]
    ident = [e for e in mine if e["kind"] == "question"] + [e for e in mine if e["kind"] == "patient_report"]
    comm = [e for e in mine if e["kind"] in ("note", "handoff", "plan", "medication")]
    def ev(rows, n=2):
        return [{"quote": (r.get("quote") or r["text"])[:180], "entry_id": r["entry_id"]} for r in rows[:n]]
    return {"use": {"count": len(used), "not_assessable": idx == 0 or not [e for e in es if e["stage_index"] < idx],
                    "evidence": [{"quote": (u.get("quote") or e["text"])[:180], "entry_id": e["entry_id"], "how": u["how"]} for e, u in used[:2]]},
            "contribute": {"count": len([e for e in mine if e["kind"] in ("fact", "artifact", "order", "decision")]),
                           "evidence": ev([e for e in mine if e["kind"] in ("fact", "decision")])},
            "identify": {"count": len(ident), "evidence": ev(ident)},
            "communicate": {"count": len(comm), "evidence": ev(comm)}}


def debrief(j: dict, stages_public: list[dict]) -> dict:
    record, case = j["record"], j["case"]
    es = record["entries"]
    known = set(rec.fact_ids(record))
    stages, roles = [], {}
    for i, sdef in enumerate(j["definition"]["stages"]):
        sst, pub = j["stages"][i], stages_public[i]
        objs = [rec.public(o) for o in sst["objectives"]]
        row = {"stage_id": sdef["stage_id"], "title": pub["title"], "interaction_type": sdef["interaction_type"], "kind": stage_kind(sdef),
               "role": sdef["learner_role"], "played_by": sst["played_by"], "player": sst["player"], "status": sst["status"],
               "objectives": objs, "behaviors": _behaviors(j, i, sdef, objs), "result": sst["result"], "result_note": sst.get("result_note"),
               "writeback": pub["writeback"]}
        fb = sst.get("session_feedback")
        if fb and sst["played_by"] == "human":
            row["encounter_feedback"] = {k: fb.get(k) for k in ("strengths", "next_time", "communication", "structure", "rubric", "grader", "formative_note")}
        if sst.get("handoff") and sst["handoff"].get("grading"):
            row["handoff"] = {"colleague": sst["handoff"]["colleague"], "sbar": sst["handoff"]["sbar"], "grading": rec.public(sst["handoff"]["grading"]),
                              "questions": [{k: q.get(k) for k in ("question_id", "text", "about", "answered", "answer", "unresolved", "attempts")}
                                            for q in sst["handoff"]["questions"]]}
        stages.append(row)
        r = roles.setdefault(sdef["learner_role"]["label"], {"role": sdef["learner_role"], "stages": [], "played_by": [], "counts": {k: 0 for k in
                             ("met", "partly_demonstrated", "not_observed", "not_assessable")}, "objectives": []})
        r["stages"].append(sdef["stage_id"])
        r["played_by"].append(sst["played_by"])
        for o in objs:
            r["counts"][o["result"]] += 1
            r["objectives"].append({"stage_id": sdef["stage_id"], "objective_id": o["objective_id"], "criterion": o["criterion"], "result": o["result"],
                                    "evidence": o["evidence"][:1]})
    # team-level findings
    hand = [(i, s) for i, s in enumerate(j["stages"]) if s.get("handoff") and s["handoff"].get("grading")]
    lost, omitted, unsupported = [], [], []
    for i, s in hand:
        g = s["handoff"]["grading"]
        for el in g["elements"].values():
            for o in el["omitted"]:
                row = {"text": o["text"], "label": o["label"], "critical": o["critical"], "element": el["label"], "provenance": o["provenance"],
                       "handoff_stage": s["stage_id"]}
                omitted.append(row)
                if o["critical"]:
                    lost.append(dict(row, how="known to the team before the handoff, not passed on"))
            for u in el["unsupported"]:
                unsupported.append({"quote": u["quote"], "reason": u["reason"], "element": el["label"], "handoff_stage": s["stage_id"]})
    for e in es:
        for u in e.get("unsupported") or []:
            if e["kind"] != "handoff":
                unsupported.append({"quote": u["quote"], "reason": u["reason"], "element": e["kind"], "handoff_stage": None, "stage_id": e["stage_id"]})
    never = [{"fact_id": f["fact_id"], "category": f.get("category"), "text": f.get("statement"), "critical": True,
              "how": "in the case, never reached the shared record"} for f in case.get("facts") or [] if f.get("critical") and f["fact_id"] not in known]
    carried = [{"entry": rec.provenance(e), "used_in": e["used_in"]} for e in es if e.get("used_in")]
    ft = case.get("faculty_truth") or {}
    disp = rec.latest(record, "disposition")
    return {"journey_id": j["journey_id"], "status": j["status"], "labels": ["met", "partly_demonstrated", "not_observed", "not_assessable"],
            "stages": stages, "roles": list(roles.values()),
            "team": {"information_lost": lost, "never_found": never, "discrepancies_unresolved": rec.public(rec.unresolved(record)),
                     "discrepancies_resolved": rec.public([d for d in record["discrepancies"] if d["resolved"]]),
                     "handoff_omitted": omitted, "unsupported_statements": unsupported, "carried_forward": carried,
                     "summary": {"entries": len(es), "facts_recorded": len(known), "critical_never_found": len(never),
                                 "lost_at_handoff": len(lost), "unresolved_discrepancies": len(rec.unresolved(record)),
                                 "unsupported_statements": len(unsupported), "carried_forward": len(carried),
                                 "handoff_questions_unresolved": len([q for _, s in hand for q in s["handoff"]["questions"] if q.get("unresolved")])},
                     "unsupported_check": claims.SCOPE_NOTE},
            "case_debrief": {"diagnosis": ft.get("diagnosis"), "expected_disposition": ft.get("expected_disposition"),
                             "recorded_disposition": disp.get("value") if disp else None, "teaching_points": ft.get("teaching_points") or []},
            "formative_note": "Formative feedback from deterministic rules over the shared record and transcripts. Not a validated assessment.",
            "results": [s["result"] for s in j["stages"] if s["result"]]}
