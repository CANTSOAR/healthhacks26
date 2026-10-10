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

    # ------------------------------------------------------------ safety net for questions no topic matched
    _WEAK = {"pain", "hurt", "ach", "sore", "problem", "symptom", "sick", "ill", "bad", "histori", "med", "feel", "doctor", "hospit", "issu", "troubl",
             "today", "recent", "late", "ever", "anyth", "someth", "anywher", "normal", "usual", "chang", "start", "stop", "happen", "notic", "bother"}

    def _distinctive(self, norm: str) -> set[str]:
        from . import conversation as conv
        from .patient import _GENERIC
        generic = {tx.stem(w) for w in _GENERIC} | tx.STOPWORDS | {tx.stem(w) for w in tx.STOPWORDS} | self._WEAK
        out: set[str] = set()
        for raw in norm.replace("-", " ").split():
            st = tx.stem(raw)
            if len(st) >= 3 and not st.isdigit() and st not in generic:
                out.add(st)
            for syn in conv.BODY_SYNONYMS.get(raw, []) + conv.BODY_SYNONYMS.get(st, []):
                out.add(tx.stem(syn))
        return out

    def _text_hits(self, toks: list[str], words: set[str], topics: list[str], min_len: int = 2) -> float:
        """Distinctive words of the question found in a text, plus topic phrases found in it. A one-word topic phrase is too
        weak to tie a question to a FACT ("blood" is not "blood pressure"), so facts need a phrase of `min_len` words."""
        have = set(toks)
        score = float(len(words & have))
        for key in topics:
            for p in tx.TOPICS.get(key, []):
                pt = tx.tokens(p)
                if len(pt) >= min_len and "you" not in pt and "your" not in pt and tx.contains_phrase(toks, pt, slack=1):
                    score += len(pt)
        return score

    def case_text_match(self, norm: str, topics: list[str]) -> tuple[list[str], bool]:
        """Facts (any category, any rule) whose own wording touches the question, best first, and whether the description the
        case was drafted from touches it. Used only when no topic matched: a default "no" must never contradict the case."""
        # a question on a recognised topic is checked phrase by phrase ("chest pain" must be in the text, not just "pain");
        # only a question on no recognised topic falls back to its distinctive words
        words = set() if topics else self._distinctive(norm)
        if not words and not topics:
            return [], False
        scored = []
        for i, f in enumerate(self.facts):
            if f.get("category") == "allergies":
                continue                # "do you take codeine?" is not answered by "I'm allergic to codeine"; allergy questions match by topic
            blob = " ".join(str(f.get(k) or "") for k in ("statement", "patient_answer", "label"))
            s = self._text_hits(tx.tokens(blob), words, topics)
            if s > 0:
                hidden = self.rule(f) in ("after_rapport", "denied_until_confronted")
                scored.append((-s, 0 if hidden else 1, i, f["fact_id"]))
        scored.sort()
        src = str((self.case.get("review") or {}).get("source_description") or "")
        # ... but for the description itself any mention is enough to rule out a flat "no"
        in_source = bool(src) and self._text_hits(tx.tokens(src), words or self._distinctive(norm), topics, min_len=1) > 0
        return [fid for *_, fid in scored], in_source

    def pain_facts(self) -> list[str]:
        """What "do you have pain anywhere?" should be answered from: the complaint first, then any other fact about pain."""
        from . import conversation as conv
        out = []
        for cats in (("chief_complaint",), ("hpi",), ("ros", "pmh", "medications", "social")):
            for f in self.facts:
                if f.get("category") in cats and self.rule(f) in ("volunteered", "if_asked") and f.get("patient_knows") is not False \
                        and f.get("polarity") != "negative":
                    blob = " ".join(str(f.get(k) or "") for k in ("statement", "patient_answer")) + " " + f["fact_id"].replace(".", " ").replace("_", " ") \
                        + " " + " ".join(str(t).replace("_", " ") for t in f.get("topics") or [])
                    if set(tx.tokens(blob)) & conv.PAIN_WORDS and f["fact_id"] not in out:
                        out.append(f["fact_id"])
        return out[:1]

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
        norm = getattr(intent, "norm", "") or tx.normalize(text)
        via_extra = "feelings"
        probe = False
        blocked = {"injection", "backchannel", "closing", "summarising", "explaining"} & set(conv)
        if "probe_hidden" in conv and "injection" not in conv:
            # "is there something you're afraid to tell me?": asks about everything the patient is holding back
            hidden = [f["fact_id"] for f in self.facts if self.rule(f) == "after_rapport" and f["fact_id"] not in already and f.get("patient_knows") is not False]
            if hidden:
                matched, probe, via_extra = hidden[:2], True, "general invitation to say what is held back"
            elif not matched:
                conv = dict(conv)
                conv.setdefault("ice", ["probe"])
        in_source = False
        if not matched and intent.is_question and not blocked and "ice" not in conv and not intent.requests and not getattr(intent, "off_topic", False):
            if "generic_pain" in conv and not getattr(intent, "topics_asked", None):
                matched = self.pain_facts()
                via_extra = "pain, asked in general"
            if not matched:
                cands, in_source = self.case_text_match(norm, list(getattr(intent, "topics_asked", []) or []) + (["progression"] if "progression" in conv else []))
                matched = cands[:1]
                via_extra = "the case's own wording"
        # a concealed fact wins over a neighbouring symptom fact: "No, I'm not coughing" is not the answer to "coughing up blood?"
        hid = [fid for fid in matched if self.rule(self.by_id[fid]) in ("after_rapport", "denied_until_confronted") and fid not in already]
        if hid and len(matched) > len(hid):
            top = max(intent.fact_scores.get(fid) or 0 for fid in hid)
            matched = [fid for fid in matched if fid in hid or self.by_id[fid].get("category") not in ("ros", "hpi", "chief_complaint")
                       or (intent.fact_scores.get(fid) or 0) > top]
        ev["matched_intents"] = [m for m in ev["matched_intents"] if m["fact_id"] in matched] + \
            [{"fact_id": fid, "score": None, "via": via_extra} for fid in matched if fid not in {m["fact_id"] for m in ev["matched_intents"]}]
        voiced_before = {fid for e in state["ledger"][:-1] if e.get("kind") == "turn"
                         for fid in list(e.get("disclosed_fact_ids") or []) + list(e.get("restated_fact_ids") or [])
                         if (e.get("rule_fired") or {}).get(fid) not in ("on_request", "chart_initial")}
        outcome["restated"], outcome["noncommittal"] = [], False
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
                elif fid in voiced_before or fid in ev["disclosed_fact_ids"]:
                    outcome["repeated"].append(fid)
                else:
                    # known to the care team (chart, an earlier stage) but never said to THIS listener: no "Like I said"
                    outcome["restated"].append(fid)
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
                    outcome["covered" if f.get("cover_answer") and not probe else "deflected"].append(fid)
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
        if "injection" not in conv and "ice" not in conv and not getattr(intent, "off_topic", False) and (
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
                outcome["restated"] = []
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
        elif outcome["repeated"] or outcome["restated"]:
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
        elif intent.is_question and not any(f.get("category") == "chief_complaint" for f in self.facts) \
                and tx.phrase_in(norm, tx.TOPICS["chief_complaint"]):
            ev["result"] = "answered_from_case_summary"  # "what brings you in?" is always answerable
            outcome["social"] = "complaint_fallback"
        elif intent.is_question and "closing" not in intent.cues and "summarising" not in intent.cues and "backchannel" not in conv:
            topics = list(getattr(intent, "topics_asked", []) or [])
            defined = {str(t).lower() for f in self.facts for t in (f.get("topics") or [])} | {f["fact_id"].split(".")[-1] for f in self.facts}
            free = [t for t in topics if t not in defined]
            if in_source or "progression" in conv:
                # the text the case was drafted from mentions this, but no fact answers it: never a flat "no"
                ev["result"] = "answered_noncommittal"
                outcome["noncommittal"] = True
            elif self.case.get("default_negatives", True) and (free or (not topics and getattr(intent, "clinical_yes_no", False))):
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
        ev["deflected_fact_ids"] = list(outcome["deflected"])
        ev["repeated_fact_ids"] = outcome["repeated"]
        if outcome["restated"]:
            ev["restated_fact_ids"] = list(outcome["restated"])
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
        return {"released": list(ev["disclosed_fact_ids"]), "repeated": [], "restated": [], "covered": [], "deflected": [], "patient_unknown": [],
                "spontaneous": [], "request_results": {req: ev["result"]}, "not_specified": False, "noncommittal": False, "event": ev}

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
                if f and f.get("cover_answer") and fid not in (ev.get("deflected_fact_ids") or []) and not any(n["_fact"] == fid for n in notes):
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
