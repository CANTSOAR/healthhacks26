"""Patient-facing stages: the stage-scoped view of the case, ledger -> shared-record sync, the
sampler-equivalent for a stage nobody plays, the stage's written outputs, and stage objectives.

A played stage is an ordinary encounter session (encounter.session / encounter.disclosure) on a copy of the
case narrowed to the role's scope and opened with what earlier stages recorded. The disclosure engine alone
decides what is released, exactly as in a single encounter.
"""
from __future__ import annotations

import copy
import fnmatch
import random

from ..disclosure import PATIENT_VOICED, Engine
from ..session import DISPOSITIONS, order_label
from . import record as rec
from .definition import DEFAULT_MINUTES

LABELS = ("met", "partly_demonstrated", "not_observed", "not_assessable")


def _req_in_scope(request: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(request, p) for p in patterns)


def _fact_in_scope(f: dict, stage: dict) -> bool:
    sc = stage.get("scope") or {}
    d = f.get("disclosure") or {}
    if d.get("rule") == "on_request":
        return _req_in_scope(str(d.get("request") or "").lower(), sc.get("requests") or [])
    cats = sc.get("fact_categories")
    return cats == "all" or f.get("category") in (cats or [])


def stage_case(case: dict, definition: dict, stage: dict, stage_index: int, record: dict) -> dict:
    """The case as this role may explore it: in-scope facts and requests, plus everything the team already recorded."""
    c = {k: copy.deepcopy(v) for k, v in case.items() if not k.startswith("_")}
    known = set(rec.fact_ids(record))
    released = set(rec.artifact_ids(record))
    patterns = (stage.get("scope") or {}).get("requests") or []
    team_triages = any(s["interaction_type"] == "triage" for s in definition["stages"])
    c["facts"] = [f for f in c.get("facts") or [] if f["fact_id"] in known or _fact_in_scope(f, stage)]
    chart = c.setdefault("chart", {})
    arts = []
    for a in chart.get("artifacts") or []:
        rel = a.get("release") or {}
        if a["artifact_id"] in released:
            a["release"] = {"rule": "initial"}
            arts.append(a)
        elif rel.get("rule") == "initial":
            if not (team_triages and a.get("section_id") == "triage"):      # the team writes its own triage note
                arts.append(a)
        elif rel.get("rule") == "on_request" and _req_in_scope(Engine._artifact_request(a), patterns):
            arts.append(a)
        elif rel.get("rule") not in ("initial", "on_request") and _req_in_scope("order:*", patterns):
            arts.append(a)                                                   # on_fact / delayed releases follow the orders
    chart["artifacts"] = arts
    secs = [s for s in chart.get("sections") or [] if not (team_triages and s.get("section_id") == "triage")]
    text = rec.handover_text(record, stage_index)
    if text:
        secs.insert(0, {"section_id": "team_record", "title": "From the shared record", "release": "initial", "static_text": text})
    chart["sections"] = secs
    fact_ids = {f["fact_id"] for f in c["facts"]}
    reqs = set(Engine(c).case_requests)
    c["objectives"] = [o for o in (c.get("objectives") or []) if stage.get("case_objectives")
                       and set(o.get("linked_fact_ids") or []) <= fact_ids and {str(r).lower() for r in o.get("linked_requests") or []} <= reqs]
    prof = c.get("profile") or {}
    brief = str(stage.get("brief") or "").replace("{name}", str(prof.get("name") or "the patient")).replace("{age}", str(prof.get("age") or ""))
    c["prebrief"] = brief or c.get("prebrief")
    c["learner_role"] = stage["learner_role"]["label"]
    c["status"] = "published"
    return c


def scoped_requests(engine: Engine, stage: dict) -> list[dict]:
    patterns = (stage.get("scope") or {}).get("requests") or []
    return [r for r in engine.available_requests() if _req_in_scope(r["request"], patterns)]


def request_text(request: str) -> str:
    kind, _, name = request.partition(":")
    words = name.replace("_", " ")
    return {"exam": f"Examination: {words}", "order": f"Ordered: {order_label(request) or words}"}.get(kind, f"Requested: {words}")


