"""Handoff stage: the learner gives an SBAR to an AI colleague, who asks clarifying questions and reads back.

Everything is judged against the SHARED RECORD (what the team actually learned), never the hidden case truth:
  conveyed     a record entry the SBAR (or an answer to the colleague) communicated
  omitted      a record entry the receiver needed and did not get
  unsupported  a statement naming a figure, medicine, allergy, test or imaging result, or piece of past history that
               the record does not hold (quoted back). The rules are in claims.py; free-text reasoning is not checked.

The colleague does not take a non-answer: a reply that does not supply what was asked is asked for once more and
then recorded as unresolved.

Offline the colleague is rule-based: questions come from fixed templates chosen by what is missing, and the
read-back is assembled from record entries. Online a model may re-word those approved lines; the wording is
checked with the encounter's own grounding check against the record and rejected on any new clinical content.
"""
from __future__ import annotations

import re

from .. import taxonomy as tx
from ..matcher import match_facts
from ..patient import _numbers, _stems, clinical_lexicon, filler_stems, grounding_check
from ..providers import Provider, ProviderError
from . import claims
from . import record as rec

ELEMENTS = {"S": "Situation", "B": "Background", "A": "Assessment", "R": "Recommendation"}
_CAT_ELEMENT = {"identity": "S", "chief_complaint": "S", "hpi": "S", "vitals": "S", "ros": "S",
                "pmh": "B", "medications": "B", "allergies": "B", "social": "B", "family": "B", "risk": "B", "concealed": "B",
                "exam": "A", "lab": "A", "imaging": "A", "diagnosis": "A"}
_UNCERTAIN = ("unclear", "not sure", "unsure", "uncertain", "pending", "unconfirmed", "don't know", "do not know", "still waiting",
              "awaiting", "not yet", "possible", "possibly", "might", "may be", "query", "conflict", "does not match", "doesn't match",
              "disagree", "inconsistent")
_ASK = ("please", "need you to", "can you", "could you", "would you", "recommend", "suggest", "i'd like", "i would like", "plan is", "next step",
        "follow up", "follow-up", "repeat", "monitor", "watch", "check", "chase", "review", "continue", "start", "hold", "give")
_HEAD = re.compile(r"^\s*(situation|background|assessment|recommendation|recommendations|s|b|a|r)\s*[:\-–]\s*", re.I)

COLLEAGUE_SYSTEM = ("You voice a clinician colleague receiving a handoff in a teaching simulation. Re-word the APPROVED LINES as one short, "
                    "natural spoken reply in the colleague's style. Do not add any clinical fact, number, drug, test or finding that is not "
                    "in the approved lines. Keep every question. Reply with the spoken words only.")


def parse_sbar(body: dict) -> dict[str, str]:
    """Four fields, or one free text with S:/B:/A:/R: (or Situation: ...) headings."""
    out = {k: str(body.get(n) or "").strip()[:3000] for k, n in (("S", "situation"), ("B", "background"), ("A", "assessment"), ("R", "recommendation"))}
    text = str(body.get("text") or "").strip()
    if text and not any(out.values()):
        cur = "S"
        for line in text.splitlines():
            m = _HEAD.match(line)
            if m:
                cur = m.group(1)[0].upper()
                line = line[m.end():]
            if line.strip():
                out[cur] = (out[cur] + " " + line.strip()).strip()
    return out


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?;])\s+|\n+", text or "")
    return [p.strip() for p in parts if len(p.strip()) > 2]


def _content(text: str) -> set[str]:
    return {s for s in _stems(text) if len(s) >= 3 and s not in filler_stems()}


# ---------------------------------------------------------------- what the receiver needs, from the record

