"""Journey instances: one JSON file per journey in <data_dir>/journeys/, holding the definition and case snapshot
it started with, the shared record, every stage's state and result, and an append-only log.

Each completed stage emits an interaction-contract result (contracts/interaction.schema.json#/$defs/result), so a
journey is a chain of the simulation's own interactions. Only the clinician_encounter stage writes back to a live
simulation (through the encounter session's existing write-back hook); the other types have no simulator
write-back yet.
"""
from __future__ import annotations

import copy
import json
import random
import threading
import uuid
from pathlib import Path
from typing import Any, Callable

from ..clinicians import list_clinicians
from ..disclosure import Engine, student_event
from ..grader import build_transcript
from ..paths import data_dir
from ..providers import Provider, get_provider
from ..session import EncounterError, EncounterManager, learner_case_view, patient_view
from ..store import now_iso
from . import handoff as ho
from . import record as rec
from . import stages as st
from . import synthesis
from .definition import DEFAULT_MINUTES, applies_to, stage_kind, validate_definition


class JourneyError(Exception):
    def __init__(self, message: str, status: int = 400, detail: dict | None = None):
        super().__init__(message)
        self.status = status
        self.detail = detail or {}


def pick_clinician(staff_role: str | None, clinician_id: str | None = None, avoid: str | None = None) -> dict:
    """A fictional colleague for a role: the named profile when it is loaded, otherwise the first with that staff role."""
    pool = list_clinicians()["clinicians"]
    keep = ("id", "name", "credentials", "role", "staff_role", "specialty", "communication_style", "source")
    c = next((x for x in pool if x["id"] == clinician_id), None)
    if c is None:
        same = [x for x in pool if x.get("staff_role") == staff_role] or \
               [x for x in pool if {x.get("staff_role"), staff_role} <= {"rn", "charge_rn"}] or \
               [x for x in pool if {x.get("staff_role"), staff_role} <= {"attending", "resident", "app"}] or pool
        c = next((x for x in same if x["id"] != avoid), same[0])
    return {k: c.get(k) for k in keep}