def _source_for(f: dict, rule: str) -> str:
    if rule in PATIENT_VOICED:
        return "patient_statement"
    return "measurement" if f.get("category") in ("vitals", "exam") else "chart_artifact"


def add_fact(record: dict, stage: dict, idx: int, who: dict, engine: Engine, fid: str, rule: str, turn: int | None, quote: str | None = None,
             **extra) -> dict | None:
    if rec.has_fact(record, fid):
        return None
    f = engine.by_id[fid]
    sid, stitle = rec.section_for(f.get("category"))
    if f.get("chart_section"):
        sid = f["chart_section"]
    return rec.add(record, stage, idx, who, "fact", engine.fact_text(f), _source_for(f, rule), turn, fact_id=fid, category=f.get("category"),
                   section=sid, section_title=stitle, rule=rule, quote=(quote or "")[:240] or None,
                   status="patient_reported" if rule in PATIENT_VOICED else "established", polarity=f.get("polarity"),
                   _critical=bool(f.get("critical")), **extra)


def add_cover(record: dict, stage: dict, idx: int, who: dict, engine: Engine, fid: str, turn: int | None, quote: str | None) -> dict | None:
    f = engine.by_id.get(fid) or {}
    cover = f.get("cover_answer")
    if not cover or rec.has_fact(record, fid):
        return None
    if any(e["kind"] == "patient_report" and e.get("_about") == fid and e["stage_id"] == stage["stage_id"] for e in record["entries"]):
        return None
    sid, stitle = rec.section_for(f.get("category"))
    return rec.add(record, stage, idx, who, "patient_report", cover, "patient_statement", turn, status="patient_reported",
                   section=f.get("chart_section") or sid, section_title=stitle, quote=(quote or "")[:240] or None, _about=fid)


def add_request(record: dict, stage: dict, idx: int, who: dict, request: str, result: str | None, turn: int | None) -> dict:
    cur = next((e for e in record["entries"] if e["kind"] == "order" and e.get("request") == request), None)
    status = {"released": "resulted", "already_available": "resulted", "pending": "pending", "not_available": "no result defined"}.get(result or "", result or "requested")
    if cur:
        if status == "resulted":
            cur["order_status"] = status
        return cur
    return rec.add(record, stage, idx, who, "order", request_text(request), "inference", turn, request=request, order_status=status,
                   is_order=request.startswith("order:") and order_label(request) is not None)


def add_artifact(record: dict, stage: dict, idx: int, who: dict, engine: Engine, aid: str, turn: int | None) -> dict | None:
    if aid in rec.artifact_ids(record):
        return None
    a = engine.art_by_id[aid]
    req = Engine._artifact_request(a)
    for e in record["entries"]:
        if e["kind"] == "order" and e.get("request") == req:
            e["order_status"] = "resulted"
    return rec.add(record, stage, idx, who, "artifact", f"{a.get('title') or aid} added to the chart", "chart_artifact", turn, artifact_id=aid,
                   title=a.get("title") or aid, artifact_kind=a.get("kind"))