def expected_items(record: dict, stage: dict) -> list[dict]:
    """Record entries grouped into SBAR items. `critical` marks what the receiver must not miss."""
    sb = stage.get("sbar") or {}
    crit_kinds = set(sb.get("critical") or ["allergies", "pending_results", "concealed", "disposition", "discrepancies", "critical_facts"])
    items: list[dict] = []
    stage_id = stage["stage_id"]
    for e in record["entries"]:
        if e["stage_id"] == stage_id or e.get("status") == "unsupported":
            continue
        item = None
        if e["kind"] == "fact":
            cat = e.get("category")
            el = _CAT_ELEMENT.get(cat or "", "B")
            hidden_first = e.get("rule") in ("after_rapport", "denied_until_confronted")
            kind = "allergies" if cat == "allergies" else "concealed" if hidden_first else "fact"
            crit = (kind == "allergies" and "allergies" in crit_kinds) or (kind == "concealed" and "concealed" in crit_kinds) or \
                   (bool(e.get("_critical")) and "critical_facts" in crit_kinds)
            item = {"element": "B" if kind == "concealed" else el, "kind": kind, "critical": crit, "label": e.get("section_title") or "Finding"}
        elif e["kind"] == "decision" and e.get("key") == "disposition":
            item = {"element": "R", "kind": "disposition", "critical": "disposition" in crit_kinds, "label": "Disposition"}
        elif e["kind"] == "decision":
            item = {"element": "S", "kind": "decision", "critical": False, "label": "Acuity"}
        elif e["kind"] == "order" and e.get("is_order") and e.get("order_status") != "resulted":
            item = {"element": "R", "kind": "pending_results", "critical": "pending_results" in crit_kinds, "label": "Pending result"}
        elif e["kind"] == "note":
            item = {"element": "A", "kind": "assessment", "critical": False, "label": "Assessment note"}
        elif e["kind"] == "medication":
            item = {"element": "B", "kind": "medication", "critical": False, "label": "Reconciled medicine"}
        elif e["kind"] == "plan":
            item = {"element": "R", "kind": "plan", "critical": False, "label": "Plan item"}
        elif e["kind"] == "question":
            item = {"element": "R", "kind": "open_question", "critical": False, "label": "Open question"}
        if item:
            item.update(item_id=f"i-{e['entry_id']}", entry_ids=[e["entry_id"]], text=e["text"], provenance=rec.provenance(e))
            items.append(item)
    for d in rec.unresolved(record):
        items.append({"item_id": f"i-{d['discrepancy_id']}", "element": "A", "kind": "discrepancies", "critical": "discrepancies" in crit_kinds,
                      "label": "Unresolved conflict", "entry_ids": [x["entry_id"] for x in d["entries"]], "text": d["note"],
                      "provenance": d["entries"][0]})
    return items


def _record_text(record: dict, case: dict, stage_id: str) -> str:
    prof = case.get("profile") or {}
    parts = [str(prof.get(k) or "") for k in ("name", "age", "gender")] + [str(case.get("setting") or "")]
    for e in record["entries"]:
        if e["stage_id"] != stage_id and e.get("status") != "unsupported":   # a flagged note is not support for anything
            parts += [e["text"], str(e.get("title") or ""), str(e.get("value") or ""), str(e.get("_result_text") or "")]
    for d in record["discrepancies"]:
        parts.append(d["note"])
    shown = set(rec.artifact_ids(record))                   # the team has read these documents, so their content is on the record
    for a in (case.get("chart") or {}).get("artifacts") or []:
        if a.get("artifact_id") in shown:
            c = a.get("content")
            rows = c if isinstance(c, list) else [c]
            parts += [" ".join(str(v) for v in r.values()) if isinstance(r, dict) else str(r or "") for r in rows]
    return " ".join(parts)


_MED_SKIP = {"patient", "report", "take", "taking", "stop", "stopped", "none", "nothing", "medicine", "medication", "prescribed", "regular"}


def unknown_medicine(line: str, record_text: str) -> str | None:
    """Heuristic for a reconciled-medicines line: its leading word (the medicine's name) appears nowhere in the record."""
    r = _stems(record_text)
    for w in tx.tokens(line):
        if len(w) >= 5 and w not in filler_stems() and w not in _MED_SKIP and not w.isdigit():
            return None if w in r else w
    return None


