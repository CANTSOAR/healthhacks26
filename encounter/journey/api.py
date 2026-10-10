"""Journey routes. Included by encounter.api's router, so they are served under /api wherever the encounter
routes are. Student responses carry the shared record (what the team learned) and never the case: no faculty
truth, no undisclosed fact, no objective criteria tied to hidden content before the debrief.

    GET  /journeys/templates                      journey definitions (optionally ?case_id= to filter to those that apply)
    GET  /journeys/templates/{journey_id}         one definition, in full
    POST /journeys                                {case_id, template_id?, learner?, seed?} or {run_id, patient_id, template_id?}
    GET  /journeys                                journey log index (?case_id=)
    GET  /journeys/{id}                           state: stage statuses, shared record with provenance, discrepancies
    POST /journeys/{id}/auto                      {until?} let the sampler resolve the unfinished stages before `until` (or all)
    POST /journeys/{id}/stages/{sid}/start        {mode: human|auto, learner?, quality?}  start, resume, or sample a stage
    GET  /journeys/{id}/stages/{sid}              stage view (chart + transcript, or the handoff conversation)
    POST /journeys/{id}/stages/{sid}/turn         {text, request_id?}   say something to the patient / answer the colleague
    POST /journeys/{id}/stages/{sid}/request      {request, request_id?}
    POST /journeys/{id}/stages/{sid}/sbar         {situation, background, assessment, recommendation} or {text}
    POST /journeys/{id}/stages/{sid}/finish       {acuity?, note?, orders?, disposition?, med_list?, plan?, open_questions?}
    GET  /journeys/{id}/care-plan                 synthesized from the shared record only
    GET  /journeys/{id}/debrief                   per stage, per role, team findings (409 until complete)
    GET  /journeys/{id}/log                       append-only journey events and the chain of interaction results
"""
from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Query

from ..resolver import ClinicianEncounterResolver
from ..store import CaseError
from . import definition as defs
from .manager import JourneyError, JourneyManager

router = APIRouter(tags=["journey"])

_jm: tuple[object, JourneyManager] | None = None


def jmanager() -> JourneyManager:
    """One journey manager per encounter manager (tests swap the encounter manager through encounter.api.configure)."""
    global _jm
    from .. import api as enc_api
    enc = enc_api.manager()
    if _jm is None or _jm[0] is not enc:
        _jm = (enc, JourneyManager(enc, getattr(enc, "_data", None), enc.provider))
    return _jm[1]


def _err(e: JourneyError):
    raise HTTPException(status_code=e.status, detail={"message": str(e), **e.detail})


@router.get("/journeys/templates")
def list_templates(case_id: str | None = Query(None)):
    out = [defs.summary(d) for d in defs.list_definitions() if not case_id or defs.applies_to(d, case_id)]
    if case_id:
        try:
            default = defs.default_for(case_id)["journey_id"]
        except KeyError:
            default = None
        for d in out:
            d["default"] = d["journey_id"] == default
    return out


@router.get("/journeys/templates/{journey_id}")
def get_template(journey_id: str):
    try:
        return defs.get_definition(journey_id)
    except KeyError:
        raise HTTPException(404, detail={"message": f"journey template '{journey_id}' not found"})


