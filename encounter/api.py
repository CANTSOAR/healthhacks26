"""FastAPI router for the encounter engine. Mount under /api:

    from encounter.api import router as encounter_router
    app.include_router(encounter_router, prefix="/api")

Routes follow the "Encounter" section of contracts/api.md. Student routes never return faculty_truth,
undisclosed facts, cover or true answers of withheld facts, or objectives before the encounter is finished.

Simulator hand-off: the server registers a lookup so `POST /api/encounters {run_id, patient_id}` can reach
the live simulation:

    from encounter.api import register_sim_lookup
    register_sim_lookup(lambda run_id: (sim, b) or None)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Body, HTTPException, Query, Response
from fastapi.responses import FileResponse, JSONResponse

from . import rubric as rubric_mod
from . import templates as tpl
from .clinicians import list_clinicians
from .paths import private_dir
from .providers import get_provider, voice_status
from .resolver import ClinicianEncounterResolver, ResolverError
from .samples import ensure_sample_cases
from .session import EncounterError, EncounterManager, default_manager
from .store import CaseError, CaseStore, default_store
from .validate import validate_case

router = APIRouter(tags=["encounter"])

_sim_lookup: Callable[[str], Any] | None = None
_store: CaseStore | None = None
_manager: EncounterManager | None = None
_samples_done = False


def register_sim_lookup(fn: Callable[[str], Any] | None) -> None:
    """fn(run_id) -> (sim, b) for a live run, or None."""
    global _sim_lookup
    _sim_lookup = fn


def configure(store: CaseStore | None = None, manager: EncounterManager | None = None) -> None:
    """Tests and the standalone app can inject a store / manager."""
    global _store, _manager, _samples_done
    _store, _manager, _samples_done = store, manager, False


def store() -> CaseStore:
    global _samples_done
    s = _store or default_store()
    if not _samples_done:
        _samples_done = True
        try:
            ensure_sample_cases(s)          # organizers' sample patients, only when .private/ has them
        except Exception:
            pass
    return s


def manager() -> EncounterManager:
    return _manager or default_manager()


def _case_err(e: CaseError):
    raise HTTPException(status_code=e.status, detail={"message": str(e), **e.detail})


def _clean(case: dict) -> dict:
    return {k: v for k, v in case.items() if not k.startswith("_")}


# ---------------------------------------------------------------- faculty: cases

@router.get("/cases")
def list_cases(status: str | None = Query(None), all_versions: bool = Query(False)):
    if status not in (None, "", "draft", "approved", "published"):
        raise HTTPException(422, detail={"message": "status must be draft, approved or published"})
    return store().list(status or None, all_versions)


@router.get("/cases/{case_id}")
def get_case(case_id: str, version: int | None = Query(None), view: str = Query("faculty")):
    try:
        c = store().get(case_id, version)
    except CaseError as e:
        _case_err(e)
    if view == "student":
        from .session import learner_case_view, patient_view
        return {"case": learner_case_view(c), "patient": patient_view(c), "status": c.get("status")}
    out = _clean(c)
    out["versions"] = store().versions(case_id)
    out["seed"] = bool(c.get("_seed"))
    return out


@router.post("/cases", status_code=201)
def create_case(body: dict = Body(...)):
    """Body: a full or partial case; or {from_template, overrides}; or {from_description: "free text"}."""
    notes: list[str] = []
    meta: dict = {}
    try:
        if isinstance(body.get("from_description"), str):
            res = tpl.from_description(body["from_description"], get_provider())
            draft, notes = res["case"], res["notes"]
            meta = {"method": res["method"], "fallback": res["fallback"], "template_id": res["template_id"]}
            for k, v in (body.get("overrides") or {}).items():
                if k not in ("case_id", "version", "status"):
                    draft[k] = v
        elif body.get("from_template"):
            try:
                draft = tpl.from_template(str(body["from_template"]), body.get("overrides") or {})
            except KeyError as e:
                raise HTTPException(404, detail={"message": str(e).strip("'\"")})
            notes = [f"Draft generated from condition template '{body['from_template']}'. Review every fact before approval."]
            meta = {"method": "template", "template_id": body["from_template"]}
        else:
            draft = dict(body)
        saved = store().create(draft)
    except CaseError as e:
        _case_err(e)
    out = _clean(saved)
    out["validation"] = validate_case({k: v for k, v in out.items() if k != "updated"}, rubric_mod.get_rubric(out.get("rubric_id")))
    out["notes"] = notes
    out["created_from"] = meta
    return out


@router.put("/cases/{case_id}")
def update_case(case_id: str, body: dict = Body(...)):
    try:
        before = store().get(case_id)
        saved = store().update(case_id, body)
    except CaseError as e:
        _case_err(e)
    out = _clean(saved)
    out["validation"] = validate_case({k: v for k, v in out.items() if k != "updated"}, rubric_mod.get_rubric(out.get("rubric_id")))
    out["new_version_created"] = saved["version"] != before["version"]
    return out


@router.post("/cases/{case_id}/validate")
def validate_stored_case(case_id: str, version: int | None = Query(None), body: dict | None = Body(None)):
    """Validates the stored case; if a body is sent, validates that (unsaved) content instead."""
    try:
        if body:
            base = _clean(store().get(case_id, version))
            base.update({k: v for k, v in body.items() if k not in ("case_id", "version", "status")})
            from .store import fill_defaults
            c = fill_defaults(base)
            c.pop("updated", None)
            return validate_case(c, rubric_mod.get_rubric(c.get("rubric_id")))
        return store().validate(case_id, version)
    except CaseError as e:
        _case_err(e)


@router.post("/cases/{case_id}/approve")
def approve_case(case_id: str, body: dict | None = Body(None)):
    try:
        return _clean(store().approve(case_id, (body or {}).get("reviewer")))
    except CaseError as e:
        _case_err(e)


@router.post("/cases/{case_id}/publish")
def publish_case(case_id: str):
    try:
        return _clean(store().publish(case_id))
    except CaseError as e:
        _case_err(e)


_PLACEHOLDER = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 240" role="img" aria-label="{name}">
<rect width="240" height="240" rx="28" fill="#E9ECFB"/><circle cx="120" cy="96" r="44" fill="#C9D2F7"/>
<path d="M40 216c8-46 40-68 80-68s72 22 80 68z" fill="#C9D2F7"/>
<text x="120" y="110" text-anchor="middle" font-family="Inter,Arial,sans-serif" font-size="34" font-weight="600" fill="#2F55F5">{initials}</text></svg>"""