def match_sentence(sentence: str, items: list[dict], record: dict, case: dict) -> list[str]:
    """Item ids this sentence conveys: the encounter's topic matcher for case facts, word overlap for everything else."""
    hit: list[str] = []
    known = {e["fact_id"]: e["entry_id"] for e in record["entries"] if e.get("fact_id")}
    facts = [f for f in case.get("facts") or [] if f["fact_id"] in known]
    intent = match_facts(sentence, facts)
    fact_hits = {known[fid] for fid in intent.fact_ids}
    sc = _content(sentence)
    norm = tx.normalize(sentence)
    for it in items:
        ok = bool(set(it["entry_ids"]) & fact_hits) and it["kind"] != "discrepancies"
        ic = _content(it["text"])
        if not ok and ic:
            shared = sc & ic
            ok = len(shared) >= max(2, int(0.5 * len(ic) + 0.5)) or (len(ic) <= 2 and shared == ic)
        if not ok and it["kind"] == "disposition":
            word = it["text"].split(": ")[-1]
            ok = tx.stem(word) in _stems(sentence) or (word == "admit" and "admission" in norm)
        if not ok and it["kind"] == "decision":
            m = re.search(r"\d", it["text"])
            ok = bool(m) and bool(re.search(rf"\b(esi|acuity|level|category)\s*{m.group(0)}\b", norm))
        if not ok and it["kind"] == "pending_results":
            name = _content(it["text"].split(": ", 1)[-1].split(" (")[0])
            ok = bool(name) and name <= sc
        if not ok and it["kind"] == "discrepancies":
            pair = [rec.find(record, x) for x in it["entry_ids"]]
            touched = [p for p in pair if p and (len(sc & _content(p["text"] + " " + str(p.get("title") or ""))) >= 2 or p["entry_id"] in fact_hits)]
            ok = len(touched) == 2 or (bool(touched) and any(w in norm for w in _UNCERTAIN + ("but", "however", "although", "despite")))
        if ok:
            hit.append(it["item_id"])
    return hit


_NEG = re.compile(r"\b(no|not|none|nil|never|denies|denied|without|nkda|negative|free of|isn't|doesn't|does not|hasn't|has not)\b", re.I)
_HEDGE = re.compile(r"\b(i think|i suspect|i believe|my impression|impression is|likely|probably|possibly|possible|may be|might|could be|"
                    r"consistent with|suggests?|concern(ed)? for|worried about|query|in my view|looks like|seems)\b", re.I)
_CLAUSE = re.compile(r"\s*(?:,\s*and\s+|\s+and\s+|\s+but\s+|;\s*)", re.I)
_drug_stems: set[str] | None = None


def drug_stems() -> set[str]:
    global _drug_stems
    if _drug_stems is None:
        from ..patient import DRUG_CLASSES
        _drug_stems = {tx.stem(w) for members in DRUG_CLASSES.values() for m in members for w in m.replace("-", " ").split() if len(w) >= 4}
    return _drug_stems


def clauses(sentence: str) -> list[str]:
    parts = [c.strip() for c in _CLAUSE.split(sentence) if c and len(c.strip()) > 2]
    return parts if len(parts) > 1 else [sentence]


def unsupported_reason(sentence: str, element: str, record_text: str, record: dict, case: dict, hit_entries: list[dict] | None = None,
                       context: str | None = None) -> str | None:
    """Why a statement has no support in the record, or None.
    - a figure, or a named medicine, that appears nowhere in the record
    - a medicine, allergy, test or imaging result, or piece of past history the record does not hold (claims.py)
    - the opposite of a recorded negative ("no known allergies" on the record, "allergic to ..." in the statement)
    - (statement matches no record entry) it states as a finding something the team never recorded, or, under
      Situation / Background, it uses clinical terms the record does not hold. A hedged assessment is interpretation
      and a recommendation is a request, so neither is held to this."""
    known = set(rec.fact_ids(record))
    new_nums = _numbers(sentence) - _numbers(record_text)
    s_stems, r_stems = _stems(sentence), _stems(record_text)
    new = s_stems - r_stems
    if new_nums:
        return f"the figure {', '.join(sorted(new_nums))} is not in the shared record"
    drugs = sorted(new & drug_stems())
    if drugs:
        return f"no entry in the shared record mentions {', '.join(drugs[:3])}"
    typed = claims.claim_reason(sentence, element, record_text, context)
    if typed:
        return typed
    for e in hit_entries or []:
        if e.get("polarity") == "negative" and not _NEG.search(sentence):
            return f"the shared record says the opposite: \"{e['text']}\""
    if hit_entries:
        return None
    # a recommendation asks for things, and a hedged assessment ("I think", "likely") is marked as interpretation: neither claims a finding
    claims_finding = element in ("S", "B") or (element == "A" and not _HEDGE.search(sentence))
    hidden = [f for f in case.get("facts") or [] if f["fact_id"] not in known]
    if claims_finding and hidden and match_facts(sentence, hidden).fact_ids:
        return "nothing in the shared record supports this"
    lex = sorted(new & clinical_lexicon())
    if element in ("S", "B") and lex:
        return f"no entry in the shared record mentions {', '.join(lex[:3])}"
    return None


