"""Disclosure engine: the single, deterministic authority on which facts are available.

The intent step (offline matcher or a model) only proposes fact IDs. This module applies each
fact's authored rule and appends one event per learner action to an append-only ledger. The
learner-visible chart is derived from the ledger, never from the case directly.

Rules
  volunteered              offered at the first open question / question about the complaint, or when asked
  if_asked                 released when the learner asks about it
  after_rapport            released when asked AND rapport >= rapport_needed; until then the patient gives the
                           cover_answer (or a neutral deflection). If rapport is reached later, the patient
                           comes back to it unprompted.
  denied_until_confronted  the patient gives the authored cover_answer (the misreport) until the learner has
                           SEEN one of confront_with (a disclosed fact or released artifact) and raises it
  chart_initial            in the chart from the start
  on_request               released by an order / exam / artifact request ('order:troponin', 'exam:abdomen')

Rapport (integer, never below 0): +1 introduction (once), +1 agenda/permission (once), +1 per turn with an
empathy statement, +1 per turn with normalising language, +1 for the first open question,
-1 per turn with judgmental language. A formative heuristic, not a validated measure.
"""
from __future__ import annotations

from datetime import datetime, timezone

from . import taxonomy as tx
from . import normals
from .matcher import Intent, canonical_request, fact_phrases, _match_phrase

PATIENT_VOICED = ("volunteered", "if_asked", "after_rapport", "denied_until_confronted")
MAX_RELEASE_PER_TURN = 5