@router.get("/cases/{case_id}/image")
def case_image(case_id: str, version: int | None = Query(None)):
    """The patient's photo when the case names one under .private/ and it exists; otherwise an initials placeholder (SVG)."""
    try:
        c = store().get(case_id, version)
    except CaseError as e:
        _case_err(e)
    prof = c.get("profile") or {}
    img = prof.get("image")
    if isinstance(img, str) and img and not img.startswith(("http://", "https://")):
        p = Path(img)
        if not p.is_absolute():
            p = private_dir().parent / img
        try:
            root = private_dir().resolve()
            rp = p.resolve()
            if rp.is_file() and root in rp.parents and rp.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                return FileResponse(str(rp), headers={"Cache-Control": "private, max-age=3600"})
        except Exception:
            pass
    name = str(prof.get("name") or "Patient")
    initials = "".join(w[0] for w in name.split()[:2]).upper() or "P"
    safe = "".join(ch for ch in name if ch.isalnum() or ch == " ")
    return Response(_PLACEHOLDER.format(name=safe, initials=initials), media_type="image/svg+xml", headers={"X-Placeholder": "1"})


# ---------------------------------------------------------------- faculty: templates, rubrics, clinicians

@router.get("/templates")
def get_templates():
    return tpl.list_templates()


@router.get("/templates/{template_id}")
def get_template(template_id: str):
    try:
        return tpl.get_template(template_id)
    except KeyError:
        raise HTTPException(404, detail={"message": f"template '{template_id}' not found"})


@router.get("/rubrics")
def get_rubrics():
    return rubric_mod.summaries()


@router.get("/rubrics/{rubric_id}")
def get_rubric(rubric_id: str):
    ids = {r["rubric_id"] for r in rubric_mod.list_rubrics()}
    if rubric_id != "default" and rubric_id not in ids:
        raise HTTPException(404, detail={"message": f"rubric '{rubric_id}' not found"})
    return rubric_mod.get_rubric(rubric_id)


@router.get("/clinicians")
def get_clinicians():
    return list_clinicians()