def grade_sbar(sbar: dict[str, str], answers: list[dict], record: dict, case: dict, stage: dict) -> dict:
    items = expected_items(record, stage)
    rtext = _record_text(record, case, stage["stage_id"])
    conveyed: dict[str, dict] = {}
    elements: dict[str, dict] = {}
    statements: list[dict] = []
    for el, label in ELEMENTS.items():
        elements[el] = {"element": el, "label": label, "text": sbar.get(el, ""), "conveyed": [], "omitted": [], "unsupported": [],
                        "interpretations": []}
        for s in sentences(sbar.get(el, "")):
            statements.append({"element": el, "text": s, "prompted": False, "question_id": None})
    for a in answers:
        for s in sentences(a.get("text") or ""):
            statements.append({"element": a.get("element") or "B", "text": s, "prompted": True, "question_id": a.get("question_id")})
    by_item = {it["item_id"]: it for it in items}
    for st in statements:
        hits = match_sentence(st["text"], items, record, case)
        bad = False
        for cl in clauses(st["text"]):
            ch = hits if cl == st["text"] else match_sentence(cl, items, record, case)
            hit_entries = [e for e in (rec.find(record, x) for i in ch for x in by_item[i]["entry_ids"]) if e]
            why = unsupported_reason(cl, st["element"], rtext, record, case, hit_entries, st["text"])
            if why:
                bad = True
                elements[st["element"]]["unsupported"].append({"quote": cl if cl != st["text"] else st["text"], "reason": why, "element": st["element"],
                                                               "element_label": ELEMENTS[st["element"]], "prompted": st["prompted"]})
                hits = [i for i in hits if i not in ch or cl != st["text"] and len(clauses(st["text"])) > 1 and i in
                        [x for c2 in clauses(st["text"]) if c2 != cl for x in match_sentence(c2, items, record, case)]]
        for iid in hits:
            if iid not in conveyed:
                conveyed[iid] = {"quote": st["text"], "prompted": st["prompted"], "said_in": st["element"]}
        if not hits and not bad and st["element"] in ("A", "R") and not st["prompted"]:
            elements[st["element"]]["interpretations"].append(st["text"])
    for it in items:
        el = elements[it["element"]]
        row = {"item_id": it["item_id"], "label": it["label"], "kind": it["kind"], "critical": it["critical"], "entry_ids": it["entry_ids"],
               "text": it["text"], "provenance": it["provenance"]}
        if it["item_id"] in conveyed:
            c = conveyed[it["item_id"]]
            el["conveyed"].append(dict(row, quote=c["quote"], prompted=c["prompted"], said_in=ELEMENTS[c["said_in"]]))
        else:
            el["omitted"].append(row)
    crit_total = crit_un = crit_pr = 0
    for el in elements.values():
        crit = [c for c in el["conveyed"] if c["critical"]]
        miss = [o for o in el["omitted"] if o["critical"]]
        crit_total += len(crit) + len(miss)
        crit_un += len([c for c in crit if not c["prompted"]])
        crit_pr += len([c for c in crit if c["prompted"]])
        has_items = bool(el["conveyed"] or el["omitted"])
        said = bool(el["text"].strip())
        if not said and not has_items:
            el["result"], el["feedback"] = "not_assessable", "The record held nothing for this part and nothing was said."
        elif not said and el["conveyed"]:
            asked = [c for c in el["conveyed"] if c["prompted"]]
            elsewhere = sorted({c["said_in"] for c in el["conveyed"] if not c["prompted"]})
            how = []
            if elsewhere:
                how.append(f"{len(el['conveyed']) - len(asked)} item(s) that belong here were mentioned under {', '.join(elsewhere)} instead")
            if asked:
                how.append(f"{len(asked)} came out only in a reply to the colleague's questions")
            el["result"], el["feedback"] = "partly_demonstrated", f"Nothing was said under {el['label']}; {' and '.join(how)}."
        elif not said:
            el["result"], el["feedback"] = "not_observed", f"Nothing was said under {el['label']}."
        elif el["unsupported"] or miss or any(c["prompted"] for c in crit):
            el["result"] = "partly_demonstrated"
            bits = []
            if miss:
                bits.append(f"{len(miss)} item(s) the receiver needed were left out")
            if any(c["prompted"] for c in crit):
                bits.append("some came only after the colleague asked")
            if el["unsupported"]:
                bits.append(f"{len(el['unsupported'])} statement(s) are not supported by the record")
            el["feedback"] = "; ".join(bits).capitalize() + "."
        elif el["conveyed"] or el["interpretations"] or not has_items:
            el["result"], el["feedback"] = "met", "Covered what the record holds for this part."
        else:
            el["result"], el["feedback"] = "partly_demonstrated", "Something was said, but none of it matches what the record holds for this part."
    n_unsup = sum(len(el["unsupported"]) for el in elements.values())
    understanding = round((crit_un + 0.5 * crit_pr) / crit_total, 3) if crit_total else None
    present = [el for el in elements.values() if el["result"] != "not_assessable"]
    el_score = sum({"met": 1.0, "partly_demonstrated": 0.5, "not_observed": 0.0}[e["result"]] for e in present) / len(present) if present else 0.0
    score = (0.6 * understanding + 0.4 * el_score) if understanding is not None else el_score
    score = round(max(0.0, score - 0.1 * n_unsup), 3)
    all_text = " ".join(sbar.values()).lower()
    uncertain_items = [it for it in items if it["kind"] in ("discrepancies", "pending_results", "open_question")]
    unc_said = [s["text"] for s in statements if names_uncertainty(s["text"])]
    ask_said = [s for s in sentences(sbar.get("R", "")) if any(w in s.lower() for w in _ASK)]
    behaviors = [
        _behavior("Situation stated", elements["S"]), _behavior("Relevant background given", elements["B"]),
        _behavior("Findings and assessment given", elements["A"]),
        {"behavior": "Findings kept apart from interpretation", "observed": "yes" if (elements["A"]["conveyed"] and not n_unsup) else "no" if n_unsup else "not_assessable",
         "evidence_location": "SBAR, Assessment", "quote": (elements["A"]["conveyed"][0]["quote"] if elements["A"]["conveyed"] else None),
         "feedback": "Findings quoted from the record; interpretation added on top." if (elements["A"]["conveyed"] and not n_unsup)
         else ("A statement was presented as fact without support in the record." if n_unsup else "No recorded findings were reported in the assessment.")},
        {"behavior": "Uncertainty named", "observed": "not_assessable" if not uncertain_items and not unc_said else "yes" if unc_said else "no",
         "evidence_location": "SBAR", "quote": unc_said[0] if unc_said else None,
         "feedback": "Said what is still pending or unclear." if unc_said else
         ("Nothing uncertain was on the record, and no uncertainty was named." if not uncertain_items else
          "The record holds pending or conflicting items that were passed on as settled or not at all.")},
        {"behavior": "Next action requested", "observed": "yes" if ask_said else "no", "evidence_location": "SBAR, Recommendation",
         "quote": ask_said[0] if ask_said else None,
         "feedback": "A clear next step was asked for." if ask_said else "Say what you need the receiver to do first."},
    ]
    res = "met" if score >= 0.8 and not n_unsup else "partly_demonstrated" if all_text.strip() else "not_observed"
    return {"elements": elements, "behaviors": behaviors, "n_items": len(items), "critical_total": crit_total, "critical_unprompted": crit_un,
            "critical_after_prompt": crit_pr, "n_unsupported": n_unsup, "receiver_understanding": understanding, "score": score,
            "overall": {"result": res, "feedback": f"{crit_un} of {crit_total} critical items reached the receiver unprompted"
                        + (f", {crit_pr} more after a question" if crit_pr else "") + (f"; {n_unsup} unsupported statement(s)" if n_unsup else "") + "."},
            "graded_against": "the shared record (what the team learned), not the case truth",
            "checked": claims.SCOPE_NOTE}


