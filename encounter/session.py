"""Encounter sessions: state, idempotent actions, finish + feedback + interaction result, logging to disk.

One JSON file per encounter in <data_dir>/sessions/. The session embeds a snapshot of the case version it
started with, so later edits or new versions never change a running or finished encounter.
"""
from __future__ import annotations

import copy
import json
import threading
import uuid
from pathlib import Path
from typing import Callable

from . import grader
from .disclosure import Engine, new_state, student_event
from .paths import data_dir
from .patient import respond
from .providers import Provider, get_provider
from .rubric import get_rubric
from .store import now_iso
from .taxonomy import CATEGORY_SECTION

DISPOSITIONS = ("discharge", "admit", "transfer", "undecided")


def order_label(request: str) -> str | None:
    """'order:ct_abdomen' -> 'ct abdomen (imaging)'. Plain words plus a category tag, so the simulator's
    write-back (which reads decision.orders as text) can route the patient to CT, X-ray or the lab.
    Examinations and record requests are not orders and return None."""
    kind, _, name = request.partition(":")
    if kind != "order" or name in ("prior_records", "medication_list"):
        return None
    words = name.replace("_", " ")
    if any(w in name for w in ("xray", "ct_", "mri", "ultrasound")) or name in ("ct", "xray"):
        cat = "imaging"
    elif name in ("ecg", "peak_flow"):
        cat = "bedside"
    else:
        cat = "lab"
    return f"{words} ({cat})"


class EncounterError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def learner_case_view(case: dict) -> dict:
    """What the student is told about the case before and during the encounter (no truth, no objectives)."""
    rub = get_rubric(case.get("rubric_id"))
    return {"case_id": case.get("case_id"), "version": case.get("version"), "title": case.get("title"),
            "setting": case.get("setting"), "learner_role": case.get("learner_role"), "intended_learner": case.get("intended_learner"),
            "prebrief": case.get("prebrief"), "n_objectives": len(case.get("objectives") or []),
            "rubric": {"rubric_id": rub.get("rubric_id"), "title": rub.get("title"),
                       "domains": [{"key": d.get("key"), "name": d.get("name")} for d in rub.get("domains", [])]},
            "synthetic": True, "needs_faculty_review": bool((case.get("review") or {}).get("needs_faculty_review"))}


def patient_view(case: dict) -> dict:
    p = case.get("profile") or {}
    out = {"name": p.get("name"), "age": p.get("age"), "gender": p.get("gender"),
           "image": f"/api/cases/{case.get('case_id')}/image"}
    if p.get("voice"):
        out["voice"] = p["voice"]
    return out