# ---------------------------------------------------------------- student: encounters

def _enc_err(e: EncounterError):
    raise HTTPException(status_code=e.status, detail={"message": str(e)})


@router.post("/encounters", status_code=201)
def start_encounter(body: dict = Body(...)):
    """Body {case_id, version?, preview?} or {run_id, patient_id}."""
    try:
        if body.get("case_id"):
            try:
                if body.get("version") is not None:
                    case = store().get(str(body["case_id"]), int(body["version"]))
                elif body.get("preview"):
                    case = store().get(str(body["case_id"]))
                else:
                    case = store().get(str(body["case_id"]), status="published")
            except CaseError as e:
                _case_err(e)
            return manager().start(case, preview=bool(body.get("preview")), learner=body.get("learner"))
        if body.get("run_id") is not None and body.get("patient_id") is not None:
            if _sim_lookup is None:
                raise HTTPException(503, detail={"message": "no live simulation is registered with the encounter API"})
            handle = _sim_lookup(str(body["run_id"]))
            if not handle:
                raise HTTPException(404, detail={"message": f"run '{body['run_id']}' is not live"})
            sim, b = handle
            resolver = ClinicianEncounterResolver(store(), manager())
            try:
                return resolver.start(sim, int(b), int(body["patient_id"]), run_id=str(body["run_id"]), learner=body.get("learner"),
                                      require_hold=not bool(body.get("force")))
            except ResolverError as e:
                raise HTTPException(e.status, detail={"message": str(e)})
        raise HTTPException(422, detail={"message": "body must contain case_id, or run_id and patient_id"})
    except EncounterError as e:
        _enc_err(e)


@router.get("/encounters")
def list_encounters(case_id: str | None = Query(None)):
    return manager().list(case_id)


@router.get("/encounters/{encounter_id}")
def get_encounter(encounter_id: str, view: str = Query("student")):
    try:
        return manager().get(encounter_id, "faculty" if view == "faculty" else "student")
    except EncounterError as e:
        _enc_err(e)


@router.post("/encounters/{encounter_id}/turn")
def encounter_turn(encounter_id: str, body: dict = Body(...)):
    try:
        return manager().turn(encounter_id, str(body.get("text") or ""), body.get("request_id"))
    except EncounterError as e:
        _enc_err(e)


@router.post("/encounters/{encounter_id}/request")
def encounter_request(encounter_id: str, body: dict = Body(...)):
    try:
        return manager().request(encounter_id, str(body.get("request") or ""), body.get("request_id"))
    except EncounterError as e:
        _enc_err(e)


@router.post("/encounters/{encounter_id}/finish")
def encounter_finish(encounter_id: str, body: dict | None = Body(None)):
    body = body or {}
    try:
        return manager().finish(encounter_id, body.get("disposition"), body.get("orders"), body.get("summary"))
    except EncounterError as e:
        _enc_err(e)


# ---------------------------------------------------------------- voice

@router.post("/tts")
def tts(body: dict = Body(...)):
    """ElevenLabs speech for already-approved reply text when ELEVENLABS_API_KEY is set; otherwise 204 so the
    browser uses its own speech synthesis. Any upstream failure also returns 204 (never an error)."""
    key = (os.environ.get("ELEVENLABS_API_KEY") or "").strip()
    text = str(body.get("text") or "").strip()[:1200]
    if not key or not text:
        return Response(status_code=204)
    voice = str(body.get("voice") or os.environ.get("ELEVENLABS_VOICE_ID") or "21m00Tcm4TlvDq8ikWAM")
    model = os.environ.get("ELEVENLABS_MODEL_ID") or "eleven_turbo_v2_5"
    try:
        import httpx
        r = httpx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}", headers={"xi-api-key": key, "accept": "audio/mpeg"},
                       json={"text": text, "model_id": model}, timeout=20.0)
        if r.status_code == 200 and r.content:
            return Response(content=r.content, media_type="audio/mpeg", headers={"X-Voice-Provider": "elevenlabs"})
    except Exception:
        pass
    return Response(status_code=204, headers={"X-Voice-Fallback": "browser"})


@router.get("/encounter/status")
def encounter_status():
    """Convenience for the standalone app; the main server folds encounter.status() into /api/status."""
    return {"llm": get_provider().status(), "voice": voice_status()}