def sync_session(record: dict, stage: dict, idx: int, who: dict, case: dict, session_case: dict, state: dict, synced: int) -> tuple[int, list[dict]]:
    """Copy what the session's ledger released since `synced` into the shared record. Returns (new synced seq, new entries)."""
    engine = Engine(session_case)
    new: list[dict] = []
    for ev in state["ledger"]:
        if ev["seq"] < synced or ev["kind"] == "finish":
            continue
        turn, quote = ev.get("turn"), ev.get("text")
        rules = ev.get("rule_fired") or {}
        for req in ev.get("requests") or []:
            res = ev.get("result") if ev["kind"] == "request" else None
            if res is None and any((f.get("disclosure") or {}).get("rule") == "on_request" and str((f.get("disclosure") or {}).get("request")).lower() == req
                                   and f["fact_id"] in (ev.get("disclosed_fact_ids") or []) for f in engine.facts):
                res = "released"                         # asked for in conversation ("let me listen to your chest") and answered at once
            new.append(add_request(record, stage, idx, who, req, res, turn))
        for fid in ev.get("disclosed_fact_ids") or []:
            rule = rules.get(fid, "")
            if rule == "known_to_care_team":
                continue
            e = add_fact(record, stage, idx, who, engine, fid, rule, turn, quote if ev["kind"] == "turn" else None,
                         after_confrontation=bool((ev.get("confronted_with") or {}).get(fid)) or None)
            if e:
                new.append(e)
        for aid in ev.get("released_artifact_ids") or []:
            if ev["kind"] == "start" and aid in rec.artifact_ids(record):
                continue
            e = add_artifact(record, stage, idx, who, engine, aid, turn)
            if e:
                new.append(e)
        for fid in ev.get("covered_fact_ids") or []:
            e = add_cover(record, stage, idx, who, engine, fid, turn, quote)
            if e:
                new.append(e)
        # continuity: the learner came back to something an earlier stage recorded
        for fid in ev.get("repeated_fact_ids") or []:
            for e in record["entries"]:
                if e.get("fact_id") == fid:
                    rec.mark_used(e, stage["stage_id"], turn, "asked the patient about it again", quote)
        for m in ev.get("matched_intents") or []:
            for e in record["entries"]:
                if e["kind"] == "patient_report" and e.get("_about") == m.get("fact_id"):
                    rec.mark_used(e, stage["stage_id"], turn, "followed up the patient's earlier answer", quote)
        for fid, cited in (ev.get("confronted_with") or {}).items():
            for c in cited:
                for e in record["entries"]:
                    if e.get("artifact_id") == c or e.get("fact_id") == c:
                        rec.mark_used(e, stage["stage_id"], turn, "raised it with the patient", quote)
        synced = ev["seq"] + 1
    rec.detect_discrepancies(record, case)
    return synced, [e for e in new if e]


# ---------------------------------------------------------------- written outputs (human finish and sampler share this)

def normalise_writes(stage: dict, body: dict) -> tuple[dict, list[str]]:
    """Validate what the stage wants to write. Returns (clean writes, missing required keys)."""
    out: dict = {}
    acu = body.get("acuity")
    if isinstance(acu, (int, float, str)) and str(acu).strip().isdigit() and 1 <= int(acu) <= 5:
        out["acuity"] = int(acu)
    note = str(body.get("note") or body.get("summary") or "").strip()[:4000]
    if note:
        out["note"] = note
    disp = str(body.get("disposition") or "").strip().lower()
    if disp in DISPOSITIONS and disp != "undecided":
        out["disposition"] = disp
    for k in ("orders", "med_list", "plan", "open_questions"):
        v = body.get(k)
        if isinstance(v, str):
            v = [x for x in v.splitlines()]
        items = [str(x).strip()[:500] for x in (v or []) if isinstance(x, (str, int, float)) and str(x).strip()]
        if items:
            out[k] = items[:30]
    wr = stage.get("writes") or {}
    allowed = set(wr.get("required") or []) | set(wr.get("optional") or [])
    out = {k: v for k, v in out.items() if k in allowed}
    missing = [k for k in wr.get("required") or [] if k not in out and k not in ("sbar", "orders")]
    return out, missing


def apply_writes(record: dict, stage: dict, idx: int, who: dict, writes: dict, turn: int | None, support_fn=None) -> list[dict]:
    new = []

    # support is judged against the record as it stood before this stage's own written lines were added
    pre: dict[str, dict] = {}
    if support_fn is not None and who["actor"] == "human":
        for kind, lines in (("A", [writes["note"]] if "note" in writes else []), ("B", writes.get("med_list") or [])):
            for line in lines:
                pre[line] = support_fn(line, kind)

    def note_support(e: dict) -> dict:
        s = pre.get(e["text"])
        if s:
            e["supported_by"] = s["entry_ids"]
            if s["unsupported"]:
                e["status"], e["unsupported"] = "unsupported", s["unsupported"]
        return e

    if "acuity" in writes:
        new.append(rec.add(record, stage, idx, who, "decision", f"Acuity: ESI {writes['acuity']}", "inference", turn, key="acuity", value=writes["acuity"]))
    if "note" in writes:
        new.append(note_support(rec.add(record, stage, idx, who, "note", writes["note"], "inference", turn, status="assessment")))
    for line in writes.get("med_list") or []:
        new.append(note_support(rec.add(record, stage, idx, who, "medication", line, "inference", turn, status="reconciled")))
    for line in writes.get("plan") or []:
        new.append(rec.add(record, stage, idx, who, "plan", line, "inference", turn, status="planned"))
    for line in writes.get("open_questions") or []:
        new.append(rec.add(record, stage, idx, who, "question", line, "inference", turn, status="open"))
    if "disposition" in writes:
        new.append(rec.add(record, stage, idx, who, "decision", f"Disposition: {writes['disposition']}", "inference", turn, key="disposition",
                           value=writes["disposition"]))
    return new