@router.post("/journeys", status_code=201)
def start_journey(body: dict = Body(...)):
    from .. import api as enc_api
    try:
        sim_binding = sim_handle = known = None
        if body.get("case_id"):
            try:
                case = enc_api.store().get(str(body["case_id"]), status="published")
            except CaseError as e:
                raise HTTPException(e.status, detail={"message": str(e), **e.detail})
        elif body.get("run_id") is not None and body.get("patient_id") is not None:
            if enc_api._sim_lookup is None:
                raise HTTPException(503, detail={"message": "no live simulation is registered with the encounter API"})
            handle = enc_api._sim_lookup(str(body["run_id"]))
            if not handle:
                raise HTTPException(404, detail={"message": f"run '{body['run_id']}' is not live"})
            sim, b = handle
            pid = int(body["patient_id"])
            try:
                truth = sim.latent_truth(int(b), pid)
                known = sim.known_state(int(b), pid) or {}
            except Exception as e:  # noqa: BLE001
                raise HTTPException(404, detail={"message": f"patient {pid} is not in run '{body['run_id']}': {str(e)[:120]}"})
            resolver = ClinicianEncounterResolver(enc_api.store(), enc_api.manager())
            case = enc_api.store().save_published(resolver.build_case(truth, known))
            sim_binding = {"run_id": str(body["run_id"]), "b": int(b), "patient_id": pid}
            try:
                t = sim.t
                sim_binding["t_start"] = int(t[int(b)] if hasattr(t, "__getitem__") and getattr(t, "ndim", 1) > 0 else t)
            except Exception:
                pass
            sim_handle = (sim, int(b))
        else:
            raise HTTPException(422, detail={"message": "body must contain case_id, or run_id and patient_id"})
        try:
            d = defs.get_definition(str(body["template_id"])) if body.get("template_id") else defs.default_for(str(case.get("case_id")))
        except KeyError:
            raise HTTPException(404, detail={"message": f"journey template '{body.get('template_id')}' not found"})
        seed = body.get("seed")
        return jmanager().start(case, d, learner=body.get("learner"), seed=int(seed) if isinstance(seed, (int, float)) else None,
                                sim_binding=sim_binding, sim_handle=sim_handle, known_state=known)
    except JourneyError as e:
        _err(e)


@router.get("/journeys")
def list_journeys(case_id: str | None = Query(None)):
    return jmanager().list(case_id)


@router.get("/journeys/{journey_id}")
def get_journey(journey_id: str, view: str = Query("student")):
    try:
        return jmanager().view(journey_id, "faculty" if view == "faculty" else "student")
    except JourneyError as e:
        _err(e)


@router.post("/journeys/{journey_id}/auto")
def auto_resolve(journey_id: str, body: dict | None = Body(None)):
    body = body or {}
    try:
        q = body.get("quality")
        return jmanager().auto_until(journey_id, body.get("until"), float(q) if isinstance(q, (int, float)) else None)
    except JourneyError as e:
        _err(e)


@router.post("/journeys/{journey_id}/stages/{stage_id}/start")
def start_stage(journey_id: str, stage_id: str, body: dict | None = Body(None)):
    body = body or {}
    try:
        q = body.get("quality")
        return jmanager().start_stage(journey_id, stage_id, str(body.get("mode") or "human"), body.get("learner"),
                                      float(q) if isinstance(q, (int, float)) else None)
    except JourneyError as e:
        _err(e)


@router.get("/journeys/{journey_id}/stages/{stage_id}")
def get_stage(journey_id: str, stage_id: str):
    try:
        return jmanager().stage_view(journey_id, stage_id)
    except JourneyError as e:
        _err(e)


@router.post("/journeys/{journey_id}/stages/{stage_id}/turn")
def stage_turn(journey_id: str, stage_id: str, body: dict = Body(...)):
    try:
        return jmanager().turn(journey_id, stage_id, str(body.get("text") or ""), body.get("request_id"))
    except JourneyError as e:
        _err(e)


@router.post("/journeys/{journey_id}/stages/{stage_id}/request")
def stage_request(journey_id: str, stage_id: str, body: dict = Body(...)):
    try:
        return jmanager().request(journey_id, stage_id, str(body.get("request") or ""), body.get("request_id"))
    except JourneyError as e:
        _err(e)


@router.post("/journeys/{journey_id}/stages/{stage_id}/sbar")
def stage_sbar(journey_id: str, stage_id: str, body: dict = Body(...)):
    try:
        return jmanager().submit_sbar(journey_id, stage_id, body)
    except JourneyError as e:
        _err(e)


@router.post("/journeys/{journey_id}/stages/{stage_id}/finish")
def stage_finish(journey_id: str, stage_id: str, body: dict | None = Body(None)):
    try:
        return jmanager().finish(journey_id, stage_id, body)
    except JourneyError as e:
        _err(e)


@router.get("/journeys/{journey_id}/care-plan")
def care_plan(journey_id: str):
    try:
        return jmanager().care_plan(journey_id)
    except JourneyError as e:
        _err(e)


@router.get("/journeys/{journey_id}/debrief")
def debrief(journey_id: str):
    try:
        return jmanager().debrief(journey_id)
    except JourneyError as e:
        _err(e)


@router.get("/journeys/{journey_id}/log")
def journey_log(journey_id: str):
    try:
        return jmanager().log(journey_id)
    except JourneyError as e:
        _err(e)