def names_uncertainty(text: str) -> bool:
    """The statement says WHAT is uncertain. A bare "I don't know." names nothing."""
    low = (text or "").lower().replace("\u2019", "'")
    if not any(w in low for w in _UNCERTAIN):
        return False
    for w in sorted(_UNCERTAIN, key=len, reverse=True):
        low = low.replace(w, " ")
    return bool(_content(low))


_RETRACT = ("mistake", "sorry", "withdraw", "ignore that", "i was wrong", "misspoke", "not in the record", "not on the record", "assumed",
            "assumption", "scratch that", "disregard", "incorrect", "should not have", "shouldn't have", "take that back", "my error",
            "not confirmed", "not documented", "isn't in the record", "is not in the record")


def answer_resolves(question: dict, text: str, grading: dict, record: dict, case: dict, record_text: str) -> bool:
    """Did the reply supply what the colleague asked for? Judged by what the reply conveyed from the record, never by the case.
    - a question about missing record items: the reply conveyed at least one of them
    - a challenge to an unsupported statement: the reply takes it back, or is itself supported by the record
    - "what do you need me to do first": the reply asks for something"""
    low = (text or "").lower().replace("\u2019", "'")
    if question.get("item_ids"):
        got = {c["item_id"] for el in grading["elements"].values() for c in el["conveyed"]}
        return bool(set(question["item_ids"]) & got)
    if question.get("about") == "unsupported":
        if any(w in low for w in _RETRACT):
            return True
        items = [{"item_id": f"i-{e['entry_id']}", "entry_ids": [e["entry_id"]], "text": e["text"], "kind": "fact"}
                 for e in record["entries"] if e["kind"] in ("fact", "artifact", "patient_report", "medication", "note") and e.get("status") != "unsupported"]
        for s in sentences(text):
            if match_sentence(s, items, record, case) and not any(unsupported_reason(c, "B", record_text, record, case, None, s) for c in clauses(s)):
                return True
        return False
    return any(w in low for w in _ASK)