# ---------------------------------------------------------------- sampler-equivalent

def sample_quality(seed: int, stage_id: str, quality: float | None) -> float:
    """ASSUMED distribution: uniform 0.55-0.95 per unplayed stage (no measured source for stage-level staff quality)."""
    if quality is not None:
        return max(0.0, min(1.0, float(quality)))
    return round(random.Random(f"{seed}:{stage_id}:q").uniform(0.55, 0.95), 2)


def auto_resolve(record: dict, definition: dict, stage: dict, idx: int, who: dict, case: dict, seed: int, quality: float | None) -> dict:
    """Fill the stage from the case with a sampled quality, writing to the record exactly what a played stage would:
    facts found (each found with a probability set by the sampled quality), requests, the patient's authored first
    answers, and the stage's decisions. Deterministic for (journey seed, stage)."""
    q = sample_quality(seed, stage["stage_id"], quality)
    rng = random.Random(f"{seed}:{stage['stage_id']}")
    sc = stage_case(case, definition, stage, idx, record)
    engine = Engine(sc)
    ft = case.get("faculty_truth") or {}
    expected = {str(r).lower() for r in ft.get("expected_orders") or []}
    start_known = set(rec.fact_ids(record))
    found: list[str] = []
    # what the chart already holds for this role
    for f in engine.facts:
        if engine.rule(f) == "chart_initial" and add_fact(record, stage, idx, who, engine, f["fact_id"], "chart_initial", None):
            found.append(f["fact_id"])
    # requests: the ones the case expects, each with probability rising with quality
    made: list[str] = []
    for req in engine.case_requests:
        if req.startswith("artifact:"):
            continue
        p = min(1.0, q * 1.12) if req in expected else 0.25 * q
        if rng.random() < p:
            made.append(req)
            has_result = False
            for f in engine.facts:
                d = f.get("disclosure") or {}
                if d.get("rule") == "on_request" and str(d.get("request")).lower() == req:
                    has_result = True
                    if add_fact(record, stage, idx, who, engine, f["fact_id"], "on_request", None):
                        found.append(f["fact_id"])
            arts = [a for a in engine.artifacts if (a.get("release") or {}).get("rule") == "on_request" and Engine._artifact_request(a) == req]
            add_request(record, stage, idx, who, req, "released" if (has_result or arts) else "not_available", None)
            for a in arts:
                add_artifact(record, stage, idx, who, engine, a["artifact_id"], None)
    seen = set(rec.fact_ids(record)) | set(rec.artifact_ids(record))
    for f in engine.facts:
        fid, rule = f["fact_id"], engine.rule(f)
        if fid in start_known or rec.has_fact(record, fid) or rule not in PATIENT_VOICED or f.get("patient_knows") is False:
            continue
        crit = bool(f.get("critical"))
        if rule == "volunteered":
            ok = True
        elif rule == "if_asked":
            ok = rng.random() < (min(1.0, q * 1.2) if crit else q * 0.95)
        elif rule == "after_rapport":
            asked = rng.random() < q
            ok = asked and rng.random() < q * 0.7
            if asked and not ok:
                add_cover(record, stage, idx, who, engine, fid, None, None)
        else:                                          # denied_until_confronted
            asked = rng.random() < min(1.0, q * 1.12)
            evidence = [c for c in (f.get("disclosure") or {}).get("confront_with") or [] if c in seen]
            ok = asked and bool(evidence) and rng.random() < q
            if asked and not ok:
                add_cover(record, stage, idx, who, engine, fid, None, None)
            if ok:
                if not any(e["kind"] == "patient_report" and e.get("_about") == fid for e in record["entries"]):
                    add_cover(record, stage, idx, who, engine, fid, None, None)     # the first answer came first, then the correction
                for e in record["entries"]:
                    if e.get("artifact_id") in evidence or e.get("fact_id") in evidence:
                        rec.mark_used(e, stage["stage_id"], None, "raised it with the patient")
        if ok and add_fact(record, stage, idx, who, engine, fid, rule, None):
            found.append(fid)
    rec.detect_discrepancies(record, case)
    # decisions the stage must write
    wr = stage.get("writes") or {}
    keys = list(wr.get("required") or []) + list(wr.get("optional") or [])
    writes: dict = {}
    prof = case.get("profile") or {}
    mine = [e for e in record["entries"] if e["stage_id"] == stage["stage_id"]]
    if "acuity" in keys:
        true_acuity = int(ft.get("acuity") or 3)
        slip = rng.random() >= q * 1.25
        writes["acuity"] = max(1, min(5, true_acuity + (rng.choice((-1, 1)) if slip else 0)))
    if "note" in keys:
        lead = [e["text"] for e in mine if e.get("category") in ("chief_complaint", "hpi")][:3]
        said = [f"Says: \"{e['text']}\"" for e in mine if e["kind"] == "patient_report"][:2]
        who_line = f"{prof.get('age')}-year-old {prof.get('gender') or 'patient'}." if prof.get("age") else ""
        writes["note"] = " ".join(x for x in [who_line] + [t.rstrip(".") + "." for t in lead] + said if x)[:1200] or "Seen; nothing further recorded."
    if "disposition" in keys and ft.get("expected_disposition") in DISPOSITIONS:
        if rng.random() < q * 1.25:
            writes["disposition"] = ft["expected_disposition"]
    if "med_list" in keys:
        meds = [e["text"] for e in record["entries"] if e.get("category") == "medications"]
        meds += [f"Patient reports: \"{e['text']}\"" for e in record["entries"] if e["kind"] == "patient_report" and e.get("section") == "medications"]
        writes["med_list"] = meds or ["No medicines recorded"]
    if "open_questions" in keys:
        oq = [f"Unresolved: {d['note']}" for d in rec.unresolved(record)]
        oq += [f"Result pending: {e['text']}" for e in record["entries"] if e["kind"] == "order" and e.get("order_status") == "pending"]
        if oq:
            writes["open_questions"] = oq[:4]
    if "plan" in keys:
        plan = [f"Follow up {e['text'].split(': ', 1)[-1]}" for e in mine if e["kind"] == "order" and e.get("is_order")][:3]
        if writes.get("disposition"):
            plan.append({"admit": "Admit for treatment and monitoring", "discharge": "Discharge with follow-up",
                         "transfer": "Arrange transfer"}[writes["disposition"]])
        if plan:
            writes["plan"] = plan
    apply_writes(record, stage, idx, who, writes, None)
    rec.detect_discrepancies(record, case)
    minutes = float(stage.get("minutes") or DEFAULT_MINUTES.get(stage["interaction_type"], 10))
    return {"quality": q, "found": found, "requests": made, "writes": writes, "duration_min": minutes}