class EncounterManager:
    def __init__(self, data: Path | None = None, provider_fn: Callable[[], Provider] | None = None):
        self._data = Path(data) if data else None
        self._provider_fn = provider_fn or get_provider
        self._cache: dict[str, dict] = {}
        self._locks: dict[str, threading.RLock] = {}
        self._glock = threading.RLock()
        self._writeback: dict[str, Callable[[dict], None]] = {}

    @property
    def dir(self) -> Path:
        d = (self._data or data_dir()) / "sessions"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def provider(self) -> Provider:
        return self._provider_fn()

    def _lock(self, eid: str) -> threading.RLock:
        with self._glock:
            return self._locks.setdefault(eid, threading.RLock())

    def _save(self, s: dict) -> None:
        path = self.dir / f"{s['encounter_id']}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(s, ensure_ascii=False))
        tmp.replace(path)
        self._cache[s["encounter_id"]] = s

    def _load(self, eid: str) -> dict:
        if eid in self._cache:
            return self._cache[eid]
        path = self.dir / f"{eid}.json"
        if not eid.replace("-", "").isalnum() or not path.is_file():
            raise EncounterError(f"encounter '{eid}' not found", 404)
        s = json.loads(path.read_text())
        self._cache[eid] = s
        return s

    # ------------------------------------------------------------ start
    def start(self, case: dict, sim: dict | None = None, known_state: dict | None = None, preview: bool = False,
              writeback: Callable[[dict], None] | None = None, learner: str | None = None) -> dict:
        case = {k: v for k, v in copy.deepcopy(case).items() if not k.startswith("_")}
        if case.get("status") != "published" and not preview:
            raise EncounterError(f"case '{case.get('case_id')}' v{case.get('version')} is {case.get('status')}; only published "
                                 "versions can be started (use preview for a faculty test run)", 409)
        eid = "enc-" + uuid.uuid4().hex[:12]
        engine = Engine(case)
        state = new_state()
        ks = known_state or {}
        has_triage_artifact = any(a.get("section_id") == "triage" for a in (case.get("chart") or {}).get("artifacts") or [])
        if ks.get("triage_note") and not has_triage_artifact:
            # the care team's triage note from the simulator is shown as-is in an initial section
            secs = case.setdefault("chart", {}).setdefault("sections", [])
            tri = next((x for x in secs if x.get("section_id") == "triage"), None)
            if tri is None:
                secs.insert(0, {"section_id": "triage", "title": "Triage note", "release": "initial", "static_text": ks["triage_note"]})
            elif not tri.get("static_text"):
                tri["static_text"] = ks["triage_note"]
            engine = Engine(case)
        engine.start(state, known_fact_ids=ks.get("known_fact_ids"))
        prov = self.provider()
        prov.warm()
        s = {"encounter_id": eid, "case_id": case.get("case_id"), "case_version": case.get("version"), "case": case,
             "state": state, "status": "active", "started": now_iso(), "finished": None, "preview": bool(preview),
             "sim": sim, "learner": learner, "responses": {}, "feedback": None, "interaction_result": None, "written_back": False,
             "llm_at_start": prov.status()}
        with self._lock(eid):
            self._save(s)
        if writeback is not None:
            self._writeback[eid] = writeback
        return {"encounter_id": eid, "case": learner_case_view(case), "chart": engine.learner_chart(state),
                "patient": patient_view(case), "llm": {"provider": prov.name, "live": prov.live, "model": prov.model},
                "available_requests": engine.available_requests(), "rapport": 0, "status": "active", "preview": bool(preview),
                "opening_line": None, "sim": sim}

    # ------------------------------------------------------------ actions
    def _response(self, s: dict, engine: Engine, ev: dict, reply: str | None, notes: list[str], provider: str, fallback: bool) -> dict:
        state = s["state"]
        disclosed = []
        for fid in ev.get("disclosed_fact_ids") or []:
            f = engine.by_id[fid]
            section = f.get("chart_section") or CATEGORY_SECTION.get(f.get("category"), ("hpi", ""))[0]
            disclosed.append({"fact_id": fid, "chart_section": section, "text": engine.fact_text(f),
                              "category": f.get("category"), "rule": (ev.get("rule_fired") or {}).get(fid)})
        arts = []
        for aid in ev.get("released_artifact_ids") or []:
            a = engine.art_by_id[aid]
            arts.append({"artifact_id": aid, "kind": a.get("kind"), "title": a.get("title"), "section_id": a.get("section_id")})
        return {"encounter_id": s["encounter_id"], "turn": state["turn"], "request_id": ev.get("request_id"), "reply": reply,
                "notes": notes, "disclosed": disclosed, "released_artifacts": arts, "chart": engine.learner_chart(state),
                "ledger_tail": [student_event(e) for e in state["ledger"][-5:]], "rapport": state["rapport"],
                "result": student_event(ev)["result"], "provider": provider, "fallback": bool(fallback),
                "llm": self.provider().status()}

    def _active(self, eid: str) -> dict:
        s = self._load(eid)
        if s["status"] != "active":
            raise EncounterError("this encounter is finished", 409)
        return s

    def turn(self, eid: str, text: str, request_id: str | None = None) -> dict:
        text = (text or "").strip()
        if not text:
            raise EncounterError("text is required", 422)
        if len(text) > 2000:
            raise EncounterError("text is too long (2000 characters max)", 422)
        with self._lock(eid):
            s = self._load(eid)
            if request_id and request_id in s["responses"]:
                return s["responses"][request_id]            # idempotent retry: same answer, no new ledger event
            s = self._active(eid)
            request_id = request_id or "auto-" + uuid.uuid4().hex[:10]
            engine = Engine(s["case"])
            r = respond(s["case"], engine, s["state"], text, self.provider(), request_id)
            resp = self._response(s, engine, r["event"], r["reply"], r["notes"], r["provider"], r["fallback"])
            resp["wording"] = r["wording"]                          # "model" or "authored"
            resp["grounding_fallback"] = r["grounding_fallback"]    # a model-worded reply was rejected; authored wording used
            resp["timing_ms"] = r["timing_ms"]
            s["responses"][request_id] = resp
            self._save(s)
            return resp

    def request(self, eid: str, request: str, request_id: str | None = None) -> dict:
        if not (request or "").strip():
            raise EncounterError("request is required", 422)
        with self._lock(eid):
            s = self._load(eid)
            if request_id and request_id in s["responses"]:
                return s["responses"][request_id]
            s = self._active(eid)
            request_id = request_id or "auto-" + uuid.uuid4().hex[:10]
            engine = Engine(s["case"])
            out = engine.process_request(s["state"], request, request_id)
            ev = out["event"]
            req, res = next(iter(out["request_results"].items()))
            label = req.split(":", 1)[-1].replace("_", " ")
            note = {"not_available": f"{label}: not available in this scenario.",
                    "default_normal": f"{label}: result added to the chart (default normal result, synthetic).",
                    "pending": f"{label}: requested. The result is pending.",
                    "already_available": f"{label}: already in the chart."}.get(res, f"{label}: result added to the chart.")
            notes = [note] + [f"New in the chart: {engine.art_by_id[a].get('title', a)}." for a in ev["released_artifact_ids"]]
            notes += [f"New in the chart: {d['title']} (default normal)." for d in ev.get("default_results") or []]
            ev["system_notes"] = notes
            ev["provider"] = "offline"
            resp = self._response(s, engine, ev, None, notes, "offline", False)
            resp["request"] = req
            s["responses"][request_id] = resp
            self._save(s)
            return resp

    # ------------------------------------------------------------ views
    def get(self, eid: str, view: str = "student") -> dict:
        s = self._load(eid)
        engine = Engine(s["case"])
        state = s["state"]
        out = {"encounter_id": eid, "status": s["status"], "started": s["started"], "finished": s["finished"],
               "case": learner_case_view(s["case"]), "patient": patient_view(s["case"]), "chart": engine.learner_chart(state),
               "transcript": grader.build_transcript(state), "ledger": [student_event(e) for e in state["ledger"]],
               "rapport": state["rapport"], "turn": state["turn"], "available_requests": engine.available_requests(),
               "preview": s.get("preview", False), "sim": s.get("sim"), "feedback": s.get("feedback"),
               "interaction_result": s.get("interaction_result"), "written_back": s.get("written_back", False),
               "llm": self.provider().status()}
        if view == "faculty":
            out["ledger_full"] = state["ledger"]
            out["case_full"] = s["case"]
        return out

    def list(self, case_id: str | None = None) -> list[dict]:
        rows = []
        for p in sorted(self.dir.glob("enc-*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                s = self._cache.get(p.stem) or json.loads(p.read_text())
            except Exception:
                continue
            if case_id and s.get("case_id") != case_id:
                continue
            ir = s.get("interaction_result") or {}
            fb = s.get("feedback") or {}
            rows.append({"encounter_id": s["encounter_id"], "case_id": s.get("case_id"), "case_version": s.get("case_version"),
                         "title": (s.get("case") or {}).get("title"), "patient": ((s.get("case") or {}).get("profile") or {}).get("name"),
                         "status": s.get("status"), "started": s.get("started"), "finished": s.get("finished"),
                         "turns": (s.get("state") or {}).get("turn", 0), "preview": s.get("preview", False),
                         "quality": ir.get("quality"), "duration_min": ir.get("duration_min"), "grader": fb.get("grader"),
                         "rubric_total": (fb.get("rubric") or {}).get("total"), "rubric_max": (fb.get("rubric") or {}).get("max_total"),
                         "n_disclosed": len(ir.get("information_gained") or []), "sim": s.get("sim"),
                         "written_back": s.get("written_back", False)})
        return rows

    # ------------------------------------------------------------ finish
    def finish(self, eid: str, disposition: str | None = None, orders: list[str] | None = None, summary: str | None = None) -> dict:
        with self._lock(eid):
            s = self._load(eid)
            if s["status"] == "finished":
                return {"feedback": s["feedback"], "interaction_result": s["interaction_result"], "written_back": s["written_back"],
                        "encounter_id": eid, "already_finished": True}
            disp = (disposition or "undecided").strip().lower()
            if disp not in DISPOSITIONS:
                raise EncounterError(f"disposition must be one of {', '.join(DISPOSITIONS)}", 422)
            case, state = s["case"], s["state"]
            engine = Engine(case)
            from .matcher import canonical_request
            norm_orders = []
            for o in orders or []:
                if isinstance(o, str) and o.strip():
                    c = canonical_request(o if ":" in o else f"order:{o}", engine.case_requests)
                    if c not in norm_orders:
                        norm_orders.append(c)
            finish = {"disposition": disp, "orders": norm_orders, "summary": (summary or "").strip()[:4000]}
            prov = self.provider()
            feedback = grader.grade(case, state, get_rubric(case.get("rubric_id")), finish, prov)
            requested = list(state.get("requests_made", []))
            offered = set(engine.workup) | set(engine.case_requests)
            for o in norm_orders:
                if o not in requested and o in offered:          # an order the scenario cannot fulfil is not written back
                    requested.append(o)
            all_orders = [lab for lab in (order_label(r) for r in requested) if lab]
            sim = s.get("sim") or {}
            result = {
                "interaction_id": eid,
                "interaction_type": "clinician_encounter",
                "patient_id": int(sim.get("patient_id", 0) or 0),
                "participants": [
                    {"entity_id": int(sim.get("patient_id", 0) or 0), "role": "patient", "played_by": "ai"},
                    {"entity_id": s.get("learner") or "learner", "role": sim.get("staff_role") or "resident", "played_by": "human"},
                ],
                "resolver": "played",
                "duration_min": grader.duration_minutes(state),
                "information_gained": sorted(engine.disclosed(state)),
                "decision": {"kind": "disposition" if disp != "undecided" else ("orders" if all_orders else "none"),
                             "orders": all_orders, "disposition": disp, "detail": finish["summary"][:500]},
                "quality": feedback["quality"],
                "session_ref": eid,
                "objective_results": [{"objective_id": o["objective_id"], "result": o["result"]} for o in feedback["objectives"]],
            }
            feedback["requests_made"] = requested
            if isinstance(sim.get("t_start"), int):
                result["t_start"] = sim["t_start"]
            state["ledger"].append({"seq": len(state["ledger"]), "time": now_iso(), "turn": state["turn"], "actor": "learner",
                                    "kind": "finish", "case_id": case.get("case_id"), "case_version": case.get("version"),
                                    "text": finish["summary"], "request": None, "request_id": None, "matched_intents": [],
                                    "disclosed_fact_ids": [], "released_artifact_ids": [], "rule_fired": {}, "withheld": [],
                                    "result": f"finished:{disp}", "rapport": state["rapport"], "rapport_delta": 0, "rapport_reasons": [],
                                    "orders": norm_orders})
            written = False
            wb = self._writeback.pop(eid, None)
            if wb is not None:
                try:
                    wb(result)
                    written = True
                except Exception as e:  # noqa: BLE001 - feedback must still be returned
                    feedback["writeback_error"] = f"{type(e).__name__}: {str(e)[:200]}"
            s.update(status="finished", finished=now_iso(), feedback=feedback, interaction_result=result, written_back=written,
                     finish=finish)
            self._save(s)
            return {"encounter_id": eid, "feedback": feedback, "interaction_result": result, "written_back": written}


_default: EncounterManager | None = None


def default_manager() -> EncounterManager:
    global _default
    if _default is None:
        _default = EncounterManager()
    return _default