def _behavior(name: str, el: dict) -> dict:
    return {"behavior": name, "observed": {"met": "yes", "partly_demonstrated": "partly", "not_observed": "no", "not_assessable": "not_assessable"}[el["result"]],
            "evidence_location": f"SBAR, {el['label']}", "quote": (el["conveyed"][0]["quote"] if el["conveyed"] else (sentences(el["text"]) or [None])[0]),
            "feedback": el["feedback"]}


# ---------------------------------------------------------------- the colleague

_Q_TEXT = {
    "allergies": ("B", "Before I take over: any allergies I should know about?"),
    "concealed": ("B", "Was there anything the patient was slow to tell the team that changes how I should look after them?"),
    "discrepancies": ("A", "The record has two accounts that do not agree. Which one should I work from, and has anyone settled it?"),
    "pending_results": ("R", "Is anything still pending that I need to chase?"),
    "disposition": ("R", "What is the plan for this patient, and what do you need from me first?"),
    "medication": ("B", "What is the patient actually taking at home?"),
}
_CAT_Q = {"S": "Give me the headline again: what brought the patient in and how are they right now?",
          "B": "What in the history do I need to know about?", "A": "What did the examination and tests show?",
          "R": "What do you need me to do first?"}
_PRIORITY = ["unsupported", "allergies", "discrepancies", "concealed", "pending_results", "disposition", "fact"]