ARTIFACT_WORDS = {
    "lab_report": ["lab", "labs", "blood test", "blood tests", "blood work", "bloodwork", "test results", "results", "levels",
                   "bloods", "urine test", "screen"],
    "ecg": ["ecg", "ekg", "tracing", "heart tracing"],
    "xray": ["x-ray", "xray", "x ray", "film", "radiograph"],
    "ct": ["ct", "scan", "cat scan"],
    "prior_note": ["note", "notes", "record", "records", "chart", "last visit", "previous visit", "discharge", "last time",
                   "last admission", "prior visit", "clinic letter"],
    "medication_list": ["medication list", "pharmacy", "prescription record", "refill", "refills", "med list", "fill history",
                        "prescriptions"],
    "image": ["photo", "picture", "image"],
    "document": ["document", "form", "letter", "report"],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def new_state() -> dict:
    return {"turn": 0, "rapport": 0, "ledger": [], "pending_rapport": [], "covered": {}, "pending_artifacts": [],
            "requests_made": [], "flags": {"introduction": False, "agenda": False, "open_questions": 0}}


class Engine:
    def __init__(self, case: dict):
        self.case = case
        self.facts: list[dict] = list(case.get("facts") or [])
        self.by_id = {f["fact_id"]: f for f in self.facts}
        chart = case.get("chart") or {}
        self.sections: list[dict] = list(chart.get("sections") or [])
        self.artifacts: list[dict] = list(chart.get("artifacts") or [])
        self.art_by_id = {a["artifact_id"]: a for a in self.artifacts}
        self.case_requests = sorted(self._all_requests())
        self.workup = [r for r in normals.workup_for(case) if r in tx.REQUEST_ALIASES or r in self.case_requests]

    # ------------------------------------------------------------ helpers
    def _all_requests(self) -> set[str]:
        out = set()
        for f in self.facts:
            d = f.get("disclosure") or {}
            if d.get("rule") == "on_request" and d.get("request"):
                out.add(str(d["request"]).lower())
                out |= {str(r).lower() for r in d.get("also_requests") or []}
        for a in self.artifacts:
            if (a.get("release") or {}).get("rule") == "on_request":
                out.add(self._artifact_request(a))
        return out

    @staticmethod
    def _artifact_request(a: dict) -> str:
        return str((a.get("release") or {}).get("request") or f"artifact:{a['artifact_id']}").lower()

    @staticmethod
    def rule(f: dict) -> str:
        return (f.get("disclosure") or {}).get("rule", "if_asked")

    @staticmethod
    def disclosed(state: dict) -> dict[str, int]:
        """fact_id -> turn of first disclosure, derived from the ledger."""
        out: dict[str, int] = {}
        for ev in state["ledger"]:
            for fid in ev.get("disclosed_fact_ids") or []:
                out.setdefault(fid, ev.get("turn", 0))
        return out

    @staticmethod
    def released_artifacts(state: dict) -> dict[str, int]:
        out: dict[str, int] = {}
        for ev in state["ledger"]:
            for aid in ev.get("released_artifact_ids") or []:
                out.setdefault(aid, ev.get("turn", 0))
        return out

    def _event(self, state: dict, actor: str, kind: str, **kw) -> dict:
        ev = {"seq": len(state["ledger"]), "time": _now(), "turn": state["turn"], "actor": actor, "kind": kind,
              "case_id": self.case.get("case_id"), "case_version": self.case.get("version"),
              "text": None, "request": None, "request_id": None, "matched_intents": [], "disclosed_fact_ids": [],
              "released_artifact_ids": [], "rule_fired": {}, "withheld": [], "result": None, "rapport": state["rapport"],
              "rapport_delta": 0, "rapport_reasons": []}
        ev.update(kw)
        state["ledger"].append(ev)
        return ev

    # ------------------------------------------------------------ start
    def start(self, state: dict, known_fact_ids: list[str] | None = None) -> dict:
        ids = [f["fact_id"] for f in self.facts if self.rule(f) == "chart_initial"]
        for fid in known_fact_ids or []:
            if fid in self.by_id and fid not in ids:
                ids.append(fid)
        arts = [a["artifact_id"] for a in self.artifacts if (a.get("release") or {}).get("rule") == "initial"]
        rules = {fid: ("chart_initial" if self.rule(self.by_id[fid]) == "chart_initial" else "known_to_care_team") for fid in ids}
        return self._event(state, "system", "start", disclosed_fact_ids=ids, released_artifact_ids=arts, rule_fired=rules,
                           result="started")

    # ------------------------------------------------------------ rapport
    def _rapport(self, state: dict, cues: dict) -> tuple[int, list[str]]:
        delta, why = 0, []
        fl = state["flags"]
        if "introduction" in cues and not fl["introduction"]:
            fl["introduction"] = True
            delta += 1
            why.append("introduction")
        if "agenda" in cues and not fl["agenda"]:
            fl["agenda"] = True
            delta += 1
            why.append("agenda_or_permission")
        if "empathy" in cues:
            delta += 1
            why.append("empathy")
        if "normalising" in cues:
            delta += 1
            why.append("normalising")
        if "open_question" in cues and fl["open_questions"] < 1:
            fl["open_questions"] += 1
            delta += 1
            why.append("open_question")
        if "judgmental" in cues:
            delta -= 1
            why.append("judgmental")
        return delta, why

    # ------------------------------------------------------------ confrontation
    def _evidence_phrases(self, item_id: str) -> list[str]:
        if item_id in self.art_by_id:
            a = self.art_by_id[item_id]
            ph = list(ARTIFACT_WORDS.get(a.get("kind", ""), []))
            ph += [w for w in tx.normalize(a.get("title", "")).split() if len(w) > 3 and w not in tx.STOPWORDS]
            if isinstance(a.get("content"), list):
                for row in a["content"]:
                    if isinstance(row, dict) and row.get("test"):
                        ph.append(str(row["test"]))
            return ph
        f = self.by_id.get(item_id)
        if not f:
            return []
        ph = [p for p, w, _ in fact_phrases(f) if w >= 1.3]
        if f.get("label"):
            ph.append(str(f["label"]))
        return ph

    def _mentions(self, text: str, item_id: str) -> bool:
        toks = tx.tokens(text)
        return any(_match_phrase(toks, p) > 0 for p in self._evidence_phrases(item_id))

    def _confronted(self, state: dict, f: dict, text: str, cues: dict) -> tuple[bool, list[str]]:
        seen_f, seen_a = self.disclosed(state), self.released_artifacts(state)
        evidence = [c for c in (f.get("disclosure") or {}).get("confront_with") or [] if c in seen_f or c in seen_a]
        if not evidence:
            return False, []
        cited = [c for c in evidence if self._mentions(text, c)]
        if cited or "confront" in cues:
            return True, cited or evidence
        return False, evidence

    # ------------------------------------------------------------ artifacts
    def _release_artifact(self, state: dict, a: dict, ev: dict, trigger: str) -> None:
        aid = a["artifact_id"]
        if aid in self.released_artifacts(state) or aid in ev["released_artifact_ids"]:
            return
        delay = int((a.get("release") or {}).get("delay_turns") or 0)
        if delay > 0 and trigger != "due":
            if not any(p["artifact_id"] == aid for p in state["pending_artifacts"]):
                state["pending_artifacts"].append({"artifact_id": aid, "due_turn": state["turn"] + delay, "request": trigger})
                ev.setdefault("pending_artifact_ids", []).append(aid)
            return
        ev["released_artifact_ids"].append(aid)
        req = self._artifact_request(a)
        already = self.disclosed(state)
        for fid in a.get("linked_fact_ids") or []:
            f = self.by_id.get(fid)
            if not f or fid in already or fid in ev["disclosed_fact_ids"]:
                continue
            d = f.get("disclosure") or {}
            if d.get("rule") == "chart_initial" or (d.get("rule") == "on_request" and str(d.get("request", "")).lower() == req):
                ev["disclosed_fact_ids"].append(fid)
                ev["rule_fired"][fid] = "on_request" if d.get("rule") == "on_request" else "chart_initial"

    def _due_and_on_fact(self, state: dict, ev: dict) -> None:
        still = []
        for p in state["pending_artifacts"]:
            if p["due_turn"] <= state["turn"] and p["artifact_id"] in self.art_by_id:
                self._release_artifact(state, self.art_by_id[p["artifact_id"]], ev, "due")
            else:
                still.append(p)
        state["pending_artifacts"] = still
        known = set(self.disclosed(state)) | set(ev["disclosed_fact_ids"])
        for a in self.artifacts:
            r = a.get("release") or {}
            if r.get("rule") == "on_fact" and r.get("fact_id") in known:
                self._release_artifact(state, a, ev, "on_fact")

    def _apply_request(self, state: dict, req: str, ev: dict) -> str:
        """Returns released | pending | already_available | not_available."""
        already_f, already_a = self.disclosed(state), self.released_artifacts(state)
        hit, new = False, False
        delayed_fact_ids: set[str] = set()
        for a in self.artifacts:
            r = a.get("release") or {}
            if r.get("rule") == "on_request" and self._artifact_request(a) == req:
                hit = True
                if a["artifact_id"] in already_a:
                    continue
                if int(r.get("delay_turns") or 0) > 0:
                    delayed_fact_ids |= set(a.get("linked_fact_ids") or [])
                before = len(ev["released_artifact_ids"])
                self._release_artifact(state, a, ev, req)
                new = new or len(ev["released_artifact_ids"]) > before or bool(ev.get("pending_artifact_ids"))
        for f in self.facts:
            d = f.get("disclosure") or {}
            if d.get("rule") == "on_request" and req in [str(d.get("request", "")).lower()] + [str(r).lower() for r in d.get("also_requests") or []]:
                hit = True
                fid = f["fact_id"]
                if fid in already_f or fid in ev["disclosed_fact_ids"] or fid in delayed_fact_ids:
                    continue
                ev["disclosed_fact_ids"].append(fid)
                ev["rule_fired"][fid] = "on_request"
                new = True
        if not hit:
            # a standard test the case does not define: the template's unremarkable result, clearly marked synthetic
            given = {d["request"] for e in state["ledger"] for d in e.get("default_results") or []} | {d["request"] for d in ev.get("default_results") or []}
            if req in given:
                if req not in state["requests_made"]:
                    state["requests_made"].append(req)
                return "already_available"
            dr = normals.default_result(self.case, req) if req in self.workup else None
            if dr is None:
                state.setdefault("unavailable_requests", [])
                if req not in state["unavailable_requests"]:
                    state["unavailable_requests"].append(req)
                return "not_available"
            ev.setdefault("default_results", []).append(dr)
            ev["rule_fired"][req] = "template_default_normal"
            if req not in state["requests_made"]:
                state["requests_made"].append(req)
            return "default_normal"
        if req not in state["requests_made"]:
            state["requests_made"].append(req)
        if not new:
            return "pending" if any(p["request"] == req for p in state["pending_artifacts"]) else "already_available"
        if ev.get("pending_artifact_ids") and not ev["released_artifact_ids"] and not ev["disclosed_fact_ids"]:
            return "pending"
        return "released"

    # ------------------------------------------------------------ learner actions
    def process_turn(self, state: dict, text: str, intent: Intent, request_id: str | None = None) -> dict:
        state["turn"] += 1
        ev = self._event(state, "learner", "turn", text=text, request_id=request_id)
        ev["intent_source"] = intent.source
        ev["cues"] = sorted(intent.cues)
        delta, why = self._rapport(state, intent.cues)
        state["rapport"] = max(0, state["rapport"] + delta)
        ev["rapport_delta"], ev["rapport_reasons"], ev["rapport"] = delta, why, state["rapport"]

        self._due_and_on_fact(state, ev)
        already = self.disclosed(state)
        outcome = {"released": [], "repeated": [], "covered": [], "deflected": [], "patient_unknown": [], "spontaneous": [],
                   "request_results": {}, "not_specified": False, "default_negative": [], "open_prompt": [], "social": None}
        ev["matched_intents"] = [{"fact_id": fid, "score": intent.fact_scores.get(fid), "via": intent.via.get(fid)}
                                 for fid in intent.fact_ids if fid in self.by_id]

        def release(fid: str, rule: str, bucket: str = "released"):
            if fid not in ev["disclosed_fact_ids"]:
                ev["disclosed_fact_ids"].append(fid)
                ev["rule_fired"][fid] = rule
            outcome[bucket].append(fid)

        matched = [fid for fid in intent.fact_ids if fid in self.by_id]
        conv = intent.cues
        if "injection" in conv:
            matched = []                    # an attempt to talk to the system, not to the patient: no fact is in play
        if "ice" in conv:                   # "how are you feeling about all this?" is not a request to restate the complaint
            matched = [fid for fid in matched if self.by_id[fid].get("category") != "chief_complaint"]
            if not matched:             # ... it asks for the patient's worries: use an authored concern if the case has one
                tagged = [f["fact_id"] for f in self.facts if {"patient_concerns", "mood"} & {str(t).lower() for t in f.get("topics") or []}
                          and f.get("patient_knows") is not False]
                fresh = [fid for fid in tagged if fid not in already]
                matched = (fresh or tagged)[:1]
        ev["matched_intents"] = [m for m in ev["matched_intents"] if m["fact_id"] in matched] + \
            [{"fact_id": fid, "score": None, "via": "feelings"} for fid in matched if fid not in {m["fact_id"] for m in ev["matched_intents"]}]
        statement_only = (not intent.is_question) or bool({"summarising", "closing"} & set(intent.cues))
        for fid in matched:
            f = self.by_id[fid]
            rule = self.rule(f)
            if fid in already or fid in ev["disclosed_fact_ids"]:
                if statement_only:
                    continue            # the learner is summarising or explaining, not asking again
                if f.get("patient_knows") is False and {"explaining", "summarising", "closing"} & set(conv):
                    continue
                if f.get("patient_knows") is False:
                    outcome["patient_unknown"].append(fid)
                else:
                    outcome["repeated"].append(fid)
                continue
            if f.get("patient_knows") is False or rule in ("on_request", "chart_initial"):
                if {"explaining", "summarising", "closing"} & set(conv):
                    continue            # the learner is explaining a finding, not asking the patient for it
                outcome["patient_unknown"].append(fid)
                ev["withheld"].append({"fact_id": fid, "rule": rule, "reason": "patient_does_not_know" if f.get("patient_knows") is False else "needs_request"})
            elif rule in ("volunteered", "if_asked"):
                release(fid, rule)
            elif rule == "after_rapport":
                need = int((f.get("disclosure") or {}).get("rapport_needed") or 1)
                if state["rapport"] >= need:
                    release(fid, rule)
                    if fid in state["pending_rapport"]:
                        state["pending_rapport"].remove(fid)
                else:
                    outcome["covered" if f.get("cover_answer") else "deflected"].append(fid)
                    ev["withheld"].append({"fact_id": fid, "rule": rule, "reason": f"rapport {state['rapport']} < {need}"})
                    if fid not in state["pending_rapport"]:
                        state["pending_rapport"].append(fid)
            elif rule == "denied_until_confronted":
                ok, cited = self._confronted(state, f, text, intent.cues)
                if ok:
                    release(fid, rule)
                    ev.setdefault("confronted_with", {})[fid] = cited
                else:
                    outcome["covered"].append(fid)
                    ev["withheld"].append({"fact_id": fid, "rule": rule,
                                           "reason": "evidence seen but not raised" if cited else "confrontation evidence not yet seen"})
                    state["covered"].setdefault(fid, state["turn"])

        # a confrontation that cites the evidence without re-naming the topic still counts, for a fact already denied once
        if not matched and ("confront" in intent.cues):
            for fid in list(state["covered"]):
                f = self.by_id.get(fid)
                if not f or fid in already or fid in ev["disclosed_fact_ids"] or self.rule(f) != "denied_until_confronted":
                    continue
                seen = set(already) | set(self.released_artifacts(state))
                cited = [c for c in (f.get("disclosure") or {}).get("confront_with") or [] if c in seen and self._mentions(text, c)]
                if cited:
                    release(fid, "denied_until_confronted")
                    ev.setdefault("confronted_with", {})[fid] = cited

        # volunteered facts come out at the first open question or question about the complaint
        asked_complaint = any(self.by_id[fid].get("category") == "chief_complaint" for fid in matched)
        # ... but "tell me about your smoking" is an open question about something else
        if "injection" not in conv and "ice" not in conv and (
                asked_complaint or (intent.is_open_question and not [fid for fid in matched if self.by_id[fid].get("category") != "chief_complaint"])):
            for f in self.facts:
                if self.rule(f) == "volunteered" and f["fact_id"] not in already and f["fact_id"] not in ev["disclosed_fact_ids"] \
                        and len(ev["disclosed_fact_ids"]) < MAX_RELEASE_PER_TURN and f.get("patient_knows") is not False:
                    release(f["fact_id"], "volunteered")

        # rapport reached after an earlier deflection: the patient comes back to it
        if delta > 0:
            for fid in list(state["pending_rapport"]):
                f = self.by_id.get(fid)
                if f and fid not in ev["disclosed_fact_ids"] and fid not in already and \
                        state["rapport"] >= int((f.get("disclosure") or {}).get("rapport_needed") or 1) and fid not in matched:
                    release(fid, "after_rapport", "spontaneous")
                    state["pending_rapport"].remove(fid)

        # "tell me more" / "anything else?": the next thing the patient has not yet said, in the thread being discussed
        if "continuation" in conv and "injection" not in conv and not ev["disclosed_fact_ids"] and not outcome["covered"] and not outcome["deflected"]:
            nxt = self._next_in_thread(state, matched, already)
            if nxt:
                release(nxt, "open_prompt", "open_prompt")
                outcome["repeated"] = []
            elif not matched:
                outcome["social"] = "nothing_more"

        for req in intent.requests:
            outcome["request_results"][req] = self._apply_request(state, req, ev)
        if intent.requests:
            ev["requests"] = list(intent.requests)
        self._due_and_on_fact(state, ev)

        if ev["disclosed_fact_ids"] or ev["released_artifact_ids"]:
            ev["result"] = "disclosed"
        elif outcome["covered"] or outcome["deflected"]:
            ev["result"] = "withheld"
        elif outcome["repeated"]:
            ev["result"] = "repeat"
        elif outcome["patient_unknown"]:
            ev["result"] = "patient_does_not_know"
        elif intent.requests:
            ev["result"] = next(iter(outcome["request_results"].values()))
        elif "injection" in conv:
            ev["result"] = "deflected_off_topic"
            outcome["social"] = "injection"
        elif outcome["social"] == "nothing_more":
            ev["result"] = "nothing_more_to_add"
        elif "ice" in conv and not outcome["repeated"]:
            ev["result"] = "answered_from_persona"
            outcome["social"] = "ice"
        elif "explaining" in conv and not getattr(intent, "starts_as_question", False):
            ev["result"] = "no_fact_requested"          # "...does that make sense?" after an explanation
        elif intent.is_question and "closing" not in intent.cues and "summarising" not in intent.cues and "backchannel" not in conv:
            topics = list(getattr(intent, "topics_asked", []) or [])
            defined = {str(t).lower() for f in self.facts for t in (f.get("topics") or [])} | {f["fact_id"].split(".")[-1] for f in self.facts}
            free = [t for t in topics if t not in defined]
            if self.case.get("default_negatives", True) and (free or (not topics and getattr(intent, "clinical_yes_no", False))):
                ev["result"] = "answered_negative_by_default"
                ev["default_negative_topics"] = free or ["unspecified"]
                outcome["default_negative"] = free or ["unspecified"]
            elif not topics and not getattr(intent, "clinical_words", False) and self.case.get("default_negatives", True):
                ev["result"] = "deflected_off_topic"
                outcome["social"] = "off_topic"
            else:
                ev["result"] = "not_specified"
                outcome["not_specified"] = True
        else:
            ev["result"] = "no_fact_requested"
        ev["covered_fact_ids"] = outcome["covered"] + outcome["deflected"]
        ev["repeated_fact_ids"] = outcome["repeated"]
        outcome["event"] = ev
        return outcome

    def _next_in_thread(self, state: dict, matched: list[str], already: dict) -> str | None:
        story = ("chief_complaint", "hpi", "ros")
        thread = None
        if matched:
            thread = self.by_id[matched[0]].get("category")
        else:
            for e in reversed(state["ledger"]):
                voiced = [fid for fid in e.get("disclosed_fact_ids") or [] if e["kind"] == "turn" and (e.get("rule_fired") or {}).get(fid) not in ("on_request", "chart_initial")]
                if voiced:
                    thread = self.by_id[voiced[-1]].get("category")
                    break
        groups = [story if (thread in story or thread is None) else (thread,)]
        if groups[0] != story:
            groups.append(story)
        for g in groups:
            for f in self.facts:
                if f["fact_id"] not in already and f.get("category") in g and self.rule(f) in ("volunteered", "if_asked") and f.get("patient_knows") is not False:
                    return f["fact_id"]
        return None

    def process_request(self, state: dict, raw_request: str, request_id: str | None = None) -> dict:
        state["turn"] += 1
        req = canonical_request(raw_request, self.case_requests)
        ev = self._event(state, "learner", "request", text=raw_request, request=req, request_id=request_id)
        self._due_and_on_fact(state, ev)
        result = self._apply_request(state, req, ev)
        self._due_and_on_fact(state, ev)
        ev["requests"] = [req]
        ev["result"] = result if result != "released" or ev["disclosed_fact_ids"] or ev["released_artifact_ids"] else "pending"
        return {"released": list(ev["disclosed_fact_ids"]), "repeated": [], "covered": [], "deflected": [], "patient_unknown": [],
                "spontaneous": [], "request_results": {req: ev["result"]}, "not_specified": False, "event": ev}

    # ------------------------------------------------------------ views
    def fact_text(self, f: dict) -> str:
        s = (f.get("statement") or "").strip()
        if s:
            return s
        v = f.get("value")
        return f"{f.get('label') or f['fact_id']}: {v}{(' ' + f['unit']) if f.get('unit') else ''}"

    def learner_chart(self, state: dict) -> dict:
        """What the learner may see. Each fact appears once, under its section, at the turn it was released."""
        source_of: dict[str, str] = {}
        turn_of: dict[str, int] = {}
        rule_of: dict[str, str] = {}
        notes: list[dict] = []
        for ev in state["ledger"]:
            src = "chart" if ev["kind"] == "start" else ("result" if ev["kind"] == "request" else "patient")
            for fid in ev.get("disclosed_fact_ids") or []:
                if fid not in turn_of:
                    turn_of[fid] = ev["turn"]
                    r = (ev.get("rule_fired") or {}).get(fid, "")
                    rule_of[fid] = r
                    source_of[fid] = "result" if r == "on_request" else ("chart" if r in ("chart_initial", "known_to_care_team") else src)
            for k, fid in enumerate(ev.get("covered_fact_ids") or []):
                f = self.by_id.get(fid)
                if f and f.get("cover_answer") and not any(n["_fact"] == fid for n in notes):
                    notes.append({"note_id": f"n{ev['seq']}-{k}", "text": f["cover_answer"], "turn": ev["turn"], "_fact": fid,
                                  "section_id": f.get("chart_section") or tx.CATEGORY_SECTION.get(f.get("category"), ("hpi", ""))[0]})
        arts = self.released_artifacts(state)
        sections: dict[str, dict] = {}
        order: list[str] = []
        for s in self.sections:
            sections[s["section_id"]] = {"section_id": s["section_id"], "title": s.get("title", s["section_id"]),
                                         "release": s.get("release", "on_fact"), "static_text": s.get("static_text"),
                                         "facts": [], "notes": [], "artifact_ids": []}
            order.append(s["section_id"])

        def sec(sid: str, category: str | None = None) -> dict:
            if sid not in sections:
                title = dict(tx.CATEGORY_SECTION.values()).get(sid, sid.replace("_", " ").title())
                sections[sid] = {"section_id": sid, "title": title, "release": "on_fact", "static_text": None, "facts": [],
                                 "notes": [], "artifact_ids": []}
                order.append(sid)
            return sections[sid]

        for f in self.facts:                       # case order keeps the chart stable between turns
            fid = f["fact_id"]
            if fid not in turn_of:
                continue
            sid = f.get("chart_section") or tx.CATEGORY_SECTION.get(f.get("category"), ("hpi", ""))[0]
            item = {"fact_id": fid, "text": self.fact_text(f), "category": f.get("category"), "turn": turn_of[fid],
                    "source": source_of[fid], "rule": rule_of[fid], "polarity": f.get("polarity")}
            for k in ("label", "value", "unit"):
                if f.get(k) is not None:
                    item[k] = f[k]
            if f.get("ref_range"):
                item["ref_range"] = f["ref_range"]
            if f.get("flag"):
                item["flag"] = f["flag"]
            sec(sid)["facts"].append(item)
        for n in notes:
            sec(n["section_id"])["notes"].append({"note_id": n["note_id"], "text": n["text"], "turn": n["turn"], "kind": "patient_reported",
                                                  "superseded": n["_fact"] in turn_of})
        artifacts = []
        for a in self.artifacts:
            if a["artifact_id"] not in arts:
                continue
            sid = a.get("section_id") or {"lab_report": "labs", "ecg": "imaging", "xray": "imaging", "ct": "imaging"}.get(a.get("kind"), "documents")
            sec(sid)["artifact_ids"].append(a["artifact_id"])
            item = {k: a[k] for k in ("artifact_id", "kind", "title", "content", "asset", "synthetic") if k in a}
            item["section_id"] = sid
            item["turn"] = arts[a["artifact_id"]]
            item["linked_fact_ids"] = [fid for fid in (a.get("linked_fact_ids") or []) if fid in turn_of]
            artifacts.append(item)          # `interpretation` is held back until feedback
        for ev in state["ledger"]:
            for dr in ev.get("default_results") or []:
                sid = {"lab_report": "labs", "ecg": "imaging", "xray": "imaging", "ct": "imaging", "prior_note": "records", "medication_list": "records"}.get(dr["kind"],
                       "exam" if dr["request"].startswith("exam:") else "imaging")
                aid = "default." + dr["request"].replace(":", ".")
                sec(sid)["artifact_ids"].append(aid)
                artifacts.append({"artifact_id": aid, "kind": dr["kind"], "title": dr["title"], "content": dr["content"], "synthetic": True, "default_normal": True,
                                  "note": dr["note"], "section_id": sid, "turn": ev["turn"], "linked_fact_ids": []})
        visible, hidden = [], 0
        for sid in order:
            s = sections[sid]
            has = bool(s["facts"] or s["notes"] or s["artifact_ids"])
            if s["release"] == "initial" or has:
                s["visible"] = True
                visible.append(s)
            else:
                hidden += 1
        pending = [{"request": p["request"], "due_turn": p["due_turn"]} for p in state["pending_artifacts"]]
        return {"sections": visible, "artifacts": artifacts, "hidden_section_count": hidden, "pending_results": pending,
                "n_disclosed": len(turn_of), "turn": state["turn"]}

    def available_requests(self) -> list[dict]:
        """The order / examination menu: this case's own requests merged with the standard workup for its kind of
        presentation, so the menu does not reveal which tests matter. Every item returns something: the case's result,
        or the default normal result (rule `template_default_normal`). Anything else typed by the learner is
        'not available in this scenario'."""
        keys = sorted(set(self.workup) | {r for r in self.case_requests if not r.startswith("artifact:")})
        out = []
        for k in keys:
            kind, _, name = k.partition(":")
            label = name.replace("_", " ")
            label = label.upper() if len(label) <= 4 else label.capitalize()
            out.append({"request": k, "kind": kind, "label": label})
        return out


def student_event(ev: dict) -> dict:
    """Ledger event as the student may see it: nothing about facts that were matched but not released."""
    shown = set(ev.get("disclosed_fact_ids") or [])
    return {"seq": ev["seq"], "time": ev["time"], "turn": ev["turn"], "actor": ev["actor"], "kind": ev["kind"],
            "text": ev.get("text"), "request": ev.get("request"), "request_id": ev.get("request_id"),
            "case_version": ev.get("case_version"),
            "matched_intents": [m["fact_id"] for m in ev.get("matched_intents") or [] if m["fact_id"] in shown],
            "disclosed_fact_ids": list(ev.get("disclosed_fact_ids") or []),
            "released_artifact_ids": list(ev.get("released_artifact_ids") or []),
            "rule_fired": {k: v for k, v in (ev.get("rule_fired") or {}).items() if k in shown},
            "default_results": [d["request"] for d in ev.get("default_results") or []],
            "result": "answered" if ev.get("result") == "withheld" else ev.get("result"), "rapport": ev.get("rapport"), "rapport_delta": ev.get("rapport_delta"),
            "rapport_reasons": ev.get("rapport_reasons"), "reply": ev.get("reply"), "provider": ev.get("provider"),
            "fallback": ev.get("fallback", False)}