class JourneyManager:
    def __init__(self, enc: EncounterManager, data: Path | None = None, provider_fn: Callable[[], Provider] | None = None):
        self.enc = enc
        self._data = Path(data) if data else None
        self._provider_fn = provider_fn or get_provider
        self._cache: dict[str, dict] = {}
        self._locks: dict[str, threading.RLock] = {}
        self._glock = threading.RLock()
        self._sims: dict[str, tuple[Any, int]] = {}

    # ------------------------------------------------------------ storage
    @property
    def dir(self) -> Path:
        d = (self._data or data_dir()) / "journeys"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _lock(self, jid: str) -> threading.RLock:
        with self._glock:
            return self._locks.setdefault(jid, threading.RLock())

    def _save(self, j: dict) -> None:
        path = self.dir / f"{j['journey_id']}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(j, ensure_ascii=False))
        tmp.replace(path)
        self._cache[j["journey_id"]] = j

    def _load(self, jid: str) -> dict:
        if jid in self._cache:
            return self._cache[jid]
        path = self.dir / f"{jid}.json"
        if not jid.replace("-", "").isalnum() or not path.is_file():
            raise JourneyError(f"journey '{jid}' not found", 404)
        j = json.loads(path.read_text())
        self._cache[jid] = j
        return j

    @staticmethod
    def _log(j: dict, kind: str, stage_id: str | None = None, **detail) -> None:
        j["log"].append({"seq": len(j["log"]), "time": now_iso(), "kind": kind, "stage_id": stage_id, **detail})

    def _stage(self, j: dict, sid: str) -> tuple[int, dict, dict]:
        for i, d in enumerate(j["definition"]["stages"]):
            if d["stage_id"] == sid:
                return i, d, j["stages"][i]
        raise JourneyError(f"stage '{sid}' is not part of this journey", 404)

    # ------------------------------------------------------------ start
    def start(self, case: dict, definition: dict, learner: str | None = None, seed: int | None = None, sim_binding: dict | None = None,
              sim_handle: tuple[Any, int] | None = None, known_state: dict | None = None) -> dict:
        errs = validate_definition(definition)
        if errs:
            raise JourneyError("the journey definition is not valid", 422, {"errors": errs})
        if case.get("status") != "published":
            raise JourneyError(f"case '{case.get('case_id')}' is {case.get('status')}; a journey needs a published case", 409)
        if not applies_to(definition, str(case.get("case_id"))):
            raise JourneyError(f"journey '{definition['journey_id']}' is written for case '{definition['base_case']['case_id']}'", 409)
        jid = "jrn-" + uuid.uuid4().hex[:12]
        case = {k: v for k, v in copy.deepcopy(case).items() if not k.startswith("_")}
        j = {"journey_id": jid, "definition": copy.deepcopy(definition), "case": case, "case_id": case.get("case_id"),
             "case_version": case.get("version"), "seed": int(seed if seed is not None else random.SystemRandom().randrange(1, 2**31)),
             "learner": learner, "status": "active", "started": now_iso(), "finished": None, "record": rec.new_record(),
             "stages": [{"stage_id": s["stage_id"], "status": "pending", "played_by": None, "player": None, "encounter_id": None,
                         "synced": 0, "start_known": [], "writes": {}, "result": None, "objectives": [], "session_feedback": None,
                         "handoff": None, "started": None, "finished": None, "written_back": False, "writeback_note": None}
                        for s in definition["stages"]],
             "sim": sim_binding, "log": [], "llm_at_start": self._provider_fn().status()}
        self._log(j, "journey_started", None, case_id=j["case_id"], case_version=j["case_version"], journey=definition["journey_id"],
                  journey_version=definition["version"], seed=j["seed"], from_simulation=bool(sim_binding))
        if sim_handle is not None:
            self._sims[jid] = sim_handle
            self._absorb_sim_state(j, known_state or {})
        with self._lock(jid):
            self._save(j)
        return self.view(jid)

    def _absorb_sim_state(self, j: dict, known: dict) -> None:
        """A simulated patient arrives already triaged by the simulation: its triage note and known facts open the record."""
        idx = next((i for i, s in enumerate(j["definition"]["stages"]) if s["interaction_type"] == "triage"), None)
        if idx is None or idx != 0 or not known.get("triage_note"):
            return
        sdef, sst = j["definition"]["stages"][idx], j["stages"][idx]
        who = rec.by(sdef, "sim", "Simulation")
        engine = Engine(j["case"])
        rec.add(j["record"], sdef, idx, who, "note", str(known["triage_note"]), "simulation", None, status="assessment")
        gained = []
        for fid in known.get("known_fact_ids") or []:
            if fid in engine.by_id and not rec.has_fact(j["record"], fid):
                e = st.add_fact(j["record"], sdef, idx, who, engine, fid, "chart_initial", None)
                if e:
                    e["source"] = "simulation"
                    gained.append(fid)
        sst.update(status="completed", played_by="sim", player="Simulation", started=now_iso(), finished=now_iso())
        sst["result"] = {"interaction_id": f"{j['journey_id']}:{sdef['stage_id']}", "interaction_type": "triage",
                         "patient_id": int((j.get("sim") or {}).get("patient_id", 0) or 0),
                         "participants": [{"entity_id": int((j.get("sim") or {}).get("patient_id", 0) or 0), "role": "patient", "played_by": "sim"},
                                          {"entity_id": "simulation", "role": sdef["learner_role"]["staff_role"], "played_by": "sim"}],
                         "resolver": "sampled", "duration_min": 0.0, "information_gained": gained,
                         "decision": {"kind": "none", "detail": "Already resolved by the running simulation before the journey opened; its duration and quality stay in the simulation."},
                         "quality": 0.0}
        sst["result_note"] = "Resolved by the simulation before the journey opened. Duration and quality are not copied here."
        self._log(j, "stage_finished", sdef["stage_id"], played_by="sim", n_entries=len(gained) + 1)

    # ------------------------------------------------------------ stage lifecycle
    def _startable(self, j: dict, idx: int) -> None:
        if j["stages"][idx]["status"] == "completed":
            raise JourneyError("this stage is already completed", 409)
        blocked = [s["stage_id"] for s in j["stages"][:idx] if s["status"] != "completed"]
        if blocked:
            raise JourneyError(f"earlier stages are not finished yet: {', '.join(blocked)}. Play them or let the sampler resolve them.", 409,
                               {"blocked_by": blocked})

    def start_stage(self, jid: str, sid: str, mode: str = "human", learner: str | None = None, quality: float | None = None) -> dict:
        if mode not in ("human", "auto"):
            raise JourneyError("mode must be 'human' or 'auto'", 422)
        with self._lock(jid):
            j = self._load(jid)
            idx, sdef, sst = self._stage(j, sid)
            if sst["status"] == "active" and mode == "human":
                return self.stage_view(jid, sid)                       # resume
            self._startable(j, idx)
            if mode == "auto":
                if sst["status"] == "active":
                    raise JourneyError("this stage is being played; finish it instead", 409)
                self._auto(j, idx, sdef, sst, quality)
                self._save(j)
                return self.stage_view(jid, sid)
            sst.update(status="active", played_by="human", player=learner or j.get("learner") or "You", started=now_iso(),
                       start_known=rec.fact_ids(j["record"]))
            if stage_kind(sdef) == "handoff":
                cp = next(c for c in sdef["counterparts"] if c["kind"] == "colleague")
                col = pick_clinician(cp.get("staff_role"), cp.get("clinician_id"))
                col["label"] = cp.get("label") or col.get("role")
                opening = f"{col['name']}, {rec.lc(col['label']) if cp.get('label') else col.get('role')}. I am taking over this patient. Go ahead with your handoff."
                sst["handoff"] = {"colleague": col, "sbar": None, "questions": [], "answers": [], "phase": "compose", "grading": None,
                                  "messages": [{"who": "colleague", "text": opening, "time": now_iso()}], "replies": []}
            else:
                sc = st.stage_case(j["case"], j["definition"], sdef, idx, j["record"])
                binding, wb = None, None
                if j.get("sim") and sdef["interaction_type"] == "clinician_encounter":
                    binding, wb = self._hold(j, sst)
                started = self.enc.start(sc, sim=binding, known_state={"known_fact_ids": rec.fact_ids(j["record"])}, writeback=wb,
                                         learner=sst["player"])
                sst["encounter_id"] = started["encounter_id"]
                self._sync(j, idx, sdef, sst)
            self._log(j, "stage_started", sid, played_by="human", role=sdef["learner_role"]["label"])
            self._save(j)
            return self.stage_view(jid, sid)

    def _hold(self, j: dict, sst: dict) -> tuple[dict, Callable[[dict], None] | None]:
        binding = dict(j["sim"])
        handle = self._sims.get(j["journey_id"])
        if handle is None:
            sst["writeback_note"] = "The simulation run is no longer attached to this journey, so nothing is written back."
            return binding, None
        sim, b = handle
        held = bool(sim.hold_for_play(b, int(binding["patient_id"])))
        binding["held"] = held
        if not held:
            sst["writeback_note"] = "The simulation had already resolved this patient's clinician encounter, so nothing is written back."
            return binding, None

        def writeback(result: dict) -> None:
            sim.apply_interaction_result(b, result)

        return binding, writeback

    def _who(self, sdef: dict, sst: dict) -> dict:
        return rec.by(sdef, "human" if sst["played_by"] == "human" else "sampled", sst.get("player"))

    def _sync(self, j: dict, idx: int, sdef: dict, sst: dict) -> list[dict]:
        s = self.enc._load(sst["encounter_id"])
        before = len(j["record"]["discrepancies"])
        sst["synced"], new = st.sync_session(j["record"], sdef, idx, self._who(sdef, sst), j["case"], s["case"], s["state"], sst["synced"])
        if new:
            self._log(j, "record_entries_added", sdef["stage_id"], entry_ids=[e["entry_id"] for e in new])
        for d in j["record"]["discrepancies"][before:]:
            self._log(j, "discrepancy_flagged", sdef["stage_id"], discrepancy_id=d["discrepancy_id"], discrepancy_kind=d["kind"])
        return new

    def _active(self, j: dict, sid: str, kind: str) -> tuple[int, dict, dict]:
        idx, sdef, sst = self._stage(j, sid)
        if sst["status"] != "active":
            raise JourneyError("this stage is not being played" if sst["status"] == "pending" else "this stage is finished", 409)
        if stage_kind(sdef) != kind:
            raise JourneyError("this action does not apply to this kind of stage", 409)
        return idx, sdef, sst

    def _enc_action(self, jid: str, sid: str, fn: Callable[[str], dict]) -> dict:
        with self._lock(jid):
            j = self._load(jid)
            idx, sdef, sst = self._active(j, sid, "patient")
            try:
                resp = dict(fn(sst["encounter_id"]))
            except EncounterError as e:
                raise JourneyError(str(e), e.status)
            new = self._sync(j, idx, sdef, sst)
            self._save(j)
            resp.pop("encounter_id", None)
            resp.update(journey_id=jid, stage_id=sid, record=rec.student_view(j["record"]), record_added=[e["entry_id"] for e in new])
            return resp

    def turn(self, jid: str, sid: str, text: str, request_id: str | None = None) -> dict:
        j = self._load(jid)
        _, sdef, _ = self._stage(j, sid)
        if stage_kind(sdef) == "handoff":
            return self.answer(jid, sid, text)
        return self._enc_action(jid, sid, lambda eid: self.enc.turn(eid, text, request_id))

    def request(self, jid: str, sid: str, request: str, request_id: str | None = None) -> dict:
        j = self._load(jid)
        _, sdef, _ = self._stage(j, sid)
        patterns = (sdef.get("scope") or {}).get("requests") or []
        raw = (request or "").strip().lower()
        if raw and not st._req_in_scope(raw if ":" in raw else f"order:{raw}", patterns):
            raise JourneyError(f"'{request}' is outside what the {rec.lc(sdef['learner_role']['label'])} does at this stage", 409)
        resp = self._enc_action(jid, sid, lambda eid: self.enc.request(eid, request, request_id))
        if resp.get("result") == "not_available":
            with self._lock(jid):
                idx, sdef, sst = self._stage(j, sid)
                prior = next((e for e in j["record"]["entries"] if e["kind"] == "order" and e.get("request") == resp.get("request")
                              and e["stage_index"] < idx and e.get("order_status") == "resulted"), None)
                if prior:
                    rec.mark_used(prior, sid, resp.get("turn"), "looked up a result an earlier stage had requested", request)
                    for e in j["record"]["entries"]:
                        if e["kind"] == "artifact" and e["stage_id"] == prior["stage_id"] and e["stage_index"] < idx and \
                                Engine._artifact_request(Engine(j["case"]).art_by_id.get(e.get("artifact_id"), {"artifact_id": "", "release": {}})) == prior["request"]:
                            rec.mark_used(e, sid, resp.get("turn"), "looked up a result an earlier stage had requested", request)
                    label = str(resp.get("request") or "").split(":", 1)[-1].replace("_", " ")
                    resp["notes"] = [f"{label}: already on the shared record (requested by the {rec.lc(prior['by']['role_label'])} during "
                                     f"{prior['stage_title']}). It is in the chart."]
                    resp["result"] = "already_available"
                    resp["record"] = rec.student_view(j["record"])
                    self._save(j)
        return resp

    # ------------------------------------------------------------ finishing
    def _participants(self, j: dict, sdef: dict, sst: dict) -> list[dict]:
        pid = int((j.get("sim") or {}).get("patient_id", 0) or 0)
        human = sst["played_by"] == "human"
        out = []
        if stage_kind(sdef) == "patient":
            out.append({"entity_id": pid, "role": "patient", "played_by": "ai" if human else "sim"})
        out.append({"entity_id": sst.get("player") or "learner", "role": sdef["learner_role"]["staff_role"], "played_by": "human" if human else "ai"})
        if stage_kind(sdef) == "handoff":
            col = (sst.get("handoff") or {}).get("colleague") or {}
            out.append({"entity_id": col.get("id") or "colleague", "role": col.get("staff_role") or "rn", "played_by": "ai"})
        return out

    def _result(self, j: dict, idx: int, sdef: dict, sst: dict, duration: float, gained: list[str], decision: dict, quality: float) -> dict:
        r = {"interaction_id": f"{j['journey_id']}:{sdef['stage_id']}", "interaction_type": sdef["interaction_type"],
             "patient_id": int((j.get("sim") or {}).get("patient_id", 0) or 0), "participants": self._participants(j, sdef, sst),
             "resolver": "played" if sst["played_by"] == "human" else "sampled", "duration_min": round(float(duration), 1),
             "information_gained": sorted(set(gained)), "decision": decision, "quality": round(max(0.0, min(1.0, float(quality))), 3)}
        if sst["played_by"] == "human":
            if sst.get("encounter_id"):
                r["session_ref"] = sst["encounter_id"]
            r["objective_results"] = [{"objective_id": o["objective_id"], "result": o["result"]} for o in sst["objectives"]]
        if isinstance((j.get("sim") or {}).get("t_start"), int):
            r["t_start"] = j["sim"]["t_start"]
        return r

    def _decision(self, j: dict, sdef: dict, writes: dict, orders: list[str]) -> dict:
        it = sdef["interaction_type"]
        detail = str(writes.get("note") or "")[:500]
        if it == "triage" and "acuity" in writes:
            return {"kind": "acuity_assigned", "acuity": writes["acuity"], "detail": detail}
        if "disposition" in writes:
            return {"kind": "disposition", "orders": orders, "disposition": writes["disposition"], "detail": detail}
        if orders:
            return {"kind": "orders", "orders": orders, "disposition": "undecided", "detail": detail or "; ".join(writes.get("med_list") or [])[:500]}
        return {"kind": "none", "detail": detail or "; ".join(writes.get("med_list") or writes.get("plan") or [])[:500]}

    def _complete(self, j: dict, idx: int, sdef: dict, sst: dict) -> None:
        sst.update(status="completed", finished=now_iso())
        self._log(j, "stage_finished", sdef["stage_id"], played_by=sst["played_by"], quality=(sst["result"] or {}).get("quality"),
                  resolver=(sst["result"] or {}).get("resolver"))
        comp = j["definition"]["completion"]
        need = comp.get("stages") if comp["rule"] == "required_stages" else [s["stage_id"] for s in j["definition"]["stages"]]
        if all(s["status"] == "completed" for s in j["stages"] if s["stage_id"] in need) and j["status"] != "complete":
            j.update(status="complete", finished=now_iso())
            self._log(j, "journey_complete", None)

    def _orders(self, j: dict, sdef: dict) -> list[str]:
        from ..session import order_label
        out = []
        for e in j["record"]["entries"]:
            if e["stage_id"] == sdef["stage_id"] and e["kind"] == "order" and e.get("is_order"):
                lab = order_label(e["request"])
                if lab and lab not in out:
                    out.append(lab)
        return out

    def _support(self, j: dict) -> Callable[..., dict]:
        def fn(text: str, element: str = "A") -> dict:
            rtext = ho._record_text(j["record"], j["case"], "")
            items = ho.expected_items(j["record"], {"stage_id": "", "sbar": {}})
            ids, bad = [], []
            for s in ho.sentences(text):
                hits = ho.match_sentence(s, items, j["record"], j["case"])
                ids += [i[2:] for i in hits if i.startswith("i-e")]
                by_item = {it["item_id"]: it for it in items}
                hit_entries = [e for e in (rec.find(j["record"], x) for i in hits for x in by_item[i]["entry_ids"]) if e]
                why = ho.unsupported_reason(s, element, rtext, j["record"], j["case"], hit_entries)
                if not why and element == "B" and ho.unknown_medicine(s, rtext):
                    why = f"no entry in the shared record mentions {ho.unknown_medicine(s, rtext)}"
                if why:
                    bad.append({"quote": s, "reason": why})
            return {"entry_ids": sorted(set(ids)), "unsupported": bad}
        return fn

    def finish(self, jid: str, sid: str, body: dict | None = None) -> dict:
        body = body or {}
        with self._lock(jid):
            j = self._load(jid)
            idx, sdef, sst = self._stage(j, sid)
            if sst["status"] == "completed":
                return dict(self.stage_view(jid, sid), already_finished=True)
            if sst["status"] != "active":
                raise JourneyError("this stage has not been started", 409)
            if stage_kind(sdef) == "handoff":
                self._finish_handoff(j, idx, sdef, sst)
            else:
                writes, missing = st.normalise_writes(sdef, body)
                if missing:
                    raise JourneyError(f"this stage must write to the shared record: {', '.join(missing)}", 422, {"missing": missing})
                self._sync(j, idx, sdef, sst)
                who = self._who(sdef, sst)
                try:
                    fin = self.enc.finish(sst["encounter_id"], writes.get("disposition"), writes.get("orders"), writes.get("note"))
                except EncounterError as e:
                    raise JourneyError(str(e), e.status)
                s = self.enc._load(sst["encounter_id"])
                turn = s["state"]["turn"]
                patterns = (sdef.get("scope") or {}).get("requests") or []
                for req in (s.get("finish") or {}).get("orders") or []:
                    if st._req_in_scope(req, patterns):
                        st.add_request(j["record"], sdef, idx, who, req, None, turn)
                st.apply_writes(j["record"], sdef, idx, who, writes, turn, self._support(j))
                rec.detect_discrepancies(j["record"], j["case"])
                sst["writes"] = writes
                requests_made = list(s["state"].get("requests_made") or []) + list((s.get("finish") or {}).get("orders") or [])
                objs = st.grade_objectives(sdef, idx, j["record"], j["case"], writes, set(sst["start_known"]), requests_made)
                fb = fin["feedback"]
                for o in fb.get("objectives") or []:
                    objs.append({"objective_id": o["objective_id"], "criterion": o.get("criterion"), "kind": "case", "result": o["result"],
                                 "evidence": [{"quote": e.get("quote"), "turn": e.get("turn"), "entry_id": None,
                                               "location": f"{sdef.get('title') or sid}, turn {e.get('turn')}"} for e in (o.get("evidence") or [])[:3] if isinstance(e, dict)],
                                 "feedback": o.get("suggestion") or o.get("rationale") or "", "behavior": "contribute", "reveal": "debrief",
                                 "uncertain": bool(o.get("uncertain"))})
                sst["objectives"] = objs
                sst["session_feedback"] = fb
                quality = fb["quality"] if sdef.get("case_objectives") and fb.get("objectives") else \
                    st.stage_quality(sdef, j["record"], j["case"], set(sst["start_known"]), objs)
                gained = [e["fact_id"] for e in j["record"]["entries"] if e["stage_id"] == sid and e.get("fact_id")]
                sst["result"] = self._result(j, idx, sdef, sst, fin["interaction_result"]["duration_min"], gained,
                                             self._decision(j, sdef, writes, self._orders(j, sdef)), quality)
                sst["written_back"] = bool(fin.get("written_back"))
                if fb.get("writeback_error"):
                    sst["writeback_note"] = f"The simulation refused the result: {fb['writeback_error']}"
                if sst["written_back"]:
                    sst["session_result"] = fin["interaction_result"]
                    self._log(j, "written_back", sid, run_id=(j.get("sim") or {}).get("run_id"))
            self._complete(j, idx, sdef, sst)
            self._save(j)
            return self.stage_view(jid, sid)

    def _auto(self, j: dict, idx: int, sdef: dict, sst: dict, quality: float | None) -> None:
        col = pick_clinician(sdef["learner_role"]["staff_role"], (sdef.get("auto") or {}).get("clinician_id"))
        sst.update(status="active", played_by="sampled", player=col["name"], started=now_iso(), start_known=rec.fact_ids(j["record"]),
                   auto_clinician=col)
        who = rec.by(sdef, "sampled", col["name"])
        self._log(j, "stage_started", sdef["stage_id"], played_by="sampled", role=sdef["learner_role"]["label"], clinician=col["id"])
        if stage_kind(sdef) == "handoff":
            q = st.sample_quality(j["seed"], sdef["stage_id"], quality)
            rng = random.Random(f"{j['seed']}:{sdef['stage_id']}")
            cp = next(c for c in sdef["counterparts"] if c["kind"] == "colleague")
            receiver = pick_clinician(cp.get("staff_role"), cp.get("clinician_id"), avoid=col["id"])
            receiver["label"] = cp.get("label") or receiver.get("role")
            sbar = ho.auto_sbar(j["record"], sdef, q, rng)
            h = {"colleague": receiver, "sbar": sbar, "questions": [], "answers": [], "phase": "done", "grading": None, "messages": [], "replies": []}
            sst["handoff"] = h
            g = ho.grade_sbar(sbar, [], j["record"], j["case"], sdef)
            h["questions"] = ho.plan_questions(g, sdef)
            for qn in h["questions"]:
                texts = [o["text"] for el in g["elements"].values() for o in el["omitted"] if o["item_id"] in qn["item_ids"]]
                ans = " ".join(t.rstrip(".") + "." for t in texts) if texts and rng.random() < q else "I do not have that to hand."
                qn.update(answered=True, answer=ans)
                h["answers"].append({"question_id": qn["question_id"], "element": qn["element"], "text": ans})
            sst["sampled_quality"] = q
            self._finish_handoff(j, idx, sdef, sst)
        else:
            out = st.auto_resolve(j["record"], j["definition"], sdef, idx, who, j["case"], j["seed"], quality)
            sst["writes"] = out["writes"]
            sst["sampled_quality"] = out["quality"]
            sst["objectives"] = st.grade_objectives(sdef, idx, j["record"], j["case"], out["writes"], set(sst["start_known"]), out["requests"])
            sst["result"] = self._result(j, idx, sdef, sst, out["duration_min"], out["found"],
                                         self._decision(j, sdef, out["writes"], self._orders(j, sdef)), out["quality"])
            if j.get("sim") and sdef["interaction_type"] == "clinician_encounter":
                sst["writeback_note"] = "Not played by a person, so this stage is left to the simulation's own sampler; nothing is written back."
        self._complete(j, idx, sdef, sst)

    def auto_until(self, jid: str, until: str | None = None, quality: float | None = None) -> dict:
        """Let the sampler resolve every unfinished stage before `until` (or all of them)."""
        with self._lock(jid):
            j = self._load(jid)
            if until is not None:
                self._stage(j, until)
            for idx, sdef in enumerate(j["definition"]["stages"]):
                if sdef["stage_id"] == until:
                    break
                sst = j["stages"][idx]
                if sst["status"] == "pending":
                    self._auto(j, idx, sdef, sst, quality)
                elif sst["status"] == "active":
                    raise JourneyError(f"stage '{sdef['stage_id']}' is being played; finish it first", 409)
            self._save(j)
        return self.view(jid)

    # ------------------------------------------------------------ handoff
    def submit_sbar(self, jid: str, sid: str, body: dict) -> dict:
        with self._lock(jid):
            j = self._load(jid)
            idx, sdef, sst = self._active(j, sid, "handoff")
            h = sst["handoff"]
            if h["answers"]:
                raise JourneyError("the handoff has already been given; answer the colleague or finish", 409)
            sbar = ho.parse_sbar(body)
            if not any(v.strip() for v in sbar.values()):
                raise JourneyError("write at least one part of the SBAR", 422)
            h["sbar"] = sbar
            h["messages"] = h["messages"][:1] + [{"who": "learner", "kind": "sbar", "sbar": sbar, "time": now_iso(),
                                                  "text": "\n".join(f"{ho.ELEMENTS[k]}: {v}" for k, v in sbar.items() if v)}]
            g = ho.grade_sbar(sbar, [], j["record"], j["case"], sdef)
            h["questions"] = ho.plan_questions(g, sdef)
            self._log(j, "sbar_submitted", sid, n_questions=len(h["questions"]))
            self._colleague_says(j, sdef, h, g, first=True)
            self._save(j)
            return self.stage_view(jid, sid)

    def _colleague_says(self, j: dict, sdef: dict, h: dict, grading: dict, first: bool = False) -> None:
        nxt = next((q for q in h["questions"] if not q["answered"]), None)
        if nxt:
            lines = (["Thanks, I have that."] if first else ["Okay."]) + [nxt["text"]]
            h["phase"] = "questions"
            nxt["asked"] = True
            self._log(j, "colleague_question", sdef["stage_id"], question_id=nxt["question_id"], about=nxt["about"])
        else:
            lines = (["Thanks."] if first else ["Okay, thank you."]) + ho.readback_lines(grading)
            h["phase"] = "readback"
        out = ho.colleague_reply(lines, h["colleague"], j["record"], j["case"], self._provider_fn())
        h["messages"].append({"who": "colleague", "text": out["reply"], "time": now_iso(), "question_id": nxt["question_id"] if nxt else None,
                              "kind": "question" if nxt else "readback", "provider": out["provider"], "wording": out["wording"],
                              "fallback": out["fallback"]})
        h["replies"].append(out)

    def answer(self, jid: str, sid: str, text: str) -> dict:
        text = (text or "").strip()
        if not text:
            raise JourneyError("text is required", 422)
        if len(text) > 2000:
            raise JourneyError("text is too long (2000 characters max)", 422)
        with self._lock(jid):
            j = self._load(jid)
            idx, sdef, sst = self._active(j, sid, "handoff")
            h = sst["handoff"]
            if not h["sbar"]:
                raise JourneyError("give the SBAR first", 409)
            cur = next((q for q in h["questions"] if not q["answered"]), None)
            h["messages"].append({"who": "learner", "text": text, "time": now_iso(), "question_id": cur["question_id"] if cur else None})
            h["answers"].append({"question_id": cur["question_id"] if cur else None, "element": cur["element"] if cur else "R", "text": text})
            if cur:
                cur.update(answered=True, answer=text)
            g = ho.grade_sbar(h["sbar"], h["answers"], j["record"], j["case"], sdef)
            got = {c["item_id"] for el in g["elements"].values() for c in el["conveyed"]}
            for q in h["questions"]:                     # do not ask for something the learner has just supplied
                if not q["answered"] and q["item_ids"] and set(q["item_ids"]) <= got:
                    q.update(answered=True, skipped=True)
            if cur or h["phase"] != "readback":
                self._colleague_says(j, sdef, h, g)
            else:
                h["messages"].append({"who": "colleague", "text": "Noted. I will add that to what I have.", "time": now_iso(), "kind": "ack",
                                      "provider": "offline", "wording": "authored", "fallback": False})
            self._save(j)
            return self.stage_view(jid, sid)

    def _finish_handoff(self, j: dict, idx: int, sdef: dict, sst: dict) -> None:
        h = sst["handoff"]
        if not h or not h.get("sbar"):
            raise JourneyError("this stage must write to the shared record: sbar", 422, {"missing": ["sbar"]})
        who = self._who(sdef, sst)
        g = ho.grade_sbar(h["sbar"], h["answers"], j["record"], j["case"], sdef)
        h["grading"], h["phase"] = g, "done"
        for el, label in ho.ELEMENTS.items():
            text = h["sbar"].get(el) or ""
            if not text.strip():
                continue
            d = g["elements"][el]
            rec.add(j["record"], sdef, idx, who, "handoff", text, "inference", None, element=el, element_label=label,
                    status="unsupported" if d["unsupported"] else "handed_over", unsupported=[{"quote": u["quote"], "reason": u["reason"]} for u in d["unsupported"]],
                    supported_by=sorted({x for c in d["conveyed"] for x in c["entry_ids"]}))
        col_who = {"staff_role": h["colleague"].get("staff_role") or "rn", "role_label": h["colleague"].get("label") or h["colleague"].get("role"),
                   "actor": "ai", "name": h["colleague"].get("name")}
        for q in h["questions"]:
            if q.get("skipped"):
                continue
            if q.get("answer") and q["answered"]:
                rec.add(j["record"], sdef, idx, who, "handoff", q["answer"], "colleague", None, element=q["element"],
                        element_label=f"Answer to {h['colleague'].get('name')}", status="handed_over", in_reply_to=q["text"])
            else:
                rec.add(j["record"], sdef, idx, col_who, "question", f"Asked at handoff, not answered: {q['text']}", "colleague", None, status="open")
        for d in g["elements"].values():
            for c in d["conveyed"]:
                for eid in c["entry_ids"]:
                    e = rec.find(j["record"], eid)
                    if e:
                        rec.mark_used(e, sdef["stage_id"], None, "passed on at handoff" + (" after the colleague asked" if c["prompted"] else ""), c["quote"])
        sst["writes"] = {"sbar": h["sbar"]}
        sst["objectives"] = st.grade_objectives(sdef, idx, j["record"], j["case"], sst["writes"], set(sst["start_known"]), [], g)
        conveyed = []
        for d in g["elements"].values():
            for c in d["conveyed"]:
                for eid in c["entry_ids"]:
                    e = rec.find(j["record"], eid)
                    if e and e.get("fact_id"):
                        conveyed.append(e["fact_id"])
        minutes = float(sdef.get("minutes") or DEFAULT_MINUTES["handoff"])
        detail = f"SBAR to {h['colleague'].get('name')}: {g['critical_unprompted']}/{g['critical_total']} critical items unprompted, {g['n_unsupported']} unsupported."
        sst["result"] = self._result(j, idx, sdef, sst, minutes, conveyed, {"kind": "handoff_complete", "detail": detail}, g["score"])
        sst["result_note"] = f"Duration is the stage's assumed {minutes:g} minutes; a handoff has no measured duration source yet."

    # ------------------------------------------------------------ views
    def _stage_public(self, j: dict, idx: int, faculty: bool = False) -> dict:
        sdef, sst = j["definition"]["stages"][idx], j["stages"][idx]
        done = j["status"] == "complete" or faculty
        objs = []
        for o in sst["objectives"]:
            if o["kind"] == "case" and not done:
                continue                                 # the case's own objectives name hidden content: debrief only
            if o.get("reveal") == "debrief" and not done:
                objs.append({"objective_id": o["objective_id"], "criterion": o["criterion"], "kind": o["kind"],
                             "result": None, "evidence": [], "feedback": "Shown in the debrief once the journey is complete.",
                             "behavior": o.get("behavior"), "held_back": True})
            else:
                objs.append(rec.public(o))
        result = copy.deepcopy(sst["result"])
        if result and not done and "objective_results" in result:
            hidden = {o["objective_id"] for o in sst["objectives"] if o.get("reveal") == "debrief"}
            result["objective_results"] = [r for r in result["objective_results"] if r["objective_id"] not in hidden]
        cps = []
        for c in sdef["counterparts"]:
            if c["kind"] == "patient":
                cps.append({"kind": "patient", "name": (j["case"].get("profile") or {}).get("name"), "label": "Patient", "played_by": "ai"})
            else:
                col = (sst.get("handoff") or {}).get("colleague") or pick_clinician(c.get("staff_role"), c.get("clinician_id"))
                cps.append({"kind": "colleague", "name": col.get("name"), "label": c.get("label") or col.get("role"), "staff_role": col.get("staff_role"),
                            "credentials": col.get("credentials"), "played_by": "ai"})
        prof = j["case"].get("profile") or {}
        brief = str(sdef.get("brief") or "").replace("{name}", str(prof.get("name") or "the patient")).replace("{age}", str(prof.get("age") or ""))
        blocked = [s["stage_id"] for s in j["stages"][:idx] if s["status"] != "completed"]
        writeback = None
        if sdef["interaction_type"] == "clinician_encounter":
            writeback = {"supported": True, "from_simulation": bool(j.get("sim")), "written_back": bool(sst.get("written_back")), "note": sst.get("writeback_note")}
        else:
            writeback = {"supported": False, "from_simulation": bool(j.get("sim")), "written_back": False,
                         "note": "This interaction type has no simulator write-back yet; its result is kept with the journey."}
        return {"stage_id": sdef["stage_id"], "index": idx, "title": sdef.get("title") or sdef["stage_id"], "interaction_type": sdef["interaction_type"],
                "kind": stage_kind(sdef), "learner_role": sdef["learner_role"], "counterparts": cps, "brief": brief, "writes": sdef["writes"],
                "scope": sdef.get("scope"), "status": sst["status"], "played_by": sst["played_by"], "player": sst["player"],
                "started": sst["started"], "finished": sst["finished"], "result": result, "result_note": sst.get("result_note"),
                "objectives": objs, "n_case_objectives_held_back": 0 if done else len([o for o in sst["objectives"] if o["kind"] == "case"]),
                "blocked_by": blocked, "writeback": writeback, "sampled_quality": sst.get("sampled_quality"),
                "n_entries": len([e for e in j["record"]["entries"] if e["stage_id"] == sdef["stage_id"]])}

    def view(self, jid: str, view: str = "student") -> dict:
        j = self._load(jid)
        faculty = view == "faculty"
        d = j["definition"]
        out = {"journey_id": jid, "status": j["status"], "started": j["started"], "finished": j["finished"], "learner": j.get("learner"),
               "template": {"journey_id": d["journey_id"], "version": d["version"], "title": d["title"], "description": d.get("description"),
                            "completion": d["completion"]},
               "case": {k: v for k, v in learner_case_view(j["case"]).items() if k not in ("prebrief", "learner_role", "n_objectives")},
               "patient": patient_view(j["case"]), "stages": [self._stage_public(j, i, faculty) for i in range(len(j["stages"]))],
               "record": rec.student_view(j["record"]), "sim": j.get("sim"), "llm": self._provider_fn().status(), "seed": j["seed"],
               "next_stage": next((s["stage_id"] for s in j["stages"] if s["status"] != "completed"), None)}
        if faculty:
            out["case_full"] = j["case"]
            out["record_full"] = j["record"]
            out["stages_full"] = j["stages"]
        return out

    def stage_view(self, jid: str, sid: str) -> dict:
        j = self._load(jid)
        idx, sdef, sst = self._stage(j, sid)
        out = {"journey_id": jid, "journey_status": j["status"], "stage": self._stage_public(j, idx), "record": rec.student_view(j["record"]),
               "patient": patient_view(j["case"]), "llm": self._provider_fn().status(),
               "next_stage": next((s["stage_id"] for s in j["stages"] if s["status"] != "completed"), None)}
        if stage_kind(sdef) == "handoff":
            h = sst.get("handoff")
            if h:
                hv = {"colleague": h["colleague"], "sbar": h["sbar"], "phase": h["phase"], "messages": h["messages"],
                      "questions": [{k: q.get(k) for k in ("question_id", "text", "about", "element", "answered", "answer")} for q in h["questions"]
                                    if q.get("asked") or (q.get("answered") and not q.get("skipped"))],
                      "n_questions": len(h["questions"]), "max_questions": int((sdef.get("sbar") or {}).get("max_questions", 3)),
                      "grading": rec.public(h["grading"]) if sst["status"] == "completed" else None}
                out["handoff"] = hv
        elif sst.get("encounter_id"):
            s = self.enc._load(sst["encounter_id"])
            engine = Engine(s["case"])
            out["encounter"] = {"case": learner_case_view(s["case"]), "chart": engine.learner_chart(s["state"]),
                                "transcript": build_transcript(s["state"]), "ledger": [student_event(e) for e in s["state"]["ledger"]],
                                "rapport": s["state"]["rapport"], "turn": s["state"]["turn"],
                                "available_requests": st.scoped_requests(engine, sdef), "status": s["status"]}
        return out

    def list(self, case_id: str | None = None) -> list[dict]:
        rows = []
        for p in sorted(self.dir.glob("jrn-*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                j = self._cache.get(p.stem) or json.loads(p.read_text())
            except Exception:
                continue
            if case_id and j.get("case_id") != case_id:
                continue
            rows.append({"journey_id": j["journey_id"], "case_id": j.get("case_id"), "case_version": j.get("case_version"),
                         "title": (j.get("case") or {}).get("title"), "patient": ((j.get("case") or {}).get("profile") or {}).get("name"),
                         "template": j["definition"]["journey_id"], "status": j["status"], "started": j["started"], "finished": j["finished"],
                         "stages": [{"stage_id": s["stage_id"], "status": s["status"], "played_by": s["played_by"]} for s in j["stages"]],
                         "n_entries": len(j["record"]["entries"]), "from_simulation": bool(j.get("sim"))})
        return rows

    def care_plan(self, jid: str) -> dict:
        return synthesis.care_plan(self._load(jid))

    def debrief(self, jid: str) -> dict:
        j = self._load(jid)
        if j["status"] != "complete":
            left = [s["stage_id"] for s in j["stages"] if s["status"] != "completed"]
            raise JourneyError(f"the debrief opens when the journey is complete; still open: {', '.join(left)}", 409, {"open_stages": left})
        return synthesis.debrief(j, [self._stage_public(j, i) for i in range(len(j["stages"]))])

    def log(self, jid: str) -> dict:
        j = self._load(jid)
        return {"journey_id": jid, "status": j["status"], "events": j["log"],
                "results": [s["result"] for s in j["stages"] if s["result"]]}