def plan_questions(grading: dict, stage: dict) -> list[dict]:
    """Up to N clarifying questions about what is missing. A question never states the missing content."""
    n = int((stage.get("sbar") or {}).get("max_questions", 3))
    qs: list[dict] = []
    unsup = [u for el in grading["elements"].values() for u in el["unsupported"]]
    if unsup:
        u = unsup[0]
        qs.append({"about": "unsupported", "element": u["element"], "item_ids": [],
                   "text": f"You said \"{u['quote']}\"{'' if u['quote'][-1:] in '.!?' else '.'} I cannot find that in the shared record. Where does it come from?"})
    missing = [o for el in grading["elements"].values() for o in el["omitted"] if o["critical"]]
    seen: set[str] = set()
    for kind in _PRIORITY[1:]:
        group = [m for m in missing if m["kind"] == kind]
        if not group:
            continue
        if kind == "fact":
            for el in "SBAR":
                g = [m for m in group if _item_element(grading, m["item_id"]) == el]
                if g and el not in seen:
                    seen.add(el)
                    qs.append({"about": "critical_facts", "element": el, "item_ids": [m["item_id"] for m in g], "text": _CAT_Q[el]})
        else:
            el, text = _Q_TEXT[kind]
            qs.append({"about": kind, "element": el, "item_ids": [m["item_id"] for m in group], "text": text})
    if grading["elements"]["R"]["result"] == "not_observed" and not any(q["element"] == "R" for q in qs):
        qs.append({"about": "recommendation", "element": "R", "item_ids": [], "text": _CAT_Q["R"]})
    qs = qs[:max(0, n)]
    for i, q in enumerate(qs):
        q.update(question_id=f"q{i + 1}", answered=False, answer=None)
    return qs


def _item_element(grading: dict, item_id: str) -> str:
    for el, d in grading["elements"].items():
        if any(o["item_id"] == item_id for o in d["omitted"] + d["conveyed"]):
            return el
    return "B"


def readback_lines(grading: dict) -> list[str]:
    lines = ["Let me read that back."]
    for el in "SBAR":
        got = [c["text"].rstrip(".") for c in grading["elements"][el]["conveyed"]][:4]
        if got:
            lines.append(f"{ELEMENTS[el]}: {'; '.join(got)}.")
    if len(lines) == 1:
        lines.append("I did not get anything I can match to the record.")
    lines.append("Anything you did not mention I will treat as not yet known.")
    return lines


def colleague_reply(lines: list[str], colleague: dict, record: dict, case: dict, provider: Provider | None) -> dict:
    """Authored lines offline; model wording online, kept only if it adds no clinical content beyond the lines."""
    reply = " ".join(lines)
    out = {"reply": reply, "wording": "authored", "provider": "offline", "fallback": False}
    if provider is not None and provider.live:
        try:
            user = (f"COLLEAGUE\n{colleague.get('name')}, {colleague.get('role')}. Style: {colleague.get('communication_style') or 'plain and direct'}\n\n"
                    "APPROVED LINES\n" + "\n".join(f"- {ln}" for ln in lines))
            cand = provider.complete(COLLEAGUE_SYSTEM, user, max_tokens=400).strip().strip('"').strip()
            ok, reasons = grounding_check(cand, lines, case, set(rec.fact_ids(record)))
            if ok and cand.count("?") >= reply.count("?"):
                out.update(reply=cand, wording="model", provider=provider.name)
            else:
                out.update(provider=provider.name, wording_rejected={"candidate": cand, "reasons": reasons or ["a question was dropped"]})
        except ProviderError as e:
            out.update(fallback=True, provider_error=str(e)[:200])
    return out


def auto_sbar(record: dict, stage: dict, quality: float, rng) -> dict[str, str]:
    """The sampler-equivalent's SBAR: record entries only, each included with a probability set by the sampled quality."""
    out = {k: [] for k in ELEMENTS}
    for it in expected_items(record, stage):
        p = min(1.0, quality * 1.12) if it["critical"] else quality * 0.8
        if rng.random() < p:
            out[it["element"]].append(it["text"].rstrip(".") + ".")
    return {k: " ".join(v[:8]) for k, v in out.items()}