# ---------------------------------------------------------------- stage objectives

def _q(text: str | None, n: int = 180) -> str:
    t = " ".join((text or "").split())
    return t if len(t) <= n else t[: n - 1] + "…"


def grade_objectives(stage: dict, idx: int, record: dict, case: dict, writes: dict, start_known: set[str], requests_made: list[str],
                     sbar_grading: dict | None = None) -> list[dict]:
    """Journey-defined objectives for one stage, with quoted evidence from the record. Offline and deterministic.
    Entries from a sampled stage carry no learner words, so their evidence is the recorded entry itself."""
    sid = stage["stage_id"]
    mine = [e for e in record["entries"] if e["stage_id"] == sid]
    prior = [e for e in record["entries"] if e["stage_index"] < idx]
    facts = {f["fact_id"]: f for f in case.get("facts") or []}
    ft = case.get("faculty_truth") or {}
    out = []
    for o in stage.get("objectives") or []:
        kind, ev, res, fb, reveal = o.get("kind"), [], "not_observed", "", "stage"

        def quote(e: dict, loc: str | None = None):
            ev.append({"quote": _q(e.get("quote") or e["text"]), "turn": e.get("turn"), "entry_id": e["entry_id"],
                       "location": loc or f"{stage.get('title') or sid}, {'turn ' + str(e['turn']) if e.get('turn') else 'record entry'}"})

        if kind == "elicit":
            cats = set(o.get("categories") or [])
            pool = [f for f in facts.values() if f.get("category") in cats and _fact_in_scope(f, stage) and f["fact_id"] not in start_known
                    and (f.get("critical") or not o.get("critical_only", True))]
            got = [e for e in mine if e.get("fact_id") in {f["fact_id"] for f in pool}]
            for e in got[:3]:
                quote(e)
            if not pool:
                res = "not_assessable"
                fb = "Nothing in this area was left to find at this stage."
            else:
                frac = len(got) / len(pool)
                res = "met" if frac >= float(o.get("min_fraction", 0.75)) else "partly_demonstrated" if got else "not_observed"
                fb = f"{len(got)} of {len(pool)} key items in this area were added to the record."
        elif kind == "use_prior":
            used = [(e, u) for e in prior for u in e.get("used_in") or [] if u["stage_id"] == sid]
            for e, u in used[:3]:
                ev.append({"quote": _q(u.get("quote") or e["text"]), "turn": u.get("turn"), "entry_id": e["entry_id"],
                           "location": f"{stage.get('title') or sid}: {u['how']} (recorded in {e['stage_title']})"})
            res = "not_assessable" if not prior else "met" if used else "not_observed"
            fb = "Built on what an earlier stage recorded." if used else ("No earlier entries existed." if not prior else
                                                                         "Nothing recorded earlier was taken up again here.")
        elif kind == "request":
            want = [str(r).lower() for r in o.get("requests") or []]
            got = [r for r in want if r in requests_made]
            for e in mine:
                if e["kind"] == "order" and e.get("request") in got:
                    quote(e)
            need = len(want) if o.get("all", True) else 1
            res = "met" if len(got) >= need else "partly_demonstrated" if got else "not_observed"
            fb = f"{len(got)} of {len(want)} expected requests were made."
            reveal = "debrief"
        elif kind == "write":
            key = o.get("key")
            es = [e for e in mine if (e["kind"] == "decision" and e.get("key") == key) or
                  (key == "note" and e["kind"] == "note") or (key == "med_list" and e["kind"] == "medication") or
                  (key == "plan" and e["kind"] == "plan") or (key == "open_questions" and e["kind"] == "question") or
                  (key == "orders" and e["kind"] == "order")]
            for e in es[:2]:
                quote(e)
            res = "met" if es else "not_observed"
            fb = "Written to the shared record." if es else "Nothing was written for this."
        elif kind == "decision_match":
            key, reveal = o.get("key"), "debrief"
            e = next((x for x in reversed(mine) if x["kind"] == "decision" and x.get("key") == key), None)
            truth = ft.get("acuity") if key == "acuity" else ft.get("expected_disposition")
            if e is None:
                res, fb = "not_observed", "No decision was recorded."
            elif truth is None:
                res, fb = "not_assessable", "The case does not define an expected value."
            else:
                quote(e)
                if e.get("value") == truth:
                    res, fb = "met", f"Matches the case's expected {key}."
                elif key == "acuity" and abs(int(e["value"]) - int(truth)) == 1:
                    res, fb = "partly_demonstrated", f"One level away from the case's expected acuity (ESI {truth})."
                else:
                    res, fb = "not_observed", f"The case expects {('ESI ' + str(truth)) if key == 'acuity' else truth}."
        elif kind == "resolve_discrepancy":
            ds = [d for d in record["discrepancies"] if d["kind"] != "role_disagreement"]
            solved = [d for d in ds if d["resolved"] and (rec.find(record, d["resolved_by"]) or {}).get("stage_id") == sid]
            open_at_stage = [d for d in ds if not d["resolved"]]
            for d in solved[:2]:
                e = rec.find(record, d["resolved_by"])
                if e:
                    quote(e)
            if solved:
                res, fb = "met", "A conflict between the patient's account and the record was settled here."
            elif open_at_stage:
                res, fb = "not_observed", "A flagged conflict was still open when this stage ended."
                for d in open_at_stage[:1]:
                    ev.append({"quote": _q(d["note"]), "turn": None, "entry_id": d["entries"][0]["entry_id"], "location": "Shared record, flagged discrepancy"})
            else:
                res, fb = "not_assessable", "No conflict was on the record for this stage to settle."
        elif kind == "identify_open":
            es = [e for e in mine if e["kind"] == "question"]
            for e in es[:2]:
                quote(e)
            res = "met" if es else "not_observed"
            fb = "Named what is still uncertain." if es else "No open question or uncertainty was recorded."
        elif kind in ("sbar", "no_unsupported"):
            g = sbar_grading or {}
            if not g:
                res, fb = "not_assessable", "No handoff was given."
            elif kind == "no_unsupported":
                bad = [u for el in g["elements"].values() for u in el["unsupported"]]
                for u in bad[:2]:
                    ev.append({"quote": _q(u["quote"]), "turn": None, "entry_id": None, "location": f"SBAR, {u['element_label']}"})
                res = "met" if not bad else "not_observed"
                fb = "Everything stated is in the shared record." if not bad else f"{len(bad)} statement(s) have no support in the shared record."
            else:
                el = g["elements"].get(str(o.get("element") or "").upper())
                if el:
                    res, fb = el["result"], el["feedback"]
                    for c in el["conveyed"][:2]:
                        ev.append({"quote": _q(c["quote"]), "turn": None, "entry_id": (c["entry_ids"] or [None])[0], "location": f"SBAR, {el['label']}"})
                else:
                    res, fb = g["overall"]["result"], g["overall"]["feedback"]
                    for el2 in g["elements"].values():
                        for c in el2["conveyed"][:1]:
                            ev.append({"quote": _q(c["quote"]), "turn": None, "entry_id": (c["entry_ids"] or [None])[0], "location": f"SBAR, {el2['label']}"})
        assert res in LABELS
        out.append({"objective_id": o["objective_id"], "criterion": o["criterion"], "kind": kind, "result": res, "evidence": ev,
                    "feedback": fb, "behavior": o.get("behavior"), "reveal": reveal,
                    "uncertain": res in ("met", "partly_demonstrated") and not ev})
    return out


def objective_score(objs: list[dict]) -> float | None:
    vals = [{"met": 1.0, "partly_demonstrated": 0.5, "not_observed": 0.0}[o["result"]] for o in objs if o["result"] != "not_assessable"]
    return sum(vals) / len(vals) if vals else None


def stage_quality(stage: dict, record: dict, case: dict, start_known: set[str], objs: list[dict]) -> float:
    """0..1: critical in-scope facts this stage added (0.6) and its objectives (0.4). Deterministic code only."""
    pool = [f["fact_id"] for f in case.get("facts") or [] if f.get("critical") and _fact_in_scope(f, stage) and f["fact_id"] not in start_known]
    got = {e.get("fact_id") for e in record["entries"] if e["stage_id"] == stage["stage_id"]}
    crit = (len([f for f in pool if f in got]) / len(pool)) if pool else None
    obj = objective_score(objs)
    parts = [(crit, 0.6), (obj, 0.4)]
    parts = [(v, w) for v, w in parts if v is not None]
    if not parts:
        return 0.5
    return round(sum(v * w for v, w in parts) / sum(w for _, w in parts), 3)
